"""
Complete Stage 5 Feedback Loop Demonstration.

Demonstrates: Feedback → Storage → Metrics → Failure Analysis → Improvement Suggestions → Dashboard
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

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


def create_demo_feedbacks():
    """
    Create demo feedback records.
    
    IMPORTANT: These are DEMO feedbacks for illustration only, not real production data.
    """
    base_date = datetime.now() - timedelta(days=7)
    
    return [
        # Demo Stage 2 feedbacks
        FeedbackRecord(
            feedback_id="DEMO-FB-S2-001",
            incident_id="DEMO-INC-001",
            alert_ids=["DEMO-ALERT-001"],
            engineer_id="DEMO-ENG-001",
            engineer_name="Demo Engineer Alice",
            timestamp=base_date,
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
            comments="DEMO: Priority prediction incorrect - marked as Medium but should be High"
        ),
        FeedbackRecord(
            feedback_id="DEMO-FB-S2-002",
            incident_id="DEMO-INC-002",
            alert_ids=["DEMO-ALERT-002"],
            engineer_id="DEMO-ENG-001",
            engineer_name="Demo Engineer Alice",
            timestamp=base_date + timedelta(hours=4),
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
            comments="DEMO: Another priority misprediction"
        ),
        # Demo Stage 3 feedbacks
        FeedbackRecord(
            feedback_id="DEMO-FB-S3-001",
            incident_id="DEMO-INC-003",
            alert_ids=["DEMO-ALERT-003", "DEMO-ALERT-004"],
            engineer_id="DEMO-ENG-002",
            engineer_name="Demo Engineer Bob",
            timestamp=base_date + timedelta(hours=8),
            stage=FeedbackStage.CORRELATION,
            correlation_feedback=CorrelationFeedback(
                grouping_correct=False,
                should_be_separate_incidents=True,  # False merge
                correlation_usefulness=2
            ),
            overall_quality=2,
            estimated_time_saved_minutes=15,
            comments="DEMO: These alerts are from different services and should not be grouped"
        ),
        FeedbackRecord(
            feedback_id="DEMO-FB-S3-002",
            incident_id="DEMO-INC-004",
            alert_ids=["DEMO-ALERT-005", "DEMO-ALERT-006"],
            engineer_id="DEMO-ENG-002",
            engineer_name="Demo Engineer Bob",
            timestamp=base_date + timedelta(hours=12),
            stage=FeedbackStage.CORRELATION,
            correlation_feedback=CorrelationFeedback(
                grouping_correct=False,
                should_be_separate_incidents=True,  # Another false merge
                correlation_usefulness=2
            ),
            overall_quality=2,
            estimated_time_saved_minutes=10,
            comments="DEMO: Similarity threshold too loose - unrelated alerts grouped"
        ),
        # Demo Stage 4 feedbacks
        FeedbackRecord(
            feedback_id="DEMO-FB-S4-001",
            incident_id="DEMO-INC-005",
            alert_ids=["DEMO-ALERT-007"],
            engineer_id="DEMO-ENG-003",
            engineer_name="Demo Engineer Charlie",
            timestamp=base_date + timedelta(hours=16),
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
            comments="DEMO: RCA incorrect - needed network traces to identify real cause"
        ),
        FeedbackRecord(
            feedback_id="DEMO-FB-S4-002",
            incident_id="DEMO-INC-006",
            alert_ids=["DEMO-ALERT-008"],
            engineer_id="DEMO-ENG-003",
            engineer_name="Demo Engineer Charlie",
            timestamp=base_date + timedelta(hours=20),
            stage=FeedbackStage.RCA,
            rca_feedback=RCAFeedback(
                rca_correct=True,  # RCA correct
                rca_helpful=True,
                evidence_sufficient=False,  # Still missing some evidence
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
            comments="DEMO: RCA correct but would be even better with network traces"
        )
    ]


def main():
    """Run complete feedback loop demonstration."""
    
    print("=" * 80)
    print("STAGE 5 COMPLETE FEEDBACK LOOP DEMONSTRATION")
    print("=" * 80)
    print()
    print("⚠️  IMPORTANT: This demo uses ILLUSTRATIVE feedback data")
    print("   These are NOT real production feedbacks or validated results")
    print()
    
    # Paths
    demo_db = project_root / "data" / "feedback_demo_complete.db"
    demo_dashboard = project_root / "dashboard_demo_complete.html"
    
    # Step 1: Create demo feedbacks
    print("[1/6] Creating demo feedback records...")
    feedbacks = create_demo_feedbacks()
    print(f"   Created {len(feedbacks)} demo feedbacks")
    print(f"     - Stage 2 (Classification): 2 feedbacks")
    print(f"     - Stage 3 (Correlation): 2 feedbacks")
    print(f"     - Stage 4 (RCA): 2 feedbacks")
    print()
    
    # Step 2: Save to storage
    print("[2/6] Saving to database...")
    store = FeedbackStore(str(demo_db))
    for feedback in feedbacks:
        store.save_feedback(feedback)
    print(f"   ✅ Saved to {demo_db}")
    print()
    
    # Step 3: Calculate metrics
    print("[3/6] Calculating performance metrics...")
    calculator = MetricsCalculator()
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()
    
    retrieved = store.get_feedback_in_date_range(start_date, end_date)
    
    system_metrics = calculator.calculate_system_metrics(retrieved, start_date, end_date)
    stage2_metrics = calculator.calculate_stage2_metrics(retrieved)
    stage3_metrics = calculator.calculate_stage3_metrics(retrieved)
    stage4_metrics = calculator.calculate_stage4_metrics(retrieved)
    
    print(f"   System Metrics:")
    print(f"     - Total feedback: {system_metrics.total_feedback_count}")
    print(f"     - Average quality: {system_metrics.average_overall_quality:.2f}/5")
    print(f"     - Time saved: {system_metrics.total_time_saved_minutes} minutes")
    print(f"     - Quality trend: {system_metrics.quality_trend_direction}")
    print()
    
    if stage2_metrics:
        print(f"   Stage 2 (Classification):")
        print(f"     - Priority accuracy: {stage2_metrics.priority_accuracy:.1%}")
        print(f"     - Most corrected: {stage2_metrics.most_corrected_field}")
    
    if stage3_metrics:
        print(f"   Stage 3 (Correlation):")
        print(f"     - Grouping accuracy: {stage3_metrics.grouping_accuracy:.1%}")
        print(f"     - False positive rate: {stage3_metrics.false_positive_rate:.1%}")
    
    if stage4_metrics:
        print(f"   Stage 4 (RCA):")
        print(f"     - Correctness rate: {stage4_metrics.rca_correctness_rate:.1%}")
        print(f"     - Most missing evidence: {stage4_metrics.most_missing_evidence_type}")
    print()
    
    # Step 4: Failure analysis
    print("[4/6] Analyzing failure patterns...")
    analyzer = FailureAnalyzer()
    analysis_results = analyzer.analyze_all(retrieved)
    
    print(f"   Patterns found: {analysis_results['patterns']['total']}")
    print(f"     - Stage 2 patterns: {len(analysis_results['patterns']['stage2'])}")
    print(f"     - Stage 3 patterns: {len(analysis_results['patterns']['stage3'])}")
    print(f"     - Stage 4 patterns: {len(analysis_results['patterns']['stage4'])}")
    print()
    
    # Show pattern details
    if analysis_results['patterns']['stage2']:
        print("   Stage 2 Failure Patterns:")
        for pattern in analysis_results['patterns']['stage2']:
            print(f"     • {pattern.description}")
            print(f"       Occurrences: {pattern.occurrence_count}")
    
    if analysis_results['patterns']['stage3']:
        print("   Stage 3 Failure Patterns:")
        for pattern in analysis_results['patterns']['stage3']:
            print(f"     • {pattern.description}")
            print(f"       Occurrences: {pattern.occurrence_count}")
    
    if analysis_results['patterns']['stage4']:
        print("   Stage 4 Failure Patterns:")
        for pattern in analysis_results['patterns']['stage4']:
            print(f"     • {pattern.description}")
            print(f"       Occurrences: {pattern.occurrence_count}")
    print()
    
    # Step 5: Improvement suggestions
    print("[5/6] Generating improvement suggestions...")
    suggestions = analysis_results['suggestions']
    print(f"   Suggestions: {len(suggestions)} total")
    print(f"     - High priority: {analysis_results['summary']['high_priority_suggestions']}")
    print(f"     - Medium priority: {analysis_results['summary']['medium_priority_suggestions']}")
    print()
    
    if suggestions:
        print("   Top Improvement Suggestions:")
        for i, suggestion in enumerate(suggestions[:3], 1):
            print(f"     {i}. [{suggestion.priority.upper()}] {suggestion.description}")
            print(f"        Stage: {suggestion.stage.value}")
            print(f"        Impact: {suggestion.estimated_impact}")
    print()
    
    # Step 6: Generate dashboard
    print("[6/6] Generating dashboard...")
    generator = DashboardGenerator()
    generator.generate_dashboard(retrieved, start_date, end_date, demo_dashboard)
    print(f"   ✅ Dashboard saved to: {demo_dashboard}")
    print()
    
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()
    print("✅ Complete Feedback Loop Demonstrated:")
    print("   1. ✅ Feedback collection (6 demo records)")
    print("   2. ✅ Storage in SQLite database")
    print("   3. ✅ Metrics calculation (system + stage-specific)")
    print("   4. ✅ Failure pattern detection")
    print("   5. ✅ Improvement suggestion generation")
    print("   6. ✅ Dashboard generation (HTML)")
    print()
    print("📂 Generated Files:")
    print(f"   - Database: {demo_db}")
    print(f"   - Dashboard: {demo_dashboard}")
    print()
    print("💡 Open dashboard: file://{demo_dashboard}")
    print()
    print("⚠️  REMINDER: All feedback in this demo is ILLUSTRATIVE")
    print("   Real production deployment requires actual human feedback")
    print()


if __name__ == '__main__':
    main()
