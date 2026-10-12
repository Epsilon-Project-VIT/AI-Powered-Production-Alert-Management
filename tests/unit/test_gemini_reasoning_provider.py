"""
Unit tests for Gemini Reasoning Provider and Stage 4 Integration.

All tests run completely offline using mocked Gemini responses.
No network calls or live API keys are used.
"""

import os
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import pytest
import requests

from alert_management.llm import (
    GeminiConfig,
    GeminiClient,
    GeminiAuthenticationError,
    GeminiConfigurationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiProviderError,
    GeminiStructuredOutputError,
)
from alert_management.stage4_analysis.reasoning import (
    GeminiReasoningProvider,
    GeminiRCAOutput,
    GeminiRCACache,
    MockReasoningProvider,
    get_reasoning_provider,
)
from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    Evidence,
    SourceType,
    DiagnosisStatus,
    ActionType,
    ProbableRootCause,
)


@pytest.fixture
def mock_gemini_config():
    """Create test configuration with non-secret dummy key."""
    return GeminiConfig(
        api_key="test-dummy-api-key-12345",
        model="gemini-2.5-flash",
        enabled=True,
        timeout_seconds=5,
        max_retries=1,
        rpm_limit=60
    )


@pytest.fixture
def sample_incident_context():
    """Create sample incident context."""
    now = datetime(2026, 10, 11, 12, 0, 0)
    return IncidentContext(
        incident_id="INC-SYNTH-99001",
        client="EA Sports",
        alert_ids=["ALT-001", "ALT-002"],
        primary_alert_id="ALT-001",
        incident_start=now,
        incident_end=now + timedelta(minutes=15),
        alert_count=2,
        services=["game-server", "database"],
        components=["database"],
        normalized_descriptions=[
            "High database connection pool utilization",
            "Timeout acquiring database connection"
        ],
        diagnostic_start=now - timedelta(minutes=15),
        diagnostic_end=now + timedelta(minutes=30)
    )


@pytest.fixture
def sample_evidence():
    """Create sample valid evidence items."""
    now = datetime(2026, 10, 11, 12, 0, 0)
    return [
        Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="ev_log_db_pool_01",
            timestamp=now,
            description="DB connection pool saturation: 100/100 active connections",
            weight=0.9,
            is_mock=True
        ),
        Evidence(
            source="metrics",
            source_type=SourceType.MOCK,
            source_id="ev_metric_db_pool_02",
            timestamp=now,
            description="db_connection_pool_utilization reached 100% threshold",
            weight=0.85,
            is_mock=True
        )
    ]


# ---------------------------------------------------------------------------
# 1. Configuration & Security Tests
# ---------------------------------------------------------------------------

def test_gemini_config_loading_and_missing_key():
    """Verify GeminiConfig loads from environment and raises ValueError when key is absent."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-secret-key-xyz", "GEMINI_MODEL": "gemini-1.5-flash"}, clear=True):
        config = GeminiConfig.from_env(load_env=False)
        assert config.model == "gemini-1.5-flash"
        assert config.api_key == "test-secret-key-xyz"

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiConfig.from_env(load_env=False)
        assert GeminiConfig.try_from_env(load_env=False) is None


def test_gemini_config_repr_does_not_leak_api_key(mock_gemini_config):
    """Verify repr(GeminiConfig) does NOT expose the API key."""
    config_repr = repr(mock_gemini_config)
    assert "test-dummy-api-key-12345" not in config_repr
    assert "api_key" not in config_repr or "test-dummy-api-key-12345" not in config_repr


# ---------------------------------------------------------------------------
# 2. Response Parsing & Evidence Grounding Tests
# ---------------------------------------------------------------------------

def test_gemini_successful_rca_parsing(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify valid Gemini response is parsed into RCAResult with valid evidence IDs."""
    mock_client = Mock()
    mock_client.chat_completion_structured.return_value = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.88,
            "description": "Database connection pool saturated under peak load",
            "supporting_evidence_ids": ["ev_log_db_pool_01", "ev_metric_db_pool_02"]
        },
        alternative_hypotheses=[
            {
                "component": "game-server",
                "failure_type": "request_spike",
                "confidence": 0.35,
                "reason_for_lower_rank": "Telemetry shows DB pool exhausted before server errors"
            }
        ],
        missing_evidence=[],
        recommended_actions=[
            {
                "action": "Increase connection pool maximum limit",
                "priority": 1,
                "action_type": "remediation",
                "rationale": "Mitigate pool saturation",
                "requires_human_approval": False  # Should be overridden to True!
            }
        ],
        support_communication="DB pool exhaustion confirmed.",
        stakeholder_communication="Database degradation being investigated."
    )

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    candidates = [
        ProbableRootCause(
            component="database",
            failure_type="pool_exhaustion",
            confidence=0.85,
            description="Pre-ranked candidate"
        )
    ]

    result = provider.analyze(
        context=sample_incident_context,
        evidence=sample_evidence,
        rca_candidates=candidates
    )

    assert result.diagnosis_status == DiagnosisStatus.SUFFICIENT_EVIDENCE
    assert result.probable_root_cause is not None
    assert result.probable_root_cause.component == "database"
    assert result.probable_root_cause.failure_type == "pool_exhaustion"
    assert result.probable_root_cause.confidence == 0.88
    assert set(result.probable_root_cause.supporting_evidence_ids) == {"ev_log_db_pool_01", "ev_metric_db_pool_02"}
    assert result.reasoning_provider == "gemini"
    assert result.human_review_required is True
    # Mandatory policy gate check:
    assert result.recommended_actions[0].requires_human_approval is True


def test_gemini_unknown_evidence_ids_rejection(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify hallucinated/unknown evidence IDs in Gemini output are strictly rejected."""
    mock_client = Mock()
    mock_client.chat_completion_structured.return_value = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.90,
            "description": "Root cause",
            "supporting_evidence_ids": ["ev_log_db_pool_01", "hallucinated_unknown_ev_999"]
        },
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    synth = provider.synthesize_rca(sample_incident_context, sample_evidence, [])

    prc = synth["probable_root_cause"]
    assert prc is not None
    # Unknown ID must have been stripped
    assert "hallucinated_unknown_ev_999" not in prc.supporting_evidence_ids
    assert prc.supporting_evidence_ids == ["ev_log_db_pool_01"]


# ---------------------------------------------------------------------------
# 3. Error Handling, Rate Limiting & Explicit Fallback Tests
# ---------------------------------------------------------------------------

def test_gemini_malformed_json_triggers_explicit_fallback(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify malformed JSON/schema output triggers explicit fallback with no guessed root cause."""
    mock_client = Mock()
    mock_client.chat_completion_structured.side_effect = GeminiStructuredOutputError("JSON schema mismatch")

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    result = provider.analyze(sample_incident_context, sample_evidence, [])

    assert result.diagnosis_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert result.probable_root_cause is None
    assert result.reasoning_provider == "gemini_fallback"
    assert any("schema_validation_error" in r for r in result.review_reasons)
    assert result.human_review_required is True


def test_gemini_auth_error_triggers_explicit_fallback(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify HTTP 401/403 authentication failure triggers safe fallback without leaking credentials."""
    mock_client = Mock()
    mock_client.chat_completion_structured.side_effect = GeminiAuthenticationError("Authentication failed")

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    result = provider.analyze(sample_incident_context, sample_evidence, [])

    assert result.diagnosis_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert result.probable_root_cause is None
    assert result.reasoning_provider == "gemini_fallback"
    assert any("authentication_error" in r for r in result.review_reasons)
    # Ensure dummy API key is never present in review reasons or comms
    assert mock_gemini_config.api_key not in result.support_communication
    assert mock_gemini_config.api_key not in str(result.review_reasons)


def test_gemini_rate_limit_429_triggers_explicit_fallback(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify HTTP 429 rate limit exceeded triggers rate_limit_exceeded fallback."""
    mock_client = Mock()
    mock_client.chat_completion_structured.side_effect = GeminiRateLimitError("Rate limit exceeded")

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    result = provider.analyze(sample_incident_context, sample_evidence, [])

    assert result.diagnosis_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert result.probable_root_cause is None
    assert result.reasoning_provider == "gemini_fallback"
    assert any("rate_limit_exceeded" in r for r in result.review_reasons)


def test_gemini_timeout_triggers_explicit_fallback(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify network timeout triggers timeout fallback."""
    mock_client = Mock()
    mock_client.chat_completion_structured.side_effect = GeminiTimeoutError("Request timed out")

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    result = provider.analyze(sample_incident_context, sample_evidence, [])

    assert result.diagnosis_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert result.probable_root_cause is None
    assert result.reasoning_provider == "gemini_fallback"
    assert any("timeout" in r for r in result.review_reasons)


def test_client_http_429_retries_and_raises_rate_limit_error():
    """Verify GeminiClient handles HTTP 429 response headers and raises GeminiRateLimitError."""
    config = GeminiConfig(api_key="test-key", max_retries=1, rpm_limit=100)
    client = GeminiClient(config)

    mock_resp_429 = Mock(spec=requests.Response)
    mock_resp_429.status_code = 429
    mock_resp_429.headers = {"Retry-After": "0.01"}

    with patch.object(client.session, "post", return_value=mock_resp_429):
        with pytest.raises(GeminiRateLimitError, match="rate limit"):
            client.chat_completion([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# 4. Safety & Policy Gate Tests
# ---------------------------------------------------------------------------

def test_human_approval_mandatory_for_remediation(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify Gemini can never auto-approve remediation actions."""
    mock_client = Mock()
    mock_client.chat_completion_structured.return_value = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        recommended_actions=[
            {
                "action": "Restart database server",
                "priority": 1,
                "action_type": "remediation",
                "requires_human_approval": False
            },
            {
                "action": "Check thread dump",
                "priority": 2,
                "action_type": "diagnostic",
                "requires_human_approval": False
            }
        ],
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    synth = provider.synthesize_rca(sample_incident_context, sample_evidence, [])

    actions = synth["recommended_actions"]
    assert len(actions) == 2
    # Remediation MUST require human approval regardless of LLM suggestion
    assert actions[0].action_type == ActionType.REMEDIATION
    assert actions[0].requires_human_approval is True
    # Diagnostic can stay False
    assert actions[1].action_type == ActionType.DIAGNOSTIC
    assert actions[1].requires_human_approval is False


# ---------------------------------------------------------------------------
# 5. Caching & Deduplication Tests
# ---------------------------------------------------------------------------

def test_gemini_rca_cache_deduplication(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify identical incident context and evidence sets use cache and avoid redundant API calls."""
    mock_client = Mock()
    mock_client.chat_completion_structured.return_value = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.88,
            "supporting_evidence_ids": ["ev_log_db_pool_01"]
        },
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )

    cache = GeminiRCACache(max_size=10)
    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client, cache=cache)

    # First call: invokes client
    res1 = provider.synthesize_rca(sample_incident_context, sample_evidence, [])
    assert provider.request_count == 1
    assert provider.cache_hit_count == 0

    # Second call: uses cache
    res2 = provider.synthesize_rca(sample_incident_context, sample_evidence, [])
    assert provider.request_count == 1
    assert provider.cache_hit_count == 1
    assert res1["probable_root_cause"].component == res2["probable_root_cause"].component


# ---------------------------------------------------------------------------
# 6. Provider Factory & Mock Preservation Tests
# ---------------------------------------------------------------------------

def test_preservation_of_mock_reasoning_provider():
    """Verify MockReasoningProvider is preserved and functional."""
    mock_prov = get_reasoning_provider("mock")
    assert isinstance(mock_prov, MockReasoningProvider)
    assert mock_prov.get_provider_type() == "mock"


def test_factory_function_configurable_selection(mock_gemini_config):
    """Verify get_reasoning_provider instantiates appropriate provider based on setting."""
    with patch.dict(os.environ, {"REASONING_PROVIDER": "mock"}):
        p = get_reasoning_provider()
        assert isinstance(p, MockReasoningProvider)

    with patch.dict(os.environ, {"REASONING_PROVIDER": "gemini", "GEMINI_API_KEY": "dummy-key"}):
        p = get_reasoning_provider()
        assert isinstance(p, GeminiReasoningProvider)

    with pytest.raises(ValueError, match="Unknown reasoning provider"):
        get_reasoning_provider("invalid_provider_name")


def test_factory_function_model_override():
    """Verify get_reasoning_provider accepts and applies model override."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
        p = get_reasoning_provider("gemini", model="gemini-3.5-flash-lite")
        assert isinstance(p, GeminiReasoningProvider)
        assert p.config.model == "gemini-3.5-flash-lite"


def test_gemini_provider_model_selection():
    """Verify GeminiReasoningProvider respects model passed in constructor."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
        provider = GeminiReasoningProvider(model="gemini-3.1-flash-lite")
        assert provider.config.model == "gemini-3.1-flash-lite"


# ---------------------------------------------------------------------------
# 7. Grounding, Citation Verification & Safe Downgrade Tests
# ---------------------------------------------------------------------------

def test_gemini_sufficient_evidence_without_ids_triggers_correction_and_safe_downgrade(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify sufficient_evidence with 0 valid IDs triggers correction and safely downgrades to ambiguous/insufficient."""
    mock_client = Mock()
    # Both initial request and correction return response without valid IDs
    uncited_output = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.85,
            "description": "Database connection pool exhausted",
            "supporting_evidence_ids": []
        },
        alternative_hypotheses=[
            {
                "component": "application",
                "failure_type": "leak",
                "confidence": 0.40,
                "reason_for_lower_rank": "Less likely"
            }
        ],
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )
    mock_client.chat_completion_structured.return_value = uncited_output

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    res = provider.analyze(sample_incident_context, sample_evidence, [])

    # Must have triggered correction request (2 total requests)
    assert provider.request_count == 2
    assert provider.correction_count == 1
    # Must have safely downgraded because 0 valid evidence IDs exist!
    assert res.diagnosis_status in (DiagnosisStatus.AMBIGUOUS, DiagnosisStatus.INSUFFICIENT_EVIDENCE)
    assert res.probable_root_cause is not None
    assert res.probable_root_cause.is_tentative is True
    assert res.probable_root_cause.confidence <= 0.35
    assert res.probable_root_cause.supporting_evidence_ids == []


def test_gemini_sufficient_evidence_succeeds_after_controlled_correction(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify sufficient_evidence initially uncited succeeds when correction supplies valid IDs."""
    mock_client = Mock()
    # Call 1: uncited
    uncited_output = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.85,
            "description": "Database connection pool exhausted",
            "supporting_evidence_ids": []
        },
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )
    # Call 2: corrected with valid evidence ID
    corrected_output = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.88,
            "description": "Database connection pool exhausted",
            "supporting_evidence_ids": ["ev_log_db_pool_01"]
        },
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )
    mock_client.chat_completion_structured.side_effect = [uncited_output, corrected_output]

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    res = provider.analyze(sample_incident_context, sample_evidence, [])

    assert provider.request_count == 2
    assert provider.correction_count == 1
    assert res.diagnosis_status == DiagnosisStatus.SUFFICIENT_EVIDENCE
    assert res.probable_root_cause is not None
    assert res.probable_root_cause.is_tentative is False
    assert res.probable_root_cause.supporting_evidence_ids == ["ev_log_db_pool_01"]


def test_gemini_all_hallucinated_evidence_ids_downgrades_safely(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify that when all cited IDs are hallucinated/unknown, it downgrades safely without inventing IDs."""
    mock_client = Mock()
    hallucinated_output = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.90,
            "description": "Database connection pool exhausted",
            "supporting_evidence_ids": ["completely_invented_id_123", "fake_evidence_456"]
        },
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )
    mock_client.chat_completion_structured.return_value = hallucinated_output

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    res = provider.analyze(sample_incident_context, sample_evidence, [])

    # All hallucinated IDs stripped, 0 remain -> downgrades safely
    assert res.diagnosis_status != DiagnosisStatus.SUFFICIENT_EVIDENCE
    assert res.probable_root_cause is not None
    assert res.probable_root_cause.is_tentative is True
    assert res.probable_root_cause.supporting_evidence_ids == []


def test_gemini_uncertain_ambiguous_preserves_hypotheses_without_rejection(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify valid uncertain / ambiguous diagnosis is preserved and not rejected."""
    mock_client = Mock()
    ambiguous_output = GeminiRCAOutput(
        diagnosis_status="ambiguous",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.50,
            "description": "Possible DB pool exhaustion",
            "supporting_evidence_ids": ["ev_log_db_pool_01"]
        },
        alternative_hypotheses=[
            {
                "component": "application",
                "failure_type": "memory_leak",
                "confidence": 0.48,
                "reason_for_lower_rank": "Competing hypothesis with similar evidence weight"
            }
        ],
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )
    mock_client.chat_completion_structured.return_value = ambiguous_output

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    res = provider.analyze(sample_incident_context, sample_evidence, [])

    # Ambiguous does not trigger correction
    assert provider.request_count == 1
    assert provider.correction_count == 0
    assert res.diagnosis_status == DiagnosisStatus.AMBIGUOUS
    assert res.probable_root_cause.is_tentative is True
    assert len(res.alternative_hypotheses) == 1
    assert res.alternative_hypotheses[0].component == "application"


def test_gemini_provenance_and_human_approval_preserved(mock_gemini_config, sample_incident_context, sample_evidence):
    """Verify telemetry and reasoning provenance flags and human approval requirements are enforced."""
    mock_client = Mock()
    mock_client.chat_completion_structured.return_value = GeminiRCAOutput(
        diagnosis_status="sufficient_evidence",
        probable_root_cause={
            "component": "database",
            "failure_type": "pool_exhaustion",
            "confidence": 0.85,
            "description": "Database connection pool saturated",
            "supporting_evidence_ids": ["ev_log_db_pool_01"]
        },
        recommended_actions=[
            {
                "action": "Restart database instance",
                "priority": 1,
                "action_type": "remediation",
                "requires_human_approval": False  # Must be forced to True
            }
        ],
        support_communication="Tech comm",
        stakeholder_communication="Biz comm"
    )

    provider = GeminiReasoningProvider(config=mock_gemini_config, client=mock_client)
    res = provider.analyze(sample_incident_context, sample_evidence, [])

    assert res.reasoning_provider == "gemini"
    assert res.telemetry_is_mock is True
    assert res.human_review_required is True
    assert res.recommended_actions[0].requires_human_approval is True


