"""Gemini configuration and OpenAI-compatible client."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Type

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .exceptions import (
    NIMAuthenticationError,
    NIMConfigurationError,
    NIMProviderError,
    NIMRateLimitError,
    NIMStructuredOutputError,
    NIMTimeoutError,
    GeminiAuthenticationError,
    GeminiConfigurationError,
    GeminiError,
    GeminiProviderError,
    GeminiRateLimitError,
    GeminiStructuredOutputError,
    GeminiTimeoutError,
)

logger = logging.getLogger(__name__)


class GeminiConfig(BaseModel):
    """Configuration for the Gemini API client via OpenAI-compatible endpoint."""

    api_key: str = Field(..., min_length=1, repr=False, description="Google Gemini API key")
    base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai",
        description="Gemini API base URL"
    )
    model: str = Field(
        default="gemini-flash-latest",
        description="Model identifier (e.g., 'gemini-flash-latest', 'gemini-3.8-flash')"
    )
    enabled: bool = Field(default=False, description="Whether Gemini is enabled")
    timeout_seconds: int = Field(default=30, ge=1, description="Request timeout in seconds")
    max_retries: int = Field(default=2, ge=0, description="Maximum bounded retries for retryable errors")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=4096, ge=1, description="Maximum output tokens")
    rpm_limit: int = Field(default=15, ge=1, description="Proactive request rate limit (requests per minute)")

    @classmethod
    def from_env(cls, load_env: bool = True, model: Optional[str] = None) -> "GeminiConfig":
        if load_env:
            load_dotenv()
        # GEMINI_* is preferred; NVIDIA_NIM_* remains a compatibility alias
        # for existing deployments that already point to Gemini.
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY (or legacy NVIDIA_API_KEY) is required")
        chosen_model = model or os.getenv("GEMINI_MODEL") or os.getenv("NVIDIA_NIM_MODEL", cls.model_fields["model"].default)
        return cls(
            api_key=api_key,
            base_url=os.getenv("GEMINI_BASE_URL") or os.getenv("NVIDIA_NIM_BASE_URL", cls.model_fields["base_url"].default),
            model=chosen_model,
            enabled=(os.getenv("GEMINI_ENABLED") or os.getenv("NVIDIA_NIM_ENABLED", "false")).lower() == "true",
            timeout_seconds=int(os.getenv("GEMINI_TIMEOUT_SECONDS") or os.getenv("NVIDIA_NIM_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("GEMINI_MAX_RETRIES") or os.getenv("NVIDIA_NIM_MAX_RETRIES", "2")),
            temperature=float(os.getenv("GEMINI_TEMPERATURE") or os.getenv("NVIDIA_NIM_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("GEMINI_MAX_TOKENS") or os.getenv("NVIDIA_NIM_MAX_TOKENS", "4096")),
            rpm_limit=int(os.getenv("GEMINI_RPM_LIMIT", "15")),
        )

    @classmethod
    def try_from_env(cls, load_env: bool = True, model: Optional[str] = None) -> Optional["GeminiConfig"]:
        try:
            return cls.from_env(load_env=load_env, model=model)
        except ValueError:
            return None


class GeminiClient:
    """Validated client for Gemini's OpenAI-compatible chat endpoint."""

    def __init__(self, config: GeminiConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        })
        self._last_request_time: float = 0.0

    def _wait_for_rate_limit(self) -> None:
        """Enforce proactive client-side rate limiting based on configured RPM."""
        if self.config.rpm_limit <= 0:
            return
        min_interval = 60.0 / self.config.rpm_limit
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < min_interval and self._last_request_time > 0:
            sleep_needed = min_interval - elapsed
            time.sleep(sleep_needed)
        self._last_request_time = time.monotonic()

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute chat completion with bounded retries, timeouts, and rate-limiting."""
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature if temperature is None else temperature,
            "max_tokens": self.config.max_tokens if max_tokens is None else max_tokens
        }
        if response_format:
            payload["response_format"] = response_format

        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            self._wait_for_rate_limit()
            try:
                response = self.session.post(url, json=payload, timeout=self.config.timeout_seconds)
                if response.status_code == 200:
                    return response.json()
                if response.status_code in (401, 403):
                    raise GeminiAuthenticationError("Gemini authentication failed (HTTP 401/403)")
                if response.status_code == 404:
                    raise GeminiConfigurationError(f"Gemini model or endpoint not found: {self.config.model}")
                if response.status_code == 429:
                    raw_text = getattr(response, "text", "")
                    resp_text = str(raw_text) if isinstance(raw_text, str) else ""
                    if "quota" in resp_text.lower() or "resource_exhausted" in resp_text.lower():
                        raise GeminiRateLimitError(f"Gemini quota exhausted (HTTP 429 RESOURCE_EXHAUSTED): {resp_text[:200]}")
                    retry_after = response.headers.get("Retry-After") if hasattr(response, "headers") else None
                    delay = float(retry_after) if retry_after else float(2 ** attempt)
                    if attempt < self.config.max_retries:
                        time.sleep(min(delay, 10.0))
                        continue
                    raise GeminiRateLimitError(f"Gemini rate limit exceeded (HTTP 429): {resp_text[:200]}")
                if response.status_code in (408,) or response.status_code >= 500:
                    if attempt < self.config.max_retries:
                        time.sleep(2 ** attempt)
                        continue
                raise GeminiProviderError(f"Gemini request failed with HTTP {response.status_code}")
            except (GeminiAuthenticationError, GeminiConfigurationError, GeminiRateLimitError):
                raise
            except requests.Timeout as error:
                last_error = error
                if attempt < self.config.max_retries:
                    continue
                raise GeminiTimeoutError("Gemini request timed out") from error
            except requests.RequestException as error:
                last_error = error
                if attempt < self.config.max_retries:
                    continue
                raise GeminiProviderError(f"Gemini network request failed: {type(error).__name__}") from error

        raise GeminiProviderError("Gemini retries exhausted") from last_error

    def chat_completion_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Type[BaseModel],
        **kwargs: Any
    ) -> BaseModel:
        """Execute chat completion and parse structured output into specified schema."""
        instruction = "Respond only with a JSON object matching this schema. Schema: " + json.dumps(schema.model_json_schema())
        enhanced_messages = [dict(message) for message in messages]
        if enhanced_messages and enhanced_messages[-1]["role"] == "user":
            enhanced_messages[-1]["content"] += "\n\n" + instruction
        else:
            enhanced_messages.append({"role": "system", "content": instruction})

        response = self.chat_completion(enhanced_messages, response_format={"type": "json_object"}, **kwargs)
        try:
            raw_text = response["choices"][0]["message"]["content"]
            if raw_text is None:
                raise GeminiStructuredOutputError("Gemini returned empty message content")
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            data = json.loads(cleaned_text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise GeminiStructuredOutputError("Gemini returned malformed structured output") from error
        try:
            return schema.model_validate(data)
        except Exception as error:
            raise GeminiStructuredOutputError("Gemini response did not satisfy the requested schema") from error
