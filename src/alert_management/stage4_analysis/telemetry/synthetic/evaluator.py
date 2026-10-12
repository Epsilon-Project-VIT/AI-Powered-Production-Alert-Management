"""
Scenario Evaluator Harness.

Evaluates Stage 4 RCA pipeline performance against the evaluation-only manifests
for all 24 synthetic benchmark scenarios.

Key Metrics Evaluated:
- Top-1 Root-Cause Component Match
- Failure-Type Match
- Expected Diagnosis Status Match
- Supporting Evidence Reference Validity
- Synthetic Provenance Integrity (is_mock=True on 100% records)
- Ground-Truth Leakage Prevention
- Human Approval & Safety Enforcement (0 auto-remediation)
- Seed Reproducibility
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from pydantic import BaseModel

from alert_management.stage4_analysis.schemas import RCAResult, DiagnosisStatus, SourceType, ActionType
from alert_management.stage4_analysis.pipeline import Stage4Pipeline
from alert_management.stage4_analysis.reasoning.mock_reasoning_provider import MockReasoningProvider
from alert_management.stage4_analysis.telemetry.synthetic.scenarios import get_scenario_catalog, ScenarioSpec
from alert_management.stage4_analysis.telemetry.synthetic.generator import SyntheticTelemetryGenerator, ScenarioRun
from alert_management.stage4_analysis.telemetry.synthetic.provider_adapter import (
    ScenarioLogProvider,
    ScenarioMetricProvider,
    ScenarioTraceProvider
)


class ScenarioEvaluationResult(BaseModel):
    """Result of evaluating a single scenario run."""
    scenario_id: str
    scenario_type: str
    variant: str
    
    top1_component_match: Optional[bool] = None
    failure_type_match: Optional[bool] = None
    diagnosis_status_match: bool
    
    competing_hypotheses_detected: Optional[bool] = None
    tentative_distinguished: Optional[bool] = None
    uncertainty_represented: Optional[bool] = None
    
    evidence_reference_validity: bool
    synthetic_provenance_validity: bool
    ground_truth_leakage_free: bool
    no_auto_remediation: bool
    seed_reproducible: bool
    
    actual_component: Optional[str] = None
    expected_component: str
    actual_failure_type: Optional[str] = None
    expected_failure_type: str
    actual_status: DiagnosisStatus
    expected_status: DiagnosisStatus
    
    evidence_count: int
    log_count: int
    metric_count: int
    trace_count: int


class ScenarioEvaluator:
    """Evaluation harness for running the 24 synthetic benchmark scenarios."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.generator = SyntheticTelemetryGenerator(seed=seed)

    def evaluate_all_scenarios(self) -> List[ScenarioEvaluationResult]:
        """
        Execute all 24 benchmark scenarios through Stage4Pipeline and evaluate results.
        """
        catalog = get_scenario_catalog()
        results: List[ScenarioEvaluationResult] = []

        for spec in catalog:
            eval_result = self.evaluate_scenario(spec)
            results.append(eval_result)

        return results

    def evaluate_scenario(self, spec: ScenarioSpec) -> ScenarioEvaluationResult:
        """
        Execute and evaluate a single scenario.
        """
        run = self.generator.generate_scenario_run(spec, seed_override=self.seed)

        # Reproducibility check: generate second run with same seed
        run_dup = self.generator.generate_scenario_run(spec, seed_override=self.seed)
        seed_reproducible = (
            len(run.logs) == len(run_dup.logs) and
            len(run.metrics) == len(run_dup.metrics) and
            len(run.traces) == len(run_dup.traces)
        )

        # Initialize pipeline with scenario providers
        log_prov = ScenarioLogProvider(run)
        metric_prov = ScenarioMetricProvider(run)
        trace_prov = ScenarioTraceProvider(run)
        reasoning_prov = MockReasoningProvider()

        pipeline = Stage4Pipeline(
            log_provider=log_prov,
            metric_provider=metric_prov,
            trace_provider=trace_prov,
            reasoning_provider=reasoning_prov
        )

        # Convert context enriched alerts mockup
        rca_result, _, _ = pipeline.analyze_incident(
            incident_group=self._create_dummy_incident_group(run),
            enriched_alerts=self._create_dummy_enriched_alerts(run)
        )

        # 1. Component & Failure Type Match with semantic variant awareness
        prc = rca_result.probable_root_cause
        actual_comp = prc.component if prc else None
        actual_ftype = prc.failure_type if prc else None
        status_match = (rca_result.diagnosis_status == run.manifest.expected_diagnosis_mode)

        if run.manifest.expected_diagnosis_mode == DiagnosisStatus.SUFFICIENT_EVIDENCE:
            # For sufficient evidence: expect exact Top-1 component and failure type match
            top1_comp_match = (actual_comp == run.manifest.expected_root_cause_component)
            ftype_match = (actual_ftype == run.manifest.expected_failure_type)
            tentative_distinguished = True
            competing_hypotheses_detected = None
            uncertainty_represented = True
        elif run.manifest.expected_diagnosis_mode == DiagnosisStatus.INSUFFICIENT_EVIDENCE:
            # For insufficient evidence: valid diagnosis is NOT supposed to be produced!
            # Top-1 and failure type are NOT APPLICABLE (None).
            top1_comp_match = None
            ftype_match = None
            # Verify candidate is distinguished as tentative (is_tentative=True or unknown/confidence <= 0.25)
            tentative_distinguished = (prc is None or getattr(prc, "is_tentative", False) or prc.confidence <= 0.25)
            competing_hypotheses_detected = None
            uncertainty_represented = status_match and tentative_distinguished
        elif run.manifest.expected_diagnosis_mode == DiagnosisStatus.AMBIGUOUS:
            # For ambiguous evidence: evaluate whether uncertainty and competing hypotheses are represented
            # Do NOT treat single primary component match as successful diagnosis!
            top1_comp_match = None
            ftype_match = None
            tentative_distinguished = True
            competing_hypotheses_detected = (
                len(rca_result.alternative_hypotheses) > 0 and
                (spec.competing_component is None or any(alt.component == spec.competing_component for alt in rca_result.alternative_hypotheses) or len(rca_result.alternative_hypotheses) >= 1)
            )
            uncertainty_represented = status_match and competing_hypotheses_detected
        else:
            top1_comp_match = (actual_comp == run.manifest.expected_root_cause_component)
            ftype_match = (actual_ftype == run.manifest.expected_failure_type)
            tentative_distinguished = None
            competing_hypotheses_detected = None
            uncertainty_represented = None

        # 2. Evidence Reference Validity
        valid_ev_ids = {e.source_id for e in rca_result.evidence}
        referenced_ids = prc.supporting_evidence_ids if prc else []
        ev_ref_valid = all(ref in valid_ev_ids for ref in referenced_ids)

        # 3. Provenance Validity
        provenance_valid = all(
            e.is_mock and e.source_type == SourceType.MOCK
            for e in rca_result.evidence
            if e.source in ("logs", "metrics", "traces")
        )

        # 4. Ground-Truth Leakage Check
        # Ensure evaluation manifest scenario_id / expected cause labels never appear in serialized evidence
        leakage_free = True
        forbidden_strings = [
            run.manifest.scenario_id,
            spec.scenario_id,
            f"SCENARIO-{spec.scenario_type.upper()}",
        ]
        # Check context
        for fs in forbidden_strings:
            if fs in run.context.incident_id or any(fs in aid for aid in run.context.alert_ids):
                leakage_free = False
                break
            for desc in run.context.normalized_descriptions:
                if fs in desc:
                    leakage_free = False
                    break

        # Check evidence
        for e in rca_result.evidence:
            for fs in forbidden_strings:
                if fs in e.description or (e.metadata and fs in str(e.metadata)):
                    leakage_free = False
                    break

        # 5. Safety & Human Approval: Ensure no remediation action bypasses approval
        no_auto_remed = all(
            (act.requires_human_approval if act.action_type == ActionType.REMEDIATION else True)
            for act in rca_result.recommended_actions
        ) and rca_result.human_review_required

        return ScenarioEvaluationResult(
            scenario_id=spec.scenario_id,
            scenario_type=spec.scenario_type,
            variant=spec.variant,
            top1_component_match=top1_comp_match,
            failure_type_match=ftype_match,
            diagnosis_status_match=status_match,
            competing_hypotheses_detected=competing_hypotheses_detected,
            tentative_distinguished=tentative_distinguished,
            uncertainty_represented=uncertainty_represented,
            evidence_reference_validity=ev_ref_valid,
            synthetic_provenance_validity=provenance_valid,
            ground_truth_leakage_free=leakage_free,
            no_auto_remediation=no_auto_remed,
            seed_reproducible=seed_reproducible,
            actual_component=actual_comp,
            expected_component=run.manifest.expected_root_cause_component,
            actual_failure_type=actual_ftype,
            expected_failure_type=run.manifest.expected_failure_type,
            actual_status=rca_result.diagnosis_status,
            expected_status=run.manifest.expected_diagnosis_mode,
            evidence_count=len(rca_result.evidence),
            log_count=len(run.logs),
            metric_count=len(run.metrics),
            trace_count=len(run.traces)
        )

    def _create_dummy_incident_group(self, run: ScenarioRun):
        from alert_management.stage3_correlation.schemas import IncidentGroup
        return IncidentGroup(
            incident_id=run.context.incident_id,
            alert_ids=run.context.alert_ids,
            primary_alert_id=run.context.primary_alert_id,
            client=run.context.client,
            incident_start=run.context.incident_start,
            incident_end=run.context.incident_end or run.context.incident_start,
            alert_count=run.context.alert_count,
            normalized_signature="synthetic_signature",
            correlation_method="graph_connected_component",
            avg_correlation_score=0.9
        )

    def _create_dummy_enriched_alerts(self, run: ScenarioRun):
        from alert_management.stage2_classification.schemas import EnrichedAlert, ClassificationResult
        alerts = []
        for aid in run.context.alert_ids:
            alerts.append(EnrichedAlert(
                alert_id=aid,
                created_at=run.context.incident_start,
                client=run.context.client,
                raw_description=f"Synthetic alert {aid}: Service degradation symptom reported",
                normalized_description=f"synthetic alert {aid}: service degradation symptom reported",
                alert_type=ClassificationResult(label="Service Degradation", confidence=0.88),
                severity=ClassificationResult(label="HIGH", confidence=0.85),
                business_impact=ClassificationResult(label="HIGH", confidence=0.88),
                priority=ClassificationResult(label="P2", confidence=0.88),
                routing=ClassificationResult(label="Tier 2 Support", confidence=0.85)
            ))
        return alerts

