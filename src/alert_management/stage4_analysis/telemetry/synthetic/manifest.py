"""
Evaluation-only manifest schema for ground-truth isolation.

CRITICAL SECURITY & PROVENANCE INVARIANT:
The ScenarioEvaluationManifest contains ground-truth injected fault labels.
It MUST NEVER be passed to Stage 4 reasoning models, prompt builders, or
exposed through runtime telemetry retrieval paths.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from alert_management.stage4_analysis.schemas import DiagnosisStatus


class ScenarioVariant(str, Enum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    AMBIGUOUS = "ambiguous"



class ScenarioEvaluationManifest(BaseModel):
    """
    Evaluation-only manifest for benchmarking Stage 4 RCA performance.

    Contains ground-truth injected fault information. Must be strictly isolated
    from runtime telemetry retrieval and LLM prompt serialization.
    """
    scenario_id: str = Field(
        ...,
        description="Unique identifier for the benchmark scenario run"
    )

    scenario_type: str = Field(
        ...,
        description="Type of scenario (e.g., 'db_pool_exhaustion', 'api_lb_failure')"
    )

    variant: str = Field(
        ...,
        description="Scenario variant: 'sufficient', 'insufficient', or 'ambiguous'"
    )

    expected_root_cause_component: str = Field(
        ...,
        description="Ground-truth component where failure originated"
    )

    expected_failure_type: str = Field(
        ...,
        description="Ground-truth failure mechanism"
    )

    expected_diagnosis_mode: DiagnosisStatus = Field(
        ...,
        description="Expected diagnosis status: sufficient_evidence, insufficient_evidence, or ambiguous"
    )

    expected_supporting_signals: List[str] = Field(
        default_factory=list,
        description="Key metric/log/trace signals expected to be present"
    )

    incident_id: str = Field(
        default="INC-BENCHMARK-001",
        description="Associated candidate incident ID"
    )

    source_alert_ids: List[str] = Field(
        default_factory=list,
        description="Source alert IDs for candidate incident"
    )

    start_time: datetime = Field(
        default_factory=lambda: datetime(2026, 10, 10, 11, 30, 0),
        description="Start time of telemetry window"
    )

    end_time: datetime = Field(
        default_factory=lambda: datetime(2026, 10, 10, 12, 5, 0),
        description="End time of telemetry window"
    )

    fault_onset: datetime = Field(
        ...,
        description="Timestamp when injected fault begins"
    )

    fault_recovery: Optional[datetime] = Field(
        default=None,
        description="Timestamp when fault is resolved (if applicable)"
    )

    is_evaluation_only: bool = Field(
        default=True,
        description="Explicit flag ensuring this object is never sent to reasoning models"
    )

