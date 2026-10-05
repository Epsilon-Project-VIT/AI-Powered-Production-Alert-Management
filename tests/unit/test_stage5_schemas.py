"""
Unit tests for Stage 5 feedback schemas.
"""

import pytest
from datetime import datetime

from alert_management.stage5_feedback.schemas import (
    FeedbackRecord,
    ClassificationFeedback,
    CorrelationFeedback,
    RCAFeedback,
    FeedbackStage,
    FeedbackSummary,
    FailurePattern,
    ImprovementSuggestion
)


class TestClassificationFeedback:
    """Test ClassificationFeedback schema."""
    
    def test_create_classification_feedback(self):
        """Create classification feedback."""
        feedback = ClassificationFeedback(
            alert_type_correct=True,
            severity_correct=True,
            business_impact_correct=False,
            business_impact_actual="LOW",
            priority_correct=True,
            routing_correct=True,
            classification_usefulness=4,
            notes="Business impact was overestimated"
        )
        
        assert feedback.alert_type_correct is True
        assert feedback.business_impact_correct is False
        assert feedback.business_impact_actual == "LOW"
        assert feedback.classification_usefulness == 4


class TestCorrelationFeedback:
    """Test CorrelationFeedback schema."""
    
    def test_create_correlation_feedback(self):
        """Create correlation feedback."""
        feedback = CorrelationFeedback(
            grouping_correct=False,
            should_be_separate_incidents=True,
            should_exclude_alerts=["INC001", "INC002"],
            correlation_usefulness=2,
            notes="INC001 and INC002 are unrelated"
        )
        
        assert feedback.grouping_correct is False
        assert feedback.should_be_separate_incidents is True
        assert len(feedback.should_exclude_alerts) == 2
        assert feedback.correlation_usefulness == 2


class TestRCAFeedback:
    """Test RCAFeedback schema."""
    
    def test_create_rca_feedback(self):
        """Create RCA feedback."""
        feedback = RCAFeedback(
            rca_correct=True,
            rca_helpful=True,
            evidence_sufficient=False,
            evidence_relevant=True,
            missing_evidence_types=["network_traces"],
            recommendations_helpful=True,
            recommendations_actionable=True,
            support_communication_quality=4,
            stakeholder_communication_quality=5,
            rca_usefulness=4,
            notes="Would benefit from network trace data"
        )
        
        assert feedback.rca_correct is True
        assert feedback.evidence_sufficient is False
        assert "network_traces" in feedback.missing_evidence_types
        assert feedback.support_communication_quality == 4
        assert feedback.rca_usefulness == 4


class TestFeedbackRecord:
    """Test FeedbackRecord schema."""
    
    def test_create_complete_feedback_record(self):
        """Create complete feedback record with all stages."""
        record = FeedbackRecord(
            feedback_id="FEEDBACK-001",
            incident_id="INCIDENT-EA-001",
            alert_ids=["INC3528891", "INC3528892"],
            engineer_id="ENG123",
            engineer_name="John Doe",
            timestamp=datetime(2026, 8, 6, 15, 30, 0),
            stage=FeedbackStage.END_TO_END,
            classification_feedback=ClassificationFeedback(
                alert_type_correct=True,
                severity_correct=True,
                business_impact_correct=True,
                priority_correct=True,
                routing_correct=True,
                classification_usefulness=5
            ),
            correlation_feedback=CorrelationFeedback(
                grouping_correct=True,
                correlation_usefulness=5
            ),
            rca_feedback=RCAFeedback(
                rca_correct=True,
                rca_helpful=True,
                evidence_sufficient=True,
                evidence_relevant=True,
                recommendations_helpful=True,
                recommendations_actionable=True,
                support_communication_quality=4,
                stakeholder_communication_quality=5,
                rca_usefulness=5
            ),
            overall_quality=5,
            estimated_time_saved_minutes=45,
            comments="Excellent analysis, saved significant time"
        )
        
        assert record.feedback_id == "FEEDBACK-001"
        assert record.incident_id == "INCIDENT-EA-001"
        assert len(record.alert_ids) == 2
        assert record.stage == FeedbackStage.END_TO_END
        assert record.overall_quality == 5
        assert record.estimated_time_saved_minutes == 45
        
        # Verify all feedback sections present
        assert record.classification_feedback is not None
        assert record.correlation_feedback is not None
        assert record.rca_feedback is not None
    
    def test_create_rca_only_feedback(self):
        """Create feedback record with only RCA feedback."""
        record = FeedbackRecord(
            feedback_id="FEEDBACK-002",
            incident_id="INCIDENT-EA-002",
            alert_ids=["INC001"],
            engineer_id="ENG456",
            engineer_name="Jane Smith",
            timestamp=datetime(2026, 8, 7, 10, 0, 0),
            stage=FeedbackStage.RCA,
            rca_feedback=RCAFeedback(
                rca_correct=False,
                rca_helpful=False,
                actual_root_cause="Network congestion, not database issue",
                evidence_sufficient=False,
                evidence_relevant=False,
                missing_evidence_types=["network_metrics", "traces"],
                recommendations_helpful=False,
                recommendations_actionable=False,
                support_communication_quality=2,
                stakeholder_communication_quality=2,
                rca_usefulness=2
            ),
            overall_quality=2,
            comments="RCA was incorrect, missed network layer"
        )
        
        assert record.stage == FeedbackStage.RCA
        assert record.classification_feedback is None
        assert record.correlation_feedback is None
        assert record.rca_feedback is not None
        assert record.rca_feedback.rca_correct is False
        assert record.overall_quality == 2


class TestFeedbackSummary:
    """Test FeedbackSummary schema."""
    
    def test_create_feedback_summary(self):
        """Create feedback summary."""
        summary = FeedbackSummary(
            total_feedback_count=10,
            date_range_start=datetime(2026, 8, 1),
            date_range_end=datetime(2026, 8, 31),
            average_overall_quality=4.2,
            total_time_saved_minutes=450,
            average_time_saved_minutes=45.0,
            classification_feedback_count=8,
            correlation_feedback_count=6,
            rca_feedback_count=10,
            classification_accuracy=0.875,
            correlation_accuracy=0.833,
            rca_correctness_rate=0.9,
            rca_helpfulness_rate=0.95,
            average_rca_usefulness=4.3,
            average_support_communication_quality=4.1,
            average_stakeholder_communication_quality=4.5
        )
        
        assert summary.total_feedback_count == 10
        assert summary.average_overall_quality == 4.2
        assert summary.total_time_saved_minutes == 450
        assert summary.classification_accuracy == 0.875
        assert summary.rca_correctness_rate == 0.9


class TestFailurePattern:
    """Test FailurePattern schema."""
    
    def test_create_failure_pattern(self):
        """Create failure pattern."""
        pattern = FailurePattern(
            pattern_id="PATTERN-001",
            pattern_type="classification",
            description="Consistently misclassifies BATCH/WORKFLOW alerts as DATABASE alerts",
            frequency=15,
            severity="high",
            example_incident_ids=["INC001", "INC002", "INC003"],
            affected_clients=["Pizza Hut", "Bridgestone"],
            affected_alert_types=["BATCH", "WORKFLOW"],
            suggested_improvement="Add more BATCH/WORKFLOW training examples to Stage 2 model"
        )
        
        assert pattern.pattern_id == "PATTERN-001"
        assert pattern.pattern_type == "classification"
        assert pattern.frequency == 15
        assert pattern.severity == "high"
        assert len(pattern.example_incident_ids) == 3


class TestImprovementSuggestion:
    """Test ImprovementSuggestion schema."""
    
    def test_create_improvement_suggestion(self):
        """Create improvement suggestion."""
        suggestion = ImprovementSuggestion(
            suggestion_id="SUGGEST-001",
            priority="high",
            category="data",
            title="Add more BATCH/WORKFLOW training data",
            description="Stage 2 model struggles with BATCH/WORKFLOW alerts. Add 50+ examples to training set.",
            estimated_impact="Would improve classification accuracy by ~10% for batch-related alerts",
            affected_stage=FeedbackStage.CLASSIFICATION,
            supporting_pattern_ids=["PATTERN-001", "PATTERN-002"],
            estimated_effort="medium"
        )
        
        assert suggestion.priority == "high"
        assert suggestion.category == "data"
        assert suggestion.affected_stage == FeedbackStage.CLASSIFICATION
        assert len(suggestion.supporting_pattern_ids) == 2
        assert suggestion.estimated_effort == "medium"
