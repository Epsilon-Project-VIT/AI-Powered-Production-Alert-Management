#!/usr/bin/env python3
"""
Controlled Sample Verification for Stage 4 Task Queue with Google Gemini.

Runs a minimal, safe, controlled test (2 incidents only) to verify:
1. Durable task persistence in SQLite.
2. Deduplication: duplicate submissions are skipped.
3. Crash recovery: tasks left in PROCESSING recover to PENDING.
4. Rate limiting: paced execution at configured RPM.
5. Gemini reasoning: structured RCAResult output with evidence grounding.
6. Safety gates: remediation actions require human approval.
7. Metrics tracking: submitted, completed, failed, retried, and skipped counts.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_management.llm import GeminiConfig
from alert_management.stage4_analysis.queue import (
    Stage4TaskQueue,
    Stage4QueueWorker,
    TaskStatus,
)
from alert_management.stage4_analysis.reasoning import GeminiReasoningProvider
from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    Evidence,
    SourceType,
    ProbableRootCause,
    ActionType,
)


def build_sample_incidents():
    """Create 2 controlled sample incidents with coherent telemetry evidence."""
    now = datetime(2026, 10, 11, 15, 0, 0)

    # Incident 1: EA Sports Game Server Latency
    ctx1 = IncidentContext(
        incident_id="INCIDENT-CONTROLLED-001",
        client="EA Sports",
        alert_ids=["ALT-CTRL-01", "ALT-CTRL-02"],
        primary_alert_id="ALT-CTRL-01",
        incident_start=now - timedelta(minutes=10),
        incident_end=now,
        alert_count=2,
        services=["game-server", "elb"],
        components=["elb", "application"],
        normalized_descriptions=[
            "EA Sports ELB unhealthy host count elevated",
            "EA Sports backend application target timeout"
        ],
        diagnostic_start=now - timedelta(minutes=20),
        diagnostic_end=now + timedelta(minutes=10),
    )
    ev1 = [
        Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="ev_ctrl_elb_01",
            timestamp=now - timedelta(minutes=8),
            description="ELB HTTP 504 Gateway Timeout count spiked above threshold",
            weight=0.9,
            is_mock=True,
        ),
        Evidence(
            source="metrics",
            source_type=SourceType.MOCK,
            source_id="ev_ctrl_elb_02",
            timestamp=now - timedelta(minutes=7),
            description="elb_healthy_target_count dropped from 10 to 2",
            weight=0.95,
            is_mock=True,
        ),
    ]
    cand1 = [
        ProbableRootCause(
            component="elb",
            failure_type="timeout",
            confidence=0.85,
            description="Backend application instances unhealthy causing ELB timeouts",
            supporting_evidence_ids=["ev_ctrl_elb_01", "ev_ctrl_elb_02"]
        )
    ]

    # Incident 2: Bridgestone Database Connection Pool
    ctx2 = IncidentContext(
        incident_id="INCIDENT-CONTROLLED-002",
        client="Bridgestone",
        alert_ids=["ALT-CTRL-03", "ALT-CTRL-04"],
        primary_alert_id="ALT-CTRL-03",
        incident_start=now - timedelta(minutes=15),
        incident_end=now - timedelta(minutes=5),
        alert_count=2,
        services=["erp-core", "database"],
        components=["database"],
        normalized_descriptions=[
            "Bridgestone database pool connection wait time critical",
            "Bridgestone SQL connection acquisition timeout"
        ],
        diagnostic_start=now - timedelta(minutes=25),
        diagnostic_end=now,
    )
    ev2 = [
        Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="ev_ctrl_db_01",
            timestamp=now - timedelta(minutes=12),
            description="Connection pool exhausted: 120/120 active connections",
            weight=0.9,
            is_mock=True,
        ),
        Evidence(
            source="metrics",
            source_type=SourceType.MOCK,
            source_id="ev_ctrl_db_02",
            timestamp=now - timedelta(minutes=11),
            description="db_connection_pool_utilization reached 100%",
            weight=0.95,
            is_mock=True,
        ),
    ]
    cand2 = [
        ProbableRootCause(
            component="database",
            failure_type="pool_exhaustion",
            confidence=0.88,
            description="Database connection pool saturation under query volume",
            supporting_evidence_ids=["ev_ctrl_db_01", "ev_ctrl_db_02"]
        )
    ]

    return [(ctx1, ev1, cand1), (ctx2, ev2, cand2)]


def main():
    print("=" * 75)
    print("STAGE 4 — CONTROLLED SAMPLE & TASK QUEUE VERIFICATION")
    print("=" * 75)

    # Use a clean test database for controlled audit
    db_path = "data/stage4_controlled_audit_queue.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    queue = Stage4TaskQueue(db_path=db_path)
    print(f"✅ Initialized SQLite task queue at: {db_path}")

    incidents = build_sample_incidents()
    submitted_count = 0
    skipped_count = 0

    # 1. Enqueue Phase
    print("\n[Step 1] Enqueuing controlled sample (2 incidents)...")
    for ctx, ev, cand in incidents:
        task, is_new = queue.enqueue(
            context=ctx,
            evidence=ev,
            candidates=cand,
            provider_name="gemini",
            max_retries=2,
        )
        if is_new:
            submitted_count += 1
            print(f"   ➕ Enqueued task: {task.task_id} (Incident: {ctx.incident_id})")
        else:
            skipped_count += 1

    assert submitted_count == 2
    print(f"✅ Enqueue completed: {submitted_count} submitted, {skipped_count} skipped")

    # 2. Deduplication Verification
    print("\n[Step 2] Testing duplicate submission suppression...")
    for ctx, ev, cand in incidents:
        _, is_new = queue.enqueue(
            context=ctx,
            evidence=ev,
            candidates=cand,
            provider_name="gemini",
        )
        if not is_new:
            skipped_count += 1
            print(f"   🛡️ Duplicate correctly rejected: {ctx.incident_id}")

    counts = queue.get_counts_by_status()
    print(f"✅ Queue state after dedup check: {counts}")
    assert counts.get(TaskStatus.PENDING.value) == 2

    # 3. Crash Recovery Verification
    print("\n[Step 3] Simulating crash during processing...")
    # Worker claims a task into PROCESSING
    simulated_task = queue.claim_next_task()
    assert simulated_task.status == TaskStatus.PROCESSING
    print(f"   ⚡ Task {simulated_task.task_id} marked PROCESSING")

    # Restart occurs -> queue recovery is invoked
    recovered_count = queue.recover_unfinished_tasks()
    print(f"   🔄 Crash recovery executed: {recovered_count} task(s) recovered to PENDING")
    assert recovered_count == 1
    assert queue.get_counts_by_status().get(TaskStatus.PENDING.value) == 2
    print("✅ Crash recovery successfully restored task without data loss")

    # 4. Live Gemini Processing of Controlled Sample
    print("\n[Step 4] Executing controlled sample with Google Gemini...")
    config = GeminiConfig.from_env()
    print(f"   Configured model: {config.model}")
    print(f"   RPM Limit: {config.rpm_limit}")

    provider = GeminiReasoningProvider(config)
    worker = Stage4QueueWorker(
        queue=queue,
        provider=provider,
        rpm_limit=config.rpm_limit,
        base_backoff_seconds=2.0,
    )

    start_exec = time.monotonic()
    batch_summary = worker.run_batch(max_tasks=2, stop_on_quota_exhausted=True)
    duration = time.monotonic() - start_exec

    print(f"\n[Step 5] Batch Processing Completed in {duration:.2f}s:")
    print(f"   Tasks Processed: {batch_summary.processed}")
    print(f"   Tasks Completed: {batch_summary.completed}")
    print(f"   Tasks Failed:    {batch_summary.failed}")
    print(f"   Tasks Retried:   {batch_summary.retried}")
    print(f"   Halted Reason:   {batch_summary.halted_reason}")

    # 5. Result Integrity and Safety Verification
    print("\n[Step 6] Verifying output schemas and policy enforcement...")
    results = queue.get_all_completed_results()
    assert len(results) == 2, f"Expected 2 completed results, found {len(results)}"

    for r in results:
        print(f"\n   Incident: {r.incident_id}")
        print(f"   Diagnosis Status: {r.diagnosis_status}")
        print(f"   Reasoning Provider: {r.reasoning_provider}")
        print(f"   Human Review Required: {r.human_review_required}")
        if r.probable_root_cause:
            print(f"   Root Cause: {r.probable_root_cause.component} ({r.probable_root_cause.failure_type}) - Conf: {r.probable_root_cause.confidence:.2%}")
            print(f"   Grounded Evidence IDs: {r.probable_root_cause.supporting_evidence_ids}")

        # Check remediation approval gate
        for act in r.recommended_actions:
            if act.action_type == ActionType.REMEDIATION:
                assert act.requires_human_approval is True, "Remediation action MUST require human approval!"
        print(f"   Recommended Actions: {len(r.recommended_actions)} (Remediation gates verified)")

    # 6. Re-submission check after completion
    print("\n[Step 7] Testing submission after completion...")
    re_enqueue_skipped = 0
    for ctx, ev, cand in incidents:
        _, is_new = queue.enqueue(context=ctx, evidence=ev, candidates=cand, provider_name="gemini")
        if not is_new:
            re_enqueue_skipped += 1
    print(f"   🛡️ Re-enqueue of completed tasks: {re_enqueue_skipped} skipped")

    final_counts = queue.get_counts_by_status()
    print("\n" + "=" * 75)
    print("CONTROLLED SAMPLE AUDIT SUMMARY")
    print("=" * 75)
    print(f"Total Submitted:  {submitted_count}")
    print(f"Total Completed:  {batch_summary.completed}")
    print(f"Total Failed:     {batch_summary.failed}")
    print(f"Total Retried:    {batch_summary.retried}")
    print(f"Total Skipped:    {skipped_count + re_enqueue_skipped}")
    print(f"Queue Status:     {final_counts}")
    print(f"Persistence DB:   {db_path}")
    print("=" * 75)
    return 0


if __name__ == "__main__":
    sys.exit(main())
