"""
Stage 3: Alert Correlation & Incident Grouping

This stage groups related alerts into incidents using:
- Exact/signature matching
- Semantic similarity (embeddings + HDBSCAN)
- Temporal proximity validation
- Client/service matching
"""

from .schemas import IncidentGroup, CorrelationScore
from .pipeline import CorrelationPipeline

__all__ = [
    'IncidentGroup',
    'CorrelationScore',
    'CorrelationPipeline',
]
