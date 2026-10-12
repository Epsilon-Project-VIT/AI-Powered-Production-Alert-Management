#!/usr/bin/env python3
"""
Stage 4 — End-to-End Live Gemini RCA Validation

Validates the complete Stage 4 RCA pipeline using real historical alerts,
synthetic mock telemetry, and Google Gemini 3.5 Flash-Lite (gemini-3.5-flash-lite):

Pipeline:
  Stage 3 candidate incident group (Real Historical Alerts)
  → IncidentContext
  → Mock Telemetry Collection (Logs, Metrics, Traces)
  → Evidence Generation & Storage (EvidenceStore, Anomaly Episodes)
  → RCA Candidate Generation & Ranking
  → GeminiReasoningProvider (gemini-3.5-flash-lite)
  → RCAResult Parsing & Pydantic Validation
  → Evidence-ID Citation Validation
  → PolicyGate Evaluation (Human Approval for Consequential Actions)
  → Communication Generation (Support & Stakeholder Messages)
  → Durable Persistence in SQLite Queue

Provenance Labels:
  - REAL HISTORICAL ALERT INPUT
  - MOCK TELEMETRY
  - GEMINI-GENERATED RCA
  - ILLUSTRATIVE RCA — NOT GROUND-TRUTH VALIDATED
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Path setup
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from alert_management.llm import GeminiConfig
from alert_management.stage4_analysis.analysis import (
    AnomalyDetector,
    LogAnalyzer,
    TraceAnalyzer,
)
from alert_management.stage4_analysis.communication import MessageGenerator
from alert_management.stage4_analysis.context import IncidentContextBuilder
from alert_management.stage4_analysis.evidence import EvidenceStore
from alert_management.stage4_analysis.policy import PolicyDecision, PolicyGate
from alert_management.stage4_analysis.queue import (
    ErrorCategory,
    Stage4QueueWorker,
    Stage4TaskQueue,
    TaskStatus,
)
from alert_management.stage4_analysis.rca import (
    RCACandidateGenerator,
    RCACandidateRanker,
)
from alert_management.stage4_analysis.reasoning import GeminiReasoningProvider
from alert_management.stage4_analysis.schemas import (
    ActionType,
    DiagnosisStatus,
    Evidence,
    IncidentContext,
    ProbableRootCause,
    RCAResult,
    RecommendedAction,
)
from alert_management.stage4_analysis.telemetry.mock_log_provider import (
    MockLogProvider,
)
from alert_management.stage4_analysis.telemetry.mock_metric_provider import (
    MockMetricProvider,
)
from alert_management.stage4_analysis.telemetry.mock_trace_provider import (
    MockTraceProvider,
)
from scripts.run_stage4_canonical_analysis import (
    convert_to_incident_group,
    create_enriched_alerts,
    load_raw_alerts,
    load_stage2_predictions,
    load_stage3_incidents,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TARGET_MODEL_ID = "gemini-3.5-flash-lite"
MAX_LIVE_REQUESTS = 2
TARGET_INCIDENT_IDS = ["INCIDENT-0011"]


def main():
    print("=" * 80)
    print("STAGE 4 — END-TO-END LIVE GEMINI RCA VALIDATION (BOUNDED FINAL RUN)")
    print("=" * 80)
    print("PROVENANCE AND METHODOLOGY LABELS:")
    print("  • REAL HISTORICAL ALERT INPUT")
    print("  • MOCK TELEMETRY")
    print("  • GEMINI-GENERATED RCA")
    print("  • ILLUSTRATIVE RCA — NOT GROUND-TRUTH VALIDATED")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    raw_excel_path = base_dir / "data" / "raw" / "Data_Alert_Ticket_Segregation.xlsx"
    stage2_path = base_dir / "data" / "stage2_models_canonical"
    stage3_path = base_dir / "data" / "stage3_canonical_results" / "incident_groups.json"
    queue_db_path = base_dir / "data" / "stage4_task_queue.db"
    output_report_path = base_dir / "data" / "stage4_live_gemini_validation_results.json"

    # 1. Config Inspection & Verification (Secure Key Handling)
    config = GeminiConfig.from_env(model=TARGET_MODEL_ID)
    print(f"\n[1. Configuration & Security Audit]")
    print(f"  Model Identifier:       {config.model}")
    print(f"  Target Model ID:        {TARGET_MODEL_ID}")
    print(f"  Conservative RPM Limit: 5 (spacing: 12.0s per request)")
    print(f"  Max Live Requests:      {MAX_LIVE_REQUESTS}")
    print(f"  API Key Configured:     {'Yes (Secure, length: %d)' % len(config.api_key)}")
    print(f"  Queue DB Path:          {queue_db_path}")

    assert config.model == TARGET_MODEL_ID, f"Model mismatch: expected {TARGET_MODEL_ID}, got {config.model}"

    # 2. Inspect Initial Queue State & Guard Completed/Failed Tasks
    queue = Stage4TaskQueue(db_path=str(queue_db_path))
    initial_counts = queue.get_counts_by_status()
    print(f"\n[2. Initial Queue Audit]")
    print(f"  Counts by status: {initial_counts}")
    assert initial_counts.get("completed", 0) >= 12, "Expected at least 12 completed tasks to be preserved"

    with queue._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT incident_id, status FROM stage4_tasks WHERE status = 'completed'")
        completed_rows = cursor.fetchall()
        completed_ids = {r["incident_id"] for r in completed_rows}
        print(f"  Preserved completed incidents ({len(completed_ids)}): {', '.join(sorted(completed_ids))}")

        # Check INCIDENT-0015 state
        cursor.execute("SELECT incident_id, status, error_category, retry_count FROM stage4_tasks WHERE incident_id = 'INCIDENT-0015'")
        inc15 = cursor.fetchone()
        assert inc15 is not None and inc15["status"] == "failed", "INCIDENT-0015 must remain in preserved failed status"
        print(f"  Preserved failed history: {inc15['incident_id']} (status: {inc15['status']}, category: {inc15['error_category']}, retries: {inc15['retry_count']})")

    # Verify target incident selection does not intersect with previously completed incidents or INCIDENT-0015
    for tid in TARGET_INCIDENT_IDS:
        assert tid not in completed_ids, f"Target incident {tid} was already completed; rerun prohibited"
        assert tid != "INCIDENT-0015", "INCIDENT-0015 must not be selected for re-execution"

    print(f"\n[3. Preparing Real Historical Alert Data & Mock Telemetry for Target {TARGET_INCIDENT_IDS[0]}]")
    raw_df = load_raw_alerts(raw_excel_path)
    s2_preds = load_stage2_predictions(stage2_path)
    enriched_alerts = create_enriched_alerts(raw_df, s2_preds)
    all_incidents = load_stage3_incidents(stage3_path)
    incident_dict_map = {g["incident_id"]: g for g in all_incidents}

    context_builder = IncidentContextBuilder()
    log_provider = MockLogProvider()
    metric_provider = MockMetricProvider()
    trace_provider = MockTraceProvider()
    log_analyzer = LogAnalyzer()
    anomaly_detector = AnomalyDetector()
    trace_analyzer = TraceAnalyzer()
    candidate_generator = RCACandidateGenerator()
    candidate_ranker = RCACandidateRanker()
    policy_gate = PolicyGate()
    message_generator = MessageGenerator()

    prepared_targets: List[Dict[str, Any]] = []

    for inc_id in TARGET_INCIDENT_IDS:
        raw_group = incident_dict_map[inc_id]
        ig = convert_to_incident_group(raw_group)
        inc_alerts = [enriched_alerts[aid] for aid in ig.alert_ids if aid in enriched_alerts]

        ctx = context_builder.build_context(ig, inc_alerts)
        logs = log_provider.get_logs(ctx, ctx.diagnostic_start, ctx.diagnostic_end, ctx.services)
        metrics = metric_provider.get_metrics(ctx, ctx.diagnostic_start, ctx.diagnostic_end, ctx.services)
        traces = trace_provider.get_traces(ctx, ctx.diagnostic_start, ctx.diagnostic_end, ctx.services)

        store = EvidenceStore()
        store.add_bulk(log_analyzer.analyze(logs, ctx.diagnostic_start, ctx.diagnostic_end, ctx.incident_start, ctx.incident_end))
        anoms = anomaly_detector.detect_anomalies(metrics, ctx.diagnostic_start, ctx.diagnostic_end, ctx.incident_start, ctx.incident_end)
        store.add_bulk(anomaly_detector.generate_evidence(anoms))
        store.add_bulk(trace_analyzer.analyze(traces, ctx.diagnostic_start, ctx.diagnostic_end, ctx.incident_start, ctx.incident_end))

        evidence = store.get_all()
        ranked_cands = candidate_ranker.rank_candidates(candidate_generator.generate_candidates(ctx, evidence), evidence)

        task, is_new = queue.enqueue(
            context=ctx,
            evidence=evidence,
            candidates=ranked_cands,
            provider_name="gemini",
            model_name=TARGET_MODEL_ID,
            max_retries=1,
            force_retry_failed=False,
        )

        prepared_targets.append({
            "incident_id": inc_id,
            "task_id": task.task_id,
            "context": ctx,
            "evidence": evidence,
            "candidates": ranked_cands,
            "alert_count": len(inc_alerts),
            "client": ctx.client,
        })
        print(f"  • Enqueued {task.task_id} ({inc_id}: {ctx.client}, {len(inc_alerts)} alerts, {len(evidence)} evidence items)")

    pre_run_counts = queue.get_counts_by_status()
    print(f"  Pre-run queue state: {pre_run_counts}")

    # 4. Execute Controlled Live Requests Serially (Max 3)
    print(f"\n[4. Executing Complete Stage 4 Path Live (Serial with 12s Rate Limiter)]")
    provider = GeminiReasoningProvider(config=config)
    worker = Stage4QueueWorker(
        queue=queue,
        provider=provider,
        rpm_limit=5,  # 12.0s spacing strictly adhering to 5 RPM
        base_backoff_seconds=5.0,
        max_backoff_seconds=60.0,
    )

    executed_records: List[Dict[str, Any]] = []
    live_requests_attempted = 0
    live_requests_completed = 0

    batch_start = time.monotonic()
    for item in prepared_targets:
        inc_id = item["incident_id"]
        task_id = item["task_id"]
        ctx = item["context"]
        evidence = item["evidence"]
        valid_ev_ids = {e.source_id for e in evidence if e.source_id}

        # Check if task is already completed from previous run
        existing_task = queue.get_task(task_id)
        if existing_task and existing_task.status == TaskStatus.COMPLETED:
            print(f"\n--- Incident {inc_id} ({ctx.client}) already completed in queue: Reusing completed result ---")
            task = existing_task
            status = TaskStatus.COMPLETED
            measured_latency = 0.0
        else:
            print(f"\n--- Processing Live Request for {inc_id} ({ctx.client}) (Max {MAX_LIVE_REQUESTS} API calls total) ---")
            t0 = time.monotonic()
            process_res = worker.process_one()
            measured_latency = time.monotonic() - t0

            if not process_res:
                print(f"  No eligible task returned by worker for {task_id}.")
                break

            task, status = process_res
            print(f"  Task {task.task_id} ({inc_id}): status={status.value}, duration={measured_latency:.2f}s")
            print(f"  Provider requests: attempted={provider.request_count}, completed={provider.success_count}, corrections={provider.correction_count}")

        if status == TaskStatus.FAILED:
            print(f"  Task failed! Category: {task.error_category}, Msg: {task.error_message}")
            rec = {
                "incident_id": inc_id,
                "client": ctx.client,
                "alert_count": item["alert_count"],
                "evidence_count": len(evidence),
                "model_id_used": task.model_name,
                "api_outcome": "failed",
                "measured_latency_seconds": round(measured_latency, 2),
                "error_category": task.error_category.value if task.error_category else None,
                "error_message": task.error_message,
                "is_new_live_run": True,
            }
            executed_records.append(rec)
            if task.error_category == ErrorCategory.QUOTA_EXHAUSTED:
                print("  Quota exhaustion encountered! Halting live execution immediately.")
                break
            continue

        # Fetch fully-populated task and result from queue
        current_task = queue.get_task(task.task_id) or task
        rca_res: RCAResult = current_task.get_result()
        assert rca_res is not None, "Completed task must contain valid RCAResult"

        # Validate Evidence Citations
        prc = rca_res.probable_root_cause
        cited_ids = prc.supporting_evidence_ids if prc else []
        valid_cited = [cid for cid in cited_ids if cid in valid_ev_ids]
        invalid_cited = [cid for cid in cited_ids if cid not in valid_ev_ids]

        # Policy Gate Evaluation
        action_decisions: List[Tuple[RecommendedAction, PolicyDecision]] = []
        if rca_res.recommended_actions:
            action_decisions = policy_gate.evaluate_actions(rca_res.recommended_actions)

        # Verify no remediation was auto-approved or executed
        remediations = [a for a, dec in action_decisions if a.action_type == ActionType.REMEDIATION]
        unapproved_remediations = [a for a, dec in action_decisions if a.action_type == ActionType.REMEDIATION and dec != PolicyDecision.REQUIRES_HUMAN_REVIEW]
        assert len(unapproved_remediations) == 0, f"Policy violation: {len(unapproved_remediations)} remediation actions bypassed human review"

        # Communication Generation
        support_msg = message_generator.generate_support_message(ctx, rca_res, action_decisions)
        stakeholder_msg = message_generator.generate_stakeholder_message(ctx, rca_res)

        # Update RCAResult communications and persist updated version in queue
        rca_res.support_communication = support_msg
        rca_res.stakeholder_communication = stakeholder_msg
        queue.mark_completed(task.task_id, rca_res)

        evidence_sources = {
            "logs": len([e for e in evidence if e.source == "logs"]),
            "metrics": len([e for e in evidence if e.source == "metrics"]),
            "traces": len([e for e in evidence if e.source == "traces"]),
            "mock_percentage": 100.0 if all(e.is_mock for e in evidence) else 0.0,
        }

        rec = {
            "incident_id": inc_id,
            "client": ctx.client,
            "alert_count": item["alert_count"],
            "evidence_count": len(evidence),
            "evidence_sources": evidence_sources,
            "model_id_used": task.model_name,
            "api_outcome": "completed",
            "measured_latency_seconds": round(measured_latency, 2),
            "diagnosis_status": rca_res.diagnosis_status.value,
            "probable_root_cause": {
                "component": prc.component if prc else None,
                "failure_type": prc.failure_type if prc else None,
                "confidence": prc.confidence if prc else None,
                "description": prc.description if prc else None,
                "supporting_evidence_ids": prc.supporting_evidence_ids if prc else [],
                "is_tentative": prc.is_tentative if prc else False,
            } if prc else None,
            "model_reported_confidence": prc.confidence if prc else None,
            "alternative_hypotheses": [
                {
                    "component": alt.component,
                    "failure_type": alt.failure_type,
                    "confidence": alt.confidence,
                    "reason_for_lower_rank": alt.reason_for_lower_rank,
                }
                for alt in rca_res.alternative_hypotheses
            ],
            "evidence_ids_cited_total": len(cited_ids),
            "valid_evidence_citations": valid_cited,
            "invalid_evidence_citations": invalid_cited,
            "recommendations_total": len(rca_res.recommended_actions),
            "remediation_actions_count": len(remediations),
            "policy_gate_decisions": [
                {
                    "action": act.action,
                    "action_type": act.action_type.value,
                    "requires_human_approval": act.requires_human_approval,
                    "decision": dec.value,
                }
                for act, dec in action_decisions
            ],
            "all_remediations_gated_behind_human_approval": all(a.requires_human_approval for a in remediations),
            "human_review_required": rca_res.human_review_required,
            "policy_gate_accepted": True,
            "support_communication_length": len(support_msg),
            "stakeholder_communication_length": len(stakeholder_msg),
            "reasoning_provenance": rca_res.reasoning_provider,
            "telemetry_provenance": "MOCK TELEMETRY",
            "is_new_live_run": True,
        }
        executed_records.append(rec)

    total_batch_duration = time.monotonic() - batch_start
    final_queue_counts = queue.get_counts_by_status()
    pause_status = queue.get_pause_status()
    live_requests_attempted = provider.request_count
    live_requests_completed = provider.success_count
    live_corrections_attempted = provider.correction_count

    # Load prior validation records if available and mark them as prior runs
    prior_records = []
    if output_report_path.exists():
        try:
            with open(output_report_path, "r") as f:
                old_data = json.load(f)
                for old_inc in old_data.get("incidents", []):
                    if old_inc.get("incident_id") not in {r["incident_id"] for r in executed_records}:
                        old_inc["is_new_live_run"] = False
                        old_inc["is_prior_run"] = True
                        prior_records.append(old_inc)
        except Exception:
            pass

    combined_incidents = prior_records + executed_records

    # 5. Output JSON Report
    report_data = {
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "model": TARGET_MODEL_ID,
        "batch_duration_seconds": round(total_batch_duration, 2),
        "new_live_requests_attempted": live_requests_attempted,
        "new_live_requests_completed": live_requests_completed,
        "new_live_corrections_attempted": live_corrections_attempted,
        "queue_status_final": final_queue_counts,
        "queue_pause_status": pause_status,
        "provenance_labels": [
            "REAL HISTORICAL ALERT INPUT",
            "MOCK TELEMETRY",
            "GEMINI-GENERATED RCA",
            "ILLUSTRATIVE RCA — NOT GROUND-TRUTH VALIDATED",
        ],
        "latest_validated_incident": executed_records[0] if executed_records else None,
        "incidents": combined_incidents,
        "disclaimer": (
            "Historical production alerts lack established ground-truth root causes, "
            "and telemetry inputs are generated from synthetic mock episodes. "
            "No claims of improved real-world root cause analysis accuracy, calibrated "
            "confidence, or production readiness are made or implied."
        )
    }

    with open(output_report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"\n✅ Saved complete live validation results to: {output_report_path}")

    # 6. Display Summary Table
    print("\n" + "=" * 80)
    print("LIVE STAGE 4 RCA VALIDATION RESULTS SUMMARY")
    print("=" * 80)
    print(f"{'Incident ID':<15} {'Client':<12} {'Alerts':<7} {'Diag Status':<20} {'Component':<12} {'Conf':<7} {'Actions':<8} {'Gated':<6}")
    print("-" * 80)
    for r in executed_records:
        inc_id = r["incident_id"]
        client = r["client"][:11]
        alerts = r["alert_count"]
        status = r.get("diagnosis_status", "N/A")
        prc = r.get("probable_root_cause") or {}
        comp = (prc.get("component") or "N/A")[:11]
        conf = f"{r.get('model_reported_confidence', 0.0):.2f}" if r.get("model_reported_confidence") is not None else "N/A"
        acts = r.get("recommendations_total", 0)
        gated = "YES" if r.get("all_remediations_gated_behind_human_approval", True) else "NO"
        print(f"{inc_id:<15} {client:<12} {alerts:<7} {status:<20} {comp:<12} {conf:<7} {acts:<8} {gated:<6}")
    print("=" * 80)
    print(f"Total Live Requests: {live_requests_completed} completed / {live_requests_attempted} attempted")
    print(f"Final Queue State:   {final_queue_counts}")
    print(f"Queue Pause State:   {pause_status}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
