"""Explicit live Gemini smoke test; excluded unless credentials and enablement exist."""
import os
import pytest
from alert_management.llm import GeminiConfig
from alert_management.stage2_classification.gemini_classifier import GeminiClassifier
from alert_management.stage2_classification.schemas import ClassificationResult

pytestmark = pytest.mark.gemini_live

@pytest.fixture(scope="module")
def config():
    if os.getenv("RUN_GEMINI_LIVE_TESTS", "false").lower() != "true":
        pytest.skip("set RUN_GEMINI_LIVE_TESTS=true to permit a live request")
    config = GeminiConfig.try_from_env()
    if config is None or not config.enabled:
        pytest.skip("Gemini is not enabled or credentials are unavailable")
    return config

def test_gemini_stage2_priority_smoke(config):
    result = GeminiClassifier(config).predict_priority(
        "EA Sports", "application server unresponsive timeout errors increasing",
        lambda: ClassificationResult(label="3 - Medium", confidence=0.0),
    )
    assert result.label in {"2 - High", "3 - Medium", "4 - Low"}


def test_gemini_stage4_rca_live(config):
    """Controlled live Stage 4 RCA test using an anonymized synthetic incident."""
    from datetime import datetime, timedelta
    from alert_management.stage4_analysis.reasoning.gemini_reasoning_provider import GeminiReasoningProvider
    from alert_management.stage4_analysis.schemas import (
        IncidentContext,
        Evidence,
        SourceType,
        ProbableRootCause,
        DiagnosisStatus,
    )

    provider = GeminiReasoningProvider(config)
    now = datetime.now()
    context = IncidentContext(
        incident_id="TEST-GEMINI-LIVE-001",
        client="EA Sports",
        alert_ids=["ALT-LIVE-001", "ALT-LIVE-002"],
        primary_alert_id="ALT-LIVE-001",
        incident_start=now,
        incident_end=now + timedelta(minutes=10),
        alert_count=2,
        services=["game-server", "database"],
        components=["database"],
        normalized_descriptions=[
            "High database connection pool utilization",
            "Timeout acquiring database connection from pool"
        ],
        diagnostic_start=now - timedelta(minutes=15),
        diagnostic_end=now + timedelta(minutes=25)
    )
    evidence = [
        Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="live_test_ev_01",
            timestamp=now,
            description="Database connection pool exhausted: 100/100 active connections",
            weight=0.9,
            is_mock=True
        ),
        Evidence(
            source="metrics",
            source_type=SourceType.MOCK,
            source_id="live_test_ev_02",
            timestamp=now,
            description="db_connection_pool_utilization reached 100% threshold",
            weight=0.85,
            is_mock=True
        )
    ]
    candidates = [
        ProbableRootCause(
            component="database",
            failure_type="pool_exhaustion",
            confidence=0.85,
            description="Database connection pool exhaustion"
        )
    ]

    rca_result = provider.analyze(context, evidence, candidates)

    assert rca_result.incident_id == "TEST-GEMINI-LIVE-001"
    assert rca_result.diagnosis_status in {
        DiagnosisStatus.SUFFICIENT_EVIDENCE,
        DiagnosisStatus.AMBIGUOUS,
        DiagnosisStatus.INSUFFICIENT_EVIDENCE
    }
    assert rca_result.human_review_required is True
    if rca_result.probable_root_cause:
        valid_ids = {e.source_id for e in evidence}
        for ref_id in rca_result.probable_root_cause.supporting_evidence_ids:
            assert ref_id in valid_ids
