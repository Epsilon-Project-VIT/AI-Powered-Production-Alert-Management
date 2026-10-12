"""
Exceptions for LLM integrations (NVIDIA NIM and Google Gemini).
"""


class LLMError(Exception):
    """Base exception for all LLM-related errors."""
    pass


class NIMError(LLMError):
    """Base exception for all NIM-related errors."""
    pass


class NIMAuthenticationError(NIMError):
    """Authentication/authorization failed (401/403)."""
    pass


class NIMConfigurationError(NIMError):
    """Configuration error (missing API key, invalid model, 404)."""
    pass


class NIMRateLimitError(NIMError):
    """Rate limit exceeded (429)."""
    pass


class NIMTimeoutError(NIMError):
    """Request timeout (408 or client timeout)."""
    pass


class NIMProviderError(NIMError):
    """Provider error (5xx, malformed response, invalid data)."""
    pass


class NIMStructuredOutputError(NIMError):
    """Structured output validation failed."""
    pass


# Gemini-specific exception classes (multiple inheritance retains backwards compatibility)
class GeminiError(NIMError):
    """Base exception for all Gemini-related errors."""
    pass


class GeminiAuthenticationError(GeminiError, NIMAuthenticationError):
    """Authentication/authorization failed (401/403)."""
    pass


class GeminiConfigurationError(GeminiError, NIMConfigurationError):
    """Configuration error (missing API key, invalid model, 404)."""
    pass


class GeminiRateLimitError(GeminiError, NIMRateLimitError):
    """Rate limit exceeded (429)."""
    pass


class GeminiTimeoutError(GeminiError, NIMTimeoutError):
    """Request timeout."""
    pass


class GeminiProviderError(GeminiError, NIMProviderError):
    """Provider error (5xx, network error, retries exhausted)."""
    pass


class GeminiStructuredOutputError(GeminiError, NIMStructuredOutputError):
    """Structured output validation failed."""
    pass
