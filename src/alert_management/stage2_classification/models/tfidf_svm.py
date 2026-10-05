"""
TF-IDF + SVM classifier.

Benchmark model for Stage 2 classification.
"""

from typing import List
import numpy as np
from pathlib import Path
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

from .base import BaseClassifier


class TfidfSVMClassifier(BaseClassifier):
    """
    TF-IDF vectorization + Support Vector Machine classifier.
    
    Benchmark model for Stage 2 classification.
    """
    
    def __init__(
        self,
        model_name: str,
        max_features: int = 5000,
        ngram_range: tuple = (1, 2),
        C: float = 1.0,
        kernel: str = 'linear',
        calibrate: bool = True
    ):
        """
        Initialize TF-IDF + SVM classifier.
        
        Args:
            model_name: Descriptive name for the model
            max_features: Maximum number of TF-IDF features
            ngram_range: Range of n-grams to extract
            C: Regularization parameter
            kernel: SVM kernel type ('linear', 'rbf', etc.)
            calibrate: Whether to calibrate probabilities
        """
        super().__init__(model_name)
        
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.C = C
        self.kernel = kernel
        self.calibrate = calibrate
        
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            lowercase=True,
            strip_accents='unicode',
            stop_words='english'
        )
        
        self.classifier = SVC(
            C=C,
            kernel=kernel,
            probability=True,
            random_state=42,
            class_weight='balanced'
        )
        
        self.pipeline = Pipeline([
            ('vectorizer', self.vectorizer),
            ('classifier', self.classifier)
        ])
        
        self.calibrated_classifier = None
    
    def fit(self, texts: List[str], labels: List[str]) -> 'TfidfSVMClassifier':
        """Train the TF-IDF + SVM model."""
        if len(texts) != len(labels):
            raise ValueError("texts and labels must have the same length")
        
        if len(texts) == 0:
            raise ValueError("Cannot train on empty dataset")
        
        self.pipeline.fit(texts, labels)
        
        if self.calibrate and len(set(labels)) > 1:
            self.calibrated_classifier = CalibratedClassifierCV(
                self.pipeline,
                cv=3,
                method='sigmoid'
            )
            self.calibrated_classifier.fit(texts, labels)
        
        self.classes_ = self.pipeline.classes_
        self.is_trained = True
        
        return self
    
    def predict(self, texts: List[str]) -> List[str]:
        """Predict labels for the provided texts."""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_name} has not been trained")
        
        if self.calibrate and self.calibrated_classifier is not None:
            predictions = self.calibrated_classifier.predict(texts)
        else:
            predictions = self.pipeline.predict(texts)
        
        return predictions.tolist()
    
    def predict_proba(self, texts: List[str]) -> np.ndarray:
        """Predict class probabilities for the provided texts."""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_name} has not been trained")
        
        if self.calibrate and self.calibrated_classifier is not None:
            probas = self.calibrated_classifier.predict_proba(texts)
        else:
            probas = self.pipeline.predict_proba(texts)
        
        return probas
    
    def save(self, path: Path) -> None:
        """Save the trained model to disk."""
        if not self.is_trained:
            raise ValueError(f"Cannot save untrained model {self.model_name}")
        
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        model_file = path / f"{self.model_name}.joblib"
        
        model_data = {
            'pipeline': self.pipeline,
            'calibrated_classifier': self.calibrated_classifier,
            'is_trained': self.is_trained,
            'classes_': self.classes_,
            'config': {
                'max_features': self.max_features,
                'ngram_range': self.ngram_range,
                'C': self.C,
                'kernel': self.kernel,
                'calibrate': self.calibrate
            }
        }
        
        joblib.dump(model_data, model_file)
    
    def load(self, path: Path) -> 'TfidfSVMClassifier':
        """Load a trained model from disk."""
        path = Path(path)
        model_file = path / f"{self.model_name}.joblib"
        
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        
        model_data = joblib.load(model_file)
        
        self.pipeline = model_data['pipeline']
        self.calibrated_classifier = model_data['calibrated_classifier']
        self.is_trained = model_data['is_trained']
        self.classes_ = model_data['classes_']
        
        config = model_data['config']
        self.max_features = config['max_features']
        self.ngram_range = config['ngram_range']
        self.C = config['C']
        self.kernel = config['kernel']
        self.calibrate = config['calibrate']
        
        return self
