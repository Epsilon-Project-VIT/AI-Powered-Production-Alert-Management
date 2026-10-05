"""Gemini configuration and OpenAI-compatible client."""

import json
import os
import time
from typing import Any, Dict, List, Optional, Type

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .exceptions import NIMAuthenticationError, NIMConfigurationError, NIMProviderError, NIMStructuredOutputError, NIMTimeoutError


class GeminiConfig(BaseModel):
    """Configuration for the Gemini OpenAI-compatible endpoint."""

    api_key: str = Field(..., min_length=1)
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    model: str = "gemini-3.8-flash"
    enabled: bool = False
    timeout_seconds: int = Field(default=30, ge=1)
    max_retries: int = Field(default=1, ge=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        load_dotenv()
        # GEMINI_* is preferred; NVIDIA_NIM_* remains a compatibility alias
        # for existing deployments that already point to Gemini.
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY (or legacy NVIDIA_API_KEY) is required")
        return cls(
            api_key=api_key,
            base_url=os.getenv("GEMINI_BASE_URL") or os.getenv("NVIDIA_NIM_BASE_URL", cls.model_fields["base_url"].default),
            model=os.getenv("GEMINI_MODEL") or os.getenv("NVIDIA_NIM_MODEL", cls.model_fields["model"].default),
            enabled=(os.getenv("GEMINI_ENABLED") or os.getenv("NVIDIA_NIM_ENABLED", "false")).lower() == "true",
            timeout_seconds=int(os.getenv("GEMINI_TIMEOUT_SECONDS") or os.getenv("NVIDIA_NIM_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("GEMINI_MAX_RETRIES") or os.getenv("NVIDIA_NIM_MAX_RETRIES", "1")),
            temperature=float(os.getenv("GEMINI_TEMPERATURE") or os.getenv("NVIDIA_NIM_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("GEMINI_MAX_TOKENS") or os.getenv("NVIDIA_NIM_MAX_TOKENS", "4096")),
        )

    @classmethod
    def try_from_env(cls) -> Optional["GeminiConfig"]:
        try:
            return cls.from_env()
        except ValueError:
            return None


class GeminiClient:
    """Validated client for Gemini's OpenAI-compatible chat endpoint."""

    def __init__(self, config: GeminiConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"})

    def chat_completion(self, messages: List[Dict[str, str]], response_format: Optional[Dict[str, Any]] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        payload: Dict[str, Any] = {"model": self.config.model, "messages": messages, "temperature": self.config.temperature if temperature is None else temperature, "max_tokens": self.config.max_tokens if max_tokens is None else max_tokens}
        if response_format:
            payload["response_format"] = response_format
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.post(url, json=payload, timeout=self.config.timeout_seconds)
                if response.status_code == 200:
                    return response.json()
                if response.status_code in (401, 403):
                    raise NIMAuthenticationError("Gemini authentication failed")
                if response.status_code == 404:
                    raise NIMConfigurationError("Gemini model or endpoint was not found")
                if response.status_code in (408, 429) or response.status_code >= 500:
                    if attempt < self.config.max_retries:
                        time.sleep(2 ** attempt)
                        continue
                raise NIMProviderError(f"Gemini request failed with HTTP {response.status_code}")
            except requests.Timeout as error:
                last_error = error
                if attempt < self.config.max_retries:
                    continue
                raise NIMTimeoutError("Gemini request timed out") from error
            except requests.RequestException as error:
                last_error = error
                if attempt < self.config.max_retries:
                    continue
                raise NIMProviderError("Gemini network request failed") from error
        raise NIMProviderError("Gemini retries exhausted") from last_error

    def chat_completion_structured(self, messages: List[Dict[str, str]], schema: Type[BaseModel], **kwargs: Any) -> BaseModel:
        instruction = "Respond only with a JSON object matching this schema. Schema: " + json.dumps(schema.model_json_schema())
        enhanced_messages = [dict(message) for message in messages]
        if enhanced_messages and enhanced_messages[-1]["role"] == "user":
            enhanced_messages[-1]["content"] += "\n\n" + instruction
        else:
            enhanced_messages.append({"role": "system", "content": instruction})
        response = self.chat_completion(enhanced_messages, response_format={"type": "json_object"}, **kwargs)
        try:
            data = json.loads(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise NIMStructuredOutputError("Gemini returned malformed structured output") from error
        try:
            return schema.model_validate(data)
        except Exception as error:
            raise NIMStructuredOutputError("Gemini response did not satisfy the requested schema") from error
