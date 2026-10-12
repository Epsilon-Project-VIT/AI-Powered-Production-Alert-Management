import pytest
from datetime import datetime, timezone, timedelta
from alert_management.stage4_analysis.telemetry.synthetic.generator import SyntheticTelemetryGenerator
from alert_management.stage4_analysis.telemetry.synthetic.manifest import ScenarioEvaluationManifest, ScenarioVariant
from alert_management.stage4_analysis.telemetry.synthetic.scenarios import (
    ALL_SCENARIOS,
    get_scenario_spec,
    build_evaluation_manifest,
)
from alert_management.stage4_analysis.telemetry.synthetic.provider_adapter import (
    ScenarioLogProvider,
    ScenarioMetricProvider,
    ScenarioTraceProvider,
)
from alert_management.stage4_analysis.telemetry.synthetic.evaluator import ScenarioEvaluator
from alert_management.stage4_analysis.schemas import DiagnosisStatus


def test_scenario_manifest_building():
    """Verify all 8 scenarios build manifests for 3 variants (24 total)."""
    assert len(ALL_SCENARIOS) == 8
    manifests = []
    for s_type in ALL_SCENARIOS:
        for v in [ScenarioVariant.SUFFICIENT, ScenarioVariant.INSUFFICIENT, ScenarioVariant.AMBIGUOUS]:
            manifest = build_evaluation_manifest(s_type, v.value)
            assert manifest is not None
            assert manifest.scenario_type == s_type
            assert manifest.variant == v.value
            assert manifest.incident_id != ""
            assert len(manifest.source_alert_ids) > 0
            manifests.append(manifest)
    assert len(manifests) == 24


def test_seed_reproducibility():
    """Verify that using the same seed produces identical telemetry outputs."""
    spec = get_scenario_spec("db_pool_exhaustion", "sufficient")
    gen1 = SyntheticTelemetryGenerator(seed=42)
    run1 = gen1.generate_scenario_run(spec, seed_override=42)

    gen2 = SyntheticTelemetryGenerator(seed=42)
    run2 = gen2.generate_scenario_run(spec, seed_override=42)

    assert len(run1.logs) == len(run2.logs)
    assert len(run1.metrics) == len(run2.metrics)
    assert len(run1.traces) == len(run2.traces)

    for l1, l2 in zip(run1.logs, run2.logs):
        assert l1.timestamp == l2.timestamp
        assert l1.message == l2.message

    for m1, m2 in zip(run1.metrics, run2.metrics):
        assert m1.timestamp == m2.timestamp
        assert m1.value == m2.value

    # Different seed should yield variation
    gen3 = SyntheticTelemetryGenerator(seed=999)
    run3 = gen3.generate_scenario_run(spec, seed_override=999)
    messages1 = [l.message for l in run1.logs]
    messages3 = [l.message for l in run3.logs]
    assert messages1 != messages3 or [m.value for m in run1.metrics] != [m.value for m in run3.metrics]


def test_multi_modal_correlation():
    """Verify cross-modality correlation (trace IDs, span IDs, service names, fault window)."""
    spec = get_scenario_spec("api_lb_failure", "sufficient")
    gen = SyntheticTelemetryGenerator(seed=123)
    run = gen.generate_scenario_run(spec)

    log_trace_ids = {l.metadata.get("trace_id") for l in run.logs if l.metadata and l.metadata.get("trace_id")}
    span_trace_ids = {s.trace_id for s in run.traces if s.trace_id}

    # Trace IDs from spans should overlap with logs
    assert len(log_trace_ids.intersection(span_trace_ids)) > 0

    services_in_logs = {l.component for l in run.logs}
    services_in_spans = {s.component for s in run.traces}

    assert spec.primary_component in services_in_logs or spec.primary_component in services_in_spans


def test_ground_truth_leakage_prevention():
    """Verify ground-truth manifest labels never leak into telemetry fields."""
    for s_type in ALL_SCENARIOS:
        spec = get_scenario_spec(s_type, "sufficient")
        gen = SyntheticTelemetryGenerator(seed=42)
        run = gen.generate_scenario_run(spec)

        manifest = build_evaluation_manifest(s_type, "sufficient")

        for log in run.logs:
            assert "ground_truth" not in log.message.lower()
            assert manifest.scenario_id not in log.message

        for span in run.traces:
            assert "ground_truth" not in span.component.lower()


def test_provenance_tracking():
    """Verify is_mock / source_type=MOCK is preserved across all providers."""
    spec = get_scenario_spec("queue_backlog", "sufficient")
    gen = SyntheticTelemetryGenerator(seed=42)
    run = gen.generate_scenario_run(spec)

    log_provider = ScenarioLogProvider(run)
    metric_provider = ScenarioMetricProvider(run)
    trace_provider = ScenarioTraceProvider(run)

    logs = log_provider.get_logs(run.context, run.context.diagnostic_start, run.context.diagnostic_end)
    metrics = metric_provider.get_metrics(run.context, run.context.diagnostic_start, run.context.diagnostic_end)
    traces = trace_provider.get_traces(run.context, run.context.diagnostic_start, run.context.diagnostic_end)

    assert len(logs) > 0
    for l in logs:
        assert l.is_mock is True
        assert l.source_type.value.lower() == "mock"

    assert len(metrics) > 0
    for m in metrics:
        assert m.is_mock is True
        assert m.source_type.value.lower() == "mock"

    assert len(traces) > 0
    for t in traces:
        assert t.is_mock is True
        assert t.source_type.value.lower() == "mock"



def test_runtime_context_and_reasoning_input_leakage():
    """
    Regression test: Inspect the complete runtime context, incident group, enriched alerts,
    and trace operations supplied to the reasoning provider to ensure zero leakage of hidden
    evaluation answers across all 24 scenarios.
    """
    from alert_management.stage4_analysis.telemetry.synthetic.scenarios import get_scenario_catalog
    catalog = get_scenario_catalog()
    assert len(catalog) == 24

    for spec in catalog:
        gen = SyntheticTelemetryGenerator(seed=42)
        run = gen.generate_scenario_run(spec)
        manifest = run.manifest

        # 1. IncidentContext identifiers must be opaque
        assert "SCENARIO" not in run.context.incident_id
        assert spec.scenario_type.upper() not in run.context.incident_id
        assert spec.primary_component.upper() not in run.context.incident_id
        assert spec.failure_type.upper() not in run.context.incident_id
        assert manifest.scenario_id not in run.context.incident_id

        # 2. Alert IDs must be opaque
        for aid in run.context.alert_ids:
            assert "SCENARIO" not in aid
            assert spec.scenario_type[:4].upper() not in aid
            assert manifest.scenario_id not in aid

        # 3. Normalized descriptions must NOT disclose the ground truth answer
        for desc in run.context.normalized_descriptions:
            assert spec.failure_type not in desc.lower()
            assert manifest.scenario_id not in desc

        # 4. Trace spans must not leak failure types in operation names
        for span in run.traces:
            assert f"execute_{spec.failure_type[:10]}" != span.operation
            assert "ground_truth" not in span.operation.lower()
            assert manifest.scenario_id not in span.operation

        # 5. Manifest must be completely isolated from telemetry payloads
        for log in run.logs:
            assert manifest.scenario_id not in log.message
        for metric in run.metrics:
            assert manifest.scenario_id not in metric.metric_name


def test_scenario_evaluator_all_24():
    """Run full benchmark evaluator on all 24 scenarios and check results."""
    evaluator = ScenarioEvaluator(seed=42)
    results = evaluator.evaluate_all_scenarios()
    assert len(results) == 24

    sufficient_res = [r for r in results if r.variant == "sufficient"]
    insufficient_res = [r for r in results if r.variant == "insufficient"]
    ambiguous_res = [r for r in results if r.variant == "ambiguous"]

    assert len(sufficient_res) == 8
    assert len(insufficient_res) == 8
    assert len(ambiguous_res) == 8

    # All runs must satisfy provenance, safety, ground-truth isolation, seed reproducibility
    for r in results:
        assert r.synthetic_provenance_validity is True
        assert r.ground_truth_leakage_free is True
        assert r.no_auto_remediation is True
        assert r.seed_reproducible is True
        assert r.evidence_reference_validity is True

    # Sufficient variants should match top-1 component and failure type when sufficient evidence is expected
    for r in sufficient_res:
        if r.expected_status == DiagnosisStatus.SUFFICIENT_EVIDENCE:
            assert r.top1_component_match is True
            assert r.failure_type_match is True
        else:
            assert r.top1_component_match is None
            assert r.competing_hypotheses_detected is True
        assert r.diagnosis_status_match is True

    # Insufficient variants expected to match expected status (insufficient_evidence) and distinguish tentative candidate
    for r in insufficient_res:
        assert r.diagnosis_status_match is True
        assert r.top1_component_match is None  # N/A: valid diagnosis not supposed to be produced
        assert r.failure_type_match is None
        assert r.tentative_distinguished is True

    # Ambiguous variants expected to match expected status (ambiguous) and represent competing hypotheses
    for r in ambiguous_res:
        assert r.diagnosis_status_match is True
        assert r.top1_component_match is None  # N/A: competing hypotheses present
        assert r.failure_type_match is None
        assert r.competing_hypotheses_detected is True


def test_inter_process_seed_reproducibility():
    """Verify that opaque incident IDs and telemetry are deterministic and process-independent."""
    import subprocess
    import sys

    code = """
from alert_management.stage4_analysis.telemetry.synthetic.generator import SyntheticTelemetryGenerator
from alert_management.stage4_analysis.telemetry.synthetic.scenarios import get_scenario_spec
spec = get_scenario_spec("db_pool_exhaustion", "sufficient")
run = SyntheticTelemetryGenerator(seed=42).generate_scenario_run(spec)
print(f"{run.context.incident_id}|{len(run.logs)}|{run.logs[0].log_id}|{run.metrics[0].value}")
"""
    cmd = [sys.executable, "-c", code]
    p1 = subprocess.run(cmd, capture_output=True, text=True, env={"PYTHONHASHSEED": "0", "PYTHONPATH": "src"})
    p2 = subprocess.run(cmd, capture_output=True, text=True, env={"PYTHONHASHSEED": "999999", "PYTHONPATH": "src"})

    assert p1.returncode == 0
    assert p2.returncode == 0
    assert p1.stdout.strip() == p2.stdout.strip()
    assert "INC-SYNTH-" in p1.stdout


def test_frozen_bundles_persistence_and_loading(tmp_path):
    """Verify frozen bundles and isolated manifests are persisted and loaded correctly."""
    from alert_management.stage4_analysis.telemetry.synthetic.frozen_bundles import (
        freeze_all_scenarios,
        load_frozen_bundles,
        load_frozen_manifests,
    )
    bundles, manifests = freeze_all_scenarios(tmp_path, seed=42)
    assert len(bundles) == 24
    assert len(manifests) == 24

    loaded_b = load_frozen_bundles(tmp_path)
    loaded_m = load_frozen_manifests(tmp_path)
    assert len(loaded_b) == 24
    assert len(loaded_m) == 24

    for b in loaded_b:
        assert b.telemetry_is_mock is True
        assert len(b.all_evidence) > 0 or b.missing_evidence
        assert b.incident_context.incident_id.startswith("INC-SYNTH-")
        # Ensure evaluation manifest does not leak into bundle fields
        assert not hasattr(b, "expected_root_cause_component")
        assert not hasattr(b, "expected_failure_type")


def test_provider_comparison_runner(tmp_path):
    """Verify comparison runner runs both providers against frozen bundles."""
    from alert_management.stage4_analysis.telemetry.synthetic.frozen_bundles import freeze_all_scenarios
    from alert_management.stage4_analysis.telemetry.synthetic.compare_providers import run_provider_comparison

    freeze_all_scenarios(tmp_path, seed=42)
    report = run_provider_comparison(frozen_dir=tmp_path)

    assert report.total_scenarios == 24
    assert len(report.records) == 24
    assert report.mock_provider_status == "AVAILABLE"
    # In test environment without NVIDIA_API_KEY, NIM status is cleanly recorded
    assert report.nim_provider_status in ("UNCONFIGURED", "AVAILABLE")

    for rec in report.records:
        assert rec.mock_outcome.available is True
        assert rec.mock_outcome.status_match is True
        assert rec.mock_outcome.evidence_reference_validity is True
        assert rec.mock_outcome.all_remediations_require_human_approval is True
