"""
Base classifier interface for Stage 2 models.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import numpy as np
from pathlib import Path


class BaseClassifier(ABC):
    """
    Abstract base class for all Stage 2 classifiers.
    
    All classification models must implement this interface to ensure
    consistency across different architectures (TF-IDF, embeddings, etc.).
    """
    
    def __init__(self, model_name: str):
        """
        Initialize the classifier.
        
        Args:
            model_name: Descriptive name for the model (e.g., "tfidf_lr_priority")
        """
        self.model_name = model_name
        self.is_trained = False
        self.classes_ = None
    
    @abstractmethod
    def fit(self, texts: List[str], labels: List[str]) -> 'BaseClassifier':
        """
        Train the classifier on the provided data.
        
        Args:
            texts: List of normalized alert descriptions
            labels: List of ground-truth labels
            
        Returns:
            self (for method chaining)
        """
        pass
    
    @abstractmethod
    def predict(self, texts: List[str]) -> List[str]:
        """
        Predict labels for the provided texts.
        
        Args:
            texts: List of normalized alert descriptions
            
        Returns:
            List of predicted labels
        """
        pass
    
    @abstractmethod
    def predict_proba(self, texts: List[str]) -> np.ndarray:
        """
        Predict class probabilities for the provided texts.
        
        Args:
            texts: List of normalized alert descriptions
            
        Returns:
            Array of shape (n_samples, n_classes) with probabilities
        """
        pass
    
    def predict_with_confidence(self, texts: List[str]) -> List[Tuple[str, float]]:
        """
        Predict labels with confidence scores.
        
        Args:
            texts: List of normalized alert descriptions
            
        Returns:
            List of (label, confidence) tuples
        """
        if not self.is_trained:
            raise ValueError(f"Model {self.model_name} has not been trained")
        
        probas = self.predict_proba(texts)
        labels = self.predict(texts)
        
        # Confidence is the maximum probability for each prediction
        confidences = np.max(probas, axis=1)
        
        return list(zip(labels, confidences))
    
    @abstractmethod
    def save(self, path: Path) -> None:
        """
        Save the trained model to disk.
        
        Args:
            path: Directory path where model should be saved
        """
        pass
    
    @abstractmethod
    def load(self, path: Path) -> 'BaseClassifier':
        """
        Load a trained model from disk.
        
        Args:
            path: Directory path where model is saved
            
        Returns:
            self (for method chaining)
        """
        pass
    
    def __repr__(self) -> str:
        """String representation of the classifier."""
        trained_status = "trained" if self.is_trained else "untrained"
        return f"{self.__class__.__name__}(name='{self.model_name}', status='{trained_status}')"
