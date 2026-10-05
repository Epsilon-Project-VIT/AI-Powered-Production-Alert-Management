"""
NVIDIA NIM API client with OpenAI-compatible interface.
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

import requests

from .config import NIMConfig
from .exceptions import (
    NIMAuthenticationError,
    NIMConfigurationError,
    NIMRateLimitError,
    NIMTimeoutError,
    NIMProviderError,
    NIMStructuredOutputError
)

logger = logging.getLogger(__name__)


class NIMClient:
    """
    NVIDIA NIM API client using OpenAI-compatible chat completions endpoint.
    
    Features:
    - Authentication via API key
    - Bounded retries for retryable errors
    - Safe logging (never logs API key)
    - Structured JSON output support
    - Response validation
    """
    
    def __init__(self, config: NIMConfig):
        """
        Initialize NIM client.
        
        Args:
            config: NIM configuration
        """
        self.config = config
        self.session = requests.Session()
        
        # Set headers (but never log them)
        self.session.headers.update({
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        })
        
        logger.info(
            f"Initialized NIM client: model={config.model}, "
            f"base_url={config.base_url}, timeout={config.timeout_seconds}s"
        )
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Call NIM chat completion API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            response_format: Optional structured output format
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            API response dict
            
        Raises:
            NIMAuthenticationError: 401/403
            NIMConfigurationError: 404 or invalid model
            NIMRateLimitError: 429
            NIMTimeoutError: Request timeout
            NIMProviderError: 5xx or malformed response
        """
        url = f"{self.config.base_url}/chat/completions"
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }
        
        if response_format:
            payload["response_format"] = response_format
        
        # Log request (without API key)
        logger.debug(
            f"NIM request: model={self.config.model}, "
            f"messages={len(messages)}, temperature={payload['temperature']}"
        )
        
        # Execute with retries
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.post(
                    url,
                    json=payload,
                    timeout=self.config.timeout_seconds
                )
                
                # Handle HTTP errors
                if response.status_code == 200:
                    result = response.json()
                    logger.debug(f"NIM response received: {len(result.get('choices', []))} choices")
                    return result
                elif response.status_code in (401, 403):
                    raise NIMAuthenticationError(
                        f"Authentication failed (HTTP {response.status_code}). "
                        "Check NVIDIA_API_KEY environment variable."
                    )
                elif response.status_code == 404:
                    raise NIMConfigurationError(
                        f"Model or endpoint not found (HTTP 404). "
                        f"Check NVIDIA_NIM_MODEL={self.config.model} and base URL."
                    )
                elif response.status_code == 429:
                    # Rate limit - retryable
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    if attempt < self.config.max_retries:
                        logger.warning(f"Rate limit hit, retrying after {retry_after}s...")
                        time.sleep(retry_after)
                        continue
                    else:
                        raise NIMRateLimitError("Rate limit exceeded and max retries exhausted")
                elif response.status_code == 408:
                    # Timeout - retryable
                    if attempt < self.config.max_retries:
                        logger.warning(f"Request timeout (408), retrying ({attempt + 1}/{self.config.max_retries})...")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        raise NIMTimeoutError("Request timeout and max retries exhausted")
                elif 500 <= response.status_code < 600:
                    # Server error - retryable
                    if attempt < self.config.max_retries:
                        logger.warning(
                            f"Server error (HTTP {response.status_code}), "
                            f"retrying ({attempt + 1}/{self.config.max_retries})..."
                        )
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        raise NIMProviderError(
                            f"Server error (HTTP {response.status_code}) and max retries exhausted"
                        )
                else:
                    raise NIMProviderError(
                        f"Unexpected HTTP status {response.status_code}: {response.text[:200]}"
                    )
            
            except requests.Timeout as e:
                # Client-side timeout - retryable
                if attempt < self.config.max_retries:
                    logger.warning(f"Client timeout, retrying ({attempt + 1}/{self.config.max_retries})...")
                    time.sleep(2 ** attempt)
                    last_error = e
                    continue
                else:
                    raise NIMTimeoutError(f"Client timeout and max retries exhausted: {e}")
            
            except requests.RequestException as e:
                # Network error - retryable
                if attempt < self.config.max_retries:
                    logger.warning(f"Network error, retrying ({attempt + 1}/{self.config.max_retries})...")
                    time.sleep(2 ** attempt)
                    last_error = e
                    continue
                else:
                    raise NIMProviderError(f"Network error and max retries exhausted: {e}")
        
        # Should not reach here, but handle gracefully
        if last_error:
            raise NIMProviderError(f"Max retries exhausted: {last_error}")
        else:
            raise NIMProviderError("Unknown error occurred")
    
    def chat_completion_structured(
        self,
        messages: List[Dict[str, str]],
        schema: type[BaseModel],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> BaseModel:
        """
        Call NIM with structured JSON output validated against Pydantic schema.
        
        Args:
            messages: List of message dicts
            schema: Pydantic model class for validation
            temperature: Override temperature
            max_tokens: Override max tokens
            
        Returns:
            Validated Pydantic model instance
            
        Raises:
            NIMStructuredOutputError: If response doesn't match schema
            Other NIM exceptions from chat_completion
        """
        # Request JSON format
        response_format = {"type": "json_object"}
        
        # Add schema instruction to system message
        schema_json = schema.model_json_schema()
        schema_instruction = (
            f"\n\nYou must respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(schema_json, indent=2)}\n```\n"
            f"Do not include any text outside the JSON object."
        )
        
        # Append to last user message or create system message
        enhanced_messages = messages.copy()
        if enhanced_messages and enhanced_messages[-1]["role"] == "user":
            enhanced_messages[-1]["content"] += schema_instruction
        else:
            enhanced_messages.append({
                "role": "system",
                "content": schema_instruction
            })
        
        # Call API
        response = self.chat_completion(
            messages=enhanced_messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Extract content (use .get() to handle thinking models that may omit 'content')
        try:
            content = response["choices"][0]["message"].get("content", "")
        except (KeyError, IndexError) as e:
            raise NIMProviderError(f"Malformed API response: missing content: {e}")
        
        if not content:
            raise NIMProviderError(
                "API returned empty content. If using a thinking model (e.g. Gemini), "
                "increase max_tokens to account for internal thinking tokens."
            )
        
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise NIMStructuredOutputError(f"Response is not valid JSON: {e}\nContent: {content[:200]}")
        
        # Validate against schema
        try:
            return schema.model_validate(data)
        except Exception as e:
            raise NIMStructuredOutputError(f"Response doesn't match schema: {e}\nData: {data}")
    
    def extract_text_content(self, response: Dict[str, Any]) -> str:
        """
        Extract text content from API response.
        
        Handles thinking models (e.g. Gemini) where 'content' may be absent
        if thinking tokens exhausted the token budget.
        
        Args:
            response: API response dict
            
        Returns:
            Content string
            
        Raises:
            NIMProviderError: If response is malformed or content is empty
        """
        try:
            content = response["choices"][0]["message"].get("content", "")
            if not content:
                raise NIMProviderError(
                    "API returned empty content. If using a thinking model (e.g. Gemini), "
                    "increase max_tokens to account for internal thinking tokens."
                )
            return content
        except (KeyError, IndexError) as e:
            raise NIMProviderError(f"Malformed API response: missing content: {e}")
