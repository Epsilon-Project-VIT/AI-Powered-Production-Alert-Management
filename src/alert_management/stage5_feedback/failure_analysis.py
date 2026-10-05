"""
Failure Analysis.

Identifies systematic weaknesses from collected feedback to guide improvements.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from collections import Counter

from .schemas import FeedbackRecord, FeedbackStage


@dataclass
class FailurePattern:
    """
    Systematic failure pattern identified from feedback.
    
    Note: This represents observed feedback patterns, not validated ground truth.
    """
    pattern_id: str
    stage: FeedbackStage
    pattern_type: str  # e.g., "priority_misclassification", "false_merge", "missing_evidence"
    description: str
    occurrence_count: int
    affected_incidents: List[str]
    supporting_feedback_ids: List[str]
    suggested_improvement: str
    is_validated: bool = False  # Whether pattern confirmed by domain expert
    
    def __post_init__(self):
        """Validate pattern data."""
        if self.occurrence_count <= 0:
            raise ValueError("Occurrence count must be positive")
        if len(self.affected_incidents) == 0:
            raise ValueError("Must have at least one affected incident")


@dataclass
class ConfidenceBucket:
    """
    Observed confidence vs feedback correctness.
    
    Note: This is NOT calibrated confidence. This is observed behavior from feedback.
    """
    confidence_range: str  # e.g., "0.8-1.0"
    prediction_count: int
    correct_count: int
    observed_correctness_rate: float
    
    @property
    def confidence_midpoint(self) -> float:
        """Get midpoint of confidence range."""
        parts = self.confidence_range.split('-')
        return (float(parts[0]) + float(parts[1])) / 2


@dataclass
class ImprovementSuggestion:
    """Actionable improvement derived from observed patterns."""
    suggestion_id: str
    stage: FeedbackStage
    priority: str  # "high", "medium", "low"
    description: str
    supporting_patterns: List[str]  # pattern_ids
    estimated_impact: str  # "high", "medium", "low"
    implementation_notes: str


class FailureAnalyzer:
    """Analyze feedback to identify systematic failure patterns."""
    
    def analyze_stage2_failures(
        self,
        feedbacks: List[FeedbackRecord]
    ) -> List[FailurePattern]:
        """
        Analyze Stage 2 classification failures.
        
        Detects patterns such as:
        - Priority incorrectly predicted
        - Routing incorrectly predicted
        - Repeated confusion between specific classes
        
        Args:
            feedbacks: List of feedback records with classification feedback
        
        Returns:
            List of identified failure patterns
        """
        patterns = []
        
        # Filter to classification feedback
        classification_feedbacks = [
            f for f in feedbacks
            if f.classification_feedback is not None
        ]
        
        if not classification_feedbacks:
            return patterns
        
        # Pattern: Priority incorrect
        priority_incorrect = [
            f for f in classification_feedbacks
            if not f.classification_feedback.priority_correct
        ]
        
        if len(priority_incorrect) >= 2:  # At least 2 occurrences to be a pattern
            patterns.append(FailurePattern(
                pattern_id="stage2_priority_incorrect",
                stage=FeedbackStage.CLASSIFICATION,
                pattern_type="priority_misclassification",
                description=f"Priority incorrectly predicted in {len(priority_incorrect)} cases",
                occurrence_count=len(priority_incorrect),
                affected_incidents=[f.incident_id for f in priority_incorrect],
                supporting_feedback_ids=[f.feedback_id for f in priority_incorrect],
                suggested_improvement="Review Priority model training data and features. "
                                    "Consider collecting additional high-priority examples.",
                is_validated=False
            ))
        
        # Pattern: Routing incorrect
        routing_incorrect = [
            f for f in classification_feedbacks
            if not f.classification_feedback.routing_correct
        ]
        
        if len(routing_incorrect) >= 2:
            patterns.append(FailurePattern(
                pattern_id="stage2_routing_incorrect",
                stage=FeedbackStage.CLASSIFICATION,
                pattern_type="routing_misclassification",
                description=f"Routing incorrectly predicted in {len(routing_incorrect)} cases",
                occurrence_count=len(routing_incorrect),
                affected_incidents=[f.incident_id for f in routing_incorrect],
                supporting_feedback_ids=[f.feedback_id for f in routing_incorrect],
                suggested_improvement="Review routing assignments for affected incidents. "
                                    "Check if new team structures require model retraining.",
                is_validated=False
            ))
        
        # Pattern: Alert Type incorrect
        alert_type_incorrect = [
            f for f in classification_feedbacks
            if not f.classification_feedback.alert_type_correct
        ]
        
        if len(alert_type_incorrect) >= 2:
            patterns.append(FailurePattern(
                pattern_id="stage2_alert_type_incorrect",
                stage=FeedbackStage.CLASSIFICATION,
                pattern_type="alert_type_misclassification",
                description=f"Alert Type incorrectly predicted in {len(alert_type_incorrect)} cases",
                occurrence_count=len(alert_type_incorrect),
                affected_incidents=[f.incident_id for f in alert_type_incorrect],
                supporting_feedback_ids=[f.feedback_id for f in alert_type_incorrect],
                suggested_improvement="Review Alert Type predictions. Note: No ground truth labels "
                                    "in training data - consider manual labeling effort.",
                is_validated=False
            ))
        
        return patterns
    
    def analyze_stage3_failures(
        self,
        feedbacks: List[FeedbackRecord]
    ) -> List[FailurePattern]:
        """
        Analyze Stage 3 correlation failures.
        
        Detects patterns such as:
        - False merges (alerts grouped together incorrectly)
        - False splits (related alerts not grouped)
        - Missing alerts from incidents
        
        Args:
            feedbacks: List of feedback records with correlation feedback
        
        Returns:
            List of identified failure patterns
        """
        patterns = []
        
        # Filter to correlation feedback
        correlation_feedbacks = [
            f for f in feedbacks
            if f.correlation_feedback is not None
        ]
        
        if not correlation_feedbacks:
            return patterns
        
        # Pattern: False merges (should be separate)
        false_merges = [
            f for f in correlation_feedbacks
            if f.correlation_feedback.should_be_separate_incidents
        ]
        
        if len(false_merges) >= 2:
            patterns.append(FailurePattern(
                pattern_id="stage3_false_merge",
                stage=FeedbackStage.CORRELATION,
                pattern_type="false_positive_grouping",
                description=f"Alerts incorrectly grouped together in {len(false_merges)} cases",
                occurrence_count=len(false_merges),
                affected_incidents=[f.incident_id for f in false_merges],
                supporting_feedback_ids=[f.feedback_id for f in false_merges],
                suggested_improvement="Review correlation thresholds (cosine distance < 0.3). "
                                    "Consider tightening semantic similarity threshold or "
                                    "strengthening temporal validation.",
                is_validated=False
            ))
        
        # Pattern: Missing alerts (false splits)
        false_splits = [
            f for f in correlation_feedbacks
            if len(f.correlation_feedback.should_include_additional_alerts) > 0
        ]
        
        if len(false_splits) >= 2:
            total_missing = sum(
                len(f.correlation_feedback.should_include_additional_alerts)
                for f in false_splits
            )
            
            patterns.append(FailurePattern(
                pattern_id="stage3_missing_alerts",
                stage=FeedbackStage.CORRELATION,
                pattern_type="false_negative_grouping",
                description=f"Missing alerts in {len(false_splits)} incidents ({total_missing} alerts total)",
                occurrence_count=len(false_splits),
                affected_incidents=[f.incident_id for f in false_splits],
                supporting_feedback_ids=[f.feedback_id for f in false_splits],
                suggested_improvement="Review correlation recall. Consider loosening similarity "
                                    "threshold or expanding temporal window for related alerts.",
                is_validated=False
            ))
        
        return patterns
    
    def analyze_stage4_failures(
        self,
        feedbacks: List[FeedbackRecord]
    ) -> List[FailurePattern]:
        """
        Analyze Stage 4 RCA failures.
        
        Detects patterns such as:
        - RCA incorrect or unhelpful
        - Evidence insufficient or irrelevant
        - Missing telemetry types
        - Poor recommendations
        
        Args:
            feedbacks: List of feedback records with RCA feedback
        
        Returns:
            List of identified failure patterns
        """
        patterns = []
        
        # Filter to RCA feedback
        rca_feedbacks = [
            f for f in feedbacks
            if f.rca_feedback is not None
        ]
        
        if not rca_feedbacks:
            return patterns
        
        # Pattern: RCA incorrect
        rca_incorrect = [
            f for f in rca_feedbacks
            if not f.rca_feedback.rca_correct
        ]
        
        if len(rca_incorrect) >= 2:
            patterns.append(FailurePattern(
                pattern_id="stage4_rca_incorrect",
                stage=FeedbackStage.RCA,
                pattern_type="incorrect_root_cause",
                description=f"RCA incorrect in {len(rca_incorrect)} cases",
                occurrence_count=len(rca_incorrect),
                affected_incidents=[f.incident_id for f in rca_incorrect],
                supporting_feedback_ids=[f.feedback_id for f in rca_incorrect],
                suggested_improvement="Review RCA reasoning logic. Consider integrating LLM for "
                                    "improved causal analysis. Collect validated RCAs for training.",
                is_validated=False
            ))
        
        # Pattern: Evidence insufficient
        evidence_insufficient = [
            f for f in rca_feedbacks
            if not f.rca_feedback.evidence_sufficient
        ]
        
        if len(evidence_insufficient) >= 2:
            # Find most commonly missing evidence types
            missing_evidence_types = []
            for f in evidence_insufficient:
                missing_evidence_types.extend(f.rca_feedback.missing_evidence_types)
            
            most_common = Counter(missing_evidence_types).most_common(3)
            
            patterns.append(FailurePattern(
                pattern_id="stage4_evidence_insufficient",
                stage=FeedbackStage.RCA,
                pattern_type="insufficient_evidence",
                description=f"Evidence insufficient in {len(evidence_insufficient)} cases. "
                          f"Most missing: {', '.join(t for t, _ in most_common)}",
                occurrence_count=len(evidence_insufficient),
                affected_incidents=[f.incident_id for f in evidence_insufficient],
                supporting_feedback_ids=[f.feedback_id for f in evidence_insufficient],
                suggested_improvement=f"Integrate additional telemetry sources. Priority: "
                                    f"{', '.join(f'{t} ({c} requests)' for t, c in most_common)}",
                is_validated=False
            ))
        
        # Pattern: Recommendations not helpful
        recommendations_unhelpful = [
            f for f in rca_feedbacks
            if not f.rca_feedback.recommendations_helpful
        ]
        
        if len(recommendations_unhelpful) >= 2:
            patterns.append(FailurePattern(
                pattern_id="stage4_recommendations_unhelpful",
                stage=FeedbackStage.RCA,
                pattern_type="poor_recommendations",
                description=f"Recommendations not helpful in {len(recommendations_unhelpful)} cases",
                occurrence_count=len(recommendations_unhelpful),
                affected_incidents=[f.incident_id for f in recommendations_unhelpful],
                supporting_feedback_ids=[f.feedback_id for f in recommendations_unhelpful],
                suggested_improvement="Review recommendation generation logic. Consider incorporating "
                                    "runbooks and historical incident resolutions.",
                is_validated=False
            ))
        
        return patterns
    
    def analyze_confidence_vs_feedback(
        self,
        feedbacks: List[FeedbackRecord],
        confidence_field: str = "priority"  # Which field to analyze
    ) -> List[ConfidenceBucket]:
        """
        Analyze observed confidence vs feedback correctness.
        
        Note: This is NOT calibrated confidence. This analyzes the relationship
        between model confidence and human feedback to identify miscalibration.
        
        Args:
            feedbacks: List of feedback records
            confidence_field: Which classification field to analyze
        
        Returns:
            List of confidence buckets with observed correctness rates
        """
        # Filter to classification feedback
        classification_feedbacks = [
            f for f in feedbacks
            if f.classification_feedback is not None
        ]
        
        if not classification_feedbacks:
            return []
        
        # Note: Current implementation doesn't have confidence scores available
        # This is a placeholder for when confidence tracking is added
        
        # Define buckets
        buckets = [
            ("0.0-0.2", 0.0, 0.2),
            ("0.2-0.4", 0.2, 0.4),
            ("0.4-0.6", 0.4, 0.6),
            ("0.6-0.8", 0.6, 0.8),
            ("0.8-1.0", 0.8, 1.0)
        ]
        
        # TODO: Implement once confidence scores are tracked in feedback
        # For now, return empty list
        return []
    
    def generate_improvement_suggestions(
        self,
        patterns: List[FailurePattern]
    ) -> List[ImprovementSuggestion]:
        """
        Generate actionable improvement suggestions from identified patterns.
        
        Args:
            patterns: List of identified failure patterns
        
        Returns:
            List of improvement suggestions prioritized by impact
        """
        suggestions = []
        
        # Group patterns by stage
        stage2_patterns = [p for p in patterns if p.stage == FeedbackStage.CLASSIFICATION]
        stage3_patterns = [p for p in patterns if p.stage == FeedbackStage.CORRELATION]
        stage4_patterns = [p for p in patterns if p.stage == FeedbackStage.RCA]
        
        # Stage 2 suggestions
        if stage2_patterns:
            priority_patterns = [p for p in stage2_patterns if "priority" in p.pattern_type.lower()]
            if priority_patterns:
                total_occurrences = sum(p.occurrence_count for p in priority_patterns)
                suggestions.append(ImprovementSuggestion(
                    suggestion_id="improve_priority_model",
                    stage=FeedbackStage.CLASSIFICATION,
                    priority="high" if total_occurrences > 5 else "medium",
                    description="Improve Priority classification model",
                    supporting_patterns=[p.pattern_id for p in priority_patterns],
                    estimated_impact="high" if total_occurrences > 5 else "medium",
                    implementation_notes=f"Priority model has {total_occurrences} observed errors. "
                                        "Current audit shows 53.73% test accuracy. Consider: "
                                        "(1) Collect Alert Type, Severity, Business Impact labels "
                                        "(2) Feature engineering with temporal patterns "
                                        "(3) Address class imbalance (3-Medium dominates)"
                ))
        
        # Stage 3 suggestions
        if stage3_patterns:
            merge_patterns = [p for p in stage3_patterns if "false_positive" in p.pattern_type or "merge" in p.pattern_type]
            if merge_patterns:
                total_occurrences = sum(p.occurrence_count for p in merge_patterns)
                suggestions.append(ImprovementSuggestion(
                    suggestion_id="reduce_false_merges",
                    stage=FeedbackStage.CORRELATION,
                    priority="medium",
                    description="Reduce false positive groupings",
                    supporting_patterns=[p.pattern_id for p in merge_patterns],
                    estimated_impact="medium",
                    implementation_notes=f"Observed {total_occurrences} false merge cases. "
                                        "Review temporal threshold (currently 10 minutes) and "
                                        "semantic similarity threshold (currently cosine < 0.3). "
                                        "Consider tightening thresholds or adding contextual validation."
                ))
            
            split_patterns = [p for p in stage3_patterns if "false_negative" in p.pattern_type or "missing" in p.pattern_type]
            if split_patterns:
                total_occurrences = sum(p.occurrence_count for p in split_patterns)
                suggestions.append(ImprovementSuggestion(
                    suggestion_id="reduce_missing_alerts",
                    stage=FeedbackStage.CORRELATION,
                    priority="medium",
                    description="Reduce missing alert groupings",
                    supporting_patterns=[p.pattern_id for p in split_patterns],
                    estimated_impact="medium",
                    implementation_notes=f"Observed {total_occurrences} incidents with missing alerts. "
                                        "Consider loosening similarity threshold or expanding "
                                        "temporal window for related alerts."
                ))
        
        # Stage 4 suggestions
        if stage4_patterns:
            evidence_patterns = [p for p in stage4_patterns if "evidence" in p.pattern_type.lower()]
            if evidence_patterns:
                total_occurrences = sum(p.occurrence_count for p in evidence_patterns)
                suggestions.append(ImprovementSuggestion(
                    suggestion_id="improve_evidence_collection",
                    stage=FeedbackStage.RCA,
                    priority="high",
                    description="Integrate additional telemetry sources",
                    supporting_patterns=[p.pattern_id for p in evidence_patterns],
                    estimated_impact="high",
                    implementation_notes=f"Evidence insufficient in {total_occurrences} cases. "
                                        "Current implementation uses mock telemetry. "
                                        "Priority integrations: Splunk (logs), Datadog (metrics), "
                                        "Jaeger (traces). Review feedback for most-requested types."
                ))
            
            rca_patterns = [p for p in stage4_patterns if "rca" in p.pattern_type.lower() or "root_cause" in p.pattern_type]
            if rca_patterns:
                total_occurrences = sum(p.occurrence_count for p in rca_patterns)
                suggestions.append(ImprovementSuggestion(
                    suggestion_id="improve_rca_reasoning",
                    stage=FeedbackStage.RCA,
                    priority="high",
                    description="Improve RCA reasoning quality",
                    supporting_patterns=[p.pattern_id for p in rca_patterns],
                    estimated_impact="high",
                    implementation_notes=f"RCA incorrect in {total_occurrences} cases. "
                                        "Current implementation uses rule-based reasoning. "
                                        "Consider: (1) Integrate LLM (OpenAI/Claude) "
                                        "(2) Collect validated RCAs for fine-tuning "
                                        "(3) Implement similarity search for historical incidents"
                ))
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order[s.priority])
        
        return suggestions
    
    def analyze_all(
        self,
        feedbacks: List[FeedbackRecord]
    ) -> Dict:
        """
        Perform complete failure analysis across all stages.
        
        Args:
            feedbacks: List of all feedback records
        
        Returns:
            Dict containing all analysis results
        """
        # Analyze each stage
        stage2_patterns = self.analyze_stage2_failures(feedbacks)
        stage3_patterns = self.analyze_stage3_failures(feedbacks)
        stage4_patterns = self.analyze_stage4_failures(feedbacks)
        
        # Combine all patterns
        all_patterns = stage2_patterns + stage3_patterns + stage4_patterns
        
        # Generate improvement suggestions
        suggestions = self.generate_improvement_suggestions(all_patterns)
        
        # Confidence analysis (placeholder for when confidence tracking added)
        confidence_buckets = self.analyze_confidence_vs_feedback(feedbacks)
        
        return {
            "patterns": {
                "stage2": stage2_patterns,
                "stage3": stage3_patterns,
                "stage4": stage4_patterns,
                "total": len(all_patterns)
            },
            "suggestions": suggestions,
            "confidence_analysis": confidence_buckets,
            "summary": {
                "total_patterns_found": len(all_patterns),
                "high_priority_suggestions": len([s for s in suggestions if s.priority == "high"]),
                "medium_priority_suggestions": len([s for s in suggestions if s.priority == "medium"]),
                "low_priority_suggestions": len([s for s in suggestions if s.priority == "low"])
            }
        }
