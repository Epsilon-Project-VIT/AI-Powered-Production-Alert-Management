"""
Stage 2: Alert Understanding & Routing

This stage classifies standardized alerts to determine:
- Alert Type (what kind of technical problem)
- Severity (how technically serious)
- Business Impact (effect on client/business)
- Priority (urgency of response)
- Routing / Assignment Group (which team handles it)
"""

from .schemas import EnrichedAlert, ClassificationResult
from .pipeline import ClassificationPipeline

__all__ = [
    'EnrichedAlert',
    'ClassificationResult',
    'ClassificationPipeline',
]
