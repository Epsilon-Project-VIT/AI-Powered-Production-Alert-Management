"""
Telemetry providers for Stage 4.

Provides abstract interfaces and concrete implementations for:
- Log providers
- Metric providers
- Trace providers

All providers support both mock (for development) and real (for production) data sources.
"""

from .interfaces import LogProvider, MetricProvider, TraceProvider

__all__ = ['LogProvider', 'MetricProvider', 'TraceProvider']
