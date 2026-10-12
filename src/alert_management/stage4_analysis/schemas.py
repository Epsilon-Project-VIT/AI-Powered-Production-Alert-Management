"""
Pydantic schemas for Stage 4: Incident Analysis & RCA.

All schemas include provenance tracking to distinguish mock from real data.
"""

from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class DiagnosisStatus(str, Enum):
    """Status of RCA diagnosis."""
    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AMBIGUOUS = "ambiguous"


class SourceType(str, Enum):
    """Type of evidence source."""
    MOCK = "mock"
    REAL = "real"
    MODEL_PREDICTION = "model_prediction"  # Stage 2 predictions, not real telemetry
    HISTORICAL_ALERT = "historical_alert"  # Historical alert/ticket data


class ActionType(str, Enum):
    """Type of recommended action."""
    DIAGNOSTIC = "diagnostic"
    REMEDIATION = "remediation"
    ESCALATION = "escalation"


class IncidentContext(BaseModel):
    """
    Normalized incident context from Stage 3 IncidentGroup.
    
    Contains all information needed to perform RCA on a candidate incident.
    """
    incident_id: str = Field(
        ...,
        description="Incident identifier from Stage 3"
    )
    
    client: str = Field(
        ...,
        description="Impacted client name"
    )
    
    alert_ids: List[str] = Field(
        ...,
        description="List of alert IDs in this candidate incident group",
        min_length=1
    )
    
    primary_alert_id: str = Field(
        ...,
        description="Primary/representative alert ID"
    )
    
    incident_start: datetime = Field(
        ...,
        description="First alert timestamp"
    )
    
    incident_end: Optional[datetime] = Field(
        default=None,
        description="Last alert timestamp (if multiple alerts)"
    )
    
    alert_count: int = Field(
        ...,
        ge=1,
        description="Number of alerts in candidate group"
    )
    
    services: List[str] = Field(
        default_factory=list,
        description="Extracted service names from alerts"
    )
    
    components: List[str] = Field(
        default_factory=list,
        description="Extracted component names from alerts"
    )
    
    normalized_descriptions: List[str] = Field(
        ...,
        description="Normalized alert descriptions",
        min_length=1
    )
    
    diagnostic_start: datetime = Field(
        ...,
        description="Start of diagnostic time window (before incident_start)"
    )
    
    diagnostic_end: datetime = Field(
        ...,
        description="End of diagnostic time window (after incident_end)"
    )
    
    stage2_predictions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Stage 2 classification predictions if available"
    )


class Evidence(BaseModel):
    """
    Single piece of evidence supporting RCA.
    
    CRITICAL: All evidence must include provenance (source_type, is_mock).
    """
    source: str = Field(
        ...,
        description="Evidence source: logs, metrics, traces, historical_alerts, runbook, etc."
    )
    
    source_type: SourceType = Field(
        ...,
        description="Whether source is mock, real data, or model prediction"
    )
    
    source_id: str = Field(
        ...,
        description="Unique identifier for this evidence item"
    )
    
    timestamp: datetime = Field(
        ...,
        description="When this evidence was observed"
    )
    
    description: str = Field(
        ...,
        description="Human-readable evidence description"
    )
    
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Evidence weight/importance (0.0-1.0)"
    )
    
    is_mock: bool = Field(
        ...,
        description="Explicit flag: True if mock/synthetic data, False if real"
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional evidence metadata"
    )
    
    @model_validator(mode='after')
    def validate_provenance_consistency(self):
        """Ensure provenance flags are internally consistent."""
        # MOCK source type must have is_mock=True
        if self.source_type == SourceType.MOCK and not self.is_mock:
            raise ValueError("source_type='mock' requires is_mock=True")
        
        # REAL source type must have is_mock=False
        if self.source_type == SourceType.REAL and self.is_mock:
            raise ValueError("source_type='real' requires is_mock=False")
        
        # MODEL_PREDICTION should have is_mock=False (it's a prediction, not mock telemetry)
        if self.source_type == SourceType.MODEL_PREDICTION and self.is_mock:
            raise ValueError("source_type='model_prediction' should have is_mock=False (predictions are not mock telemetry)")
        
        return self


class ProbableRootCause(BaseModel):
    """
    Primary RCA candidate (most likely root cause).
    
    IMPORTANT: Confidence is experimental, NOT a calibrated probability.
    """
    component: str = Field(
        ...,
        description="Component where failure occurred (e.g., 'database', 'application')"
    )
    
    failure_type: str = Field(
        ...,
        description="Type of failure (e.g., 'connection_pool_exhaustion', 'timeout')"
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Experimental confidence score (NOT calibrated probability)"
    )
    
    description: str = Field(
        ...,
        description="Detailed description of the probable root cause"
    )
    
    supporting_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Evidence source_ids that support this hypothesis"
    )
    
    is_tentative: bool = Field(
        default=False,
        description="Flag indicating tentative hypothesis when evidence is inconclusive or insufficient"
    )


class AlternativeHypothesis(BaseModel):
    """
    Alternative RCA candidate (lower-ranked hypothesis).
    """
    component: str = Field(
        ...,
        description="Component where failure might have occurred"
    )
    
    failure_type: str = Field(
        ...,
        description="Type of failure"
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Experimental confidence score"
    )
    
    reason_for_lower_rank: str = Field(
        ...,
        description="Why this hypothesis ranks lower than the primary"
    )


class RecommendedAction(BaseModel):
    """
    Suggested remediation or diagnostic action.
    
    CRITICAL: Consequential actions must require human approval.
    """
    action: str = Field(
        ...,
        description="Description of the recommended action"
    )
    
    priority: int = Field(
        ...,
        ge=1,
        le=5,
        description="Action priority (1=highest, 5=lowest)"
    )
    
    action_type: ActionType = Field(
        ...,
        description="Type of action: diagnostic, remediation, or escalation"
    )
    
    runbook_reference: Optional[str] = Field(
        default=None,
        description="Reference to relevant runbook/playbook (if available)"
    )
    
    requires_human_approval: bool = Field(
        default=True,
        description="Whether action requires human review before execution"
    )
    
    rationale: str = Field(
        ...,
        description="Why this action is recommended"
    )


class RCAResult(BaseModel):
    """
    Complete RCA analysis result - output of Stage 4.
    
    This is the final structured output containing diagnosis, evidence,
    recommendations, and communications.
    """
    incident_id: str = Field(
        ...,
        description="Incident identifier from Stage 3"
    )
    
    analysis_timestamp: datetime = Field(
        ...,
        description="When this RCA analysis was performed"
    )
    
    diagnosis_status: DiagnosisStatus = Field(
        ...,
        description="Overall diagnosis status"
    )
    
    # RCA results
    probable_root_cause: Optional[ProbableRootCause] = Field(
        default=None,
        description="Primary root cause hypothesis (if sufficient evidence)"
    )
    
    alternative_hypotheses: List[AlternativeHypothesis] = Field(
        default_factory=list,
        description="Alternative root cause hypotheses"
    )
    
    # Evidence
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="All evidence items with provenance"
    )
    
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Types of evidence that were unavailable"
    )
    
    # Actions
    recommended_actions: List[RecommendedAction] = Field(
        default_factory=list,
        description="Recommended diagnostic/remediation actions"
    )
    
    runbook_reference: Optional[str] = Field(
        default=None,
        description="Reference to applicable runbook (if available)"
    )
    
    # Communications
    support_communication: str = Field(
        ...,
        description="Technical communication for support team"
    )
    
    stakeholder_communication: str = Field(
        ...,
        description="Business-friendly communication for stakeholders"
    )
    
    # Review flags
    human_review_required: bool = Field(
        default=True,
        description="Whether human review is required"
    )
    
    review_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons why human review is required"
    )
    
    # Provenance - CRITICAL for auditing
    telemetry_is_mock: bool = Field(
        ...,
        description="True if telemetry data is mock/synthetic"
    )
    
    retrieval_source: str = Field(
        default="historical_alert_ticket_patterns",
        description="Source of historical pattern retrieval"
    )
    
    reasoning_provider: str = Field(
        default="mock",
        description="Reasoning provider used: 'mock' or 'bedrock_claude'"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "incident_id": "INCIDENT-0042",
                "analysis_timestamp": "2026-09-26T20:00:00",
                "diagnosis_status": "sufficient_evidence",
                "probable_root_cause": {
                    "component": "database",
                    "failure_type": "connection_pool_exhaustion",
                    "confidence": 0.82,
                    "description": "Database connection pool reached capacity, causing downstream timeouts"
                },
                "evidence": [
                    {
                        "source": "metrics",
                        "source_type": "mock",
                        "source_id": "mock_metric_001",
                        "timestamp": "2026-09-26T19:45:00",
                        "description": "DB connection pool utilization at 100%",
                        "weight": 0.9,
                        "is_mock": True
                    }
                ],
                "telemetry_is_mock": True,
                "reasoning_provider": "mock",
                "support_communication": "Incident analysis based on mock telemetry (prototype)...",
                "stakeholder_communication": "Service disruption detected. Investigation in progress..."
            }]
        }
    }


class LogRecord(BaseModel):
    """Mock or real log entry with provenance."""
    log_id: str = Field(..., description="Unique log identifier")
    timestamp: datetime = Field(..., description="Log timestamp")
    component: str = Field(..., description="Component that generated the log")
    level: str = Field(..., description="Log level: ERROR, WARN, INFO, DEBUG")
    message: str = Field(..., description="Log message")
    source_type: SourceType = Field(..., description="Mock, real, or model prediction")
    is_mock: bool = Field(..., description="True if mock data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional log metadata")
    
    @model_validator(mode='after')
    def validate_provenance_consistency(self):
        """Ensure provenance flags are internally consistent."""
        if self.source_type == SourceType.MOCK and not self.is_mock:
            raise ValueError("source_type='mock' requires is_mock=True")
        if self.source_type == SourceType.REAL and self.is_mock:
            raise ValueError("source_type='real' requires is_mock=False")
        return self


class MetricRecord(BaseModel):
    """Mock or real metric data point with provenance."""
    metric_id: str = Field(..., description="Unique metric identifier")
    timestamp: datetime = Field(..., description="Metric timestamp")
    metric_name: str = Field(..., description="Metric name (e.g., 'cpu_utilization')")
    component: str = Field(..., description="Component being measured")
    value: float = Field(..., description="Metric value")
    unit: str = Field(..., description="Metric unit (e.g., 'percent', 'milliseconds')")
    source_type: SourceType = Field(..., description="Mock, real, or model prediction")
    is_mock: bool = Field(..., description="True if mock data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metric metadata")
    
    @model_validator(mode='after')
    def validate_provenance_consistency(self):
        """Ensure provenance flags are internally consistent."""
        if self.source_type == SourceType.MOCK and not self.is_mock:
            raise ValueError("source_type='mock' requires is_mock=True")
        if self.source_type == SourceType.REAL and self.is_mock:
            raise ValueError("source_type='real' requires is_mock=False")
        return self


class TraceSpan(BaseModel):
    """Mock or real distributed trace span with provenance."""
    span_id: str = Field(..., description="Unique span identifier")
    parent_span_id: Optional[str] = Field(default=None, description="Parent span ID (if nested)")
    trace_id: str = Field(..., description="Trace identifier")
    component: str = Field(..., description="Component executing this span")
    operation: str = Field(..., description="Operation name")
    start_time: datetime = Field(..., description="Span start time")
    end_time: datetime = Field(..., description="Span end time")
    duration_ms: float = Field(..., ge=0.0, description="Span duration in milliseconds")
    status: str = Field(..., description="Span status: ok, error, timeout")
    source_type: SourceType = Field(..., description="Mock, real, or model prediction")
    is_mock: bool = Field(..., description="True if mock data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional span metadata")
    
    @model_validator(mode='after')
    def validate_provenance_consistency(self):
        """Ensure provenance flags are internally consistent."""
        if self.source_type == SourceType.MOCK and not self.is_mock:
            raise ValueError("source_type='mock' requires is_mock=True")
        if self.source_type == SourceType.REAL and self.is_mock:
            raise ValueError("source_type='real' requires is_mock=False")
        return self


class AnomalyDetection(BaseModel):
    """Detected metric anomaly."""
    metric_name: str = Field(..., description="Metric that showed anomaly")
    component: str = Field(..., description="Component where anomaly detected")
    timestamp: datetime = Field(..., description="When anomaly occurred")
    observed_value: float = Field(..., description="Observed metric value")
    expected_value: float = Field(..., description="Expected baseline value")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Anomaly score (0-1)")
    detection_method: str = Field(..., description="Detection method: z_score, mad, isolation_forest")
    is_anomalous: bool = Field(..., description="Whether this is classified as anomalous")
    source_type: SourceType = Field(..., description="Source type of the underlying metric")
    is_mock: bool = Field(..., description="Whether the underlying metric is mock data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional detection metadata")
