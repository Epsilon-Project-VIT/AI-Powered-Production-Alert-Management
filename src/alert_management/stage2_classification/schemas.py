"""
Pydantic schemas for Stage 2: Alert Classification & Routing.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class AlertType(str, Enum):
    """Types of technical problems."""
    API = "API"
    BATCH_WORKFLOW = "BATCH/WORKFLOW"
    DATABASE = "DATABASE"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    NETWORK = "NETWORK"
    APPLICATION = "APPLICATION"
    MONITORING = "MONITORING"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    """Technical severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class BusinessImpact(str, Enum):
    """Business impact levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class Priority(str, Enum):
    """Priority levels (derived from severity + business impact)."""
    P1_CRITICAL = "1 - Critical"
    P2_HIGH = "2 - High"
    P3_MEDIUM = "3 - Medium"
    P4_LOW = "4 - Low"
    UNKNOWN = "UNKNOWN"


class ClassificationResult(BaseModel):
    """
    Result of a single classification task.
    
    Contains the predicted label and confidence score.
    """
    
    label: str = Field(
        ...,
        description="Predicted label"
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score (0.0 to 1.0)"
    )

    provider: str = Field(default="ml", description="Prediction provider")
    model: Optional[str] = Field(default=None, description="Provider model identifier")
    latency_ms: Optional[float] = Field(default=None, ge=0.0)
    is_fallback: bool = False
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v


class EnrichedAlert(BaseModel):
    """
    Enriched alert object - output of Stage 2.
    
    Contains all Stage 1 information plus Stage 2 classifications.
    """
    
    # Stage 1 fields (passed through)
    alert_id: str = Field(
        ...,
        description="Unique alert identifier",
        min_length=1
    )
    
    created_at: datetime = Field(
        ...,
        description="Timestamp of alert creation"
    )
    
    client: str = Field(
        ...,
        description="Impacted client name",
        min_length=1
    )
    
    raw_description: str = Field(
        ...,
        description="Original alert description",
        min_length=1
    )
    
    normalized_description: str = Field(
        ...,
        description="Normalized description",
        min_length=1
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional fields from source system"
    )
    
    # Stage 2 fields (new classifications)
    alert_type: ClassificationResult = Field(
        ...,
        description="Classified alert type"
    )
    
    severity: ClassificationResult = Field(
        ...,
        description="Classified severity level"
    )
    
    business_impact: ClassificationResult = Field(
        ...,
        description="Classified business impact"
    )
    
    priority: ClassificationResult = Field(
        ...,
        description="Classified priority"
    )
    
    routing: ClassificationResult = Field(
        ...,
        description="Classified routing/assignment group"
    )
    
    @field_validator('alert_id', 'client', 'raw_description', 'normalized_description')
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        """Ensure string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "alert_id": "INC3528892",
                    "created_at": "2026-08-06T02:30:02",
                    "client": "Bridgestone",
                    "raw_description": "Data Hub Alert (Workflow) : P1BGSN - BGSN_Batch_Extract_Point_Redemption_Delta_AZREWARDS - FAILURE",
                    "normalized_description": "data hub alert workflow <priority>bgsn bgsn_batch_extract_point_redemption_delta_azrewards failure",
                    "metadata": {"Active": True},
                    "alert_type": {
                        "label": "BATCH/WORKFLOW",
                        "confidence": 0.91
                    },
                    "severity": {
                        "label": "HIGH",
                        "confidence": 0.87
                    },
                    "business_impact": {
                        "label": "HIGH",
                        "confidence": 0.82
                    },
                    "priority": {
                        "label": "2 - High",
                        "confidence": 0.72
                    },
                    "routing": {
                        "label": "Client Support Subscription Services - Bridgestone",
                        "confidence": 0.93
                    }
                }
            ]
        }
    }
