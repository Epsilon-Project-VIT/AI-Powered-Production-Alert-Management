import json
from unittest.mock import Mock

import pytest
import requests

from alert_management.llm import GeminiClient, GeminiConfig
from alert_management.llm.exceptions import NIMProviderError, NIMStructuredOutputError, NIMTimeoutError
from alert_management.stage2_classification.gemini_classifier import GeminiClassificationPrediction, GeminiClassifier
from alert_management.stage2_classification.schemas import ClassificationResult


@pytest.fixture
def config():
    return GeminiConfig(api_key="test-key", enabled=True, max_retries=0)


def fallback():
    return ClassificationResult(label="3 - Medium", confidence=0.42)


def prediction(label="2 - High", model=None):
    model_name = model or GeminiConfig.model_fields["model"].default
    return GeminiClassificationPrediction(predicted_label=label, confidence=0.8, reason="arrival-time alert fields", model=model_name)


def test_valid_priority_response_preserves_gemini_provenance(config):
    client = Mock()
    client.chat_completion_structured.return_value = prediction()
    result = GeminiClassifier(config, client).predict_priority("EA Sports", "server timeout", fallback)
    assert (result.label, result.provider, result.model, result.is_fallback) == ("2 - High", "gemini", config.model, False)


def test_invalid_label_uses_deterministic_fallback(config):
    client = Mock()
    client.chat_completion_structured.return_value = prediction("1 - Critical")
    classifier = GeminiClassifier(config, client)
    result = classifier.predict_priority("EA Sports", "server timeout", fallback)
    assert result.is_fallback and result.label == "3 - Medium"
    assert classifier.schema_failure_count == 1

@pytest.mark.parametrize("response", [
    {"choices": [{"message": {"content": "not-json"}}]},
    {"choices": [{"message": {"content": json.dumps({"predicted_label": "2 - High"})}}]},
])
def test_malformed_or_missing_structured_output_is_rejected(config, response):
    client = GeminiClient(config)
    client.chat_completion = Mock(return_value=response)
    with pytest.raises(NIMStructuredOutputError):
        client.chat_completion_structured([{"role": "user", "content": "x"}], GeminiClassificationPrediction)


def test_timeout_and_api_error_use_fallback(config):
    for error in (NIMTimeoutError("timeout"), NIMProviderError("api")):
        client = Mock()
        client.chat_completion_structured.side_effect = error
        result = GeminiClassifier(config, client).predict_priority("EA Sports", "server timeout", fallback)
        assert result.is_fallback


def test_arrival_time_payload_rejects_leakage_and_filters_metadata():
    with pytest.raises(ValueError):
        GeminiClassifier.arrival_time_input("EA Sports", "timeout", {"Priority": "2 - High"})
    payload = GeminiClassifier.arrival_time_input("EA Sports", "timeout", {"Active": True, "noise": "x"})
    assert payload["metadata"] == {"Active": True}
