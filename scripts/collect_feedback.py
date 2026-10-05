"""
CLI Feedback Collection Tool.

Interactive command-line tool for collecting feedback from support engineers.
"""

import sys
from pathlib import Path
from datetime import datetime
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


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no answer."""
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{question} [{default_str}]: ").strip().lower()
        if not response:
            return default
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        print("Please answer 'y' or 'n'")


def prompt_rating(question: str, min_val: int = 1, max_val: int = 5) -> int:
    """Prompt for rating (1-5)."""
    while True:
        try:
            response = input(f"{question} ({min_val}-{max_val}): ").strip()
            rating = int(response)
            if min_val <= rating <= max_val:
                return rating
            print(f"Please enter a number between {min_val} and {max_val}")
        except ValueError:
            print(f"Please enter a valid number between {min_val} and {max_val}")


def prompt_optional_int(question: str) -> int:
    """Prompt for optional integer."""
    while True:
        response = input(f"{question} [press Enter to skip]: ").strip()
        if not response:
            return None
        try:
            return int(response)
        except ValueError:
            print("Please enter a valid number or press Enter to skip")


def prompt_list(question: str) -> list:
    """Prompt for comma-separated list."""
    response = input(f"{question} [comma-separated, or press Enter to skip]: ").strip()
    if not response:
        return []
    return [item.strip() for item in response.split(',') if item.strip()]


def collect_classification_feedback() -> ClassificationFeedback:
    """Collect Stage 2 classification feedback."""
    print("\n" + "=" * 80)
    print("STAGE 2: CLASSIFICATION FEEDBACK")
    print("=" * 80)
    
    # Alert type
    alert_type_correct = prompt_yes_no("Was the alert type classification correct?")
    alert_type_actual = None
    if not alert_type_correct:
        alert_type_actual = input("What should the alert type be?: ").strip()
    
    # Severity
    severity_correct = prompt_yes_no("Was the severity classification correct?")
    severity_actual = None
    if not severity_correct:
        severity_actual = input("What should the severity be?: ").strip()
    
    # Business impact
    business_impact_correct = prompt_yes_no("Was the business impact classification correct?")
    business_impact_actual = None
    if not business_impact_correct:
        business_impact_actual = input("What should the business impact be?: ").strip()
    
    # Priority
    priority_correct = prompt_yes_no("Was the priority classification correct?")
    priority_actual = None
    if not priority_correct:
        priority_actual = input("What should the priority be?: ").strip()
    
    # Routing
    routing_correct = prompt_yes_no("Was the routing classification correct?")
    routing_actual = None
    if not routing_correct:
        routing_actual = input("What should the routing be?: ").strip()
    
    # Usefulness
    usefulness = prompt_rating("How useful was the classification overall?")
    
    # Notes
    notes = input("Additional notes [press Enter to skip]: ").strip() or None
    
    return ClassificationFeedback(
        alert_type_correct=alert_type_correct,
        alert_type_actual=alert_type_actual,
        severity_correct=severity_correct,
        severity_actual=severity_actual,
        business_impact_correct=business_impact_correct,
        business_impact_actual=business_impact_actual,
        priority_correct=priority_correct,
        priority_actual=priority_actual,
        routing_correct=routing_correct,
        routing_actual=routing_actual,
        classification_usefulness=usefulness,
        notes=notes
    )


def collect_correlation_feedback() -> CorrelationFeedback:
    """Collect Stage 3 correlation feedback."""
    print("\n" + "=" * 80)
    print("STAGE 3: CORRELATION FEEDBACK")
    print("=" * 80)
    
    grouping_correct = prompt_yes_no("Were the alerts correctly grouped into an incident?")
    
    should_be_separate = False
    should_include = []
    should_exclude = []
    
    if not grouping_correct:
        should_be_separate = prompt_yes_no("Should the grouped alerts be separate incidents?")
        should_include = prompt_list("Alert IDs that should have been included")
        should_exclude = prompt_list("Alert IDs that should be excluded")
    
    usefulness = prompt_rating("How useful was the correlation?")
    notes = input("Additional notes [press Enter to skip]: ").strip() or None
    
    return CorrelationFeedback(
        grouping_correct=grouping_correct,
        should_be_separate_incidents=should_be_separate,
        should_include_additional_alerts=should_include,
        should_exclude_alerts=should_exclude,
        correlation_usefulness=usefulness,
        notes=notes
    )


def collect_rca_feedback() -> RCAFeedback:
    """Collect Stage 4 RCA feedback."""
    print("\n" + "=" * 80)
    print("STAGE 4: ROOT CAUSE ANALYSIS FEEDBACK")
    print("=" * 80)
    
    rca_correct = prompt_yes_no("Was the root cause analysis correct?")
    rca_helpful = prompt_yes_no("Was the RCA helpful (even if not 100% correct)?")
    
    actual_root_cause = None
    if not rca_correct:
        actual_root_cause = input("What was the actual root cause?: ").strip()
    
    evidence_sufficient = prompt_yes_no("Was sufficient evidence provided?")
    evidence_relevant = prompt_yes_no("Was the evidence relevant?")
    
    missing_evidence = []
    if not evidence_sufficient:
        print("\nWhat types of evidence were missing?")
        print("Examples: logs, metrics, traces, network_traces, database_metrics")
        missing_evidence = prompt_list("Missing evidence types")
    
    recommendations_helpful = prompt_yes_no("Were the recommendations helpful?")
    recommendations_actionable = prompt_yes_no("Were the recommendations actionable?")
    
    support_comm_quality = prompt_rating("Support communication quality?")
    stakeholder_comm_quality = prompt_rating("Stakeholder communication quality?")
    
    rca_usefulness = prompt_rating("Overall RCA usefulness?")
    notes = input("Additional notes [press Enter to skip]: ").strip() or None
    
    return RCAFeedback(
        rca_correct=rca_correct,
        rca_helpful=rca_helpful,
        actual_root_cause=actual_root_cause,
        evidence_sufficient=evidence_sufficient,
        evidence_relevant=evidence_relevant,
        missing_evidence_types=missing_evidence,
        recommendations_helpful=recommendations_helpful,
        recommendations_actionable=recommendations_actionable,
        support_communication_quality=support_comm_quality,
        stakeholder_communication_quality=stakeholder_comm_quality,
        rca_usefulness=rca_usefulness,
        notes=notes
    )


def main():
    """Main CLI entry point."""
    print("=" * 80)
    print("FEEDBACK COLLECTION TOOL")
    print("=" * 80)
    print()
    
    # Basic information
    incident_id = input("Incident ID: ").strip()
    if not incident_id:
        print("Error: Incident ID is required")
        return 1
    
    alert_ids_str = input("Alert IDs [comma-separated]: ").strip()
    alert_ids = [aid.strip() for aid in alert_ids_str.split(',') if aid.strip()]
    if not alert_ids:
        print("Error: At least one alert ID is required")
        return 1
    
    engineer_id = input("Your Engineer ID: ").strip()
    engineer_name = input("Your Name: ").strip()
    
    if not engineer_id or not engineer_name:
        print("Error: Engineer ID and name are required")
        return 1
    
    print("\nWhat stage would you like to provide feedback on?")
    print("1. Classification only (Stage 2)")
    print("2. Correlation only (Stage 3)")
    print("3. RCA only (Stage 4)")
    print("4. End-to-end (all stages)")
    
    stage_choice = input("Choice [1-4]: ").strip()
    
    classification_feedback = None
    correlation_feedback = None
    rca_feedback = None
    
    if stage_choice == "1":
        stage = FeedbackStage.CLASSIFICATION
        classification_feedback = collect_classification_feedback()
    elif stage_choice == "2":
        stage = FeedbackStage.CORRELATION
        correlation_feedback = collect_correlation_feedback()
    elif stage_choice == "3":
        stage = FeedbackStage.RCA
        rca_feedback = collect_rca_feedback()
    elif stage_choice == "4":
        stage = FeedbackStage.END_TO_END
        classification_feedback = collect_classification_feedback()
        correlation_feedback = collect_correlation_feedback()
        rca_feedback = collect_rca_feedback()
    else:
        print("Invalid choice")
        return 1
    
    # Overall feedback
    print("\n" + "=" * 80)
    print("OVERALL FEEDBACK")
    print("=" * 80)
    
    overall_quality = prompt_rating("Overall quality of the AI system's output?")
    time_saved = prompt_optional_int("Estimated time saved (minutes)")
    comments = input("General comments [press Enter to skip]: ").strip() or None
    
    # Create feedback record
    feedback_id = f"FEEDBACK-{uuid.uuid4().hex[:8].upper()}"
    
    feedback = FeedbackRecord(
        feedback_id=feedback_id,
        incident_id=incident_id,
        alert_ids=alert_ids,
        engineer_id=engineer_id,
        engineer_name=engineer_name,
        timestamp=datetime.now(),
        stage=stage,
        classification_feedback=classification_feedback,
        correlation_feedback=correlation_feedback,
        rca_feedback=rca_feedback,
        overall_quality=overall_quality,
        estimated_time_saved_minutes=time_saved,
        comments=comments
    )
    
    # Save to database
    print("\n" + "=" * 80)
    print("SAVING FEEDBACK")
    print("=" * 80)
    
    db_path = "data/feedback.db"
    store = FeedbackStore(db_path)
    
    try:
        store.save_feedback(feedback)
        print(f"✅ Feedback saved successfully!")
        print(f"   Feedback ID: {feedback_id}")
        print(f"   Database: {db_path}")
        print()
        print("Thank you for your feedback!")
        return 0
    except Exception as e:
        print(f"❌ Error saving feedback: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
