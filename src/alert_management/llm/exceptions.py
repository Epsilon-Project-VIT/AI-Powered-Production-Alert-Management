"""
Exceptions for NVIDIA NIM integration.
"""


class NIMError(Exception):
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
