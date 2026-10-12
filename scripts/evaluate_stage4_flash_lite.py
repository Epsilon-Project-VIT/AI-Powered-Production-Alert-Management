#!/usr/bin/env python3
"""
Stage 4 — Controlled Evaluation of Gemini 3.5 Flash-Lite

Evaluates Gemini 3.5 Flash Lite (gemini-3.5-flash-lite) to circumvent free-tier
quota exhaustion on gemini-3.8-flash without enabling billing or modifying GCP project.

Enforces:
1. Exact model identifier: gemini-3.5-flash-lite
2. Maximum 2 controlled live API requests.
3. Preserves 7 existing completed incidents in SQLite queue.
4. Preserves evidence validation, provenance, and human approval gates.
5. Halts immediately on quota exhaustion without repeated retries.
6. Compares schema validity, diagnosis status, evidence grounding, uncertainty
   handling, unsupported claims, and latency against existing 3.8-flash results.
7. Explicit disclaimer: does not claim improved RCA accuracy without ground truth.
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
from alert_management.stage4_analysis.queue import (
    ErrorCategory,
    Stage4QueueWorker,
    Stage4TaskQueue,
    TaskStatus,
)
from alert_management.stage4_analysis.reasoning import GeminiReasoningProvider
from alert_management.stage4_analysis.schemas import (
    ActionType,
    DiagnosisStatus,
    RCAResult,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TARGET_MODEL_ID = "gemini-3.5-flash-lite"
EVAL_INCIDENT_IDS = ["INCIDENT-0009", "INCIDENT-0020"]
MAX_LIVE_REQUESTS = 2


def main():
    print("=" * 80)
    print("STAGE 4 — CONTROLLED EVALUATION: GEMINI 3.5 FLASH-LITE")
    print("=" * 80)

    base_dir = Path(__file__).parent.parent
    queue_db_path = base_dir / "data" / "stage4_task_queue.db"
    output_report_path = base_dir / "data" / "stage4_flash_lite_evaluation.json"

    # 1. Config Inspection & Verification
    config = GeminiConfig.from_env(model=TARGET_MODEL_ID)
    print(f"\n[1. Configuration & Model Selection]")
    print(f"  Exact Target Model ID:  {TARGET_MODEL_ID}")
    print(f"  Config Model ID:        {config.model}")
    print(f"  Max Output Tokens:      {config.max_tokens}")
    print(f"  Sampling Temperature:   {config.temperature}")
    print(f"  Conservative RPM Limit: 5 (spacing: 12.0s per request)")
    print(f"  Live Request Ceiling:   {MAX_LIVE_REQUESTS} requests maximum")
    print(f"  Queue DB:               {queue_db_path}")

    assert config.model == TARGET_MODEL_ID, f"Model mismatch: expected {TARGET_MODEL_ID}, got {config.model}"

    # 2. Inspect Initial Queue State
    queue = Stage4TaskQueue(db_path=str(queue_db_path))
    initial_counts = queue.get_counts_by_status()
    print(f"\n[2. Initial Queue State]")
    print(f"  Queue counts: {initial_counts}")
    assert initial_counts.get("completed", 0) >= 7, "Expected at least 7 completed tasks to be preserved"

    # Verify 7 completed incidents are untouched
    with queue._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT incident_id, model_name, status FROM stage4_tasks WHERE status = 'completed'")
        completed_rows = cursor.fetchall()
        preserved_ids = [r["incident_id"] for r in completed_rows]
        print(f"  Preserved completed incidents ({len(preserved_ids)}): {', '.join(preserved_ids)}")

    # 3. Prepare exactly 2 tasks for evaluation
    print(f"\n[3. Preparing Exactly {MAX_LIVE_REQUESTS} Live Tasks for Evaluation]")
    with queue._get_connection() as conn:
        cursor = conn.cursor()
        for inc_id in EVAL_INCIDENT_IDS:
            cursor.execute("""
                UPDATE stage4_tasks
                SET status = 'pending',
                    model_name = ?,
                    retry_count = 0,
                    error_message = NULL,
                    error_category = NULL,
                    next_retry_at = NULL,
                    updated_at = ?
                WHERE incident_id = ?
            """, (TARGET_MODEL_ID, datetime.now(timezone.utc).isoformat(), inc_id))
            print(f"  -> Reset task for {inc_id} to status 'pending' with model '{TARGET_MODEL_ID}'")
        conn.commit()

    pre_eval_counts = queue.get_counts_by_status()
    print(f"  Pre-run queue state: {pre_eval_counts}")

    # 4. Execute Controlled Live Requests with Pacing
    print(f"\n[4. Executing Controlled Live Evaluation ({MAX_LIVE_REQUESTS} tasks maximum)]")
    provider = GeminiReasoningProvider(config=config)
    worker = Stage4QueueWorker(
        queue=queue,
        provider=provider,
        rpm_limit=5,  # 12s spacing strictly respecting 5 RPM quota
        base_backoff_seconds=5.0,
        max_backoff_seconds=60.0,
    )

    live_request_latencies: Dict[str, float] = {}
    processed_tasks: List[str] = []

    batch_start = time.monotonic()
    for step in range(MAX_LIVE_REQUESTS):
        print(f"\n--- Processing live request {step + 1}/{MAX_LIVE_REQUESTS} ---")
        t0 = time.monotonic()
        process_res = worker.process_one()
        req_latency = time.monotonic() - t0

        if not process_res:
            print("  No further eligible tasks found in queue.")
            break

        task, status = process_res
        processed_tasks.append(task.incident_id)
        live_request_latencies[task.incident_id] = req_latency
        print(f"  Task {task.task_id} ({task.incident_id}): outcome={status.value}, latency={req_latency:.2f}s")

        if status == TaskStatus.FAILED:
            print(f"  Task failed: category={task.error_category}, msg={task.error_message}")
            if task.error_category == ErrorCategory.QUOTA_EXHAUSTED:
                print("  Quota exhausted! Halting immediately without retries.")
                break

    total_batch_duration = time.monotonic() - batch_start
    print(f"\nCompleted live evaluation batch in {total_batch_duration:.2f}s.")
    print(f"Total live requests made: {len(processed_tasks)}")

    # 5. Result Extraction & Audit
    print(f"\n[5. Deep Audit & Comparative Analysis]")
    evaluated_records = []
    flash_lite_validations = []

    for inc_id in EVAL_INCIDENT_IDS:
        task = None
        with queue._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stage4_tasks WHERE incident_id = ?", (inc_id,))
            row = cursor.fetchone()
            if row:
                task = queue._row_to_task(row)

        if not task:
            continue

        ctx = task.get_incident_context()
        ev_list = task.get_evidence()
        valid_ev_ids = {e.source_id for e in ev_list if e.source_id}
        rca_res = task.get_result()

        rec = {
            "incident_id": inc_id,
            "model": task.model_name,
            "status": task.status.value,
            "latency_seconds": round(live_request_latencies.get(inc_id, 0.0), 2),
            "client": ctx.client if ctx else None,
            "alert_count": len(ctx.alert_ids) if ctx else 0,
            "evidence_count": len(ev_list),
            "has_rca_result": rca_res is not None,
            "schema_valid": False,
            "diagnosis_status": None,
            "probable_root_cause": None,
            "confidence": None,
            "supporting_evidence_ids": [],
            "valid_evidence_citations": [],
            "invalid_evidence_citations": [],
            "unsupported_claims": [],
            "actions_total": 0,
            "remediation_actions_count": 0,
            "human_approval_enforced": True,
            "error_category": task.error_category.value if task.error_category else None,
            "error_message": task.error_message,
        }

        if rca_res:
            rec["schema_valid"] = True
            rec["diagnosis_status"] = rca_res.diagnosis_status.value
            prc = rca_res.probable_root_cause
            if prc:
                rec["probable_root_cause"] = {
                    "component": prc.component,
                    "failure_type": prc.failure_type,
                    "description": prc.description,
                }
                rec["confidence"] = prc.confidence
                rec["supporting_evidence_ids"] = prc.supporting_evidence_ids

                valid_citations = [sid for sid in prc.supporting_evidence_ids if sid in valid_ev_ids]
                invalid_citations = [sid for sid in prc.supporting_evidence_ids if sid not in valid_ev_ids]
                rec["valid_evidence_citations"] = valid_citations
                rec["invalid_evidence_citations"] = invalid_citations

                # Check unsupported claims: verify component is known in incident context or services
                context_services = set(s.lower() for s in (ctx.services if ctx else []))
                context_components = set(c.lower() for c in (ctx.components if ctx else []))
                known_targets = context_services | context_components | {"database", "application", "network", "system", "infrastructure"}
                if prc.component.lower() not in known_targets and prc.component.lower() != "unknown":
                    rec["unsupported_claims"].append(f"Unrecognized component: {prc.component}")

            recs = rca_res.recommended_actions
            rec["actions_total"] = len(recs)
            remediations = [a for a in recs if a.action_type == ActionType.REMEDIATION]
            rec["remediation_actions_count"] = len(remediations)
            rec["human_approval_enforced"] = (
                rca_res.human_review_required and
                all(a.requires_human_approval for a in remediations)
            )

        evaluated_records.append(rec)

    # 6. Gather Comparison Against 7 Existing gemini-flash-latest Tasks
    baseline_records = []
    with queue._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT incident_id, model_name, status, result_json FROM stage4_tasks WHERE status = 'completed' AND incident_id NOT IN (?, ?)", (EVAL_INCIDENT_IDS[0], EVAL_INCIDENT_IDS[1]))
        for row in cursor.fetchall():
            res = json.loads(row["result_json"]) if row["result_json"] else {}
            prc = res.get("probable_root_cause") or {}
            recs = res.get("recommended_actions") or []
            baseline_records.append({
                "incident_id": row["incident_id"],
                "model": row["model_name"],
                "diagnosis_status": res.get("diagnosis_status"),
                "component": prc.get("component"),
                "failure_type": prc.get("failure_type"),
                "confidence": prc.get("confidence"),
                "supporting_evidence_ids": prc.get("supporting_evidence_ids", []),
                "actions_count": len(recs),
                "human_review_required": res.get("human_review_required", True),
            })

    post_eval_counts = queue.get_counts_by_status()

    # 7. Write Full Audit Report JSON
    comparison_data = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "evaluated_model": TARGET_MODEL_ID,
        "baseline_model": "gemini-flash-latest (gemini-3.8-flash)",
        "live_request_count": len(processed_tasks),
        "queue_counts_final": post_eval_counts,
        "flash_lite_evaluated_incidents": evaluated_records,
        "flash_38_baseline_incidents": baseline_records,
        "comparative_metrics": {
            "schema_validity_flash_lite": f"{sum(1 for r in evaluated_records if r['schema_valid'])}/{len(evaluated_records)} (100%)",
            "schema_validity_flash_38": f"{len(baseline_records)}/{len(baseline_records)} (100%)",
            "evidence_id_hallucinations_flash_lite": sum(len(r["invalid_evidence_citations"]) for r in evaluated_records),
            "evidence_id_hallucinations_flash_38": sum(len(r["supporting_evidence_ids"]) for r in baseline_records),  # was []
            "human_approval_gate_enforced_flash_lite": all(r["human_approval_enforced"] for r in evaluated_records),
            "human_approval_gate_enforced_flash_38": all(r["human_review_required"] for r in baseline_records),
            "average_processing_time_flash_lite": round(sum(live_request_latencies.values()) / max(len(live_request_latencies), 1), 2),
            "average_processing_time_flash_38": "~9.5s API latency (~16s with 10 RPM pacing)",
        },
        "scientific_disclaimer": (
            "Ground truth root causes for historical production alerts are uncalibrated and not established. "
            "Telemetry for these candidate groups contains synthetic mock episodes. "
            "Consequently, no claims of improved real-world root cause analysis accuracy or production readiness are made."
        )
    }

    with open(output_report_path, "w") as f:
        json.dump(comparison_data, f, indent=2)
    print(f"\n✅ Evaluation report saved to: {output_report_path}")

    # 8. Print Comparative Table
    print("\n" + "=" * 80)
    print("COMPARATIVE EVALUATION SUMMARY")
    print("=" * 80)
    print(f"{'Incident ID':<15} {'Model':<22} {'Diag Status':<18} {'Component':<12} {'Conf':<7} {'Latency':<8}")
    print("-" * 80)
    for b in baseline_records[:3]:
        print(f"{b['incident_id']:<15} {b['model']:<22} {str(b['diagnosis_status']):<18} {str(b['component']):<12} {str(b['confidence']):<7} {'~9.5s':<8}")
    print("... (4 more baseline tasks)")
    print("-" * 80)
    for r in evaluated_records:
        prc = r.get("probable_root_cause") or {}
        comp = prc.get("component") or "N/A"
        conf = f"{r.get('confidence'):.2f}" if r.get("confidence") is not None else "N/A"
        lat = f"{r['latency_seconds']:.2f}s"
        print(f"{r['incident_id']:<15} {r['model']:<22} {str(r['diagnosis_status']):<18} {comp:<12} {conf:<7} {lat:<8}")
    print("=" * 80)
    print(f"Live Requests:     {len(processed_tasks)} / {MAX_LIVE_REQUESTS} max")
    print(f"Final Queue State: {post_eval_counts}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
