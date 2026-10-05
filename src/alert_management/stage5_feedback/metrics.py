"""
Performance Metrics Calculator.

Calculates stage-specific and system-wide metrics from feedback data.
"""

from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

from .schemas import FeedbackRecord, FeedbackStage


@dataclass
class Stage2Metrics:
    """Stage 2 classification metrics."""
    total_feedback_count: int
    
    # Per-field accuracy
    alert_type_accuracy: float
    severity_accuracy: float
    business_impact_accuracy: float
    priority_accuracy: float
    routing_accuracy: float
    
    # Overall accuracy (all fields correct)
    overall_accuracy: float
    
    # Usefulness
    average_usefulness: float
    
    # Most common corrections
    most_corrected_field: str
    correction_count: int


@dataclass
class Stage3Metrics:
    """Stage 3 correlation metrics."""
    total_feedback_count: int
    
    # Grouping accuracy
    grouping_accuracy: float
    
    # Error analysis
    false_positive_rate: float  # Should be separate
    false_negative_rate: float  # Missing alerts
    
    # Usefulness
    average_usefulness: float
    
    # Incident stats
    average_alerts_per_incident: float


@dataclass
class Stage4Metrics:
    """Stage 4 RCA metrics."""
    total_feedback_count: int
    
    # RCA quality
    rca_correctness_rate: float
    rca_helpfulness_rate: float
    
    # Evidence quality
    evidence_sufficiency_rate: float
    evidence_relevance_rate: float
    most_missing_evidence_type: Optional[str]
    
    # Recommendations
    recommendations_helpful_rate: float
    recommendations_actionable_rate: float
    
    # Communication
    average_support_communication_quality: float
    average_stakeholder_communication_quality: float
    
    # Usefulness
    average_rca_usefulness: float


@dataclass
class SystemMetrics:
    """System-wide metrics."""
    total_feedback_count: int
    date_range_start: datetime
    date_range_end: datetime
    
    # Quality
    average_overall_quality: float
    quality_distribution: Dict[int, int]  # Rating -> count
    
    # Time savings
    total_time_saved_minutes: int
    average_time_saved_minutes: float
    
    # Feedback coverage
    feedback_rate_by_stage: Dict[str, int]
    
    # Trends
    quality_improving: bool
    quality_trend_direction: str  # "improving", "stable", "declining"


class MetricsCalculator:
    """Calculate performance metrics from feedback data."""
    
    def calculate_stage2_metrics(
        self,
        feedbacks: List[FeedbackRecord]
    ) -> Optional[Stage2Metrics]:
        """
        Calculate Stage 2 classification metrics.
        
        Args:
            feedbacks: List of feedback records with classification feedback
        
        Returns:
            Stage2Metrics or None if no classification feedback
        """
        # Filter to classification feedback
        classification_feedbacks = [
            f for f in feedbacks
            if f.classification_feedback is not None
        ]
        
        if not classification_feedbacks:
            return None
        
        total = len(classification_feedbacks)
        
        # Calculate per-field accuracy
        alert_type_correct = sum(
            1 for f in classification_feedbacks
            if f.classification_feedback.alert_type_correct
        )
        severity_correct = sum(
            1 for f in classification_feedbacks
            if f.classification_feedback.severity_correct
        )
        business_impact_correct = sum(
            1 for f in classification_feedbacks
            if f.classification_feedback.business_impact_correct
        )
        priority_correct = sum(
            1 for f in classification_feedbacks
            if f.classification_feedback.priority_correct
        )
        routing_correct = sum(
            1 for f in classification_feedbacks
            if f.classification_feedback.routing_correct
        )
        
        # Overall accuracy (all fields correct)
        all_correct = sum(
            1 for f in classification_feedbacks
            if (f.classification_feedback.alert_type_correct and
                f.classification_feedback.severity_correct and
                f.classification_feedback.business_impact_correct and
                f.classification_feedback.priority_correct and
                f.classification_feedback.routing_correct)
        )
        
        # Average usefulness
        avg_usefulness = sum(
            f.classification_feedback.classification_usefulness
            for f in classification_feedbacks
        ) / total
        
        # Most corrected field
        corrections = {
            "alert_type": total - alert_type_correct,
            "severity": total - severity_correct,
            "business_impact": total - business_impact_correct,
            "priority": total - priority_correct,
            "routing": total - routing_correct
        }
        most_corrected = max(corrections.items(), key=lambda x: x[1])
        
        return Stage2Metrics(
            total_feedback_count=total,
            alert_type_accuracy=alert_type_correct / total,
            severity_accuracy=severity_correct / total,
            business_impact_accuracy=business_impact_correct / total,
            priority_accuracy=priority_correct / total,
            routing_accuracy=routing_correct / total,
            overall_accuracy=all_correct / total,
            average_usefulness=avg_usefulness,
            most_corrected_field=most_corrected[0],
            correction_count=most_corrected[1]
        )
    
    def calculate_stage3_metrics(
        self,
        feedbacks: List[FeedbackRecord]
    ) -> Optional[Stage3Metrics]:
        """
        Calculate Stage 3 correlation metrics.
        
        Args:
            feedbacks: List of feedback records with correlation feedback
        
        Returns:
            Stage3Metrics or None if no correlation feedback
        """
        # Filter to correlation feedback
        correlation_feedbacks = [
            f for f in feedbacks
            if f.correlation_feedback is not None
        ]
        
        if not correlation_feedbacks:
            return None
        
        total = len(correlation_feedbacks)
        
        # Grouping accuracy
        grouping_correct = sum(
            1 for f in correlation_feedbacks
            if f.correlation_feedback.grouping_correct
        )
        grouping_accuracy = grouping_correct / total
        
        # False positive rate (should be separate)
        false_positives = sum(
            1 for f in correlation_feedbacks
            if f.correlation_feedback.should_be_separate_incidents
        )
        false_positive_rate = false_positives / total
        
        # False negative rate (missing alerts)
        false_negatives = sum(
            1 for f in correlation_feedbacks
            if len(f.correlation_feedback.should_include_additional_alerts) > 0
        )
        false_negative_rate = false_negatives / total
        
        # Average usefulness
        avg_usefulness = sum(
            f.correlation_feedback.correlation_usefulness
            for f in correlation_feedbacks
        ) / total
        
        # Average alerts per incident
        avg_alerts = sum(len(f.alert_ids) for f in correlation_feedbacks) / total
        
        return Stage3Metrics(
            total_feedback_count=total,
            grouping_accuracy=grouping_accuracy,
            false_positive_rate=false_positive_rate,
            false_negative_rate=false_negative_rate,
            average_usefulness=avg_usefulness,
            average_alerts_per_incident=avg_alerts
        )
    
    def calculate_stage4_metrics(
        self,
        feedbacks: List[FeedbackRecord]
    ) -> Optional[Stage4Metrics]:
        """
        Calculate Stage 4 RCA metrics.
        
        Args:
            feedbacks: List of feedback records with RCA feedback
        
        Returns:
            Stage4Metrics or None if no RCA feedback
        """
        # Filter to RCA feedback
        rca_feedbacks = [
            f for f in feedbacks
            if f.rca_feedback is not None
        ]
        
        if not rca_feedbacks:
            return None
        
        total = len(rca_feedbacks)
        
        # RCA quality
        rca_correct = sum(1 for f in rca_feedbacks if f.rca_feedback.rca_correct)
        rca_helpful = sum(1 for f in rca_feedbacks if f.rca_feedback.rca_helpful)
        
        # Evidence quality
        evidence_sufficient = sum(1 for f in rca_feedbacks if f.rca_feedback.evidence_sufficient)
        evidence_relevant = sum(1 for f in rca_feedbacks if f.rca_feedback.evidence_relevant)
        
        # Most missing evidence type
        missing_evidence = {}
        for f in rca_feedbacks:
            for ev_type in f.rca_feedback.missing_evidence_types:
                missing_evidence[ev_type] = missing_evidence.get(ev_type, 0) + 1
        
        most_missing = max(missing_evidence.items(), key=lambda x: x[1])[0] if missing_evidence else None
        
        # Recommendations
        recommendations_helpful = sum(1 for f in rca_feedbacks if f.rca_feedback.recommendations_helpful)
        recommendations_actionable = sum(1 for f in rca_feedbacks if f.rca_feedback.recommendations_actionable)
        
        # Communication quality
        avg_support = sum(f.rca_feedback.support_communication_quality for f in rca_feedbacks) / total
        avg_stakeholder = sum(f.rca_feedback.stakeholder_communication_quality for f in rca_feedbacks) / total
        
        # Usefulness
        avg_usefulness = sum(f.rca_feedback.rca_usefulness for f in rca_feedbacks) / total
        
        return Stage4Metrics(
            total_feedback_count=total,
            rca_correctness_rate=rca_correct / total,
            rca_helpfulness_rate=rca_helpful / total,
            evidence_sufficiency_rate=evidence_sufficient / total,
            evidence_relevance_rate=evidence_relevant / total,
            most_missing_evidence_type=most_missing,
            recommendations_helpful_rate=recommendations_helpful / total,
            recommendations_actionable_rate=recommendations_actionable / total,
            average_support_communication_quality=avg_support,
            average_stakeholder_communication_quality=avg_stakeholder,
            average_rca_usefulness=avg_usefulness
        )
    
    def calculate_system_metrics(
        self,
        feedbacks: List[FeedbackRecord],
        start_date: datetime,
        end_date: datetime
    ) -> SystemMetrics:
        """
        Calculate system-wide metrics.
        
        Args:
            feedbacks: List of all feedback records
            start_date: Start of date range
            end_date: End of date range
        
        Returns:
            SystemMetrics
        """
        if not feedbacks:
            return SystemMetrics(
                total_feedback_count=0,
                date_range_start=start_date,
                date_range_end=end_date,
                average_overall_quality=0.0,
                quality_distribution={},
                total_time_saved_minutes=0,
                average_time_saved_minutes=0.0,
                feedback_rate_by_stage={},
                quality_improving=False,
                quality_trend_direction="stable"
            )
        
        total = len(feedbacks)
        
        # Quality metrics
        avg_quality = sum(f.overall_quality for f in feedbacks) / total
        
        quality_dist = {}
        for f in feedbacks:
            quality_dist[f.overall_quality] = quality_dist.get(f.overall_quality, 0) + 1
        
        # Time savings
        time_saved_values = [f.estimated_time_saved_minutes for f in feedbacks if f.estimated_time_saved_minutes]
        total_time_saved = sum(time_saved_values) if time_saved_values else 0
        avg_time_saved = total_time_saved / len(time_saved_values) if time_saved_values else 0.0
        
        # Feedback by stage
        stage_counts = {}
        for f in feedbacks:
            stage_counts[f.stage.value] = stage_counts.get(f.stage.value, 0) + 1
        
        # Quality trend
        # Sort by timestamp
        sorted_feedbacks = sorted(feedbacks, key=lambda f: f.timestamp)
        
        # Split into first half and second half
        mid = len(sorted_feedbacks) // 2
        first_half_quality = sum(f.overall_quality for f in sorted_feedbacks[:mid]) / mid if mid > 0 else 0
        second_half_quality = sum(f.overall_quality for f in sorted_feedbacks[mid:]) / (total - mid) if (total - mid) > 0 else 0
        
        quality_improving = second_half_quality > first_half_quality
        
        if second_half_quality > first_half_quality + 0.2:
            trend = "improving"
        elif second_half_quality < first_half_quality - 0.2:
            trend = "declining"
        else:
            trend = "stable"
        
        return SystemMetrics(
            total_feedback_count=total,
            date_range_start=start_date,
            date_range_end=end_date,
            average_overall_quality=avg_quality,
            quality_distribution=quality_dist,
            total_time_saved_minutes=total_time_saved,
            average_time_saved_minutes=avg_time_saved,
            feedback_rate_by_stage=stage_counts,
            quality_improving=quality_improving,
            quality_trend_direction=trend
        )
