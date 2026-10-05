"""
Tests for Stage 5 Failure Analysis.

Verifies systematic failure pattern detection from feedback.
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
from alert_management.stage5_feedback.failure_analysis import (
    FailurePattern,
    FailureAnalyzer
)


class TestFailureAnalyzer:
    """Test failure analyzer."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.analyzer = FailureAnalyzer()
        self.base_date = datetime(2026, 9, 1, 12, 0, 0)
    
    def test_stage2_priority_pattern_detected(self):
        """Test detection of Priority misclassification pattern."""
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
                    alert_type_correct=True,
                    severity_correct=True,
                    business_impact_correct=True,
                    priority_correct=False,  # All priority incorrect
                    routing_correct=True,
                    classification_usefulness=3
                ),
                overall_quality=3
            )
            for i in range(5)
        ]
        
        patterns = self.analyzer.analyze_stage2_failures(feedbacks)
        
        priority_patterns = [p for p in patterns if "priority" in p.pattern_type.lower()]
        assert len(priority_patterns) > 0
        assert priority_patterns[0].occurrence_count == 5
        assert len(priority_patterns[0].affected_incidents) == 5
    
    def test_stage2_no_pattern_for_single_failure(self):
        """Test that single failures don't create patterns (need at least 2)."""
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
                    business_impact_correct=True,
                    priority_correct=False,  # Only 1 incorrect
                    routing_correct=True,
                    classification_usefulness=3
                ),
                overall_quality=3
            )
        ]
        
        patterns = self.analyzer.analyze_stage2_failures(feedbacks)
        
        # Should not create pattern for single occurrence
        assert len(patterns) == 0
    
    def test_stage3_false_merge_pattern_detected(self):
        """Test detection of false merge (false positive) pattern."""
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=[f"A{i*2:03d}", f"A{i*2+1:03d}"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=i),
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=False,
                    should_be_separate_incidents=True,  # False merge
                    correlation_usefulness=2
                ),
                overall_quality=2
            )
            for i in range(3)
        ]
        
        patterns = self.analyzer.analyze_stage3_failures(feedbacks)
        
        merge_patterns = [p for p in patterns if "false_positive" in p.pattern_type or "merge" in p.pattern_type]
        assert len(merge_patterns) > 0
        assert merge_patterns[0].occurrence_count == 3
    
    def test_stage3_missing_alerts_pattern_detected(self):
        """Test detection of missing alerts (false split) pattern."""
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=i),
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=False,
                    should_include_additional_alerts=[f"A{i+100:03d}"],  # Missing alerts
                    correlation_usefulness=2
                ),
                overall_quality=2
            )
            for i in range(4)
        ]
        
        patterns = self.analyzer.analyze_stage3_failures(feedbacks)
        
        split_patterns = [p for p in patterns if "false_negative" in p.pattern_type or "missing" in p.pattern_type]
        assert len(split_patterns) > 0
        assert split_patterns[0].occurrence_count == 4
    
    def test_stage4_rca_incorrect_pattern_detected(self):
        """Test detection of incorrect RCA pattern."""
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=[f"A{i:03d}"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=i),
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=False,  # RCA incorrect
                    rca_helpful=False,
                    evidence_sufficient=True,
                    evidence_relevant=True,
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=3,
                    stakeholder_communication_quality=3,
                    rca_usefulness=2
                ),
                overall_quality=2
            )
            for i in range(3)
        ]
        
        patterns = self.analyzer.analyze_stage4_failures(feedbacks)
        
        rca_patterns = [p for p in patterns if "incorrect_root_cause" in p.pattern_type]
        assert len(rca_patterns) > 0
        assert rca_patterns[0].occurrence_count == 3
    
    def test_stage4_evidence_insufficient_pattern_detected(self):
        """Test detection of insufficient evidence pattern with missing types."""
        feedbacks = [
            FeedbackRecord(
                feedback_id=f"FB{i:03d}",
                incident_id=f"INC{i:03d}",
                alert_ids=[f"A{i:03d}"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=i),
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=True,
                    rca_helpful=True,
                    evidence_sufficient=False,  # Evidence insufficient
                    evidence_relevant=True,
                    missing_evidence_types=["network_traces", "database_logs"],
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=4,
                    stakeholder_communication_quality=4,
                    rca_usefulness=3
                ),
                overall_quality=3
            )
            for i in range(5)
        ]
        
        patterns = self.analyzer.analyze_stage4_failures(feedbacks)
        
        evidence_patterns = [p for p in patterns if "insufficient_evidence" in p.pattern_type]
        assert len(evidence_patterns) > 0
        assert evidence_patterns[0].occurrence_count == 5
        assert "network_traces" in evidence_patterns[0].description
    
    def test_improvement_suggestions_generated(self):
        """Test generation of improvement suggestions from patterns."""
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
                    alert_type_correct=True,
                    severity_correct=True,
                    business_impact_correct=True,
                    priority_correct=False,  # Priority incorrect
                    routing_correct=True,
                    classification_usefulness=3
                ),
                overall_quality=3
            )
            for i in range(10)
        ]
        
        patterns = self.analyzer.analyze_stage2_failures(feedbacks)
        suggestions = self.analyzer.generate_improvement_suggestions(patterns)
        
        assert len(suggestions) > 0
        priority_suggestions = [s for s in suggestions if "priority" in s.description.lower()]
        assert len(priority_suggestions) > 0
        assert priority_suggestions[0].stage == FeedbackStage.CLASSIFICATION
        assert priority_suggestions[0].priority in ["high", "medium", "low"]
    
    def test_analyze_all_comprehensive(self):
        """Test comprehensive analysis across all stages."""
        feedbacks = [
            # Stage 2 feedback
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
                    business_impact_correct=True,
                    priority_correct=False,
                    routing_correct=True,
                    classification_usefulness=3
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
                stage=FeedbackStage.CLASSIFICATION,
                classification_feedback=ClassificationFeedback(
                    alert_type_correct=True,
                    severity_correct=True,
                    business_impact_correct=True,
                    priority_correct=False,
                    routing_correct=True,
                    classification_usefulness=3
                ),
                overall_quality=3
            ),
            # Stage 4 feedback
            FeedbackRecord(
                feedback_id="FB003",
                incident_id="INC003",
                alert_ids=["A003"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=2),
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=False,
                    rca_helpful=False,
                    evidence_sufficient=False,
                    evidence_relevant=True,
                    missing_evidence_types=["network_traces"],
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=3,
                    stakeholder_communication_quality=3,
                    rca_usefulness=2
                ),
                overall_quality=2
            ),
            FeedbackRecord(
                feedback_id="FB004",
                incident_id="INC004",
                alert_ids=["A004"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date + timedelta(hours=3),
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=False,
                    rca_helpful=False,
                    evidence_sufficient=False,
                    evidence_relevant=True,
                    missing_evidence_types=["network_traces"],
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=3,
                    stakeholder_communication_quality=3,
                    rca_usefulness=2
                ),
                overall_quality=2
            )
        ]
        
        results = self.analyzer.analyze_all(feedbacks)
        
        assert "patterns" in results
        assert "suggestions" in results
        assert "confidence_analysis" in results
        assert "summary" in results
        
        # Should have patterns from Stage 2 and Stage 4
        assert results["patterns"]["total"] > 0
        assert len(results["patterns"]["stage2"]) > 0
        assert len(results["patterns"]["stage4"]) > 0
        
        # Should have improvement suggestions
        assert len(results["suggestions"]) > 0
        
        # Summary should be accurate
        assert results["summary"]["total_patterns_found"] == results["patterns"]["total"]
    
    def test_no_patterns_with_all_correct_feedback(self):
        """Test that no patterns are identified when all feedback is positive."""
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
                    alert_type_correct=True,
                    severity_correct=True,
                    business_impact_correct=True,
                    priority_correct=True,  # All correct
                    routing_correct=True,
                    classification_usefulness=5
                ),
                overall_quality=5
            )
            for i in range(10)
        ]
        
        patterns = self.analyzer.analyze_stage2_failures(feedbacks)
        
        assert len(patterns) == 0
    
    def test_failure_pattern_validation(self):
        """Test FailurePattern validation."""
        with pytest.raises(ValueError, match="Occurrence count must be positive"):
            FailurePattern(
                pattern_id="test",
                stage=FeedbackStage.CLASSIFICATION,
                pattern_type="test",
                description="test",
                occurrence_count=0,  # Invalid
                affected_incidents=["INC001"],
                supporting_feedback_ids=["FB001"],
                suggested_improvement="test"
            )
        
        with pytest.raises(ValueError, match="Must have at least one affected incident"):
            FailurePattern(
                pattern_id="test",
                stage=FeedbackStage.CLASSIFICATION,
                pattern_type="test",
                description="test",
                occurrence_count=1,
                affected_incidents=[],  # Invalid
                supporting_feedback_ids=["FB001"],
                suggested_improvement="test"
            )
