"""
Catalog of 8 synthetic scenario types x 3 variants (24 scenario specifications).

Scenario Types:
1. db_pool_exhaustion - Database connection pool exhaustion with downstream API symptoms.
2. api_lb_failure - API/load-balancer failure while database health remains normal.
3. batch_job_failure - Batch-job/workflow execution failure.
4. sla_delivery_delay - Delayed batch/data extraction or SLA delivery.
5. queue_backlog - Queue or worker backlog.
6. cpu_memory_pressure - CPU/memory pressure.
7. network_degradation - Network degradation or packet loss.
8. ambiguous_evidence - Incomplete, ambiguous, or conflicting diagnostic evidence.

Variants per type:
- sufficient: Strong, evidence-supported diagnosis (clear signal across all modalities)
- insufficient: Incomplete evidence (key telemetry modality missing or sparse)
- ambiguous: Ambiguous/competing evidence (conflicting signals across multiple components)
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from alert_management.stage4_analysis.schemas import DiagnosisStatus


class ScenarioSpec(BaseModel):
    """Configuration specification for a synthetic benchmark scenario."""
    scenario_type: str = Field(..., description="Scenario type identifier")
    variant: str = Field(..., description="Variant: 'sufficient', 'insufficient', or 'ambiguous'")
    scenario_id: str = Field(..., description="Unique scenario ID e.g. SCENARIO-DB-POOL-SUFF")
    
    title: str = Field(..., description="Human-readable scenario title")
    description: str = Field(..., description="Scenario description")
    
    client: str = Field(default="Epsilon Corporate", description="Client context")
    primary_component: str = Field(..., description="Primary component where fault originates")
    failure_type: str = Field(..., description="Primary failure mechanism")
    
    competing_component: Optional[str] = Field(None, description="Competing component for ambiguous variant")
    competing_failure_type: Optional[str] = Field(None, description="Competing failure type for ambiguous variant")
    
    expected_diagnosis_mode: DiagnosisStatus = Field(..., description="Expected diagnosis status")
    
    # Telemetry generation controls
    include_logs: bool = Field(default=True)
    include_metrics: bool = Field(default=True)
    include_traces: bool = Field(default=True)
    
    fault_duration_minutes: int = Field(default=15)
    log_volume: str = Field(default="normal")  # 'normal', 'sparse', 'dense'


def get_scenario_catalog() -> List[ScenarioSpec]:
    """
    Return all 24 benchmark scenario specifications (8 types x 3 variants).
    """
    catalog = []
    
    scenario_types = [
        ("db_pool_exhaustion", "database", "connection_pool_exhaustion", "application", "service_error"),
        ("api_lb_failure", "elb", "service_error", "application", "timeout"),
        ("batch_job_failure", "application", "batch_execution_failure", "database", "query_timeout"),
        ("sla_delivery_delay", "extract_service", "delivery_delay", "application", "performance_degradation"),
        ("queue_backlog", "message_queue", "queue_backlog", "worker_service", "cpu_memory_pressure"),
        ("cpu_memory_pressure", "application", "resource_exhaustion", "database", "connection_pool_exhaustion"),
        ("network_degradation", "network", "network_degradation", "mulesoft", "timeout"),
        ("ambiguous_evidence", "application", "performance_degradation", "database", "connection_pool_exhaustion"),
    ]
    
    for stype, comp, ftype, comp_comp, comp_ftype in scenario_types:
        exp_mode = DiagnosisStatus.AMBIGUOUS if stype == "ambiguous_evidence" else DiagnosisStatus.SUFFICIENT_EVIDENCE
        # Variant 1: Sufficient
        catalog.append(ScenarioSpec(
            scenario_type=stype,
            variant="sufficient",
            scenario_id=f"SCENARIO-{stype.upper()}-SUFF",
            title=f"{stype.replace('_', ' ').title()} (Sufficient Evidence)",
            description=f"Strong evidence-supported diagnosis for {stype} in {comp}.",
            primary_component=comp,
            failure_type=ftype,
            expected_diagnosis_mode=exp_mode,
            include_logs=True,
            include_metrics=True,
            include_traces=True,
            log_volume="dense"
        ))

        
        # Variant 2: Insufficient
        catalog.append(ScenarioSpec(
            scenario_type=stype,
            variant="insufficient",
            scenario_id=f"SCENARIO-{stype.upper()}-INSUFF",
            title=f"{stype.replace('_', ' ').title()} (Insufficient Evidence)",
            description=f"Incomplete evidence for {stype}; traces and metrics are sparse or missing.",
            primary_component=comp,
            failure_type=ftype,
            expected_diagnosis_mode=DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            include_logs=True,
            include_metrics=False,  # Metrics missing
            include_traces=False,  # Traces missing
            log_volume="sparse"
        ))
        
        # Variant 3: Ambiguous
        catalog.append(ScenarioSpec(
            scenario_type=stype,
            variant="ambiguous",
            scenario_id=f"SCENARIO-{stype.upper()}-AMBIG",
            title=f"{stype.replace('_', ' ').title()} (Ambiguous Evidence)",
            description=f"Ambiguous conflicting evidence between {comp} and {comp_comp}.",
            primary_component=comp,
            failure_type=ftype,
            competing_component=comp_comp,
            competing_failure_type=comp_ftype,
            expected_diagnosis_mode=DiagnosisStatus.AMBIGUOUS,
            include_logs=True,
            include_metrics=True,
            include_traces=True,
            log_volume="normal"
        ))
        
    return catalog


ALL_SCENARIOS = [
    "db_pool_exhaustion",
    "api_lb_failure",
    "batch_job_failure",
    "sla_delivery_delay",
    "queue_backlog",
    "cpu_memory_pressure",
    "network_degradation",
    "ambiguous_evidence",
]


def get_scenario_spec(scenario_type: str, variant: str = "sufficient") -> ScenarioSpec:
    """Retrieve scenario specification by type and variant."""
    for spec in get_scenario_catalog():
        if spec.scenario_type == scenario_type and spec.variant == variant:
            return spec
    raise ValueError(f"No spec found for scenario_type={scenario_type}, variant={variant}")


def build_evaluation_manifest(scenario_type: str, variant: str = "sufficient") -> ScenarioEvaluationManifest:
    """Build ScenarioEvaluationManifest for benchmarking."""
    from datetime import datetime, timezone, timedelta
    from alert_management.stage4_analysis.telemetry.synthetic.manifest import ScenarioEvaluationManifest
    
    spec = get_scenario_spec(scenario_type, variant)
    now = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    
    return ScenarioEvaluationManifest(
        scenario_id=spec.scenario_id,
        scenario_type=spec.scenario_type,
        variant=spec.variant,
        incident_id=f"INC-{spec.scenario_id}",
        source_alert_ids=[f"ALT-MOCK-{spec.scenario_type.upper()}-001", f"ALT-MOCK-{spec.scenario_type.upper()}-002"],
        expected_root_cause_component=spec.primary_component,
        expected_failure_type=spec.failure_type,
        expected_diagnosis_mode=spec.expected_diagnosis_mode,
        expected_supporting_signals=[f"{spec.primary_component}_logs", f"{spec.failure_type}_metrics"],
        fault_onset=now - timedelta(minutes=15),
        fault_recovery=now,
        start_time=now - timedelta(minutes=30),
        end_time=now + timedelta(minutes=5),
        is_evaluation_only=True,
    )

