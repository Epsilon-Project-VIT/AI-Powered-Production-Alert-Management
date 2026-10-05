"""
Pydantic schemas for Stage 1: Alert Ingestion & Normalization.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Dict, Any


class StandardizedAlert(BaseModel):
    """
    Standardized alert object - output of Stage 1.
    
    This represents a cleaned, validated, and normalized alert ready for
    Stage 2 classification.
    """
    
    alert_id: str = Field(
        ...,
        description="Unique alert identifier (e.g., INC3528892)",
        min_length=1
    )
    
    created_at: datetime = Field(
        ...,
        description="Timestamp of alert creation"
    )
    
    client: str = Field(
        ...,
        description="Impacted client name (e.g., Bridgestone, EA Sports, Pizza Hut)",
        min_length=1
    )
    
    raw_description: str = Field(
        ...,
        description="Original alert description (unmodified)",
        min_length=1
    )
    
    normalized_description: str = Field(
        ...,
        description="Normalized description with dynamic values replaced",
        min_length=1
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional fields from source system"
    )
    
    @field_validator('alert_id', 'client', 'raw_description', 'normalized_description')
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        """Ensure string fields are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace-only")
        return v.strip()
    
    @field_validator('created_at')
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is valid."""
        if v is None:
            raise ValueError("created_at cannot be None")
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "alert_id": "INC3528892",
                    "created_at": "2026-08-06T02:30:02",
                    "client": "Bridgestone",
                    "raw_description": "Data Hub Alert (Workflow) : P1BGSN - BGSN_Batch_Extract_Point_Redemption_Delta_AZREWARDS - FAILURE",
                    "normalized_description": "data hub alert workflow p<priority>bgsn bgsn_batch_extract_point_redemption_delta_azrewards failure",
                    "metadata": {
                        "priority": "3 - Medium",
                        "assignment_group": "Client Support Subscription Services - Bridgestone"
                    }
                }
            ]
        }
    }
