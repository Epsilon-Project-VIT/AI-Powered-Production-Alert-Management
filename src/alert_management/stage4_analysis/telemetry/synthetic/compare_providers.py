"""
Reasoning Provider Comparison Runner.

Runs MockReasoningProvider and NIMReasoningProvider against identical frozen
evidence bundles and evaluates their outputs against isolated manifests.
"""

import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from alert_management.llm.config import NIMConfig
from alert_management.stage4_analysis.schemas import (
    RCAResult,
    DiagnosisStatus,
    ActionType,
    SourceType,
)
from alert_management.stage4_analysis.reasoning.mock_reasoning_provider import MockReasoningProvider
from alert_management.stage4_analysis.reasoning.nim_reasoning_provider import NIMReasoningProvider
from alert_management.stage4_analysis.policy.policy_gate import PolicyGate
from alert_management.stage4_analysis.telemetry.synthetic.frozen_bundles import (
    FrozenScenarioBundle,
    load_frozen_bundles,
    load_frozen_manifests,
)
from alert_management.stage4_analysis.telemetry.synthetic.manifest import ScenarioEvaluationManifest


class ProviderScenarioOutcome(BaseModel):
    """Outcome of running a single reasoning provider on a frozen bundle."""
    provider_name: str
    available: bool = True
    error_message: Optional[str] = None
    execution_latency_ms: Optional[float] = None
    
    diagnosis_status: Optional[str] = None
    status_match: Optional[bool] = None
    
    actual_component: Optional[str] = None
    expected_component: str
    top1_component_match: Optional[bool] = None  # None for Insufficient/Ambiguous
    
    actual_failure_type: Optional[str] = None
    expected_failure_type: str
    failure_type_match: Optional[bool] = None    # None for Insufficient/Ambiguous
    
    confidence: Optional[float] = None
    is_tentative: Optional[bool] = None
    tentative_distinguished: Optional[bool] = None
    
    competing_hypotheses_detected: Optional[bool] = None
    alternative_hypotheses_count: int = 0
    alternative_components: List[str] = Field(default_factory=list)
    
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    evidence_reference_validity: bool = True
    
    missing_evidence: List[str] = Field(default_factory=list)
    recommended_actions_count: int = 0
    all_remediations_require_human_approval: bool = True
    human_review_required: bool = True


class ScenarioComparisonRecord(BaseModel):
    """Paired comparison record for a scenario across providers."""
    scenario_id: str
    expected_diagnosis_mode: str
    expected_component: str
    expected_failure_type: str
    
    mock_outcome: ProviderScenarioOutcome
    nim_outcome: ProviderScenarioOutcome


class BenchmarkComparisonReport(BaseModel):
    """Aggregate benchmark comparison report across all 24 scenarios."""
    timestamp: datetime = Field(default_factory=datetime.now)
    total_scenarios: int = 24
    frozen_bundles_path: str
    
    mock_provider_status: str = "AVAILABLE"
    nim_provider_status: str
    nim_config_notes: str
    
    records: List[ScenarioComparisonRecord]


def run_provider_comparison(
    frozen_dir: Optional[Path] = None
) -> BenchmarkComparisonReport:
    """
    Execute both providers against the 24 frozen bundles and compare outcomes.
    """
    if frozen_dir is None:
        frozen_dir = Path("data/stage4_benchmark_frozen")

    bundles = load_frozen_bundles(frozen_dir)
    manifests = load_frozen_manifests(frozen_dir)

    policy_gate = PolicyGate()
    mock_provider = MockReasoningProvider()

    # Attempt to load NIM provider
    nim_config = NIMConfig.try_from_env()
    nim_provider: Optional[NIMReasoningProvider] = None
    nim_status = "UNCONFIGURED"
    nim_notes = "NVIDIA_API_KEY environment variable is not configured in this environment"

    if nim_config is not None:
        try:
            nim_provider = NIMReasoningProvider(config=nim_config)
            nim_status = "AVAILABLE"
            nim_notes = f"Model: {nim_config.model}, Base URL: {nim_config.base_url}"
        except Exception as e:
            nim_status = "ERROR"
            nim_notes = f"Failed to initialize NIMReasoningProvider: {str(e)}"

    comparison_records: List[ScenarioComparisonRecord] = []

    for bundle in bundles:
        manifest = manifests.get(bundle.scenario_id)
        if not manifest:
            continue

        valid_evidence_ids = {e.source_id for e in bundle.all_evidence}

        # 1. Run Mock Provider
        t0 = time.perf_counter()
        mock_result = mock_provider.analyze(
            context=bundle.incident_context,
            evidence=bundle.all_evidence,
            rca_candidates=bundle.ranked_candidates,
            missing_evidence=bundle.missing_evidence
        )
        mock_latency = (time.perf_counter() - t0) * 1000.0

        mock_outcome = _evaluate_rca_result(
            provider_name="MockReasoningProvider",
            result=mock_result,
            manifest=manifest,
            valid_evidence_ids=valid_evidence_ids,
            latency_ms=mock_latency,
            policy_gate=policy_gate
        )

        # 2. Run NIM Provider (or report unevaluated if unconfigured)
        if nim_provider is not None:
            t0 = time.perf_counter()
            try:
                nim_result = nim_provider.analyze(
                    context=bundle.incident_context,
                    evidence=bundle.all_evidence,
                    rca_candidates=bundle.ranked_candidates,
                    missing_evidence=bundle.missing_evidence
                )
                nim_latency = (time.perf_counter() - t0) * 1000.0
                nim_outcome = _evaluate_rca_result(
                    provider_name="NIMReasoningProvider",
                    result=nim_result,
                    manifest=manifest,
                    valid_evidence_ids=valid_evidence_ids,
                    latency_ms=nim_latency,
                    policy_gate=policy_gate
                )
            except Exception as e:
                nim_outcome = ProviderScenarioOutcome(
                    provider_name="NIMReasoningProvider",
                    available=False,
                    error_message=str(e),
                    expected_component=manifest.expected_root_cause_component,
                    expected_failure_type=manifest.expected_failure_type
                )
        else:
            nim_outcome = ProviderScenarioOutcome(
                provider_name="NIMReasoningProvider",
                available=False,
                error_message="NIM credentials not configured: NVIDIA_API_KEY environment variable is required",
                expected_component=manifest.expected_root_cause_component,
                expected_failure_type=manifest.expected_failure_type
            )

        comparison_records.append(ScenarioComparisonRecord(
            scenario_id=bundle.scenario_id,
            expected_diagnosis_mode=manifest.expected_diagnosis_mode.value,
            expected_component=manifest.expected_root_cause_component,
            expected_failure_type=manifest.expected_failure_type,
            mock_outcome=mock_outcome,
            nim_outcome=nim_outcome
        ))

    report = BenchmarkComparisonReport(
        frozen_bundles_path=str(frozen_dir / "bundles.json"),
        mock_provider_status="AVAILABLE",
        nim_provider_status=nim_status,
        nim_config_notes=nim_notes,
        records=comparison_records
    )

    # Save comparison report
    results_path = frozen_dir / "comparison_results.json"
    with open(results_path, "w") as f:
        json.dump(report.model_dump(mode="json"), f, indent=2)

    return report


def _evaluate_rca_result(
    provider_name: str,
    result: RCAResult,
    manifest: ScenarioEvaluationManifest,
    valid_evidence_ids: set[str],
    latency_ms: float,
    policy_gate: PolicyGate
) -> ProviderScenarioOutcome:
    """Evaluate an RCAResult against evaluation semantics and safety constraints."""
    prc = result.probable_root_cause
    actual_comp = prc.component if prc else None
    actual_ftype = prc.failure_type if prc else None
    conf = prc.confidence if prc else None
    is_tent = getattr(prc, "is_tentative", False) if prc else False

    status_match = (result.diagnosis_status == manifest.expected_diagnosis_mode)

    # Evidence reference validity
    referenced_ids = prc.supporting_evidence_ids if prc else []
    ev_ref_valid = all(ref in valid_evidence_ids for ref in referenced_ids)

    # Policy gate & safety
    no_auto_remed = all(
        (act.requires_human_approval if act.action_type == ActionType.REMEDIATION else True)
        for act in result.recommended_actions
    ) and result.human_review_required

    # Competing hypotheses
    alt_comps = [alt.component for alt in result.alternative_hypotheses]
    competing_detected = len(result.alternative_hypotheses) > 0

    # Semantic evaluation by diagnosis mode
    if manifest.expected_diagnosis_mode == DiagnosisStatus.SUFFICIENT_EVIDENCE:
        top1_match = (actual_comp == manifest.expected_root_cause_component)
        ftype_match = (actual_ftype == manifest.expected_failure_type)
        tent_dist = True
    elif manifest.expected_diagnosis_mode == DiagnosisStatus.INSUFFICIENT_EVIDENCE:
        top1_match = None  # N/A: no valid diagnosis supposed to be produced
        ftype_match = None
        tent_dist = (prc is None or is_tent or (conf is not None and conf <= 0.25))
    elif manifest.expected_diagnosis_mode == DiagnosisStatus.AMBIGUOUS:
        top1_match = None  # N/A: competing hypotheses present
        ftype_match = None
        tent_dist = True
    else:
        top1_match = (actual_comp == manifest.expected_root_cause_component)
        ftype_match = (actual_ftype == manifest.expected_failure_type)
        tent_dist = True

    return ProviderScenarioOutcome(
        provider_name=provider_name,
        available=True,
        execution_latency_ms=round(latency_ms, 2),
        diagnosis_status=result.diagnosis_status.value,
        status_match=status_match,
        actual_component=actual_comp,
        expected_component=manifest.expected_root_cause_component,
        top1_component_match=top1_match,
        actual_failure_type=actual_ftype,
        expected_failure_type=manifest.expected_failure_type,
        failure_type_match=ftype_match,
        confidence=conf,
        is_tentative=is_tent,
        tentative_distinguished=tent_dist,
        competing_hypotheses_detected=competing_detected,
        alternative_hypotheses_count=len(result.alternative_hypotheses),
        alternative_components=alt_comps,
        supporting_evidence_ids=referenced_ids,
        evidence_reference_validity=ev_ref_valid,
        missing_evidence=result.missing_evidence,
        recommended_actions_count=len(result.recommended_actions),
        all_remediations_require_human_approval=no_auto_remed,
        human_review_required=result.human_review_required
    )
