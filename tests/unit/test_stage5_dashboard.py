"""
Tests for Stage 5 Dashboard Generator.

Verifies HTML dashboard generation from metrics.
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
from alert_management.stage5_feedback.dashboard import DashboardGenerator


class TestDashboardGenerator:
    """Test dashboard generator."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.generator = DashboardGenerator()
        self.base_date = datetime(2026, 9, 1, 12, 0, 0)
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def test_generate_dashboard_success(self):
        """Test dashboard generation succeeds."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.RCA,
                overall_quality=4,
                estimated_time_saved_minutes=30
            )
        ]
        
        output_file = self.temp_dir / "dashboard.html"
        start_date = self.base_date - timedelta(days=7)
        end_date = self.base_date
        
        # Should not raise
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        assert output_file.exists()
        assert output_file.stat().st_size > 0
    
    def test_generated_html_file_created(self):
        """Test HTML file is created."""
        feedbacks = []
        output_file = self.temp_dir / "test_dashboard.html"
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=1)
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        assert output_file.exists()
        assert output_file.is_file()
    
    def test_dashboard_contains_summary_metrics(self):
        """Test dashboard contains system summary metrics."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.RCA,
                overall_quality=5,
                estimated_time_saved_minutes=45
            )
        ]
        
        output_file = self.temp_dir / "summary_test.html"
        start_date = self.base_date - timedelta(days=7)
        end_date = self.base_date
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        content = output_file.read_text()
        
        # Check for key summary elements
        assert "Total Feedback" in content
        assert "Average Quality" in content
        assert "Time Saved" in content
        assert "1" in content  # Total feedback count
        assert "5" in content or "5.0" in content  # Quality score
        assert "45" in content  # Time saved
    
    def test_dashboard_stage2_metrics_appear(self):
        """Test Stage 2 metrics section appears when data available."""
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
                    priority_correct=True,
                    routing_correct=True,
                    classification_usefulness=4
                ),
                overall_quality=4
            )
        ]
        
        output_file = self.temp_dir / "stage2_test.html"
        start_date = self.base_date - timedelta(days=7)
        end_date = self.base_date
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        content = output_file.read_text()
        
        assert "Stage 2: Classification" in content
        assert "Overall Accuracy" in content
        assert "Alert Type" in content
        assert "Severity" in content
        assert "Priority" in content
        assert "Routing" in content
    
    def test_dashboard_stage3_metrics_appear(self):
        """Test Stage 3 metrics section appears when data available."""
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
            )
        ]
        
        output_file = self.temp_dir / "stage3_test.html"
        start_date = self.base_date - timedelta(days=7)
        end_date = self.base_date
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        content = output_file.read_text()
        
        assert "Stage 3: Correlation" in content
        assert "Grouping Accuracy" in content
        assert "False Positive Rate" in content
        assert "False Negative Rate" in content
    
    def test_dashboard_stage4_metrics_appear(self):
        """Test Stage 4 metrics section appears when data available."""
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
            )
        ]
        
        output_file = self.temp_dir / "stage4_test.html"
        start_date = self.base_date - timedelta(days=7)
        end_date = self.base_date
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        content = output_file.read_text()
        
        assert "Stage 4: Root Cause Analysis" in content
        assert "RCA Correctness" in content
        assert "RCA Helpfulness" in content
        assert "Evidence Sufficiency" in content
        assert "Recommendations" in content
    
    def test_dashboard_empty_dataset_no_crash(self):
        """Test dashboard generation with empty feedback does not crash."""
        feedbacks = []
        output_file = self.temp_dir / "empty_test.html"
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=1)
        
        # Should not raise
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        assert output_file.exists()
        
        content = output_file.read_text()
        assert "0" in content  # Total feedback should be 0
    
    def test_dashboard_no_unsupported_performance_claims(self):
        """Test dashboard does not claim unsupported performance."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.RCA,
                overall_quality=3
            )
        ]
        
        output_file = self.temp_dir / "claims_test.html"
        start_date = self.base_date - timedelta(days=7)
        end_date = self.base_date
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        content = output_file.read_text()
        
        # Should NOT contain unsupported claims
        assert "production ready" not in content.lower()
        assert "calibrated" not in content.lower()
        assert "proven" not in content.lower()
    
    def test_dashboard_html_structure_valid(self):
        """Test generated HTML has valid structure."""
        feedbacks = [
            FeedbackRecord(
                feedback_id="FB001",
                incident_id="INC001",
                alert_ids=["A001"],
                engineer_id="ENG001",
                engineer_name="Test Engineer",
                timestamp=self.base_date,
                stage=FeedbackStage.RCA,
                overall_quality=4
            )
        ]
        
        output_file = self.temp_dir / "structure_test.html"
        start_date = self.base_date
        end_date = self.base_date + timedelta(days=1)
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        content = output_file.read_text()
        
        # Check basic HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "<head>" in content
        assert "</head>" in content
        assert "<body>" in content
        assert "</body>" in content
        assert "<title>" in content
    
    def test_dashboard_date_range_displayed(self):
        """Test dashboard displays reporting date range."""
        feedbacks = []
        output_file = self.temp_dir / "dates_test.html"
        start_date = datetime(2026, 9, 1)
        end_date = datetime(2026, 9, 30)
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        content = output_file.read_text()
        
        assert "2026-09-01" in content
        assert "2026-09-30" in content
        assert "Reporting Period" in content
    
    def test_dashboard_multiple_stages(self):
        """Test dashboard with feedback from multiple stages."""
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
            )
        ]
        
        output_file = self.temp_dir / "multi_stage_test.html"
        start_date = self.base_date - timedelta(days=7)
        end_date = self.base_date + timedelta(days=1)
        
        self.generator.generate_dashboard(feedbacks, start_date, end_date, output_file)
        
        content = output_file.read_text()
        
        # Should have both Stage 2 and Stage 4 sections
        assert "Stage 2: Classification" in content
        assert "Stage 4: Root Cause Analysis" in content
