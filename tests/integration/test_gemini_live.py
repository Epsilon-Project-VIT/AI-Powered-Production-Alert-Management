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
