"""
Reasoning providers for Stage 4 RCA synthesis.

Provides abstract interface and concrete implementations for:
- Mock reasoning provider (for development without API keys)
- Google Gemini reasoning provider (for LLM-powered RCA)
- NVIDIA NIM provider (for LLM-powered RCA)
"""

import os
from typing import Optional

from .interfaces import ReasoningProvider
from .mock_reasoning_provider import MockReasoningProvider
from .nim_reasoning_provider import NIMReasoningProvider
from .gemini_reasoning_provider import GeminiReasoningProvider, GeminiRCAOutput, GeminiRCACache


def get_reasoning_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None
) -> ReasoningProvider:
    """
    Factory function to instantiate the configured ReasoningProvider.
    
    Reads from environment variable REASONING_PROVIDER (default: 'mock').
    Supported options:
    - 'mock': MockReasoningProvider (deterministic heuristics, no API calls)
    - 'gemini': GeminiReasoningProvider (Google Gemini API via GeminiConfig)
    - 'nim': NIMReasoningProvider (NVIDIA NIM API via NIMConfig)

    Args:
        provider_name: Optional provider name ('mock', 'gemini', 'nim')
        model: Optional model override (e.g. 'gemini-3.5-flash-lite')
    """
    if provider_name is None:
        provider_name = os.getenv("REASONING_PROVIDER", "mock").strip().lower()
    else:
        provider_name = provider_name.strip().lower()

    if provider_name == "mock":
        return MockReasoningProvider()
    elif provider_name == "gemini":
        from alert_management.llm import GeminiConfig
        config = GeminiConfig.from_env()
        if model:
            config = config.model_copy(update={"model": model})
        return GeminiReasoningProvider(config=config, model=model)
    elif provider_name == "nim":
        from alert_management.llm import NIMConfig
        config = NIMConfig.from_env()
        if model:
            config = config.model_copy(update={"model": model})
        return NIMReasoningProvider(config=config)
    else:
        raise ValueError(
            f"Unknown reasoning provider: '{provider_name}'. "
            f"Expected one of: 'mock', 'gemini', 'nim'."
        )


__all__ = [
    'ReasoningProvider',
    'MockReasoningProvider',
    'NIMReasoningProvider',
    'GeminiReasoningProvider',
    'GeminiRCAOutput',
    'GeminiRCACache',
    'get_reasoning_provider',
]
