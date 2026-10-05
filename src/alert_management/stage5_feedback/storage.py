"""
Feedback Storage Layer.

Stores feedback records in SQLite database for persistence and querying.
"""

import sqlite3
import json
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from .schemas import FeedbackRecord, FeedbackSummary


class FeedbackStore:
    """
    SQLite-based storage for feedback records.
    
    Provides CRUD operations and aggregation queries for feedback data.
    """
    
    def __init__(self, db_path: str = "data/feedback.db"):
        """
        Initialize feedback store.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                engineer_id TEXT NOT NULL,
                engineer_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                stage TEXT NOT NULL,
                overall_quality INTEGER NOT NULL,
                comments TEXT,
                estimated_time_saved_minutes INTEGER,
                system_version TEXT,
                processing_time_seconds REAL,
                alert_ids_json TEXT NOT NULL,
                classification_feedback_json TEXT,
                correlation_feedback_json TEXT,
                rca_feedback_json TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Index for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_incident_id ON feedback(incident_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON feedback(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stage ON feedback(stage)
        """)
        
        conn.commit()
        conn.close()
    
    def save_feedback(self, feedback: FeedbackRecord) -> FeedbackRecord:
        """
        Save feedback record to database.
        
        Args:
            feedback: Feedback record to save
        
        Returns:
            The saved feedback record
        
        Raises:
            ValueError: If feedback_id already exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO feedback (
                    feedback_id, incident_id, engineer_id, engineer_name,
                    timestamp, stage, overall_quality, comments,
                    estimated_time_saved_minutes, system_version,
                    processing_time_seconds, alert_ids_json,
                    classification_feedback_json, correlation_feedback_json,
                    rca_feedback_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback.feedback_id,
                feedback.incident_id,
                feedback.engineer_id,
                feedback.engineer_name,
                feedback.timestamp.isoformat(),
                feedback.stage.value,
                feedback.overall_quality,
                feedback.comments,
                feedback.estimated_time_saved_minutes,
                feedback.system_version,
                feedback.processing_time_seconds,
                json.dumps(feedback.alert_ids),
                json.dumps(feedback.classification_feedback.dict()) if feedback.classification_feedback else None,
                json.dumps(feedback.correlation_feedback.dict()) if feedback.correlation_feedback else None,
                json.dumps(feedback.rca_feedback.dict()) if feedback.rca_feedback else None,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            return feedback
            
        except sqlite3.IntegrityError:
            raise ValueError(f"Feedback with ID {feedback.feedback_id} already exists")
        finally:
            conn.close()
    
    def get_feedback(self, feedback_id: str) -> Optional[FeedbackRecord]:
        """
        Retrieve feedback by ID.
        
        Args:
            feedback_id: Feedback identifier
        
        Returns:
            FeedbackRecord if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM feedback WHERE feedback_id = ?
        """, (feedback_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_feedback(row)
    
    def get_feedback_by_incident(self, incident_id: str) -> List[FeedbackRecord]:
        """
        Retrieve all feedback for an incident.
        
        Args:
            incident_id: Incident identifier
        
        Returns:
            List of feedback records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM feedback WHERE incident_id = ? ORDER BY timestamp DESC
        """, (incident_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_feedback(row) for row in rows]
    
    def get_feedback_in_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        stage: Optional[str] = None
    ) -> List[FeedbackRecord]:
        """
        Retrieve feedback within date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            stage: Optional filter by stage
        
        Returns:
            List of feedback records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if stage:
            cursor.execute("""
                SELECT * FROM feedback 
                WHERE timestamp >= ? AND timestamp <= ? AND stage = ?
                ORDER BY timestamp DESC
            """, (start_date.isoformat(), end_date.isoformat(), stage))
        else:
            cursor.execute("""
                SELECT * FROM feedback 
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            """, (start_date.isoformat(), end_date.isoformat()))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_feedback(row) for row in rows]
    
    def get_feedback_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        stage: Optional[str] = None
    ) -> FeedbackSummary:
        """
        Get aggregated feedback summary.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            stage: Optional filter by stage
        
        Returns:
            FeedbackSummary with aggregated statistics
        """
        feedbacks = self.get_feedback_in_date_range(start_date, end_date, stage)
        
        if not feedbacks:
            return FeedbackSummary(
                total_feedback_count=0,
                date_range_start=start_date,
                date_range_end=end_date,
                average_overall_quality=0.0,
                total_time_saved_minutes=0,
                average_time_saved_minutes=0.0
            )
        
        # Calculate overall metrics
        total_count = len(feedbacks)
        avg_quality = sum(f.overall_quality for f in feedbacks) / total_count
        
        time_saved_values = [f.estimated_time_saved_minutes for f in feedbacks if f.estimated_time_saved_minutes]
        total_time_saved = sum(time_saved_values) if time_saved_values else 0
        avg_time_saved = total_time_saved / len(time_saved_values) if time_saved_values else 0.0
        
        # Count stage-specific feedback
        classification_count = sum(1 for f in feedbacks if f.classification_feedback)
        correlation_count = sum(1 for f in feedbacks if f.correlation_feedback)
        rca_count = sum(1 for f in feedbacks if f.rca_feedback)
        
        # Calculate classification accuracy
        classification_accuracy = None
        if classification_count > 0:
            correct = sum(
                1 for f in feedbacks
                if f.classification_feedback and
                f.classification_feedback.alert_type_correct and
                f.classification_feedback.severity_correct and
                f.classification_feedback.priority_correct and
                f.classification_feedback.routing_correct
            )
            classification_accuracy = correct / classification_count
        
        # Calculate correlation accuracy
        correlation_accuracy = None
        if correlation_count > 0:
            correct = sum(
                1 for f in feedbacks
                if f.correlation_feedback and f.correlation_feedback.grouping_correct
            )
            correlation_accuracy = correct / correlation_count
        
        # Calculate RCA metrics
        rca_correctness_rate = None
        rca_helpfulness_rate = None
        avg_rca_usefulness = None
        if rca_count > 0:
            correct = sum(1 for f in feedbacks if f.rca_feedback and f.rca_feedback.rca_correct)
            helpful = sum(1 for f in feedbacks if f.rca_feedback and f.rca_feedback.rca_helpful)
            usefulness_values = [f.rca_feedback.rca_usefulness for f in feedbacks if f.rca_feedback]
            
            rca_correctness_rate = correct / rca_count
            rca_helpfulness_rate = helpful / rca_count
            avg_rca_usefulness = sum(usefulness_values) / len(usefulness_values)
        
        # Calculate communication quality
        avg_support_comm = None
        avg_stakeholder_comm = None
        if rca_count > 0:
            support_values = [f.rca_feedback.support_communication_quality for f in feedbacks if f.rca_feedback]
            stakeholder_values = [f.rca_feedback.stakeholder_communication_quality for f in feedbacks if f.rca_feedback]
            
            avg_support_comm = sum(support_values) / len(support_values) if support_values else None
            avg_stakeholder_comm = sum(stakeholder_values) / len(stakeholder_values) if stakeholder_values else None
        
        return FeedbackSummary(
            total_feedback_count=total_count,
            date_range_start=start_date,
            date_range_end=end_date,
            average_overall_quality=avg_quality,
            total_time_saved_minutes=total_time_saved,
            average_time_saved_minutes=avg_time_saved,
            classification_feedback_count=classification_count,
            correlation_feedback_count=correlation_count,
            rca_feedback_count=rca_count,
            classification_accuracy=classification_accuracy,
            correlation_accuracy=correlation_accuracy,
            rca_correctness_rate=rca_correctness_rate,
            rca_helpfulness_rate=rca_helpfulness_rate,
            average_rca_usefulness=avg_rca_usefulness,
            average_support_communication_quality=avg_support_comm,
            average_stakeholder_communication_quality=avg_stakeholder_comm
        )
    
    def delete_feedback(self, feedback_id: str) -> bool:
        """
        Delete feedback record.
        
        Args:
            feedback_id: Feedback identifier
        
        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM feedback WHERE feedback_id = ?", (feedback_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def _row_to_feedback(self, row: tuple) -> FeedbackRecord:
        """Convert database row to FeedbackRecord."""
        from .schemas import ClassificationFeedback, CorrelationFeedback, RCAFeedback, FeedbackStage
        
        # Parse JSON fields
        alert_ids = json.loads(row[11])
        
        classification_feedback = None
        if row[12]:
            classification_feedback = ClassificationFeedback(**json.loads(row[12]))
        
        correlation_feedback = None
        if row[13]:
            correlation_feedback = CorrelationFeedback(**json.loads(row[13]))
        
        rca_feedback = None
        if row[14]:
            rca_feedback = RCAFeedback(**json.loads(row[14]))
        
        return FeedbackRecord(
            feedback_id=row[0],
            incident_id=row[1],
            engineer_id=row[2],
            engineer_name=row[3],
            timestamp=datetime.fromisoformat(row[4]),
            stage=FeedbackStage(row[5]),
            overall_quality=row[6],
            comments=row[7],
            estimated_time_saved_minutes=row[8],
            system_version=row[9],
            processing_time_seconds=row[10],
            alert_ids=alert_ids,
            classification_feedback=classification_feedback,
            correlation_feedback=correlation_feedback,
            rca_feedback=rca_feedback
        )
