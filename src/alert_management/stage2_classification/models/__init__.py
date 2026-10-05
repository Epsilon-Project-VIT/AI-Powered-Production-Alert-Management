"""
Classification models for Stage 2.

Supports multiple model architectures:
- TF-IDF + Logistic Regression (primary)
- TF-IDF + SVM (benchmark)
- Embeddings + Logistic Regression (benchmark)
- Embeddings + SVM (benchmark)
"""

from .base import BaseClassifier
from .tfidf_lr import TfidfLogisticClassifier
from .tfidf_svm import TfidfSVMClassifier
from .embedding_lr import EmbeddingLogisticClassifier
from .embedding_svm import EmbeddingSVMClassifier

__all__ = [
    'BaseClassifier',
    'TfidfLogisticClassifier',
    'TfidfSVMClassifier',
    'EmbeddingLogisticClassifier',
    'EmbeddingSVMClassifier',
]
