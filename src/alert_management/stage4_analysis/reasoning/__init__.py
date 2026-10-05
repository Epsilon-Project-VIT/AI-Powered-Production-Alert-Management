"""
Reasoning providers for Stage 4 RCA synthesis.

Provides abstract interface and concrete implementations for:
- Mock reasoning provider (for development without API keys)
- NVIDIA NIM provider (for LLM-powered RCA)
- Bedrock Claude provider (for production, requires AWS credentials)
"""

from .interfaces import ReasoningProvider
from .mock_reasoning_provider import MockReasoningProvider
from .nim_reasoning_provider import NIMReasoningProvider

__all__ = [
    'ReasoningProvider',
    'MockReasoningProvider',
    'NIMReasoningProvider',
]
