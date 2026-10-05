"""
Stage 5 Feedback Loop Demo.

Demonstrates complete feedback collection, storage, metrics, and dashboard generation.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import uuid

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_management.stage5_feedback import (
    FeedbackRecord,
    ClassificationFeedback,
    CorrelationFeedback,
    RCAFeedback,
    FeedbackStage
)
from alert_management.stage5_feedback.storage import FeedbackStore
from alert_management.stage5_feedback.metrics import MetricsCalculator
from alert_management.stage5_feedback.dashboard import DashboardGenerator


def create_sample_feedbacks() -> list:
    """Create sample feedback records."""
    feedbacks = []
    base_time = datetime.now() - timedelta(days=7)
    
    # Sample 1: Perfect RCA
    feedbacks.append(FeedbackRecord(
        feedback_id=f"FEEDBACK-{uuid.uuid4().hex[:8].upper()}",
        incident_id="INCIDENT-EA-001",
        alert_ids=["INC3528891", "INC3528892"],
        engineer_id="ENG001",
        engineer_name="Alice Johnson",
        timestamp=base_time,
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
            support_communication_quality=5,
            stakeholder_communication_quality=5,
            rca_usefulness=5
        ),
        overall_quality=5,
        estimated_time_saved_minutes=60,
        comments="Excellent analysis, saved significant time"
    ))
    
    # Sample 2: Good RCA but missing evidence
    feedbacks.append(FeedbackRecord(
        feedback_id=f"FEEDBACK-{uuid.uuid4().hex[:8].upper()}",
        incident_id="INCIDENT-PH-002",
        alert_ids=["INC001"],
        engineer_id="ENG002",
        engineer_name="Bob Smith",
        timestamp=base_time + timedelta(days=1),
        stage=FeedbackStage.RCA,
        rca_feedback=RCAFeedback(
            rca_correct=True,
            rca_helpful=True,
            evidence_sufficient=False,
            evidence_relevant=True,
            missing_evidence_types=["network_traces"],
            recommendations_helpful=True,
            recommendations_actionable=True,
            support_communication_quality=4,
            stakeholder_communication_quality=4,
            rca_usefulness=4
        ),
        overall_quality=4,
        estimated_time_saved_minutes=45,
        comments="Good RCA but would benefit from network traces"
    ))
    
    # Sample 3: Incorrect classification
    feedbacks.append(FeedbackRecord(
        feedback_id=f"FEEDBACK-{uuid.uuid4().hex[:8].upper()}",
        incident_id="INCIDENT-BS-003",
        alert_ids=["INC002", "INC003"],
        engineer_id="ENG003",
        engineer_name="Carol Davis",
        timestamp=base_time + timedelta(days=2),
        stage=FeedbackStage.CLASSIFICATION,
        classification_feedback=ClassificationFeedback(
            alert_type_correct=False,
            alert_type_actual="BATCH",
            severity_correct=True,
            business_impact_correct=False,
            business_impact_actual="LOW",
            priority_correct=True,
            routing_correct=True,
            classification_usefulness=3,
            notes="Misclassified BATCH alert as DATABASE alert"
        ),
        overall_quality=3,
        estimated_time_saved_minutes=20
    ))
    
    # Sample 4: Incorrect grouping
    feedbacks.append(FeedbackRecord(
        feedback_id=f"FEEDBACK-{uuid.uuid4().hex[:8].upper()}",
        incident_id="INCIDENT-MIX-004",
        alert_ids=["INC004", "INC005", "INC006"],
        engineer_id="ENG001",
        engineer_name="Alice Johnson",
        timestamp=base_time + timedelta(days=3),
        stage=FeedbackStage.CORRELATION,
        correlation_feedback=CorrelationFeedback(
            grouping_correct=False,
            should_be_separate_incidents=True,
            should_exclude_alerts=["INC006"],
            correlation_usefulness=2,
            notes="INC006 is unrelated, should be separate incident"
        ),
        overall_quality=2,
        estimated_time_saved_minutes=10
    ))
    
    # Sample 5: Good end-to-end
    feedbacks.append(FeedbackRecord(
        feedback_id=f"FEEDBACK-{uuid.uuid4().hex[:8].upper()}",
        incident_id="INCIDENT-EA-005",
        alert_ids=["INC007"],
        engineer_id="ENG002",
        engineer_name="Bob Smith",
        timestamp=base_time + timedelta(days=4),
        stage=FeedbackStage.END_TO_END,
        classification_feedback=ClassificationFeedback(
            alert_type_correct=True,
            severity_correct=True,
            business_impact_correct=True,
            priority_correct=False,
            priority_actual="3 - Medium",
            routing_correct=True,
            classification_usefulness=4
        ),
        correlation_feedback=CorrelationFeedback(
            grouping_correct=True,
            correlation_usefulness=4
        ),
        rca_feedback=RCAFeedback(
            rca_correct=True,
            rca_helpful=True,
            evidence_sufficient=True,
            evidence_relevant=True,
            missing_evidence_types=[],
            recommendations_helpful=True,
            recommendations_actionable=True,
            support_communication_quality=4,
            stakeholder_communication_quality=5,
            rca_usefulness=4
        ),
        overall_quality=4,
        estimated_time_saved_minutes=50,
        comments="Very helpful, minor priority adjustment needed"
    ))
    
    return feedbacks


def main():
    """Run feedback loop demo."""
    print("=" * 80)
    print("STAGE 5 FEEDBACK LOOP DEMO")
    print("=" * 80)
    print()
    
    # Create sample feedbacks
    print("📝 Creating sample feedback records...")
    feedbacks = create_sample_feedbacks()
    print(f"   Created {len(feedbacks)} sample feedbacks")
    print()
    
    # Save to database
    print("💾 Saving to database...")
    db_path = "data/feedback_demo.db"
    store = FeedbackStore(db_path)
    
    for feedback in feedbacks:
        store.save_feedback(feedback)
    print(f"   Saved to {db_path}")
    print()
    
    # Calculate metrics
    print("📊 Calculating metrics...")
    calculator = MetricsCalculator()
    
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()
    
    system_metrics = calculator.calculate_system_metrics(feedbacks, start_date, end_date)
    stage2_metrics = calculator.calculate_stage2_metrics(feedbacks)
    stage3_metrics = calculator.calculate_stage3_metrics(feedbacks)
    stage4_metrics = calculator.calculate_stage4_metrics(feedbacks)
    
    print("   System Metrics:")
    print(f"     - Total feedback: {system_metrics.total_feedback_count}")
    print(f"     - Average quality: {system_metrics.average_overall_quality:.2f}/5")
    print(f"     - Time saved: {system_metrics.total_time_saved_minutes} minutes")
    print(f"     - Quality trend: {system_metrics.quality_trend_direction}")
    print()
    
    if stage2_metrics:
        print("   Stage 2 (Classification):")
        print(f"     - Overall accuracy: {stage2_metrics.overall_accuracy:.1%}")
        print(f"     - Most corrected: {stage2_metrics.most_corrected_field}")
        print()
    
    if stage3_metrics:
        print("   Stage 3 (Correlation):")
        print(f"     - Grouping accuracy: {stage3_metrics.grouping_accuracy:.1%}")
        print(f"     - False positive rate: {stage3_metrics.false_positive_rate:.1%}")
        print()
    
    if stage4_metrics:
        print("   Stage 4 (RCA):")
        print(f"     - Correctness rate: {stage4_metrics.rca_correctness_rate:.1%}")
        print(f"     - Helpfulness rate: {stage4_metrics.rca_helpfulness_rate:.1%}")
        if stage4_metrics.most_missing_evidence_type:
            print(f"     - Most missing evidence: {stage4_metrics.most_missing_evidence_type}")
        print()
    
    # Generate dashboard
    print("🎨 Generating dashboard...")
    generator = DashboardGenerator()
    output_path = Path("dashboard_demo.html")
    
    generator.generate_dashboard(feedbacks, start_date, end_date, output_path)
    print(f"   Dashboard saved to: {output_path.absolute()}")
    print()
    
    # Summary
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()
    print("✅ Feedback Loop Components Demonstrated:")
    print("   1. ✅ Feedback collection (5 sample records)")
    print("   2. ✅ Storage in SQLite database")
    print("   3. ✅ Metrics calculation (system + stage-specific)")
    print("   4. ✅ Dashboard generation (HTML)")
    print()
    print("📂 Generated Files:")
    print(f"   - Database: {db_path}")
    print(f"   - Dashboard: {output_path.absolute()}")
    print()
    print(f"💡 Open dashboard: file://{output_path.absolute()}")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
