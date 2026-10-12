"""
Frozen Evidence Bundles for Stage 4 Benchmark.

Generates and freezes exact runtime input bundles for the 24 synthetic scenarios
using fixed seeds, guaranteeing 100% process-independent reproducibility.

Strict Ground-Truth Isolation:
Runtime bundles contain ONLY runtime telemetry, context, evidence, and candidates.
Evaluation manifests (expected root cause component, failure type, diagnosis mode)
are saved strictly in a separate manifest file and NEVER passed to reasoning providers.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    LogRecord,
    MetricRecord,
    TraceSpan,
    Evidence,
    ProbableRootCause,
    SourceType,
)
from alert_management.stage4_analysis.telemetry.synthetic.generator import (
    SyntheticTelemetryGenerator,
    ScenarioRun,
)
from alert_management.stage4_analysis.telemetry.synthetic.manifest import ScenarioEvaluationManifest
from alert_management.stage4_analysis.telemetry.synthetic.scenarios import (
    get_scenario_catalog,
    ScenarioSpec,
)
from alert_management.stage4_analysis.telemetry.synthetic.evaluator import ScenarioEvaluator
from alert_management.stage4_analysis.telemetry.synthetic.provider_adapter import (
    ScenarioLogProvider,
    ScenarioMetricProvider,
    ScenarioTraceProvider,
)
from alert_management.stage4_analysis.evidence.evidence_store import EvidenceStore
from alert_management.stage4_analysis.analysis.log_analyzer import LogAnalyzer
from alert_management.stage4_analysis.analysis.anomaly_detector import AnomalyDetector
from alert_management.stage4_analysis.analysis.trace_analyzer import TraceAnalyzer
from alert_management.stage4_analysis.rca.candidate_generator import RCACandidateGenerator
from alert_management.stage4_analysis.rca.candidate_ranker import RCACandidateRanker


class FrozenScenarioBundle(BaseModel):
    """
    Complete frozen runtime input bundle for a scenario.
    Contains zero ground-truth answers or evaluation manifests.
    """
    scenario_id: str = Field(..., description="Opaque or scenario identifier")
    incident_context: IncidentContext = Field(..., description="Runtime IncidentContext supplied to provider")
    logs: List[LogRecord] = Field(default_factory=list, description="Raw logs retrieved for window")
    metrics: List[MetricRecord] = Field(default_factory=list, description="Raw metric records with samples")
    traces: List[TraceSpan] = Field(default_factory=list, description="Retrieved trace spans")
    metric_evidence_episodes: List[Evidence] = Field(
        default_factory=list,
        description="Bounded metric anomaly episodes with raw samples in metadata"
    )
    all_evidence: List[Evidence] = Field(
        default_factory=list,
        description="Complete evidence graph supplied to reasoning provider"
    )
    ranked_candidates: List[ProbableRootCause] = Field(
        default_factory=list,
        description="Pre-generated, ranked RCA candidate hypotheses"
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Identified missing telemetry modalities"
    )
    topology: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Service topology dependency graph"
    )
    telemetry_is_mock: bool = Field(default=True, description="Explicit mock provenance flag")
    provenance_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of mock telemetry provenance"
    )


def generate_single_bundle(
    spec: ScenarioSpec,
    generator: SyntheticTelemetryGenerator
) -> tuple[FrozenScenarioBundle, ScenarioEvaluationManifest]:
    """
    Generate a single frozen runtime bundle and its isolated manifest.
    """
    run = generator.generate_scenario_run(spec, seed_override=generator.seed)

    evaluator = ScenarioEvaluator(seed=generator.seed)
    incident_group = evaluator._create_dummy_incident_group(run)
    enriched_alerts = evaluator._create_dummy_enriched_alerts(run)

    # Use pipeline components for Phase 1-4
    from alert_management.stage4_analysis.context.context_builder import IncidentContextBuilder
    context_builder = IncidentContextBuilder()
    context = context_builder.build_context(incident_group, enriched_alerts)

    log_prov = ScenarioLogProvider(run)
    metric_prov = ScenarioMetricProvider(run)
    trace_prov = ScenarioTraceProvider(run)

    logs = log_prov.get_logs(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.services
    )
    metrics = metric_prov.get_metrics(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.services
    )
    traces = trace_prov.get_traces(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.services
    )

    # Phase 3: Evidence Store & Analyzers
    evidence_store = EvidenceStore()
    log_analyzer = LogAnalyzer()
    anomaly_detector = AnomalyDetector()
    trace_analyzer = TraceAnalyzer()

    log_evidence = log_analyzer.analyze(
        logs,
        context.diagnostic_start,
        context.diagnostic_end,
        context.incident_start,
        context.incident_end
    )
    evidence_store.add_bulk(log_evidence)

    anomalies = anomaly_detector.detect_anomalies(
        metrics,
        context.diagnostic_start,
        context.diagnostic_end,
        context.incident_start,
        context.incident_end
    )
    metric_evidence = anomaly_detector.generate_evidence(anomalies)
    evidence_store.add_bulk(metric_evidence)

    trace_evidence = trace_analyzer.analyze(
        traces,
        context.diagnostic_start,
        context.diagnostic_end,
        context.incident_start,
        context.incident_end
    )
    evidence_store.add_bulk(trace_evidence)

    all_evidence = evidence_store.get_all()

    # Phase 4: Candidate generation and ranking
    cand_generator = RCACandidateGenerator()
    cand_ranker = RCACandidateRanker()

    candidates = cand_generator.generate_candidates(context, all_evidence)
    ranked_candidates = cand_ranker.rank_candidates(candidates, all_evidence)

    # Identify missing evidence
    missing_sources = []
    if not logs:
        missing_sources.append("logs")
    if not metrics:
        missing_sources.append("metrics")
    if not traces:
        missing_sources.append("traces")

    provenance = {
        "log_count": len(logs),
        "metric_count": len(metrics),
        "trace_count": len(traces),
        "evidence_count": len(all_evidence),
        "all_records_is_mock": True,
        "source_type": "MOCK"
    }

    bundle = FrozenScenarioBundle(
        scenario_id=spec.scenario_id,
        incident_context=context,
        logs=logs,
        metrics=metrics,
        traces=traces,
        metric_evidence_episodes=metric_evidence,
        all_evidence=all_evidence,
        ranked_candidates=ranked_candidates,
        missing_evidence=missing_sources,
        topology=run.topology,
        telemetry_is_mock=True,
        provenance_summary=provenance
    )

    return bundle, run.manifest


def freeze_all_scenarios(
    output_dir: Path,
    seed: int = 42
) -> tuple[List[FrozenScenarioBundle], Dict[str, ScenarioEvaluationManifest]]:
    """
    Generate and freeze all 24 scenario bundles and separate manifests.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = get_scenario_catalog()
    generator = SyntheticTelemetryGenerator(seed=seed)

    bundles: List[FrozenScenarioBundle] = []
    manifests: Dict[str, ScenarioEvaluationManifest] = {}

    for spec in catalog:
        bundle, manifest = generate_single_bundle(spec, generator)
        bundles.append(bundle)
        manifests[spec.scenario_id] = manifest

    # 1. Write bundles (ZERO evaluation ground-truth fields)
    bundles_path = output_dir / "bundles.json"
    bundles_data = [b.model_dump(mode="json") for b in bundles]
    with open(bundles_path, "w") as f:
        json.dump(bundles_data, f, indent=2)

    # 2. Write manifests separately (ISOLATED ground-truth evaluation manifest)
    manifests_path = output_dir / "manifests.json"
    manifests_data = {
        sid: m.model_dump(mode="json")
        for sid, m in manifests.items()
    }
    with open(manifests_path, "w") as f:
        json.dump(manifests_data, f, indent=2)

    return bundles, manifests


def load_frozen_bundles(output_dir: Path) -> List[FrozenScenarioBundle]:
    """Load frozen runtime bundles from disk."""
    bundles_path = output_dir / "bundles.json"
    if not bundles_path.exists():
        raise FileNotFoundError(f"Frozen bundles not found at {bundles_path}")
    with open(bundles_path, "r") as f:
        raw_list = json.load(f)
    return [FrozenScenarioBundle.model_validate(item) for item in raw_list]


def load_frozen_manifests(output_dir: Path) -> Dict[str, ScenarioEvaluationManifest]:
    """Load isolated evaluation manifests from disk."""
    manifests_path = output_dir / "manifests.json"
    if not manifests_path.exists():
        raise FileNotFoundError(f"Evaluation manifests not found at {manifests_path}")
    with open(manifests_path, "r") as f:
        raw_dict = json.load(f)
    return {
        sid: ScenarioEvaluationManifest.model_validate(item)
        for sid, item in raw_dict.items()
    }
