"""
Unit tests for NVIDIA NIM client (offline, no API calls).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from pydantic import BaseModel, Field

from alert_management.llm import (
    NIMConfig,
    NIMClient,
    NIMAuthenticationError,
    NIMConfigurationError,
    NIMRateLimitError,
    NIMTimeoutError,
    NIMProviderError,
    NIMStructuredOutputError
)


class SampleSchema(BaseModel):
    """Sample schema for structured output tests."""
    label: str = Field(..., description="Label field")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence")


@pytest.fixture
def nim_config():
    """Create test NIM configuration."""
    return NIMConfig(
        api_key="test_key_12345",
        model="test/model",
        enabled=True,
        timeout_seconds=10,
        max_retries=2
    )


@pytest.fixture
def nim_client(nim_config):
    """Create NIM client with test config."""
    return NIMClient(nim_config)


def test_client_initialization(nim_client, nim_config):
    """Test client initializes with correct config."""
    assert nim_client.config == nim_config
    assert "Authorization" in nim_client.session.headers
    # Verify Authorization header exists (but we expect the key to be in the header)
    assert nim_client.session.headers["Authorization"].startswith("Bearer ")


def test_client_does_not_leak_api_key_in_logs(caplog, nim_config):
    """Test that API key is never logged."""
    client = NIMClient(nim_config)
    # Check that API key is not in any log messages
    for record in caplog.records:
        assert "test_key_12345" not in record.message
        assert "Bearer" not in record.message


@patch('requests.Session.post')
def test_chat_completion_success(mock_post, nim_client):
    """Test successful chat completion."""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "Test response"}}
        ]
    }
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    result = nim_client.chat_completion(messages)
    
    assert result["choices"][0]["message"]["content"] == "Test response"
    mock_post.assert_called_once()


@patch('requests.Session.post')
def test_authentication_error_401(mock_post, nim_client):
    """Test 401 authentication error."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMAuthenticationError) as exc_info:
        nim_client.chat_completion(messages)
    
    assert "Authentication failed" in str(exc_info.value)
    assert "401" in str(exc_info.value)


@patch('requests.Session.post')
def test_authentication_error_403(mock_post, nim_client):
    """Test 403 authorization error."""
    mock_response = Mock()
    mock_response.status_code = 403
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMAuthenticationError) as exc_info:
        nim_client.chat_completion(messages)
    
    assert "Authentication failed" in str(exc_info.value)
    assert "403" in str(exc_info.value)


@patch('requests.Session.post')
def test_configuration_error_404(mock_post, nim_client):
    """Test 404 model/endpoint not found."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMConfigurationError) as exc_info:
        nim_client.chat_completion(messages)
    
    assert "not found" in str(exc_info.value).lower()
    assert "404" in str(exc_info.value)


@patch('requests.Session.post')
@patch('time.sleep')  # Mock sleep to speed up test
def test_rate_limit_429_with_retry(mock_sleep, mock_post, nim_client):
    """Test 429 rate limit with retry."""
    # First call: 429, second call: 200
    mock_response_429 = Mock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}
    
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {
        "choices": [{"message": {"content": "Success after retry"}}]
    }
    
    mock_post.side_effect = [mock_response_429, mock_response_200]
    
    messages = [{"role": "user", "content": "Test"}]
    result = nim_client.chat_completion(messages)
    
    assert result["choices"][0]["message"]["content"] == "Success after retry"
    assert mock_post.call_count == 2
    mock_sleep.assert_called_once()


@patch('requests.Session.post')
@patch('time.sleep')
def test_rate_limit_exhausted(mock_sleep, mock_post, nim_client):
    """Test rate limit with max retries exhausted."""
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "1"}
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMRateLimitError) as exc_info:
        nim_client.chat_completion(messages)
    
    assert "max retries exhausted" in str(exc_info.value).lower()


@patch('requests.Session.post')
@patch('time.sleep')
def test_timeout_408_with_retry(mock_sleep, mock_post, nim_client):
    """Test 408 timeout with retry."""
    # First call: 408, second call: 200
    mock_response_408 = Mock()
    mock_response_408.status_code = 408
    
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {
        "choices": [{"message": {"content": "Success after timeout retry"}}]
    }
    
    mock_post.side_effect = [mock_response_408, mock_response_200]
    
    messages = [{"role": "user", "content": "Test"}]
    result = nim_client.chat_completion(messages)
    
    assert result["choices"][0]["message"]["content"] == "Success after timeout retry"
    assert mock_post.call_count == 2


@patch('requests.Session.post')
def test_client_timeout_error(mock_post, nim_client):
    """Test client-side timeout."""
    mock_post.side_effect = requests.Timeout("Connection timeout")
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMTimeoutError) as exc_info:
        nim_client.chat_completion(messages)
    
    assert "timeout" in str(exc_info.value).lower()


@patch('requests.Session.post')
@patch('time.sleep')
def test_server_error_5xx_with_retry(mock_sleep, mock_post, nim_client):
    """Test 5xx server error with retry."""
    # First call: 500, second call: 200
    mock_response_500 = Mock()
    mock_response_500.status_code = 500
    mock_response_500.text = "Internal Server Error"
    
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {
        "choices": [{"message": {"content": "Success after server error"}}]
    }
    
    mock_post.side_effect = [mock_response_500, mock_response_200]
    
    messages = [{"role": "user", "content": "Test"}]
    result = nim_client.chat_completion(messages)
    
    assert result["choices"][0]["message"]["content"] == "Success after server error"
    assert mock_post.call_count == 2


@patch('requests.Session.post')
@patch('time.sleep')
def test_server_error_exhausted(mock_sleep, mock_post, nim_client):
    """Test 5xx with max retries exhausted."""
    mock_response = Mock()
    mock_response.status_code = 503
    mock_response.text = "Service Unavailable"
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMProviderError) as exc_info:
        nim_client.chat_completion(messages)
    
    assert "max retries exhausted" in str(exc_info.value).lower()


@patch('requests.Session.post')
def test_malformed_response(mock_post, nim_client):
    """Test malformed JSON response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(Exception):  # Will raise during json parsing
        nim_client.chat_completion(messages)


@patch('requests.Session.post')
def test_structured_output_success(mock_post, nim_client):
    """Test successful structured output."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"label": "test_label", "confidence": 0.85}'
            }
        }]
    }
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    result = nim_client.chat_completion_structured(messages, SampleSchema)
    
    assert isinstance(result, SampleSchema)
    assert result.label == "test_label"
    assert result.confidence == 0.85


@patch('requests.Session.post')
def test_structured_output_invalid_json(mock_post, nim_client):
    """Test structured output with invalid JSON."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": 'This is not JSON'
            }
        }]
    }
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMStructuredOutputError) as exc_info:
        nim_client.chat_completion_structured(messages, SampleSchema)
    
    assert "not valid JSON" in str(exc_info.value)


@patch('requests.Session.post')
def test_structured_output_missing_field(mock_post, nim_client):
    """Test structured output missing required field."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"confidence": 0.85}'  # Missing 'label'
            }
        }]
    }
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMStructuredOutputError) as exc_info:
        nim_client.chat_completion_structured(messages, SampleSchema)
    
    assert "doesn't match schema" in str(exc_info.value)


@patch('requests.Session.post')
def test_structured_output_invalid_value(mock_post, nim_client):
    """Test structured output with invalid value (confidence > 1.0)."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"label": "test", "confidence": 1.5}'  # Invalid: > 1.0
            }
        }]
    }
    mock_post.return_value = mock_response
    
    messages = [{"role": "user", "content": "Test"}]
    
    with pytest.raises(NIMStructuredOutputError) as exc_info:
        nim_client.chat_completion_structured(messages, SampleSchema)
    
    assert "doesn't match schema" in str(exc_info.value)


@patch('requests.Session.post')
def test_extract_text_content_success(mock_post, nim_client):
    """Test extracting text content from response."""
    response = {
        "choices": [{
            "message": {"content": "Extracted text"}
        }]
    }
    
    content = nim_client.extract_text_content(response)
    assert content == "Extracted text"


def test_extract_text_content_missing_choices(nim_client):
    """Test extracting content from malformed response."""
    response = {"invalid": "structure"}
    
    with pytest.raises(NIMProviderError) as exc_info:
        nim_client.extract_text_content(response)
    
    assert "malformed" in str(exc_info.value).lower()


def test_nim_config_from_env_missing_key(monkeypatch):
    """Test config loading with missing API key."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "test/model")
    
    # Mock load_dotenv so it doesn't re-read .env and override monkeypatch
    with patch("alert_management.llm.config.load_dotenv"):
        with pytest.raises(ValueError) as exc_info:
            NIMConfig.from_env()
    
    assert "NVIDIA_API_KEY" in str(exc_info.value)


def test_nim_config_from_env_missing_model(monkeypatch):
    """Test config loading with missing model."""
    monkeypatch.setenv("NVIDIA_API_KEY", "test_key")
    monkeypatch.delenv("NVIDIA_NIM_MODEL", raising=False)
    
    # Mock load_dotenv so it doesn't re-read .env and override monkeypatch
    with patch("alert_management.llm.config.load_dotenv"):
        with pytest.raises(ValueError) as exc_info:
            NIMConfig.from_env()
    
    assert "NVIDIA_NIM_MODEL" in str(exc_info.value)


def test_nim_config_from_env_success(monkeypatch):
    """Test successful config loading from environment."""
    monkeypatch.setenv("NVIDIA_API_KEY", "test_key_67890")
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "meta/llama-3.1-70b-instruct")
    monkeypatch.setenv("NVIDIA_NIM_ENABLED", "true")
    monkeypatch.setenv("NVIDIA_NIM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("NVIDIA_NIM_MAX_RETRIES", "5")
    
    config = NIMConfig.from_env()
    
    assert config.api_key == "test_key_67890"
    assert config.model == "meta/llama-3.1-70b-instruct"
    assert config.enabled is True
    assert config.timeout_seconds == 45
    assert config.max_retries == 5


def test_nim_config_try_from_env_none_on_error(monkeypatch):
    """Test try_from_env returns None on error."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_MODEL", raising=False)
    
    # Mock load_dotenv so it doesn't re-read .env and override monkeypatch
    with patch("alert_management.llm.config.load_dotenv"):
        config = NIMConfig.try_from_env()
    
    assert config is None

