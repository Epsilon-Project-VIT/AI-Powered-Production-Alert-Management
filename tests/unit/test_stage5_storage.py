"""
Unit tests for Stage 5 feedback storage.
"""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from alert_management.stage5_feedback.schemas import (
    FeedbackRecord,
    ClassificationFeedback,
    CorrelationFeedback,
    RCAFeedback,
    FeedbackStage
)
from alert_management.stage5_feedback.storage import FeedbackStore


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_feedback.db"
        yield str(db_path)


@pytest.fixture
def feedback_store(temp_db):
    """Create feedback store with temporary database."""
    return FeedbackStore(temp_db)


@pytest.fixture
def sample_feedback():
    """Create sample feedback record."""
    return FeedbackRecord(
        feedback_id="FEEDBACK-TEST-001",
        incident_id="INCIDENT-TEST-001",
        alert_ids=["INC001", "INC002"],
        engineer_id="ENG123",
        engineer_name="Test Engineer",
        timestamp=datetime(2026, 8, 6, 15, 30, 0),
        stage=FeedbackStage.RCA,
        rca_feedback=RCAFeedback(
            rca_correct=True,
            rca_helpful=True,
            evidence_sufficient=True,
            evidence_relevant=True,
            recommendations_helpful=True,
            recommendations_actionable=True,
            support_communication_quality=4,
            stakeholder_communication_quality=5,
            rca_usefulness=4
        ),
        overall_quality=4,
        estimated_time_saved_minutes=45,
        comments="Good analysis"
    )


class TestFeedbackStore:
    """Test FeedbackStore class."""
    
    def test_init_creates_database(self, temp_db):
        """Test that initializing store creates database file."""
        store = FeedbackStore(temp_db)
        assert Path(temp_db).exists()
    
    def test_save_feedback(self, feedback_store, sample_feedback):
        """Test saving feedback record."""
        saved = feedback_store.save_feedback(sample_feedback)
        
        assert saved.feedback_id == sample_feedback.feedback_id
        assert saved.incident_id == sample_feedback.incident_id
    
    def test_save_duplicate_feedback_raises_error(self, feedback_store, sample_feedback):
        """Test that saving duplicate feedback ID raises error."""
        feedback_store.save_feedback(sample_feedback)
        
        with pytest.raises(ValueError, match="already exists"):
            feedback_store.save_feedback(sample_feedback)
    
    def test_get_feedback(self, feedback_store, sample_feedback):
        """Test retrieving feedback by ID."""
        feedback_store.save_feedback(sample_feedback)
        
        retrieved = feedback_store.get_feedback(sample_feedback.feedback_id)
        
        assert retrieved is not None
        assert retrieved.feedback_id == sample_feedback.feedback_id
        assert retrieved.incident_id == sample_feedback.incident_id
        assert retrieved.overall_quality == sample_feedback.overall_quality
        assert retrieved.rca_feedback is not None
        assert retrieved.rca_feedback.rca_correct is True
    
    def test_get_nonexistent_feedback(self, feedback_store):
        """Test retrieving nonexistent feedback returns None."""
        result = feedback_store.get_feedback("NONEXISTENT")
        assert result is None
    
    def test_get_feedback_by_incident(self, feedback_store):
        """Test retrieving all feedback for an incident."""
        # Create multiple feedback records for same incident
        for i in range(3):
            feedback = FeedbackRecord(
                feedback_id=f"FEEDBACK-{i}",
                incident_id="INCIDENT-001",
                alert_ids=["INC001"],
                engineer_id=f"ENG{i}",
                engineer_name=f"Engineer {i}",
                timestamp=datetime(2026, 8, 6, 10 + i, 0, 0),
                stage=FeedbackStage.RCA,
                overall_quality=4,
                comments=f"Feedback {i}"
            )
            feedback_store.save_feedback(feedback)
        
        feedbacks = feedback_store.get_feedback_by_incident("INCIDENT-001")
        
        assert len(feedbacks) == 3
        # Should be ordered by timestamp DESC
        assert feedbacks[0].feedback_id == "FEEDBACK-2"
        assert feedbacks[1].feedback_id == "FEEDBACK-1"
        assert feedbacks[2].feedback_id == "FEEDBACK-0"
    
    def test_get_feedback_in_date_range(self, feedback_store):
        """Test retrieving feedback within date range."""
        # Create feedback records across different dates
        dates = [
            datetime(2026, 8, 1, 10, 0, 0),
            datetime(2026, 8, 15, 10, 0, 0),
            datetime(2026, 8, 31, 10, 0, 0),
        ]
        
        for i, date in enumerate(dates):
            feedback = FeedbackRecord(
                feedback_id=f"FEEDBACK-{i}",
                incident_id=f"INCIDENT-{i}",
                alert_ids=[f"INC{i}"],
                engineer_id="ENG123",
                engineer_name="Test Engineer",
                timestamp=date,
                stage=FeedbackStage.RCA,
                overall_quality=4
            )
            feedback_store.save_feedback(feedback)
        
        # Query for middle date range
        start = datetime(2026, 8, 10)
        end = datetime(2026, 8, 20)
        
        feedbacks = feedback_store.get_feedback_in_date_range(start, end)
        
        assert len(feedbacks) == 1
        assert feedbacks[0].feedback_id == "FEEDBACK-1"
    
    def test_get_feedback_in_date_range_with_stage_filter(self, feedback_store):
        """Test retrieving feedback filtered by stage."""
        # Create feedback records with different stages
        stages = [FeedbackStage.CLASSIFICATION, FeedbackStage.CORRELATION, FeedbackStage.RCA]
        
        for i, stage in enumerate(stages):
            feedback = FeedbackRecord(
                feedback_id=f"FEEDBACK-{i}",
                incident_id=f"INCIDENT-{i}",
                alert_ids=[f"INC{i}"],
                engineer_id="ENG123",
                engineer_name="Test Engineer",
                timestamp=datetime(2026, 8, 15, 10, 0, 0),
                stage=stage,
                overall_quality=4
            )
            feedback_store.save_feedback(feedback)
        
        # Query for only RCA feedback
        start = datetime(2026, 8, 1)
        end = datetime(2026, 8, 31)
        
        feedbacks = feedback_store.get_feedback_in_date_range(start, end, stage="rca")
        
        assert len(feedbacks) == 1
        assert feedbacks[0].stage == FeedbackStage.RCA
    
    def test_get_feedback_summary(self, feedback_store):
        """Test generating feedback summary."""
        # Create multiple feedback records with varying quality
        quality_scores = [5, 4, 4, 3, 5]
        time_saved = [60, 45, 30, 20, 50]
        
        for i in range(len(quality_scores)):
            rca_feedback = None
            if i < 3:  # First 3 have RCA feedback
                rca_feedback = RCAFeedback(
                    rca_correct=i < 2,  # First 2 correct
                    rca_helpful=True,
                    evidence_sufficient=True,
                    evidence_relevant=True,
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=4,
                    stakeholder_communication_quality=4,
                    rca_usefulness=4
                )
            
            feedback = FeedbackRecord(
                feedback_id=f"FEEDBACK-{i}",
                incident_id=f"INCIDENT-{i}",
                alert_ids=[f"INC{i}"],
                engineer_id="ENG123",
                engineer_name="Test Engineer",
                timestamp=datetime(2026, 8, 15, 10 + i, 0, 0),
                stage=FeedbackStage.RCA if rca_feedback else FeedbackStage.CLASSIFICATION,
                rca_feedback=rca_feedback,
                overall_quality=quality_scores[i],
                estimated_time_saved_minutes=time_saved[i]
            )
            feedback_store.save_feedback(feedback)
        
        # Get summary
        start = datetime(2026, 8, 1)
        end = datetime(2026, 8, 31)
        
        summary = feedback_store.get_feedback_summary(start, end)
        
        assert summary.total_feedback_count == 5
        assert summary.average_overall_quality == sum(quality_scores) / len(quality_scores)
        assert summary.total_time_saved_minutes == sum(time_saved)
        assert summary.average_time_saved_minutes == sum(time_saved) / len(time_saved)
        assert summary.rca_feedback_count == 3
        assert summary.rca_correctness_rate == 2 / 3  # 2 out of 3 correct
    
    def test_delete_feedback(self, feedback_store, sample_feedback):
        """Test deleting feedback record."""
        feedback_store.save_feedback(sample_feedback)
        
        # Verify it exists
        assert feedback_store.get_feedback(sample_feedback.feedback_id) is not None
        
        # Delete it
        deleted = feedback_store.delete_feedback(sample_feedback.feedback_id)
        assert deleted is True
        
        # Verify it's gone
        assert feedback_store.get_feedback(sample_feedback.feedback_id) is None
    
    def test_delete_nonexistent_feedback(self, feedback_store):
        """Test deleting nonexistent feedback returns False."""
        deleted = feedback_store.delete_feedback("NONEXISTENT")
        assert deleted is False
