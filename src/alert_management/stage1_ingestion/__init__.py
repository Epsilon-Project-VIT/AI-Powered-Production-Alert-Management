"""
Stage 1: Alert Data Ingestion & Normalization

Converts raw/historical alerts into standardized alert objects.
"""

from .schemas import StandardizedAlert
from .pipeline import Stage1Pipeline

__all__ = ["StandardizedAlert", "Stage1Pipeline"]
