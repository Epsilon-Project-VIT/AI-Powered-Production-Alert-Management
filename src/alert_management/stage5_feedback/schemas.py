"""
Stage 5 Feedback Schemas.

Data models for collecting and storing feedback from support engineers.
"""

from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class FeedbackStage(str, Enum):
    """Stage being evaluated."""
    CLASSIFICATION = "classification"
    CORRELATION = "correlation"
    RCA = "rca"
    END_TO_END = "end_to_end"


class ClassificationFeedback(BaseModel):
    """Feedback on Stage 2 classifications."""
    
    # Correctness of each classification
    alert_type_correct: bool = Field(..., description="Whether alert type prediction was correct")
    alert_type_actual: Optional[str] = Field(None, description="Actual alert type if incorrect")
    
    severity_correct: bool = Field(..., description="Whether severity prediction was correct")
    severity_actual: Optional[str] = Field(None, description="Actual severity if incorrect")
    
    business_impact_correct: bool = Field(..., description="Whether business impact was correct")
    business_impact_actual: Optional[str] = Field(None, description="Actual business impact if incorrect")
    
    priority_correct: bool = Field(..., description="Whether priority was correct")
    priority_actual: Optional[str] = Field(None, description="Actual priority if incorrect")
    
    routing_correct: bool = Field(..., description="Whether routing was correct")
    routing_actual: Optional[str] = Field(None, description="Actual routing if incorrect")
    
    # Usefulness ratings (1-5)
    classification_usefulness: int = Field(..., ge=1, le=5, description="How useful was the classification (1-5)")
    
    # Additional context
    notes: Optional[str] = Field(None, description="Additional notes about classification quality")


class CorrelationFeedback(BaseModel):
    """Feedback on Stage 3 incident grouping."""
    
    # Was correlation correct?
    grouping_correct: bool = Field(..., description="Whether incident grouping was correct")
    
    # If incorrect, what should have happened?
    should_be_separate_incidents: bool = Field(
        False,
        description="Should the grouped alerts be separate incidents?"
    )
    should_include_additional_alerts: List[str] = Field(
        default_factory=list,
        description="Alert IDs that should have been included but weren't"
    )
    should_exclude_alerts: List[str] = Field(
        default_factory=list,
        description="Alert IDs that shouldn't have been grouped"
    )
    
    # Usefulness
    correlation_usefulness: int = Field(..., ge=1, le=5, description="How useful was the correlation (1-5)")
    
    # Additional context
    notes: Optional[str] = Field(None, description="Additional notes about correlation quality")


class RCAFeedback(BaseModel):
    """Feedback on Stage 4 RCA and recommendations."""
    
    # Root cause accuracy
    rca_correct: bool = Field(..., description="Whether the root cause analysis was correct")
    rca_helpful: bool = Field(..., description="Whether the RCA was helpful even if not 100% correct")
    actual_root_cause: Optional[str] = Field(
        None,
        description="Actual root cause if incorrect or incomplete"
    )
    
    # Evidence quality
    evidence_sufficient: bool = Field(..., description="Whether sufficient evidence was provided")
    evidence_relevant: bool = Field(..., description="Whether evidence was relevant")
    missing_evidence_types: List[str] = Field(
        default_factory=list,
        description="Types of evidence that were missing (e.g., 'logs', 'metrics', 'traces')"
    )
    
    # Recommendations
    recommendations_helpful: bool = Field(..., description="Whether recommendations were helpful")
    recommendations_actionable: bool = Field(..., description="Whether recommendations were actionable")
    
    # Communication quality
    support_communication_quality: int = Field(
        ...,
        ge=1,
        le=5,
        description="Quality of support team communication (1-5)"
    )
    stakeholder_communication_quality: int = Field(
        ...,
        ge=1,
        le=5,
        description="Quality of stakeholder communication (1-5)"
    )
    
    # Usefulness
    rca_usefulness: int = Field(..., ge=1, le=5, description="Overall RCA usefulness (1-5)")
    
    # Additional context
    notes: Optional[str] = Field(None, description="Additional notes about RCA quality")


class FeedbackRecord(BaseModel):
    """
    Complete feedback record from support engineer.
    
    Captures feedback on classification, correlation, and/or RCA quality.
    """
    
    # Identification
    feedback_id: str = Field(..., description="Unique feedback identifier")
    incident_id: str = Field(..., description="Incident this feedback relates to")
    alert_ids: List[str] = Field(..., description="Alert IDs involved in this incident")
    
    # Who provided feedback
    engineer_id: str = Field(..., description="Support engineer identifier")
    engineer_name: str = Field(..., description="Support engineer name")
    timestamp: datetime = Field(..., description="When feedback was provided")
    
    # What stage is being evaluated
    stage: FeedbackStage = Field(..., description="Primary stage being evaluated")
    
    # Stage-specific feedback (optional based on what's being evaluated)
    classification_feedback: Optional[ClassificationFeedback] = Field(
        None,
        description="Feedback on Stage 2 classification"
    )
    correlation_feedback: Optional[CorrelationFeedback] = Field(
        None,
        description="Feedback on Stage 3 correlation"
    )
    rca_feedback: Optional[RCAFeedback] = Field(
        None,
        description="Feedback on Stage 4 RCA"
    )
    
    # Overall quality
    overall_quality: int = Field(
        ...,
        ge=1,
        le=5,
        description="Overall quality rating (1-5 stars)"
    )
    comments: Optional[str] = Field(None, description="General comments about the incident handling")
    
    # Impact assessment
    estimated_time_saved_minutes: Optional[int] = Field(
        None,
        description="Estimated time saved by AI analysis (minutes)"
    )
    
    # Metadata
    system_version: Optional[str] = Field(None, description="Version of the system that generated the output")
    processing_time_seconds: Optional[float] = Field(
        None,
        description="How long the system took to process this incident"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "feedback_id": "FEEDBACK-001",
                "incident_id": "INCIDENT-EA-001",
                "alert_ids": ["INC3528891", "INC3528892"],
                "engineer_id": "ENG123",
                "engineer_name": "John Doe",
                "timestamp": "2026-08-06T15:30:00Z",
                "stage": "rca",
                "rca_feedback": {
                    "rca_correct": True,
                    "rca_helpful": True,
                    "evidence_sufficient": False,
                    "evidence_relevant": True,
                    "missing_evidence_types": ["network_traces"],
                    "recommendations_helpful": True,
                    "recommendations_actionable": True,
                    "support_communication_quality": 4,
                    "stakeholder_communication_quality": 5,
                    "rca_usefulness": 4,
                    "notes": "Good analysis but would benefit from network trace data"
                },
                "overall_quality": 4,
                "estimated_time_saved_minutes": 45,
                "comments": "Excellent work, saved significant triage time"
            }
        }


class FeedbackSummary(BaseModel):
    """Aggregated feedback summary statistics."""
    
    total_feedback_count: int = Field(..., description="Total number of feedback records")
    date_range_start: datetime = Field(..., description="Start of date range")
    date_range_end: datetime = Field(..., description="End of date range")
    
    # Overall metrics
    average_overall_quality: float = Field(..., description="Average overall quality rating")
    total_time_saved_minutes: int = Field(..., description="Total time saved across all incidents")
    average_time_saved_minutes: float = Field(..., description="Average time saved per incident")
    
    # Stage-specific metrics
    classification_feedback_count: int = Field(0, description="Count of classification feedback")
    correlation_feedback_count: int = Field(0, description="Count of correlation feedback")
    rca_feedback_count: int = Field(0, description="Count of RCA feedback")
    
    # Classification accuracy (if available)
    classification_accuracy: Optional[float] = Field(
        None,
        description="Overall classification accuracy (0-1)"
    )
    
    # Correlation accuracy (if available)
    correlation_accuracy: Optional[float] = Field(
        None,
        description="Correlation grouping accuracy (0-1)"
    )
    
    # RCA metrics (if available)
    rca_correctness_rate: Optional[float] = Field(
        None,
        description="RCA correctness rate (0-1)"
    )
    rca_helpfulness_rate: Optional[float] = Field(
        None,
        description="RCA helpfulness rate (0-1)"
    )
    average_rca_usefulness: Optional[float] = Field(
        None,
        description="Average RCA usefulness rating (1-5)"
    )
    
    # Communication quality
    average_support_communication_quality: Optional[float] = Field(
        None,
        description="Average support communication quality (1-5)"
    )
    average_stakeholder_communication_quality: Optional[float] = Field(
        None,
        description="Average stakeholder communication quality (1-5)"
    )


class FailurePattern(BaseModel):
    """Identified pattern in system failures."""
    
    pattern_id: str = Field(..., description="Unique pattern identifier")
    pattern_type: Literal["classification", "correlation", "rca"] = Field(
        ...,
        description="What type of failure"
    )
    description: str = Field(..., description="Human-readable description of the pattern")
    frequency: int = Field(..., description="How many times this pattern occurred")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="How impactful this pattern is"
    )
    
    # Example failures
    example_incident_ids: List[str] = Field(..., description="Example incidents showing this pattern")
    
    # Pattern details
    affected_clients: List[str] = Field(default_factory=list, description="Clients affected by this pattern")
    affected_alert_types: List[str] = Field(default_factory=list, description="Alert types affected")
    
    # Suggested fix
    suggested_improvement: Optional[str] = Field(
        None,
        description="Suggested improvement to address this pattern"
    )


class ImprovementSuggestion(BaseModel):
    """Suggested improvement based on feedback analysis."""
    
    suggestion_id: str = Field(..., description="Unique suggestion identifier")
    priority: Literal["low", "medium", "high", "critical"] = Field(..., description="Priority level")
    category: Literal["data", "model", "feature", "infrastructure"] = Field(
        ...,
        description="Category of improvement"
    )
    
    title: str = Field(..., description="Short title")
    description: str = Field(..., description="Detailed description")
    
    # Impact assessment
    estimated_impact: str = Field(..., description="Estimated impact if implemented")
    affected_stage: FeedbackStage = Field(..., description="Which stage this would improve")
    
    # Supporting data
    supporting_pattern_ids: List[str] = Field(
        default_factory=list,
        description="Failure patterns that support this suggestion"
    )
    estimated_effort: Literal["low", "medium", "high"] = Field(..., description="Estimated effort to implement")
