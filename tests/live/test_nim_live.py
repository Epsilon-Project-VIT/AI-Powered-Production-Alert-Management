"""
Live NVIDIA NIM integration tests.

These tests make REAL API calls and require:
- NVIDIA_API_KEY environment variable
- NVIDIA_NIM_MODEL environment variable

Run with: pytest -m nim_live tests/live/test_nim_live.py
Skip with: pytest -m "not nim_live"
"""

import pytest
import os
from pydantic import BaseModel, Field

from alert_management.llm import NIMConfig, NIMClient


pytestmark = pytest.mark.nim_live


@pytest.fixture(scope="module")
def nim_config():
    """
    Load NIM config from environment.
    
    Skip all tests if credentials not available.
    """
    try:
        config = NIMConfig.from_env()
        return config
    except ValueError as e:
        pytest.skip(f"NIM credentials not configured: {e}")


@pytest.fixture(scope="module")
def nim_client(nim_config):
    """Create NIM client for live tests."""
    return NIMClient(nim_config)


class SimpleResponse(BaseModel):
    """Simple test response schema."""
    answer: str = Field(..., description="The answer")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence")


def test_nim_smoke_connectivity(nim_client):
    """
    Smoke test: Basic NIM connectivity.
    
    Verifies API key is valid and model is accessible.
    """
    messages = [
        {"role": "user", "content": "Say 'hello' if you can read this."}
    ]
    
    response = nim_client.chat_completion(messages)
    
    assert "choices" in response
    assert len(response["choices"]) > 0
    assert "message" in response["choices"][0]
    assert "content" in response["choices"][0]["message"]
    
    content = response["choices"][0]["message"]["content"].lower()
    # Loose check - just verify we got some response
    assert len(content) > 0
    
    print(f"\n✓ NIM connectivity successful")
    print(f"  Model: {nim_client.config.model}")
    print(f"  Response length: {len(content)} chars")


def test_nim_structured_output_simple(nim_client):
    """
    Test structured JSON output with simple schema.
    """
    messages = [
        {
            "role": "user",
            "content": "What is 2+2? Provide your answer and confidence."
        }
    ]
    
    result = nim_client.chat_completion_structured(
        messages=messages,
        schema=SimpleResponse
    )
    
    assert isinstance(result, SimpleResponse)
    assert result.answer is not None
    assert 0.0 <= result.confidence <= 1.0
    
    print(f"\n✓ Structured output successful")
    print(f"  Answer: {result.answer}")
    print(f"  Confidence: {result.confidence}")


def test_nim_priority_classification_live(nim_client):
    """
    Test live Priority classification with real alert.
    """
    from alert_management.stage2_classification.nim_classifier import (
        NIMClassifier,
        NIMClassificationPrediction
    )
    
    classifier = NIMClassifier(nim_client.config)
    
    # Test alert from EA Sports
    result = classifier.predict_priority(
        client="EA Sports",
        description="application server unresponsive timeout errors increasing"
    )
    
    assert result.label in ["2 - High", "3 - Medium", "4 - Low"]
    assert 0.0 <= result.confidence <= 1.0
    
    print(f"\n✓ Priority classification successful")
    print(f"  Predicted: {result.label}")
    print(f"  Confidence: {result.confidence:.3f}")


def test_nim_routing_classification_live(nim_client):
    """
    Test live Routing classification with real alert.
    """
    from alert_management.stage2_classification.nim_classifier import NIMClassifier
    
    classifier = NIMClassifier(nim_client.config)
    
    # Test alert - should route to EA Sports based on client
    result = classifier.predict_routing(
        client="EA Sports",
        description="game server connection timeout"
    )
    
    valid_labels = [
        "Bridgestone",
        "EA Sports",
        "Pizza Hut Brands",
        "Product Support - Agility Loyalty"
    ]
    assert result.label in valid_labels
    assert 0.0 <= result.confidence <= 1.0
    
    print(f"\n✓ Routing classification successful")
    print(f"  Predicted: {result.label}")
    print(f"  Confidence: {result.confidence:.3f}")


def test_nim_correlation_adjudication_live(nim_client):
    """
    Test live correlation adjudication.
    """
    from alert_management.stage3_correlation.nim_adjudicator import (
        NIMCorrelationAdjudicator
    )
    
    adjudicator = NIMCorrelationAdjudicator(nim_client.config)
    
    # Two similar alerts (likely related)
    alert_a = {
        "client": "EA Sports",
        "timestamp": "2026-09-27T10:00:00",
        "description": "database connection timeout",
        "service": "game-service",
        "component": "database",
        "stage2_predictions": {"priority": "2 - High"}
    }
    
    alert_b = {
        "client": "EA Sports",
        "timestamp": "2026-09-27T10:05:00",
        "description": "database query slow performance",
        "service": "game-service",
        "component": "database",
        "stage2_predictions": {"priority": "2 - High"}
    }
    
    result = adjudicator.adjudicate(
        alert_a=alert_a,
        alert_b=alert_b,
        semantic_similarity=0.85,
        temporal_gap=300.0,  # 5 minutes
        correlation_score=0.82
    )
    
    assert result.decision in ["related", "unrelated", "ambiguous"]
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.rationale) > 0
    
    print(f"\n✓ Correlation adjudication successful")
    print(f"  Decision: {result.decision}")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Rationale: {result.rationale[:100]}...")


def test_nim_stage4_rca_reasoning_live(nim_client):
    """
    Test live Stage 4 RCA reasoning with EA Sports incident.
    """
    from datetime import datetime, timedelta
    from alert_management.stage4_analysis.reasoning.nim_reasoning_provider import (
        NIMReasoningProvider
    )
    from alert_management.stage4_analysis.schemas import (
        IncidentContext,
        Evidence,
        SourceType,
        ProbableRootCause
    )
    
    provider = NIMReasoningProvider(nim_client.config)
    
    # Create simple incident context
    now = datetime.now()
    context = IncidentContext(
        incident_id="TEST-NIM-001",
        client="EA Sports",
        alert_ids=["ALERT-001", "ALERT-002"],
        primary_alert_id="ALERT-001",
        incident_start=now,
        incident_end=now + timedelta(minutes=5),
        alert_count=2,
        services=["game-service"],
        components=["database"],
        normalized_descriptions=[
            "database connection timeout",
            "database query slow performance"
        ],
        diagnostic_start=now - timedelta(minutes=10),
        diagnostic_end=now + timedelta(minutes=15)
    )
    
    # Create mock evidence
    evidence = [
        Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="mock_log_001",
            timestamp=now,
            description="Database connection pool exhausted",
            weight=0.9,
            is_mock=True
        ),
        Evidence(
            source="metrics",
            source_type=SourceType.MOCK,
            source_id="mock_metric_001",
            timestamp=now,
            description="DB connection pool utilization at 100%",
            weight=0.85,
            is_mock=True
        )
    ]
    
    # Create candidate hypotheses
    candidates = [
        {
            "component": "database",
            "failure_type": "connection_pool_exhaustion",
            "confidence": 0.85,
            "description": "Database connection pool reached capacity",
            "supporting_evidence_ids": ["mock_log_001", "mock_metric_001"]
        }
    ]
    
    # Call NIM for RCA
    result = provider.synthesize_rca(
        context=context,
        evidence=evidence,
        candidate_hypotheses=candidates,
        historical_patterns=[]
    )
    
    assert "diagnosis_status" in result
    assert "support_communication" in result
    assert "stakeholder_communication" in result
    
    print(f"\n✓ Stage 4 RCA reasoning successful")
    print(f"  Diagnosis: {result['diagnosis_status']}")
    print(f"  Probable RCA: {result.get('probable_root_cause')}")
    print(f"  Missing evidence: {result.get('missing_evidence', [])}")
    print(f"  Actions: {len(result.get('recommended_actions', []))}")


if __name__ == "__main__":
    """
    Run live tests directly:
    $ export NVIDIA_API_KEY=your_key
    $ export NVIDIA_NIM_MODEL=meta/llama-3.1-70b-instruct
    $ python tests/live/test_nim_live.py
    """
    pytest.main([__file__, "-v", "-s"])
