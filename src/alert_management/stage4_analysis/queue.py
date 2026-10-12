"""
Stage 4 Durable Analysis Task Queue.

Provides a minimal, durable SQLite-backed processing queue for Stage 4 analysis tasks.
Ensures bulk-processing reliability with:
- Persistent pending, processing, completed, and failed task states.
- Crash recovery of unfinished tasks upon restart.
- Deduplication using incident identity and evidence signatures.
- Configurable request-rate limits and proactive pacing.
- Bounded exponential retries for transient errors and HTTP 429 rate limits.
- Explicit non-retried handling of authentication and quota exhaustion failures.
- Zero loss of completed results across runs.
"""

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from alert_management.llm.exceptions import (
    GeminiAuthenticationError,
    GeminiConfigurationError,
    GeminiError,
    GeminiRateLimitError,
    GeminiStructuredOutputError,
    GeminiTimeoutError,
)
from alert_management.stage4_analysis.reasoning import (
    ReasoningProvider,
    get_reasoning_provider,
)
from alert_management.stage4_analysis.schemas import (
    DiagnosisStatus,
    Evidence,
    IncidentContext,
    ProbableRootCause,
    RCAResult,
)

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution lifecycle states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ErrorCategory(str, Enum):
    """Classification of processing failures."""
    TEMPORARY = "temporary"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTHENTICATION = "authentication"
    SCHEMA_VALIDATION = "schema_validation"
    PERMANENT = "permanent"


class AnalysisTask:
    """Represents a discrete Stage 4 analysis task record."""

    def __init__(
        self,
        task_id: str,
        incident_id: str,
        dedup_hash: str,
        status: TaskStatus,
        provider_name: str,
        incident_context_json: str,
        evidence_json: str,
        candidates_json: Optional[str] = None,
        historical_patterns_json: Optional[str] = None,
        model_name: Optional[str] = None,
        result_json: Optional[str] = None,
        error_message: Optional[str] = None,
        error_category: Optional[ErrorCategory] = None,
        retry_count: int = 0,
        max_retries: int = 3,
        next_retry_at: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        completed_at: Optional[str] = None,
    ):
        self.task_id = task_id
        self.incident_id = incident_id
        self.dedup_hash = dedup_hash
        self.status = TaskStatus(status) if isinstance(status, str) else status
        self.provider_name = provider_name
        self.model_name = model_name
        self.incident_context_json = incident_context_json
        self.evidence_json = evidence_json
        self.candidates_json = candidates_json
        self.historical_patterns_json = historical_patterns_json
        self.result_json = result_json
        self.error_message = error_message
        self.error_category = (
            ErrorCategory(error_category)
            if error_category and isinstance(error_category, str)
            else error_category
        )
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.next_retry_at = next_retry_at
        self.created_at = created_at
        self.updated_at = updated_at
        self.completed_at = completed_at

    def get_incident_context(self) -> IncidentContext:
        """Deserialize IncidentContext."""
        return IncidentContext.model_validate_json(self.incident_context_json)

    def get_evidence(self) -> List[Evidence]:
        """Deserialize evidence list."""
        data = json.loads(self.evidence_json)
        return [Evidence.model_validate(item) for item in data]

    def get_candidates(self) -> List[ProbableRootCause]:
        """Deserialize RCA candidates if present."""
        if not self.candidates_json:
            return []
        data = json.loads(self.candidates_json)
        return [ProbableRootCause.model_validate(item) for item in data]

    def get_result(self) -> Optional[RCAResult]:
        """Deserialize completed RCAResult if present."""
        if not self.result_json:
            return None
        return RCAResult.model_validate_json(self.result_json)


def compute_task_dedup_hash(
    incident_id: str,
    alert_ids: List[str],
    evidence_ids: List[str],
    provider_name: str,
    version: str = "v1",
) -> str:
    """Generate deterministic SHA-256 hash identifying this exact incident and evidence set."""
    payload = {
        "incident_id": incident_id,
        "alert_ids": sorted(alert_ids),
        "evidence_ids": sorted(evidence_ids),
        "provider_name": provider_name,
        "version": version,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class Stage4TaskQueue:
    """Durable SQLite queue managing lifecycle and retries of Stage 4 analysis tasks."""

    def __init__(self, db_path: str = "data/stage4_task_queue.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        """Create schema with strict indexing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stage4_tasks (
                    task_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    dedup_hash TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    model_name TEXT,
                    incident_context_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    candidates_json TEXT,
                    historical_patterns_json TEXT,
                    result_json TEXT,
                    error_message TEXT,
                    error_category TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    next_retry_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stage4_queue_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_s4_q_status ON stage4_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_s4_q_incident ON stage4_tasks(incident_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_s4_q_dedup ON stage4_tasks(dedup_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_s4_q_retry ON stage4_tasks(next_retry_at)")
            conn.commit()

    def enqueue(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        candidates: Optional[List[ProbableRootCause]] = None,
        historical_patterns: Optional[List[Dict[str, Any]]] = None,
        provider_name: str = "gemini",
        model_name: Optional[str] = None,
        max_retries: int = 3,
        force_retry_failed: bool = False,
    ) -> Tuple[AnalysisTask, bool]:
        """
        Enqueue an incident analysis task with deduplication.

        Returns:
            Tuple[AnalysisTask, bool]: (task, is_newly_enqueued)
            is_newly_enqueued is False if a completed, active, or duplicate task was reused.
        """
        evidence_ids = [e.source_id for e in evidence if e.source_id]
        dedup_hash = compute_task_dedup_hash(
            incident_id=context.incident_id,
            alert_ids=context.alert_ids,
            evidence_ids=evidence_ids,
            provider_name=provider_name,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stage4_tasks WHERE dedup_hash = ?", (dedup_hash,))
            row = cursor.fetchone()

            if row:
                existing = self._row_to_task(row)
                if existing.status == TaskStatus.COMPLETED:
                    logger.info("Task for incident %s already completed (dedup: %s)", context.incident_id, dedup_hash[:8])
                    return existing, False

                if existing.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                    logger.info("Task for incident %s already active (%s)", context.incident_id, existing.status)
                    return existing, False

                if existing.status == TaskStatus.FAILED and not force_retry_failed:
                    logger.info("Task for incident %s in failed state (dedup: %s)", context.incident_id, dedup_hash[:8])
                    return existing, False

                # If force_retry_failed is True on a failed task:
                now_str = datetime.now(timezone.utc).isoformat()
                cursor.execute("""
                    UPDATE stage4_tasks
                    SET status = ?, retry_count = 0, next_retry_at = NULL,
                        error_message = NULL, error_category = NULL, updated_at = ?
                    WHERE dedup_hash = ?
                """, (TaskStatus.PENDING.value, now_str, dedup_hash))
                conn.commit()
                cursor.execute("SELECT * FROM stage4_tasks WHERE dedup_hash = ?", (dedup_hash,))
                return self._row_to_task(cursor.fetchone()), True

            # Insert new task
            task_id = f"task_{context.incident_id}_{int(time.time()*1000)}"
            now_str = datetime.now(timezone.utc).isoformat()
            context_json = context.model_dump_json()
            evidence_json = json.dumps([e.model_dump(mode="json") for e in evidence])
            candidates_json = json.dumps([c.model_dump(mode="json") for c in candidates]) if candidates else None
            patterns_json = json.dumps(historical_patterns) if historical_patterns else None

            cursor.execute("""
                INSERT INTO stage4_tasks (
                    task_id, incident_id, dedup_hash, status, provider_name, model_name,
                    incident_context_json, evidence_json, candidates_json, historical_patterns_json,
                    retry_count, max_retries, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """, (
                task_id, context.incident_id, dedup_hash, TaskStatus.PENDING.value,
                provider_name, model_name, context_json, evidence_json,
                candidates_json, patterns_json, max_retries, now_str, now_str
            ))
            conn.commit()
            cursor.execute("SELECT * FROM stage4_tasks WHERE task_id = ?", (task_id,))
            return self._row_to_task(cursor.fetchone()), True

    def recover_unfinished_tasks(self, stale_timeout_seconds: Optional[float] = None) -> int:
        """
        Recover tasks left in PROCESSING state after crash or restart.

        Resets processing tasks to PENDING if retries remain, or FAILED if max retries reached.
        """
        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.isoformat()
        recovered_count = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            if stale_timeout_seconds is not None:
                cutoff = (now_utc - timedelta(seconds=stale_timeout_seconds)).isoformat()
                cursor.execute("SELECT * FROM stage4_tasks WHERE status = ? AND updated_at <= ?", (TaskStatus.PROCESSING.value, cutoff))
            else:
                cursor.execute("SELECT * FROM stage4_tasks WHERE status = ?", (TaskStatus.PROCESSING.value,))

            rows = cursor.fetchall()
            for row in rows:
                task = self._row_to_task(row)
                if task.retry_count < task.max_retries:
                    cursor.execute("""
                        UPDATE stage4_tasks
                        SET status = ?, updated_at = ?
                        WHERE task_id = ?
                    """, (TaskStatus.PENDING.value, now_str, task.task_id))
                else:
                    cursor.execute("""
                        UPDATE stage4_tasks
                        SET status = ?, error_message = 'Max retries exhausted across restarts',
                            error_category = ?, updated_at = ?
                        WHERE task_id = ?
                    """, (TaskStatus.FAILED.value, ErrorCategory.PERMANENT.value, now_str, task.task_id))
                recovered_count += 1
            conn.commit()

        if recovered_count:
            logger.warning("Recovered %d unfinished tasks from previous run/crash", recovered_count)
        return recovered_count

    def get_metadata(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Fetch metadata value by key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM stage4_queue_metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_metadata(self, key: str, value: str) -> None:
        """Set metadata key-value pair."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (key, value, now_str))
            conn.commit()

    def pause_queue(
        self,
        reason: str = "daily_quota_exhausted",
        paused_until: Optional[datetime] = None,
    ) -> None:
        """
        Durably pause the queue, preventing workers from claiming tasks.
        
        Args:
            reason: Explanation for pause (e.g., 'daily_quota_exhausted')
            paused_until: Optional timestamp when the queue is expected to become eligible again
        """
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES ('is_paused', 'true', ?)
                ON CONFLICT(key) DO UPDATE SET value = 'true', updated_at = ?
            """, (now_str, now_str))
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES ('pause_reason', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """, (reason, now_str, reason, now_str))
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES ('paused_at', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """, (now_str, now_str, now_str, now_str))
            paused_until_str = paused_until.isoformat() if paused_until else ""
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES ('paused_until', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """, (paused_until_str, now_str, paused_until_str, now_str))
            conn.commit()
        logger.warning("Stage 4 task queue paused: reason=%s, paused_until=%s", reason, paused_until)

    def is_paused(self) -> bool:
        """
        Check if queue is paused.
        
        If paused_until timestamp has passed, the pause has expired and is automatically cleared.
        """
        paused_val = self.get_metadata("is_paused", "false")
        if paused_val.lower() != "true":
            return False

        paused_until_str = self.get_metadata("paused_until", "")
        if paused_until_str:
            try:
                paused_until = datetime.fromisoformat(paused_until_str)
                now_utc = datetime.now(timezone.utc)
                if now_utc >= paused_until:
                    logger.info("Durable queue pause expired at %s (current: %s); auto-resuming", paused_until_str, now_utc.isoformat())
                    self.resume_queue(reset_quota_exhausted_tasks=False)
                    return False
            except (ValueError, TypeError):
                pass
        return True

    def get_pause_status(self) -> Dict[str, Any]:
        """Get complete pause status information."""
        return {
            "is_paused": self.is_paused(),
            "pause_reason": self.get_metadata("pause_reason"),
            "paused_at": self.get_metadata("paused_at"),
            "paused_until": self.get_metadata("paused_until") or None,
        }

    def resume_queue(
        self,
        reset_quota_exhausted_tasks: bool = False,
        incident_ids: Optional[List[str]] = None,
        new_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Explicitly resume queue processing.
        
        Args:
            reset_quota_exhausted_tasks: If True, resets failed tasks with quota_exhausted
                                        category back to pending state for safe retry.
                                        NEVER touches completed tasks or non-quota failures.
            incident_ids: Optional list of specific incident IDs to reset (if None, all eligible).
            new_model: Optional new model name to assign to reset tasks.
            
        Returns:
            Dict summarizing resume actions taken.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES ('is_paused', 'false', ?)
                ON CONFLICT(key) DO UPDATE SET value = 'false', updated_at = ?
            """, (now_str, now_str))
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES ('pause_reason', '', ?)
                ON CONFLICT(key) DO UPDATE SET value = '', updated_at = ?
            """, (now_str, now_str))
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES ('paused_until', '', ?)
                ON CONFLICT(key) DO UPDATE SET value = '', updated_at = ?
            """, (now_str, now_str))
            cursor.execute("""
                INSERT INTO stage4_queue_metadata (key, value, updated_at)
                VALUES ('resumed_at', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """, (now_str, now_str, now_str, now_str))
            conn.commit()

        resumed_task_ids = []
        if reset_quota_exhausted_tasks:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT task_id, incident_id FROM stage4_tasks
                    WHERE status = ? AND error_category IN (?, ?)
                """
                params: List[Any] = [TaskStatus.FAILED.value, ErrorCategory.QUOTA_EXHAUSTED.value, ErrorCategory.RATE_LIMIT.value]
                if incident_ids:
                    query += f" AND incident_id IN ({','.join(['?']*len(incident_ids))})"
                    params.extend(incident_ids)

                cursor.execute(query, params)
                eligible_rows = cursor.fetchall()

                for row in eligible_rows:
                    tid = row["task_id"]
                    resumed_task_ids.append(tid)
                    update_query = """
                        UPDATE stage4_tasks
                        SET status = ?, retry_count = 0, error_message = NULL,
                            error_category = NULL, next_retry_at = NULL, updated_at = ?
                    """
                    update_params: List[Any] = [TaskStatus.PENDING.value, now_str]
                    if new_model:
                        update_query += ", model_name = ?"
                        update_params.append(new_model)
                    update_query += " WHERE task_id = ?"
                    update_params.append(tid)

                    cursor.execute(update_query, update_params)
                conn.commit()

        logger.info("Resumed Stage 4 task queue. Resets applied: %d tasks", len(resumed_task_ids))
        return {
            "unpaused": True,
            "resumed_tasks_count": len(resumed_task_ids),
            "resumed_task_ids": resumed_task_ids,
        }

    def claim_next_task(self) -> Optional[AnalysisTask]:
        """Atomically claim the next eligible PENDING task."""
        if self.is_paused():
            logger.info("Refusing to claim task: task queue is durably paused")
            return None

        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM stage4_tasks
                WHERE status = ? AND (next_retry_at IS NULL OR next_retry_at <= ?)
                ORDER BY created_at ASC
                LIMIT 1
            """, (TaskStatus.PENDING.value, now_str))
            row = cursor.fetchone()
            if not row:
                return None

            task = self._row_to_task(row)
            cursor.execute("""
                UPDATE stage4_tasks
                SET status = ?, updated_at = ?
                WHERE task_id = ? AND status = ?
            """, (TaskStatus.PROCESSING.value, now_str, task.task_id, TaskStatus.PENDING.value))
            conn.commit()

            if cursor.rowcount == 0:
                # Concurrent worker claimed it first
                return None

            task.status = TaskStatus.PROCESSING
            task.updated_at = now_str
            return task

    def mark_completed(self, task_id: str, result: RCAResult) -> None:
        """Mark task completed and persist full RCAResult JSON."""
        now_str = datetime.now(timezone.utc).isoformat()
        result_json = result.model_dump_json()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE stage4_tasks
                SET status = ?, result_json = ?, completed_at = ?, updated_at = ?,
                    error_message = NULL, error_category = NULL
                WHERE task_id = ?
            """, (TaskStatus.COMPLETED.value, result_json, now_str, now_str, task_id))
            conn.commit()

    def mark_failed_or_retry(
        self,
        task_id: str,
        error: Exception,
        error_category: Optional[ErrorCategory] = None,
        base_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 60.0,
    ) -> Tuple[TaskStatus, Optional[float]]:
        """
        Record failure with exponential backoff if retryable, or mark permanent failure.

        Returns:
            Tuple[TaskStatus, Optional[float]]: (new_status, delay_seconds_if_retrying)
        """
        # Categorize error if not explicitly supplied
        category = error_category or self._classify_error(error)
        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT retry_count, max_retries FROM stage4_tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return TaskStatus.FAILED, None

            retry_count = row["retry_count"]
            max_retries = row["max_retries"]

            is_retryable = category in (ErrorCategory.TEMPORARY, ErrorCategory.RATE_LIMIT)

            if is_retryable and retry_count < max_retries:
                next_count = retry_count + 1
                delay_sec = min(max_backoff_seconds, base_backoff_seconds * (2 ** retry_count))
                next_retry_at = (now_utc + timedelta(seconds=delay_sec)).isoformat()

                cursor.execute("""
                    UPDATE stage4_tasks
                    SET status = ?, retry_count = ?, next_retry_at = ?,
                        error_message = ?, error_category = ?, updated_at = ?
                    WHERE task_id = ?
                """, (
                    TaskStatus.PENDING.value, next_count, next_retry_at,
                    str(error), category.value, now_str, task_id
                ))
                conn.commit()
                return TaskStatus.PENDING, delay_sec

            # Permanent failure or retries exhausted
            new_status = TaskStatus.FAILED
            err_msg = str(error)
            if is_retryable and retry_count >= max_retries:
                err_msg = f"Retries exhausted ({max_retries}/{max_retries}): {err_msg}"

            cursor.execute("""
                UPDATE stage4_tasks
                SET status = ?, error_message = ?, error_category = ?,
                    next_retry_at = NULL, updated_at = ?
                WHERE task_id = ?
            """, (new_status.value, err_msg, category.value, now_str, task_id))
            conn.commit()
            return TaskStatus.FAILED, None

    def get_task(self, task_id: str) -> Optional[AnalysisTask]:
        """Retrieve task by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stage4_tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            return self._row_to_task(row) if row else None

    def get_task_by_dedup(self, dedup_hash: str) -> Optional[AnalysisTask]:
        """Retrieve task by deduplication hash."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stage4_tasks WHERE dedup_hash = ?", (dedup_hash,))
            row = cursor.fetchone()
            return self._row_to_task(row) if row else None

    def get_counts_by_status(self) -> Dict[str, int]:
        """Get summary counts of tasks across all states."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) as cnt FROM stage4_tasks GROUP BY status")
            counts = {s.value: 0 for s in TaskStatus}
            for row in cursor.fetchall():
                counts[row["status"]] = row["cnt"]
            return counts

    def get_all_completed_results(self) -> List[RCAResult]:
        """Fetch all completed RCAResults without modifying queue."""
        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT result_json FROM stage4_tasks WHERE status = ?", (TaskStatus.COMPLETED.value,))
            for row in cursor.fetchall():
                if row["result_json"]:
                    results.append(RCAResult.model_validate_json(row["result_json"]))
        return results

    @staticmethod
    def _classify_error(error: Exception) -> ErrorCategory:
        """Categorize exception into retryable vs non-retryable categories."""
        if isinstance(error, (GeminiAuthenticationError, GeminiConfigurationError)):
            return ErrorCategory.AUTHENTICATION
        if isinstance(error, GeminiStructuredOutputError):
            return ErrorCategory.SCHEMA_VALIDATION
        if isinstance(error, GeminiRateLimitError):
            err_str = str(error).lower()
            if "quota" in err_str or "resource_exhausted" in err_str or "exceeded your current quota" in err_str:
                return ErrorCategory.QUOTA_EXHAUSTED
            return ErrorCategory.RATE_LIMIT
        if isinstance(error, (GeminiTimeoutError, TimeoutError)):
            return ErrorCategory.TEMPORARY
        if isinstance(error, GeminiError):
            err_str = str(error).lower()
            if "quota" in err_str or "resource_exhausted" in err_str:
                return ErrorCategory.QUOTA_EXHAUSTED
            if "429" in err_str or "rate limit" in err_str or "rate_limit" in err_str:
                return ErrorCategory.RATE_LIMIT
            if "timeout" in err_str or "timed out" in err_str:
                return ErrorCategory.TEMPORARY

        err_str = str(error).lower()
        if "quota" in err_str or "resource_exhausted" in err_str or "exceeded your current quota" in err_str:
            return ErrorCategory.QUOTA_EXHAUSTED
        if "429" in err_str or "rate limit" in err_str or "rate_limit" in err_str:
            return ErrorCategory.RATE_LIMIT

        return ErrorCategory.PERMANENT

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> AnalysisTask:
        return AnalysisTask(
            task_id=row["task_id"],
            incident_id=row["incident_id"],
            dedup_hash=row["dedup_hash"],
            status=row["status"],
            provider_name=row["provider_name"],
            model_name=row["model_name"],
            incident_context_json=row["incident_context_json"],
            evidence_json=row["evidence_json"],
            candidates_json=row["candidates_json"],
            historical_patterns_json=row["historical_patterns_json"],
            result_json=row["result_json"],
            error_message=row["error_message"],
            error_category=row["error_category"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            next_retry_at=row["next_retry_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )


class QueueExecutionSummary:
    """Summary of batch queue processing."""

    def __init__(self):
        self.submitted: int = 0
        self.processed: int = 0
        self.completed: int = 0
        self.failed: int = 0
        self.retried: int = 0
        self.skipped: int = 0
        self.halted_reason: Optional[str] = None
        self.duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "submitted": self.submitted,
            "processed": self.processed,
            "completed": self.completed,
            "failed": self.failed,
            "retried": self.retried,
            "skipped": self.skipped,
            "halted_reason": self.halted_reason,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class Stage4QueueWorker:
    """Worker processing tasks from Stage4TaskQueue with proactive rate pacing and safety checks."""

    def __init__(
        self,
        queue: Stage4TaskQueue,
        provider: Optional[ReasoningProvider] = None,
        rpm_limit: int = 15,
        base_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 60.0,
    ):
        self.queue = queue
        self.provider = provider
        self.rpm_limit = max(1, rpm_limit)
        self.min_interval = 60.0 / self.rpm_limit
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self._last_request_time: float = 0.0

    def _wait_rate_limit(self) -> None:
        """Proactively pace requests to avoid burst rate-limit errors."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.monotonic()

    def process_one(self) -> Optional[Tuple[AnalysisTask, TaskStatus]]:
        """
        Claim and execute one task from the queue.

        Returns:
            Tuple[AnalysisTask, TaskStatus] if a task was processed, or None if queue is empty.
        """
        task = self.queue.claim_next_task()
        if not task:
            return None

        # Resolve provider
        provider = self.provider or get_reasoning_provider(task.provider_name, model=task.model_name)

        try:
            context = task.get_incident_context()
            evidence = task.get_evidence()
            candidates = task.get_candidates()

            # Enforce proactive RPM pacing before API invocation
            self._wait_rate_limit()

            result = provider.analyze(
                context=context,
                evidence=evidence,
                rca_candidates=candidates,
            )

            # Safety check: Verify API failure was not masked as success
            if result.reasoning_provider.endswith("_fallback"):
                # Explicit fallback occurred due to provider error
                fallback_reason = "Unknown fallback"
                if result.review_reasons:
                    fallback_reason = "; ".join(result.review_reasons)
                raise GeminiError(f"Provider fallback triggered: {fallback_reason}")

            self.queue.mark_completed(task.task_id, result)
            task.status = TaskStatus.COMPLETED
            task.result_json = result.model_dump_json()
            return task, TaskStatus.COMPLETED

        except Exception as exc:
            category = self.queue._classify_error(exc)
            new_status, _ = self.queue.mark_failed_or_retry(
                task_id=task.task_id,
                error=exc,
                error_category=category,
                base_backoff_seconds=self.base_backoff_seconds,
                max_backoff_seconds=self.max_backoff_seconds,
            )
            task.status = new_status
            task.error_category = category
            task.error_message = str(exc)

            if category == ErrorCategory.QUOTA_EXHAUSTED:
                self.queue.pause_queue(reason="daily_quota_exhausted")

            return task, new_status

    def run_batch(
        self,
        max_tasks: Optional[int] = None,
        stop_on_quota_exhausted: bool = True,
    ) -> QueueExecutionSummary:
        """
        Process tasks until queue is drained, max_tasks reached, or quota exhausted.
        """
        summary = QueueExecutionSummary()
        counts = self.queue.get_counts_by_status()
        summary.submitted = counts.get(TaskStatus.PENDING.value, 0)
        start_time = time.monotonic()

        if self.queue.is_paused():
            summary.halted_reason = "queue_paused"
            logger.info("Batch execution prevented: queue is durably paused (%s)", self.queue.get_metadata("pause_reason"))
            summary.duration_seconds = time.monotonic() - start_time
            return summary

        while True:
            if max_tasks is not None and summary.processed >= max_tasks:
                summary.halted_reason = "max_tasks_reached"
                break

            processed_result = self.process_one()
            if not processed_result:
                # No more eligible tasks right now
                break

            task, outcome_status = processed_result
            summary.processed += 1

            if outcome_status == TaskStatus.COMPLETED:
                summary.completed += 1
            elif outcome_status == TaskStatus.PENDING:
                summary.retried += 1
            elif outcome_status == TaskStatus.FAILED:
                summary.failed += 1
                if stop_on_quota_exhausted and task.error_category == ErrorCategory.QUOTA_EXHAUSTED:
                    logger.error("Halting batch processing: Gemini quota exhausted")
                    summary.halted_reason = "quota_exhausted"
                    break

        summary.duration_seconds = time.monotonic() - start_time
        return summary
