"""
Tests for Stage 5 Metrics Calculator.

Verifies metrics calculation from feedback data.
"""

import pytest
from datetime import datetime, timedelta

from alert_management.stage5_feedback.schemas import (
    FeedbackRecord,
    ClassificationFeedback,
    CorrelationFeedback,
    RCAFeedback,
    FeedbackStage
)
from alert_management.stage5_feedback.metrics import MetricsCalculator


class TestMetricsCalculator:
    """Test metrics calculator."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.calculator = MetricsCalculator()
        self.base_date = datetime(2026, 9, 1, 12, 0, 0)
    
    def test_stage2_metrics_correctness_rate(self):
        """Test Stage 2 per-field correctness calculation."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.CLASSIFICATION,
                classification_feedback=ClassificationFeedback(
                    alert_type_correct=True,
                    severity_correct=True,
                    business_impact_correct=False,
                    priority_correct=True,
                    routing_correct=True,
                    classification_usefulness=4
                ),
                overall_quality=4
            ),
            FeedbackRecord(
                feedback_id="FB002",
                incident_id="INC002",
                alert_ids=["A002"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=1),
                stage=FeedbackStage.CLASSIFICATION,
                classification_feedback=ClassificationFeedback(
                    alert_type_correct=False,
                    severity_correct=True,
                    business_impact_correct=True,
                    priority_correct=False,
                    routing_correct=True,
                    classification_usefulness=3
                ),
                overall_quality=3
            )
        ]
        
        metrics = self.calculator.calculate_stage2_metrics(feedbacks)
        
        assert metrics is not None
        assert metrics.total_feedback_count == 2
        assert metrics.alert_type_accuracy == 0.5  # 1/2
        assert metrics.severity_accuracy == 1.0  # 2/2
        assert metrics.business_impact_accuracy == 0.5  # 1/2
        assert metrics.priority_accuracy == 0.5  # 1/2
        assert metrics.routing_accuracy == 1.0  # 2/2
        assert metrics.overall_accuracy == 0.0  # 0/2 (all fields must be correct)
        assert metrics.average_usefulness == 3.5  # (4+3)/2
    
    def test_stage2_metrics_most_corrected_field(self):
        """Test identification of most corrected field."""
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=[f"A{i:03d}"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=i),
                stage=FeedbackStage.CLASSIFICATION,
                classification_feedback=ClassificationFeedback(
                    alert_type_correct=False,  # Wrong 10 times
                    severity_correct=True,
                    business_impact_correct=False,  # Wrong 10 times
                    priority_correct=False,  # Wrong 10 times
                    routing_correct=True,
                    classification_usefulness=3
                ),
                overall_quality=3
            )
            for i in range(10)
        ]
        
        metrics = self.calculator.calculate_stage2_metrics(feedbacks)
        
        # All three fields have equal correction count, should pick one
        assert metrics.most_corrected_field in ["alert_type", "business_impact", "priority"]
        assert metrics.correction_count == 10
    
    def test_stage2_metrics_empty_feedback(self):
        """Test Stage 2 metrics with no classification feedback."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.RCA,  # No classification feedback
                overall_quality=4
            )
        ]
        
        metrics = self.calculator.calculate_stage2_metrics(feedbacks)
        
        assert metrics is None
    
    def test_stage3_metrics_grouping_correctness(self):
        """Test Stage 3 grouping correctness calculation."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001", "A002"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=True,
                    correlation_usefulness=5
                ),
                overall_quality=5
            ),
            FeedbackRecord(
                feedback_id="FB002",
                incident_id="INC002",
                alert_ids=["A003", "A004"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=1),
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=False,
                    should_be_separate_incidents=True,
                    correlation_usefulness=2
                ),
                overall_quality=2
            )
        ]
        
        metrics = self.calculator.calculate_stage3_metrics(feedbacks)
        
        assert metrics is not None
        assert metrics.total_feedback_count == 2
        assert metrics.grouping_accuracy == 0.5  # 1/2
        assert metrics.average_usefulness == 3.5  # (5+2)/2
        assert metrics.average_alerts_per_incident == 2.0  # (2+2)/2
    
    def test_stage3_metrics_false_positive_rate(self):
        """Test Stage 3 false positive rate (should be separate)."""
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=["A001", "A002"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=i),
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=False,
                    should_be_separate_incidents=(i < 3),  # 3 out of 5 should be separate
                    correlation_usefulness=3
                ),
                overall_quality=3
            )
            for i in range(5)
        ]
        
        metrics = self.calculator.calculate_stage3_metrics(feedbacks)
        
        assert metrics.false_positive_rate == 0.6  # 3/5
    
    def test_stage3_metrics_false_negative_rate(self):
        """Test Stage 3 false negative rate (missing alerts)."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=False,
                    should_include_additional_alerts=["A002", "A003"],  # Missing 2 alerts
                    correlation_usefulness=2
                ),
                overall_quality=2
            ),
            FeedbackRecord(
                feedback_id="FB002",
                incident_id="INC002",
                alert_ids=["A004"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=1),
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=True,
                    should_include_additional_alerts=[],  # No missing alerts
                    correlation_usefulness=5
                ),
                overall_quality=5
            )
        ]
        
        metrics = self.calculator.calculate_stage3_metrics(feedbacks)
        
        assert metrics.false_negative_rate == 0.5  # 1/2
    
    def test_stage3_metrics_empty_feedback(self):
        """Test Stage 3 metrics with no correlation feedback."""
        feedbacks = []
        
        metrics = self.calculator.calculate_stage3_metrics(feedbacks)
        
        assert metrics is None
    
    def test_stage4_metrics_rca_correctness(self):
        """Test Stage 4 RCA correctness calculation."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=True,
                    rca_helpful=True,
                    evidence_sufficient=True,
                    evidence_relevant=True,
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=5,
                    stakeholder_communication_quality=5,
                    rca_usefulness=5
                ),
                overall_quality=5
            ),
            FeedbackRecord(
                feedback_id="FB002",
                incident_id="INC002",
                alert_ids=["A002"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=1),
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=False,
                    rca_helpful=False,
                    evidence_sufficient=False,
                    evidence_relevant=False,
                    recommendations_helpful=False,
                    recommendations_actionable=False,
                    support_communication_quality=2,
                    stakeholder_communication_quality=2,
                    rca_usefulness=2
                ),
                overall_quality=2
            )
        ]
        
        metrics = self.calculator.calculate_stage4_metrics(feedbacks)
        
        assert metrics is not None
        assert metrics.total_feedback_count == 2
        assert metrics.rca_correctness_rate == 0.5  # 1/2
        assert metrics.rca_helpfulness_rate == 0.5  # 1/2
        assert metrics.evidence_sufficiency_rate == 0.5  # 1/2
        assert metrics.evidence_relevance_rate == 0.5  # 1/2
        assert metrics.recommendations_helpful_rate == 0.5  # 1/2
        assert metrics.recommendations_actionable_rate == 0.5  # 1/2
        assert metrics.average_support_communication_quality == 3.5  # (5+2)/2
        assert metrics.average_stakeholder_communication_quality == 3.5  # (5+2)/2
        assert metrics.average_rca_usefulness == 3.5  # (5+2)/2
    
    def test_stage4_metrics_most_missing_evidence(self):
        """Test identification of most missing evidence type."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=False,
                    rca_helpful=False,
                    evidence_sufficient=False,
                    evidence_relevant=True,
                    missing_evidence_types=["network_traces", "database_logs"],
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=3,
                    stakeholder_communication_quality=3,
                    rca_usefulness=3
                ),
                overall_quality=3
            ),
            FeedbackRecord(
                feedback_id="FB002",
                incident_id="INC002",
                alert_ids=["A002"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=1),
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=True,
                    rca_helpful=True,
                    evidence_sufficient=False,
                    evidence_relevant=True,
                    missing_evidence_types=["network_traces"],  # Most common
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=4,
                    stakeholder_communication_quality=4,
                    rca_usefulness=4
                ),
                overall_quality=4
            )
        ]
        
        metrics = self.calculator.calculate_stage4_metrics(feedbacks)
        
        assert metrics.most_missing_evidence_type == "network_traces"
    
    def test_stage4_metrics_no_missing_evidence(self):
        """Test Stage 4 metrics when no evidence is missing."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=True,
                    rca_helpful=True,
                    evidence_sufficient=True,
                    evidence_relevant=True,
                    missing_evidence_types=[],  # No missing evidence
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=5,
                    stakeholder_communication_quality=5,
                    rca_usefulness=5
                ),
                overall_quality=5
            )
        ]
        
        metrics = self.calculator.calculate_stage4_metrics(feedbacks)
        
        assert metrics.most_missing_evidence_type is None
    
    def test_stage4_metrics_empty_feedback(self):
        """Test Stage 4 metrics with no RCA feedback."""
        feedbacks = []
        
        metrics = self.calculator.calculate_stage4_metrics(feedbacks)
        
        assert metrics is None
    
    def test_system_metrics_calculation(self):
        """Test system-wide metrics calculation."""
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=7)
        
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=[f"A{i:03d}"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(days=i),
                stage=FeedbackStage.RCA,
                overall_quality=3 + (i % 3),  # Mix of 3, 4, 5
                estimated_time_saved_minutes=30 + (i * 10)
            )
            for i in range(5)
        ]
        
        metrics = self.calculator.calculate_system_metrics(feedbacks, start_date, end_date)
        
        assert metrics.total_feedback_count == 5
        assert metrics.date_range_start == start_date
        assert metrics.date_range_end == end_date
        assert metrics.average_overall_quality == 3.8  # (3+4+5+3+4)/5 = 19/5
        assert metrics.total_time_saved_minutes == 250  # 30+40+50+60+70
        assert metrics.average_time_saved_minutes == 50.0  # 250/5
    
    def test_system_metrics_quality_trend(self):
        """Test quality trend detection."""
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=10)
        
        # Improving trend: earlier feedbacks have lower quality
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=[f"A{i:03d}"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(days=i),
                stage=FeedbackStage.RCA,
                overall_quality=2 if i < 5 else 5  # Improving
            )
            for i in range(10)
        ]
        
        metrics = self.calculator.calculate_system_metrics(feedbacks, start_date, end_date)
        
        assert metrics.quality_improving is True
        assert metrics.quality_trend_direction == "improving"
    
    def test_system_metrics_declining_trend(self):
        """Test declining quality trend detection."""
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=10)
        
        # Declining trend: earlier feedbacks have higher quality
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=[f"A{i:03d}"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(days=i),
                stage=FeedbackStage.RCA,
                overall_quality=5 if i < 5 else 2  # Declining
            )
            for i in range(10)
        ]
        
        metrics = self.calculator.calculate_system_metrics(feedbacks, start_date, end_date)
        
        assert metrics.quality_improving is False
        assert metrics.quality_trend_direction == "declining"
    
    def test_system_metrics_empty_feedback(self):
        """Test system metrics with no feedback."""
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=7)
        
        metrics = self.calculator.calculate_system_metrics([], start_date, end_date)
        
        assert metrics.total_feedback_count == 0
        assert metrics.average_overall_quality == 0.0
        assert metrics.total_time_saved_minutes == 0
        assert metrics.average_time_saved_minutes == 0.0
        assert metrics.quality_trend_direction == "stable"
    
    def test_system_metrics_feedback_by_stage(self):
        """Test feedback rate calculation by stage."""
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=7)
        
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.CLASSIFICATION,
                overall_quality=4
            ),
            FeedbackRecord(
                feedback_id="FB002",
                incident_id="INC002",
                alert_ids=["A002"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(days=1),
                stage=FeedbackStage.CLASSIFICATION,
                overall_quality=4
            ),
            FeedbackRecord(
                feedback_id="FB003",
                incident_id="INC003",
                alert_ids=["A003"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(days=2),
                stage=FeedbackStage.RCA,
                overall_quality=5
            )
        ]
        
        metrics = self.calculator.calculate_system_metrics(feedbacks, start_date, end_date)
        
        assert metrics.feedback_rate_by_stage["classification"] == 2
        assert metrics.feedback_rate_by_stage["rca"] == 1
