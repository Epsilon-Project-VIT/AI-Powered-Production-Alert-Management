"""
Integration test for complete Stage 5 feedback loop.

Tests the end-to-end flow: feedback → storage → metrics → failure analysis → suggestions
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from alert_management.stage5_feedback.schemas import (
    FeedbackRecord,
    ClassificationFeedback,
    CorrelationFeedback,
    RCAFeedback,
    FeedbackStage
)
from alert_management.stage5_feedback.storage import FeedbackStore
from alert_management.stage5_feedback.metrics import MetricsCalculator
from alert_management.stage5_feedback.failure_analysis import FailureAnalyzer
from alert_management.stage5_feedback.dashboard import DashboardGenerator


class TestStage5FeedbackLoopIntegration:
    """Integration test for complete feedback loop."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test_feedback.db"
        self.base_date = datetime(2026, 9, 1, 12, 0, 0)
    
    def create_demo_feedbacks(self) -> list:
        """
        Create demo feedback records for testing.
        
        Note: These are DEMO/TEST feedbacks, not real production data.
        """
        return [
            # Demo Classification feedback
            FeedbackRecord(
                feedback_id="DEMO-FB-001",
                incident_id="DEMO-INC-001",
                alert_ids=["DEMO-A001"],
                engineer_id="TEST-ENG001",
                engineer_name="Demo Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.CLASSIFICATION,
                classification_feedback=ClassificationFeedback(
                    alert_type_correct=True,
                    severity_correct=True,
                    business_impact_correct=False,  # Incorrect
                    priority_correct=False,  # Incorrect
                    routing_correct=True,
                    classification_usefulness=3
                ),
                overall_quality=3,
                estimated_time_saved_minutes=20,
                comments="Demo feedback - not real production data"
            ),
            FeedbackRecord(
                feedback_id="DEMO-FB-002",
                incident_id="DEMO-INC-002",
                alert_ids=["DEMO-A002"],
                engineer_id="TEST-ENG001",
                engineer_name="Demo Engineer",
                timestamp=self.base_date + timedelta(hours=2),
                stage=FeedbackStage.CLASSIFICATION,
                classification_feedback=ClassificationFeedback(
                    alert_type_correct=True,
                    severity_correct=True,
                    business_impact_correct=True,
                    priority_correct=False,  # Incorrect
                    routing_correct=True,
                    classification_usefulness=3
                ),
                overall_quality=3,
                estimated_time_saved_minutes=25,
                comments="Demo feedback - not real production data"
            ),
            # Demo Correlation feedback
            FeedbackRecord(
                feedback_id="DEMO-FB-003",
                incident_id="DEMO-INC-003",
                alert_ids=["DEMO-A003", "DEMO-A004"],
                engineer_id="TEST-ENG001",
                engineer_name="Demo Engineer",
                timestamp=self.base_date + timedelta(hours=4),
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=False,
                    should_be_separate_incidents=True,  # False merge
                    correlation_usefulness=2
                ),
                overall_quality=2,
                estimated_time_saved_minutes=15,
                comments="Demo feedback - not real production data"
            ),
            FeedbackRecord(
                feedback_id="DEMO-FB-004",
                incident_id="DEMO-INC-004",
                alert_ids=["DEMO-A005", "DEMO-A006"],
                engineer_id="TEST-ENG001",
                engineer_name="Demo Engineer",
                timestamp=self.base_date + timedelta(hours=6),
                stage=FeedbackStage.CORRELATION,
                correlation_feedback=CorrelationFeedback(
                    grouping_correct=False,
                    should_be_separate_incidents=True,  # Another false merge
                    correlation_usefulness=3
                ),
                overall_quality=3,
                estimated_time_saved_minutes=10,
                comments="Demo feedback - not real production data"
            ),
            # Demo RCA feedback
            FeedbackRecord(
                feedback_id="DEMO-FB-005",
                incident_id="DEMO-INC-005",
                alert_ids=["DEMO-A007"],
                engineer_id="TEST-ENG001",
                engineer_name="Demo Engineer",
                timestamp=self.base_date + timedelta(hours=8),
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=False,  # RCA incorrect
                    rca_helpful=False,
                    evidence_sufficient=False,  # Evidence insufficient
                    evidence_relevant=True,
                    missing_evidence_types=["network_traces", "database_logs"],
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=3,
                    stakeholder_communication_quality=3,
                    rca_usefulness=2
                ),
                overall_quality=2,
                estimated_time_saved_minutes=30,
                comments="Demo feedback - not real production data"
            ),
            FeedbackRecord(
                feedback_id="DEMO-FB-006",
                incident_id="DEMO-INC-006",
                alert_ids=["DEMO-A008"],
                engineer_id="TEST-ENG001",
                engineer_name="Demo Engineer",
                timestamp=self.base_date + timedelta(hours=10),
                stage=FeedbackStage.RCA,
                rca_feedback=RCAFeedback(
                    rca_correct=True,
                    rca_helpful=True,
                    evidence_sufficient=False,  # Evidence insufficient
                    evidence_relevant=True,
                    missing_evidence_types=["network_traces"],
                    recommendations_helpful=True,
                    recommendations_actionable=True,
                    support_communication_quality=5,
                    stakeholder_communication_quality=5,
                    rca_usefulness=5
                ),
                overall_quality=5,
                estimated_time_saved_minutes=45,
                comments="Demo feedback - not real production data"
            )
        ]
    
    def test_complete_feedback_loop(self):
        """Test complete feedback loop: storage → metrics → analysis → suggestions."""
        # Step 1: Create demo feedbacks
        feedbacks = self.create_demo_feedbacks()
        assert len(feedbacks) == 6
        
        # Step 2: Save to storage
        store = FeedbackStore(str(self.db_path))
        for feedback in feedbacks:
            store.save_feedback(feedback)
        
        # Verify storage
        start_date = self.base_date - timedelta(days=1)
        end_date = self.base_date + timedelta(days=1)
        retrieved = store.get_feedback_in_date_range(start_date, end_date)
        assert len(retrieved) == 6
        
        # Step 3: Calculate metrics
        calculator = MetricsCalculator()
        
        system_metrics = calculator.calculate_system_metrics(retrieved, start_date, end_date)
        assert system_metrics.total_feedback_count == 6
        assert system_metrics.total_time_saved_minutes == 145  # Sum of all time saved
        
        stage2_metrics = calculator.calculate_stage2_metrics(retrieved)
        assert stage2_metrics is not None
        assert stage2_metrics.total_feedback_count == 2
        assert stage2_metrics.priority_accuracy == 0.0  # Both incorrect
        
        stage3_metrics = calculator.calculate_stage3_metrics(retrieved)
        assert stage3_metrics is not None
        assert stage3_metrics.total_feedback_count == 2
        assert stage3_metrics.grouping_accuracy == 0.0  # Both incorrect
        
        stage4_metrics = calculator.calculate_stage4_metrics(retrieved)
        assert stage4_metrics is not None
        assert stage4_metrics.total_feedback_count == 2
        assert stage4_metrics.rca_correctness_rate == 0.5  # 1/2 correct
        assert stage4_metrics.evidence_sufficiency_rate == 0.0  # Both insufficient
        assert stage4_metrics.most_missing_evidence_type == "network_traces"
        
        # Step 4: Failure analysis
        analyzer = FailureAnalyzer()
        analysis_results = analyzer.analyze_all(retrieved)
        
        assert analysis_results["patterns"]["total"] > 0
        assert len(analysis_results["patterns"]["stage2"]) > 0
        assert len(analysis_results["patterns"]["stage3"]) > 0
        assert len(analysis_results["patterns"]["stage4"]) > 0
        
        # Step 5: Improvement suggestions
        suggestions = analysis_results["suggestions"]
        assert len(suggestions) > 0
        
        # Should have suggestions for priority model and RCA improvements
        priority_suggestions = [s for s in suggestions if "priority" in s.description.lower()]
        rca_suggestions = [s for s in suggestions if "rca" in s.description.lower() or "telemetry" in s.description.lower() or "evidence" in s.description.lower()]
        
        assert len(priority_suggestions) > 0
        assert len(rca_suggestions) > 0
        
        # Step 6: Dashboard generation
        dashboard_file = self.temp_dir / "integration_dashboard.html"
        generator = DashboardGenerator()
        generator.generate_dashboard(retrieved, start_date, end_date, dashboard_file)
        
        assert dashboard_file.exists()
        content = dashboard_file.read_text()
        assert "6" in content  # Total feedback count
        assert "145" in content  # Total time saved
    
    def test_feedback_loop_with_empty_data(self):
        """Test feedback loop handles empty data gracefully."""
        # Empty feedback list
        feedbacks = []
        
        # Storage
        store = FeedbackStore(str(self.db_path))
        
        # Metrics
        calculator = MetricsCalculator()
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=1)
        
        system_metrics = calculator.calculate_system_metrics(feedbacks, start_date, end_date)
        assert system_metrics.total_feedback_count == 0
        
        stage2_metrics = calculator.calculate_stage2_metrics(feedbacks)
        assert stage2_metrics is None
        
        # Failure analysis
        analyzer = FailureAnalyzer()
        analysis_results = analyzer.analyze_all(feedbacks)
        assert analysis_results["patterns"]["total"] == 0
        assert len(analysis_results["suggestions"]) == 0
        
        # Dashboard
        dashboard_file = self.temp_dir / "empty_dashboard.html"
        generator = DashboardGenerator()
        generator.generate_dashboard(feedbacks, start_date, end_date, dashboard_file)
        
        assert dashboard_file.exists()
    
    def test_feedback_persistence_and_retrieval(self):
        """Test feedback persists correctly and can be retrieved."""
        feedbacks = self.create_demo_feedbacks()
        
        # Save
        store = FeedbackStore(str(self.db_path))
        for feedback in feedbacks:
            store.save_feedback(feedback)
        
        # Retrieve by incident
        inc001_feedback = store.get_feedback_by_incident("DEMO-INC-001")
        assert len(inc001_feedback) == 1
        assert inc001_feedback[0].feedback_id == "DEMO-FB-001"
        
        # Retrieve by stage
        start_date = self.base_date - timedelta(days=1)
        end_date = self.base_date + timedelta(days=1)
        
        classification_feedback = store.get_feedback_in_date_range(
            start_date, end_date, stage="classification"
        )
        assert len(classification_feedback) == 2
        
        rca_feedback = store.get_feedback_in_date_range(
            start_date, end_date, stage="rca"
        )
        assert len(rca_feedback) == 2
    
    def test_demo_feedback_marked_as_demo(self):
        """Test that demo feedback is clearly marked in comments."""
        feedbacks = self.create_demo_feedbacks()
        
        for feedback in feedbacks:
            assert "Demo" in feedback.feedback_id or "DEMO" in feedback.feedback_id
            assert "Demo" in feedback.incident_id or "DEMO" in feedback.incident_id
            assert feedback.comments is not None
            assert "demo" in feedback.comments.lower() or "test" in feedback.comments.lower()
    
    def test_improvement_suggestions_are_actionable(self):
        """Test that improvement suggestions contain actionable information."""
        feedbacks = self.create_demo_feedbacks()
        
        analyzer = FailureAnalyzer()
        analysis_results = analyzer.analyze_all(feedbacks)
        
        for suggestion in analysis_results["suggestions"]:
            # Must have required fields
            assert suggestion.suggestion_id
            assert suggestion.stage
            assert suggestion.priority in ["high", "medium", "low"]
            assert suggestion.description
            assert len(suggestion.supporting_patterns) > 0
            assert suggestion.estimated_impact in ["high", "medium", "low"]
            assert suggestion.implementation_notes
            
            # Implementation notes should be actionable
            assert len(suggestion.implementation_notes) > 50  # Substantial notes
