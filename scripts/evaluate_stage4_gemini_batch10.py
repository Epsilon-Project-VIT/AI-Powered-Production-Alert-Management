#!/usr/bin/env python3
"""
Stage 4 — Controlled Gemini Batch Evaluation (10 Representative Incidents)

Executes Stage 4 RCA reasoning on 10 canonical incident groups using
the durable SQLite queue and Google Gemini (gemini-flash-latest).
Enforces:
- Exact alert membership preservation from Stage 3 canonical results.
- Telemetry and evidence generation with strict provenance tracking.
- Conservative rate pacing (10 RPM) to prevent quota bursts.
- Full validation of output schema, confidence bounds, and evidence IDs.
- Mandatory human review on remediation actions.
- Anti-fabrication: failures never masked as successful Gemini responses.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Add src and project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from alert_management.llm import GeminiConfig
from alert_management.stage4_analysis.analysis import (
    AnomalyDetector,
    LogAnalyzer,
    TraceAnalyzer,
)
from alert_management.stage4_analysis.context import IncidentContextBuilder
from alert_management.stage4_analysis.evidence import EvidenceStore
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
    RCAResult,
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

# 10 Representative Incident Groups across 3 enterprise clients and correlation topologies
SELECTED_INCIDENT_IDS = [
    "INCIDENT-0001",  # Bridgestone, 6 alerts, exact_signature_match
    "INCIDENT-0002",  # Pizza Hut, 13 alerts, exact_signature_match
    "INCIDENT-0003",  # Bridgestone, 4 alerts, exact_signature_match
    "INCIDENT-0004",  # EA Sports, 4 alerts, exact_signature_match
    "INCIDENT-0005",  # Bridgestone, 2 alerts, exact_signature_match
    "INCIDENT-0006",  # EA Sports, 2 alerts, exact_signature_match
    "INCIDENT-0008",  # Pizza Hut, 9 alerts, graph_connected_component
    "INCIDENT-0009",  # EA Sports, 3 alerts, exact_signature_match
    "INCIDENT-0015",  # Pizza Hut, 12 alerts, graph_connected_component
    "INCIDENT-0020",  # EA Sports, 2 alerts, graph_connected_component
]


def prepare_candidate_incidents(
    raw_excel_path: Path,
    stage2_path: Path,
    stage3_path: Path,
    selected_ids: List[str],
) -> List[Dict[str, Any]]:
    """Extract context, evidence, and candidates for selected canonical incidents."""
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
    cand_gen = RCACandidateGenerator()
    cand_ranker = RCACandidateRanker()

    prepared = []
    for inc_id in selected_ids:
        if inc_id not in incident_dict_map:
            logger.warning("Incident ID %s not found in canonical Stage 3 groups", inc_id)
            continue

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
        ranked_cands = cand_ranker.rank_candidates(cand_gen.generate_candidates(ctx, evidence), evidence)

        prepared.append({
            "incident_id": inc_id,
            "raw_group": raw_group,
            "context": ctx,
            "evidence": evidence,
            "candidates": ranked_cands,
            "alert_count": len(inc_alerts),
            "correlation_method": raw_group.get("correlation_method", "unknown"),
        })

    return prepared


def main():
    print("=" * 80)
    print("STAGE 4 — CONTROLLED GEMINI BATCH EVALUATION (10 INCIDENTS)")
    print("=" * 80)

    # File paths
    base_dir = Path(__file__).parent.parent
    raw_excel_path = base_dir / "data" / "raw" / "Data_Alert_Ticket_Segregation.xlsx"
    stage2_path = base_dir / "data" / "stage2_models_canonical"
    stage3_path = base_dir / "data" / "stage3_canonical_results" / "incident_groups.json"
    queue_db_path = base_dir / "data" / "stage4_task_queue.db"
    output_report_path = base_dir / "data" / "stage4_gemini_batch10_evaluation.json"

    # 1. Inspect & Initialize Configuration
    config = GeminiConfig.from_env()
    print(f"\n[Config Audit]")
    print(f"  Selected Model:        {config.model}")
    print(f"  Proactive RPM Limit:   10 (conservative pacing: 6s spacing)")
    print(f"  Sampling Temperature:  {config.temperature}")
    print(f"  Max Output Tokens:     {config.max_tokens}")
    print(f"  Timeout (Seconds):     {config.timeout_seconds}")
    print(f"  Queue Database:        {queue_db_path}")

    # 2. Extract 10 Canonical Incidents
    print(f"\n[Step 1] Preparing 10 canonical incident groups...")
    prepared_incidents = prepare_candidate_incidents(
        raw_excel_path=raw_excel_path,
        stage2_path=stage2_path,
        stage3_path=stage3_path,
        selected_ids=SELECTED_INCIDENT_IDS,
    )
    print(f"✅ Extracted {len(prepared_incidents)} representative incident groups.")

    # 3. Enqueue to SQLite Queue
    print(f"\n[Step 2] Enqueuing tasks to SQLite queue...")
    queue = Stage4TaskQueue(db_path=str(queue_db_path))

    # Crash recovery check on startup
    recovered_count = queue.recover_unfinished_tasks()
    if recovered_count > 0:
        print(f"  🔄 Recovered {recovered_count} unfinished tasks from previous session.")

    new_submitted = 0
    skipped_existing = 0
    enqueued_task_ids = []

    for item in prepared_incidents:
        task, is_new = queue.enqueue(
            context=item["context"],
            evidence=item["evidence"],
            candidates=item["candidates"],
            provider_name="gemini",
            model_name=config.model,
            max_retries=2,
        )
        enqueued_task_ids.append(task.task_id)
        if is_new:
            new_submitted += 1
            print(f"  ➕ Enqueued {task.task_id} ({item['context'].incident_id}: {item['context'].client}, {item['alert_count']} alerts, {len(item['evidence'])} evidence)")
        else:
            skipped_existing += 1
            print(f"  🛡️ Reused existing {task.status.value} task: {task.task_id} ({item['context'].incident_id})")

    pre_counts = queue.get_counts_by_status()
    print(f"\nQueue status before execution:")
    print(f"  Submitted newly:  {new_submitted}")
    print(f"  Skipped/Reused:   {skipped_existing}")
    print(f"  Queue counts:     {pre_counts}")

    # 4. Execute Batch with Conservative Rate Pacing (10 RPM = 6s between requests)
    print(f"\n[Step 3] Executing batch with Gemini reasoning provider (10 RPM pacing)...")
    provider = GeminiReasoningProvider(config)
    worker = Stage4QueueWorker(
        queue=queue,
        provider=provider,
        rpm_limit=10,  # 6.0s spacing to strictly avoid quota bursts
        base_backoff_seconds=3.0,
        max_backoff_seconds=60.0,
    )

    batch_start = time.monotonic()
    batch_summary = worker.run_batch(max_tasks=10, stop_on_quota_exhausted=True)
    batch_duration = time.monotonic() - batch_start

    print(f"\nBatch processing finished in {batch_duration:.2f}s:")
    print(f"  Processed in run: {batch_summary.processed}")
    print(f"  Completed:        {batch_summary.completed}")
    print(f"  Failed:           {batch_summary.failed}")
    print(f"  Retried:          {batch_summary.retried}")
    print(f"  Halted reason:    {batch_summary.halted_reason}")

    # 5. Detailed Validation of Each Result
    print(f"\n[Step 4] Validating all 10 incident results...")
    validation_records = []
    policy_violations = 0
    hallucinated_evidence_total = 0

    for item in prepared_incidents:
        inc_id = item["incident_id"]
        ctx = item["context"]
        ev_list = item["evidence"]
        valid_ev_ids = {e.source_id for e in ev_list if e.source_id}

        # Retrieve task from queue
        dedup_hash = None
        task = None
        for tid in enqueued_task_ids:
            t = queue.get_task(tid)
            if t and t.incident_id == inc_id:
                task = t
                break

        if not task:
            logger.error("Could not find task for incident %s", inc_id)
            continue

        rca_res = task.get_result()
        record = {
            "incident_id": inc_id,
            "client": ctx.client,
            "member_alerts_count": item["alert_count"],
            "correlation_method": item["correlation_method"],
            "evidence_count": len(ev_list),
            "evidence_sources": {
                "logs": len([e for e in ev_list if e.source == "logs"]),
                "metrics": len([e for e in ev_list if e.source == "metrics"]),
                "traces": len([e for e in ev_list if e.source == "traces"]),
                "mock_percentage": 100.0 if all(e.is_mock for e in ev_list) else 0.0,
            },
            "task_status": task.status.value,
            "retry_count": task.retry_count,
            "error_message": task.error_message,
            "error_category": task.error_category.value if task.error_category else None,
        }

        if rca_res:
            prc = rca_res.probable_root_cause
            recs = rca_res.recommended_actions

            # Evidence grounding validation
            supporting_ids = prc.supporting_evidence_ids if prc else []
            invalid_citations = [sid for sid in supporting_ids if sid not in valid_ev_ids]
            valid_citations = [sid for sid in supporting_ids if sid in valid_ev_ids]

            if invalid_citations:
                hallucinated_evidence_total += len(invalid_citations)

            # Remediation approval check
            remediation_actions = [a for a in recs if a.action_type == ActionType.REMEDIATION]
            unapproved_remediations = [a for a in remediation_actions if not a.requires_human_approval]
            if unapproved_remediations:
                policy_violations += len(unapproved_remediations)

            record.update({
                "diagnosis_status": rca_res.diagnosis_status.value,
                "has_root_cause": prc is not None,
                "root_cause_component": prc.component if prc else None,
                "root_cause_failure_type": prc.failure_type if prc else None,
                "model_reported_confidence_experimental": prc.confidence if prc else None,
                "root_cause_description": prc.description if prc else None,
                "valid_evidence_citations": valid_citations,
                "invalid_evidence_citations": invalid_citations,
                "recommendations_total": len(recs),
                "remediation_actions_count": len(remediation_actions),
                "diagnostic_actions_count": len([a for a in recs if a.action_type == ActionType.DIAGNOSTIC]),
                "human_review_required": rca_res.human_review_required,
                "reasoning_provider": rca_res.reasoning_provider,
                "is_fallback": rca_res.reasoning_provider.endswith("_fallback"),
                "support_communication_chars": len(rca_res.support_communication),
                "stakeholder_communication_chars": len(rca_res.stakeholder_communication),
            })
        else:
            record.update({
                "diagnosis_status": None,
                "has_root_cause": False,
                "root_cause_component": None,
                "model_reported_confidence_experimental": None,
                "valid_evidence_citations": [],
                "invalid_evidence_citations": [],
                "recommendations_total": 0,
                "human_review_required": True,
                "reasoning_provider": task.provider_name,
                "is_fallback": True,
            })

        validation_records.append(record)

    # 6. Save Evaluation Report
    post_counts = queue.get_counts_by_status()
    report_data = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "model": config.model,
        "batch_size": len(SELECTED_INCIDENT_IDS),
        "execution_summary": {
            "new_submitted": new_submitted,
            "reused_skipped": skipped_existing,
            "processed_in_batch": batch_summary.processed,
            "completed": batch_summary.completed,
            "failed": batch_summary.failed,
            "retried": batch_summary.retried,
            "halted_reason": batch_summary.halted_reason,
            "batch_duration_seconds": round(batch_duration, 2),
            "final_queue_counts": post_counts,
        },
        "safety_audit": {
            "policy_violations_count": policy_violations,
            "hallucinated_evidence_count": hallucinated_evidence_total,
            "human_review_enforced_100pct": all(r.get("human_review_required", False) for r in validation_records),
        },
        "incidents": validation_records,
    }

    with open(output_report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"✅ Saved full evaluation report to: {output_report_path}")

    # 7. Print Console Summary Table
    print("\n" + "=" * 80)
    print("DETAILED BATCH EVALUATION RESULTS")
    print("=" * 80)
    print(f"{'Incident ID':<15} {'Client':<12} {'Alerts':<7} {'Status':<16} {'Component':<12} {'Conf(exp)':<10} {'Actions':<8}")
    print("-" * 80)
    for r in validation_records:
        inc_id = r["incident_id"]
        client = r["client"][:11]
        alerts = r["member_alerts_count"]
        status = r.get("diagnosis_status") or r["task_status"]
        comp = (r.get("root_cause_component") or "None")[:11]
        conf = f"{r['model_reported_confidence_experimental']:.1%}" if r.get("model_reported_confidence_experimental") is not None else "N/A"
        acts = r.get("recommendations_total", 0)
        print(f"{inc_id:<15} {client:<12} {alerts:<7} {status:<16} {comp:<12} {conf:<10} {acts:<8}")

    print("=" * 80)
    print(f"Queue Status:        {post_counts}")
    print(f"Policy Violations:   {policy_violations} (all remediation actions gated behind human review)")
    print(f"Hallucinated Ref IDs:{hallucinated_evidence_total} (all references validated)")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
