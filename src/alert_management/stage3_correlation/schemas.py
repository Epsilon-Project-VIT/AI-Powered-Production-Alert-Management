"""
Pydantic schemas for Stage 3: Alert Correlation & Incident Grouping.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CorrelationScore(BaseModel):
    """
    Score indicating how strongly two alerts are correlated.
    
    Combines multiple signals:
    - Semantic similarity
    - Temporal proximity
    - Client match
    - Service/alert family match
    - Service/component compatibility
    - Stage 2 compatibility (Alert Type, Severity, Business Impact, Priority, Routing)
    """
    
    semantic_similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Embedding cosine similarity (0-1)"
    )
    
    temporal_proximity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Time-based proximity score (0-1)"
    )
    
    client_match: bool = Field(
        ...,
        description="Whether alerts are from same client"
    )
    
    alert_family_match: bool = Field(
        default=False,
        description="Whether alerts are from same alert family/service"
    )
    
    service_compatibility: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Service/component compatibility score (0-1)"
    )
    
    stage2_compatibility: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Stage 2 classification compatibility (Alert Type, Severity, etc.)"
    )
    
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Weighted overall correlation score (0-1)"
    )


class IncidentGroup(BaseModel):
    """
    Incident group - collection of correlated alerts.
    
    Output of Stage 3.
    """
    
    incident_id: str = Field(
        ...,
        description="Unique incident identifier (e.g., INCIDENT-1007)"
    )
    
    alert_ids: List[str] = Field(
        ...,
        description="List of alert IDs belonging to this incident",
        min_length=1
    )
    
    primary_alert_id: str = Field(
        ...,
        description="Primary/representative alert ID (usually earliest)"
    )
    
    client: str = Field(
        ...,
        description="Client affected by this incident"
    )
    
    incident_start: datetime = Field(
        ...,
        description="Timestamp of first alert in incident"
    )
    
    incident_end: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last alert in incident"
    )
    
    alert_count: int = Field(
        ...,
        ge=1,
        description="Number of alerts in this incident"
    )
    
    normalized_signature: str = Field(
        ...,
        description="Normalized description signature for this incident"
    )
    
    correlation_method: str = Field(
        ...,
        description="Method used to group (exact_match, semantic_clustering, etc.)"
    )
    
    avg_correlation_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Average pairwise correlation score within group"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "incident_id": "INCIDENT-1007",
                    "alert_ids": ["INC3528891", "INC3528900", "INC3528912"],
                    "primary_alert_id": "INC3528891",
                    "client": "EA Sports",
                    "incident_start": "2026-08-06T10:30:00",
                    "incident_end": "2026-08-06T11:45:00",
                    "alert_count": 3,
                    "normalized_signature": "critical autot icket eass ea sports eass_watcher_alert alert p<priority>eass_elb_errcheck <id> elb errors occurred",
                    "correlation_method": "semantic_clustering",
                    "avg_correlation_score": 0.92
                }
            ]
        }
    }
