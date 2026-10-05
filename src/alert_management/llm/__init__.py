"""
NVIDIA NIM LLM integration for alert management.

This module provides reusable LLM client infrastructure for:
- Stage 2: Classification (challenger/fallback)
- Stage 3: Correlation adjudication
- Stage 4: RCA reasoning
"""

from .gemini import GeminiClient, GeminiConfig
from .config import NIMConfig
from .nim_client import NIMClient
from .exceptions import (
    NIMError,
    NIMAuthenticationError,
    NIMConfigurationError,
    NIMRateLimitError,
    NIMTimeoutError,
    NIMProviderError,
    NIMStructuredOutputError
)

__all__ = [
    'NIMConfig',
    'NIMClient',
    'GeminiClient',
    'GeminiConfig',
    'NIMError',
    'NIMAuthenticationError',
    'NIMConfigurationError',
    'NIMRateLimitError',
    'NIMTimeoutError',
    'NIMProviderError',
    'NIMStructuredOutputError',
]
