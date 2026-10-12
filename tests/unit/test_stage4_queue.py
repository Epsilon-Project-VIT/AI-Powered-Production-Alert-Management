"""
Unit tests for Stage 4 Durable Task Queue (Stage4TaskQueue and Stage4QueueWorker).

Tests:
1. Deduplication: Completed or active tasks are not re-enqueued.
2. Crash recovery: Tasks left in PROCESSING state are safely recovered to PENDING.
3. Retry logic: Transient errors trigger exponential backoff up to max_retries.
4. Permanent errors: Auth / config errors immediately fail without wasting retries.
5. Rate limiting: Pacing prevents burst request submissions.
6. Result preservation: Validated RCAResults are persisted and retrievable.
7. Anti-fabrication: API failures cannot create fake completed results.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import pytest

from alert_management.llm.exceptions import (
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiError,
)
from alert_management.stage4_analysis.queue import (
    Stage4TaskQueue,
    Stage4QueueWorker,
    TaskStatus,
    ErrorCategory,
    compute_task_dedup_hash,
)
from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    Evidence,
    SourceType,
    DiagnosisStatus,
    ActionType,
    ProbableRootCause,
    RecommendedAction,
    RCAResult,
)


@pytest.fixture
def temp_db(tmp_path):
    """Provide isolated SQLite database path."""
    return str(tmp_path / "test_stage4_queue.db")


@pytest.fixture
def queue(temp_db):
    """Initialize test queue."""
    return Stage4TaskQueue(db_path=temp_db)


@pytest.fixture
def sample_context():
    """Sample incident context."""
    now = datetime(2026, 10, 11, 14, 0, 0)
    return IncidentContext(
        incident_id="INC-QUEUE-001",
        client="EA Sports",
        alert_ids=["ALT-101", "ALT-102"],
        primary_alert_id="ALT-101",
        incident_start=now,
        incident_end=now + timedelta(minutes=10),
        alert_count=2,
        services=["game-server"],
        components=["elb"],
        normalized_descriptions=["Target connection timeout", "504 Gateway Timeout"],
        diagnostic_start=now - timedelta(minutes=15),
        diagnostic_end=now + timedelta(minutes=20)
    )


@pytest.fixture
def sample_evidence():
    """Sample evidence items."""
    now = datetime(2026, 10, 11, 14, 0, 0)
    return [
        Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="ev_queue_log_01",
            timestamp=now,
            description="ELB target timeout",
            weight=0.9,
            is_mock=True
        ),
        Evidence(
            source="metrics",
            source_type=SourceType.MOCK,
            source_id="ev_queue_met_02",
            timestamp=now,
            description="5xx error rate spike",
            weight=0.85,
            is_mock=True
        )
    ]


@pytest.fixture
def sample_rca_result(sample_context, sample_evidence):
    """Sample valid RCAResult."""
    return RCAResult(
        incident_id=sample_context.incident_id,
        analysis_timestamp=datetime(2026, 10, 11, 14, 5, 0),
        diagnosis_status=DiagnosisStatus.SUFFICIENT_EVIDENCE,
        probable_root_cause=ProbableRootCause(
            component="elb",
            failure_type="target_timeout",
            confidence=0.92,
            description="ELB backend targets unresponsive",
            supporting_evidence_ids=["ev_queue_log_01", "ev_queue_met_02"]
        ),
        evidence=sample_evidence,
        recommended_actions=[
            RecommendedAction(
                action="Drain and replace unresponsive instances",
                priority=1,
                action_type=ActionType.REMEDIATION,
                requires_human_approval=True,
                rationale="Restore ELB healthy target capacity"
            )
        ],
        support_communication="ELB timeout confirmed on game-server backend.",
        stakeholder_communication="Service impact detected and being investigated.",
        telemetry_is_mock=True,
        reasoning_provider="gemini",
        human_review_required=True
    )


# ---------------------------------------------------------------------------
# 1. Deduplication and Enqueue Tests
# ---------------------------------------------------------------------------

def test_enqueue_and_deduplication(queue, sample_context, sample_evidence, sample_rca_result):
    """Verify tasks are deduplicated and completed tasks are not re-enqueued."""
    # 1. Initial enqueue
    task1, is_new = queue.enqueue(sample_context, sample_evidence, provider_name="gemini")
    assert is_new is True
    assert task1.status == TaskStatus.PENDING
    assert task1.incident_id == "INC-QUEUE-001"

    # 2. Duplicate enqueue while PENDING
    task2, is_new2 = queue.enqueue(sample_context, sample_evidence, provider_name="gemini")
    assert is_new2 is False
    assert task2.task_id == task1.task_id

    # 3. Mark completed
    queue.mark_completed(task1.task_id, sample_rca_result)

    # 4. Duplicate enqueue after completion
    task3, is_new3 = queue.enqueue(sample_context, sample_evidence, provider_name="gemini")
    assert is_new3 is False
    assert task3.status == TaskStatus.COMPLETED
    assert task3.task_id == task1.task_id


def test_dedup_hash_varies_with_evidence():
    """Verify deduplication hash changes when evidence or alert composition changes."""
    h1 = compute_task_dedup_hash("INC-1", ["ALT-1"], ["EV-1"], "gemini")
    h2 = compute_task_dedup_hash("INC-1", ["ALT-1"], ["EV-1", "EV-2"], "gemini")
    h3 = compute_task_dedup_hash("INC-1", ["ALT-1"], ["EV-1"], "mock")
    assert h1 != h2
    assert h1 != h3


# ---------------------------------------------------------------------------
# 2. Crash Recovery Tests
# ---------------------------------------------------------------------------

def test_crash_recovery_resets_processing_tasks(queue, sample_context, sample_evidence):
    """Simulate a crash while task is PROCESSING and verify safe recovery to PENDING."""
    task, _ = queue.enqueue(sample_context, sample_evidence)

    # Worker claims task -> status becomes PROCESSING
    claimed = queue.claim_next_task()
    assert claimed is not None
    assert claimed.status == TaskStatus.PROCESSING

    # No pending tasks currently
    assert queue.claim_next_task() is None

    # Simulate restart: crash recovery is called
    recovered = queue.recover_unfinished_tasks()
    assert recovered == 1

    # Task should now be back in PENDING
    recovered_task = queue.get_task(task.task_id)
    assert recovered_task.status == TaskStatus.PENDING

    # Worker can claim it again
    reclaimed = queue.claim_next_task()
    assert reclaimed is not None
    assert reclaimed.task_id == task.task_id


# ---------------------------------------------------------------------------
# 3. Retries, Rate Limits, and Permanent Failures
# ---------------------------------------------------------------------------

def test_transient_error_exponential_backoff_and_exhaustion(queue, sample_context, sample_evidence):
    """Verify temporary errors trigger exponential backoff until max_retries."""
    task, _ = queue.enqueue(sample_context, sample_evidence, max_retries=2)
    claimed = queue.claim_next_task()

    # Retry 1
    status1, delay1 = queue.mark_failed_or_retry(
        claimed.task_id,
        GeminiTimeoutError("Read timed out"),
        base_backoff_seconds=1.0
    )
    assert status1 == TaskStatus.PENDING
    assert delay1 == 1.0
    t1 = queue.get_task(claimed.task_id)
    assert t1.retry_count == 1
    assert t1.error_category == ErrorCategory.TEMPORARY

    # Retry 2
    status2, delay2 = queue.mark_failed_or_retry(
        claimed.task_id,
        GeminiRateLimitError("Rate limit 429"),
        base_backoff_seconds=1.0
    )
    assert status2 == TaskStatus.PENDING
    assert delay2 == 2.0
    t2 = queue.get_task(claimed.task_id)
    assert t2.retry_count == 2
    assert t2.error_category == ErrorCategory.RATE_LIMIT

    # Retry 3 -> Max retries (2) exceeded, transitions to FAILED
    status3, delay3 = queue.mark_failed_or_retry(
        claimed.task_id,
        GeminiTimeoutError("Final timeout"),
        base_backoff_seconds=1.0
    )
    assert status3 == TaskStatus.FAILED
    assert delay3 is None
    t3 = queue.get_task(claimed.task_id)
    assert t3.status == TaskStatus.FAILED
    assert "Retries exhausted" in t3.error_message


def test_authentication_error_fails_immediately(queue, sample_context, sample_evidence):
    """Verify authentication errors do NOT waste retries and fail immediately."""
    task, _ = queue.enqueue(sample_context, sample_evidence, max_retries=3)
    claimed = queue.claim_next_task()

    status, delay = queue.mark_failed_or_retry(
        claimed.task_id,
        GeminiAuthenticationError("Invalid API key")
    )
    assert status == TaskStatus.FAILED
    assert delay is None

    failed_task = queue.get_task(claimed.task_id)
    assert failed_task.status == TaskStatus.FAILED
    assert failed_task.error_category == ErrorCategory.AUTHENTICATION
    assert failed_task.retry_count == 0


# ---------------------------------------------------------------------------
# 4. Worker Execution and Rate Limiting
# ---------------------------------------------------------------------------

def test_worker_successful_execution(queue, sample_context, sample_evidence, sample_rca_result):
    """Verify worker processes task, invokes provider, and stores validated RCAResult."""
    queue.enqueue(sample_context, sample_evidence, provider_name="gemini")

    mock_provider = Mock()
    mock_provider.analyze.return_value = sample_rca_result

    worker = Stage4QueueWorker(queue=queue, provider=mock_provider, rpm_limit=60)
    summary = worker.run_batch(max_tasks=1)

    assert summary.processed == 1
    assert summary.completed == 1
    assert summary.failed == 0

    results = queue.get_all_completed_results()
    assert len(results) == 1
    assert results[0].incident_id == sample_context.incident_id
    assert results[0].probable_root_cause.component == "elb"


def test_worker_rejects_fallback_as_success(queue, sample_context, sample_evidence, sample_rca_result):
    """Verify that an API fallback result is NOT recorded as a successful Gemini RCA."""
    queue.enqueue(sample_context, sample_evidence, provider_name="gemini", max_retries=1)

    # Provider returns fallback result with reasoning_provider="gemini_fallback"
    fallback_result = sample_rca_result.model_copy(
        update={
            "reasoning_provider": "gemini_fallback",
            "diagnosis_status": DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            "probable_root_cause": None,
            "review_reasons": ["gemini_failure:rate_limit_exceeded"]
        }
    )

    mock_provider = Mock()
    mock_provider.analyze.return_value = fallback_result

    worker = Stage4QueueWorker(queue=queue, provider=mock_provider, rpm_limit=60, base_backoff_seconds=0.01)
    # First attempt triggers fallback -> marked for retry
    worker.process_one()

    task = queue.get_task_by_dedup(compute_task_dedup_hash(
        sample_context.incident_id,
        sample_context.alert_ids,
        [e.source_id for e in sample_evidence],
        "gemini"
    ))
    # It must NOT be marked completed!
    assert task.status != TaskStatus.COMPLETED
    assert task.retry_count == 1


def test_worker_halts_on_quota_exhausted(queue, sample_context, sample_evidence):
    """Verify worker halts batch execution when quota exhaustion error is encountered."""
    queue.enqueue(sample_context, sample_evidence, provider_name="gemini")

    mock_provider = Mock()
    mock_provider.analyze.side_effect = GeminiRateLimitError("RESOURCE_EXHAUSTED: Exceeded your current quota")

    worker = Stage4QueueWorker(queue=queue, provider=mock_provider, rpm_limit=60)
    summary = worker.run_batch(max_tasks=5, stop_on_quota_exhausted=True)

    assert summary.halted_reason == "quota_exhausted"
    assert summary.failed == 1
    assert summary.completed == 0


def test_claim_skips_future_retry_tasks(queue, sample_context, sample_evidence):
    """Verify that tasks whose next_retry_at is in the future are not claimed prematurely."""
    task, _ = queue.enqueue(sample_context, sample_evidence)
    claimed = queue.claim_next_task()

    # Fail with 60s backoff
    queue.mark_failed_or_retry(
        claimed.task_id,
        GeminiTimeoutError("Timeout"),
        base_backoff_seconds=60.0
    )

    # Immediately trying to claim should yield None because next_retry_at is in future
    unclaimed = queue.claim_next_task()
    assert unclaimed is None


def test_quota_exhaustion_does_not_rapid_retry(queue, sample_context, sample_evidence):
    """Verify quota exhaustion immediately fails without scheduling rapid retries."""
    task, _ = queue.enqueue(sample_context, sample_evidence)
    claimed = queue.claim_next_task()

    status, delay = queue.mark_failed_or_retry(
        claimed.task_id,
        GeminiRateLimitError("RESOURCE_EXHAUSTED: Exceeded your current quota"),
        error_category=ErrorCategory.QUOTA_EXHAUSTED
    )

    assert status == TaskStatus.FAILED
    assert delay is None

    t = queue.get_task(task.task_id)
    assert t.status == TaskStatus.FAILED
    assert t.retry_count == 0
    assert t.next_retry_at is None
    assert t.error_category == ErrorCategory.QUOTA_EXHAUSTED


def test_durable_pause_state_persisted(queue, sample_context, sample_evidence):
    """Verify queue pause state persists in SQLite metadata and halts claiming."""
    task, _ = queue.enqueue(sample_context, sample_evidence)

    assert not queue.is_paused()
    queue.pause_queue(reason="daily_quota_exhausted")

    assert queue.is_paused()
    status = queue.get_pause_status()
    assert status["is_paused"] is True
    assert status["pause_reason"] == "daily_quota_exhausted"

    # Tasks cannot be claimed while paused
    assert queue.claim_next_task() is None


def test_worker_triggers_durable_pause_and_halts_future_batches(queue, sample_context, sample_evidence):
    """Verify worker pauses queue on quota error and subsequent batches refuse to run."""
    queue.enqueue(sample_context, sample_evidence)

    mock_provider = Mock()
    mock_provider.analyze.side_effect = GeminiRateLimitError("HTTP 429 RESOURCE_EXHAUSTED quota exceeded")

    worker = Stage4QueueWorker(queue=queue, provider=mock_provider, rpm_limit=60)
    summary = worker.run_batch(max_tasks=2, stop_on_quota_exhausted=True)

    assert summary.halted_reason == "quota_exhausted"
    assert queue.is_paused()

    # Second run immediately prevented by durable pause
    summary2 = worker.run_batch(max_tasks=2)
    assert summary2.halted_reason == "queue_paused"
    assert summary2.processed == 0


def test_explicit_safe_resume_preserves_completed_and_other_failed(queue, sample_context, sample_evidence):
    """Verify safe resume only resets eligible quota-failed tasks, never completed or permanent failures."""
    # 1. Enqueue three distinct tasks
    task1, _ = queue.enqueue(sample_context, sample_evidence)  # Will complete

    ctx2 = sample_context.model_copy(update={"incident_id": "INC-QUEUE-002", "alert_ids": ["ALT-201"]})
    task2, _ = queue.enqueue(ctx2, sample_evidence)  # Will fail with permanent auth error

    ctx3 = sample_context.model_copy(update={"incident_id": "INC-QUEUE-003", "alert_ids": ["ALT-301"]})
    task3, _ = queue.enqueue(ctx3, sample_evidence)  # Will fail with quota_exhausted

    # Task 1 completes
    claimed1 = queue.claim_next_task()
    dummy_rca = RCAResult(
        incident_id="INC-QUEUE-001",
        diagnosis_status=DiagnosisStatus.SUFFICIENT_EVIDENCE,
        probable_root_cause=ProbableRootCause(
            component="database",
            failure_type="pool_exhaustion",
            confidence=0.9,
            description="Database connection pool saturation"
        ),
        support_communication="OK",
        stakeholder_communication="OK",
        reasoning_provider="mock",
        analysis_timestamp=datetime.now(timezone.utc),
        telemetry_is_mock=True,
    )
    queue.mark_completed(claimed1.task_id, dummy_rca)

    # Task 2 fails permanently (auth)
    claimed2 = queue.claim_next_task()
    queue.mark_failed_or_retry(claimed2.task_id, GeminiAuthenticationError("Invalid API key"))

    # Task 3 fails with quota exhaustion
    claimed3 = queue.claim_next_task()
    queue.mark_failed_or_retry(claimed3.task_id, GeminiRateLimitError("Quota exhausted"), error_category=ErrorCategory.QUOTA_EXHAUSTED)
    queue.pause_queue(reason="daily_quota_exhausted")

    assert queue.is_paused()

    # Resume without task reset -> unpauses, but leaves task3 failed
    res1 = queue.resume_queue(reset_quota_exhausted_tasks=False)
    assert res1["unpaused"] is True
    assert res1["resumed_tasks_count"] == 0
    assert not queue.is_paused()
    assert queue.get_task(task3.task_id).status == TaskStatus.FAILED

    # Resume with reset_quota_exhausted_tasks=True
    res2 = queue.resume_queue(reset_quota_exhausted_tasks=True, new_model="gemini-3.5-flash-lite")
    assert res2["resumed_tasks_count"] == 1
    assert task3.task_id in res2["resumed_task_ids"]

    # Verify task states:
    # Task 1 remains COMPLETED
    assert queue.get_task(task1.task_id).status == TaskStatus.COMPLETED
    # Task 2 remains FAILED (auth error preserved)
    assert queue.get_task(task2.task_id).status == TaskStatus.FAILED
    assert queue.get_task(task2.task_id).error_category == ErrorCategory.AUTHENTICATION
    # Task 3 is now PENDING and has new model
    t3 = queue.get_task(task3.task_id)
    assert t3.status == TaskStatus.PENDING
    assert t3.model_name == "gemini-3.5-flash-lite"
    assert t3.retry_count == 0
    assert t3.error_message is None

    # Now task 3 can be safely claimed
    claimed_resumed = queue.claim_next_task()
    assert claimed_resumed is not None
    assert claimed_resumed.task_id == task3.task_id


def test_pause_expiration_with_paused_until(queue, sample_context, sample_evidence):
    """Verify pause expires automatically when paused_until timestamp has passed."""
    queue.enqueue(sample_context, sample_evidence)

    # Paused until 10 seconds ago (expired)
    past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    queue.pause_queue(reason="test_expired", paused_until=past_time)

    # is_paused should detect expiration, auto-unpause, and return False
    assert not queue.is_paused()
    # Task can now be claimed
    assert queue.claim_next_task() is not None

