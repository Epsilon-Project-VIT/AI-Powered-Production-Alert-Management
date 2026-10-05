"""
TF-IDF + Logistic Regression classifier.

Primary model for Stage 2 classification.
"""

from typing import List
import numpy as np
from pathlib import Path
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

from .base import BaseClassifier


class TfidfLogisticClassifier(BaseClassifier):
    """
    TF-IDF vectorization + Logistic Regression classifier.
    
    This is the primary/default model architecture for Stage 2.
    Uses probability calibration for reliable confidence scores.
    """
    
    def __init__(
        self,
        model_name: str,
        max_features: int = 5000,
        ngram_range: tuple = (1, 2),
        C: float = 1.0,
        max_iter: int = 1000,
        calibrate: bool = True
    ):
        """
        Initialize TF-IDF + Logistic Regression classifier.
        
        Args:
            model_name: Descriptive name for the model
            max_features: Maximum number of TF-IDF features
            ngram_range: Range of n-grams to extract (default: unigrams + bigrams)
            C: Inverse of regularization strength
            max_iter: Maximum iterations for solver
            calibrate: Whether to calibrate probabilities using cross-validation
        """
        super().__init__(model_name)
        
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.C = C
        self.max_iter = max_iter
        self.calibrate = calibrate
        
        # Initialize pipeline
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            lowercase=True,
            strip_accents='unicode',
            stop_words='english'
        )
        
        self.classifier = LogisticRegression(
            C=C,
            max_iter=max_iter,
            random_state=42,
            class_weight='balanced'  # Handle class imbalance
        )
        
        self.pipeline = Pipeline([
            ('vectorizer', self.vectorizer),
            ('classifier', self.classifier)
        ])
        
        self.calibrated_classifier = None
    
    def fit(self, texts: List[str], labels: List[str]) -> 'TfidfLogisticClassifier':
        """
        Train the TF-IDF + Logistic Regression model.
        
        Args:
            texts: List of normalized alert descriptions
            labels: List of ground-truth labels
            
        Returns:
            self (for method chaining)
        """
        if len(texts) != len(labels):
            raise ValueError("texts and labels must have the same length")
        
        if len(texts) == 0:
            raise ValueError("Cannot train on empty dataset")
        
        # Train the base pipeline
        self.pipeline.fit(texts, labels)
        
        # Optionally calibrate probabilities
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
        """
        Predict labels for the provided texts.
        
        Args:
            texts: List of normalized alert descriptions
            
        Returns:
            List of predicted labels
        """
        if not self.is_trained:
            raise ValueError(f"Model {self.model_name} has not been trained")
        
        if self.calibrate and self.calibrated_classifier is not None:
            predictions = self.calibrated_classifier.predict(texts)
        else:
            predictions = self.pipeline.predict(texts)
        
        return predictions.tolist()
    
    def predict_proba(self, texts: List[str]) -> np.ndarray:
        """
        Predict class probabilities for the provided texts.
        
        Args:
            texts: List of normalized alert descriptions
            
        Returns:
            Array of shape (n_samples, n_classes) with probabilities
        """
        if not self.is_trained:
            raise ValueError(f"Model {self.model_name} has not been trained")
        
        if self.calibrate and self.calibrated_classifier is not None:
            probas = self.calibrated_classifier.predict_proba(texts)
        else:
            probas = self.pipeline.predict_proba(texts)
        
        return probas
    
    def save(self, path: Path) -> None:
        """
        Save the trained model to disk.
        
        Args:
            path: Directory path where model should be saved
        """
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
                'max_iter': self.max_iter,
                'calibrate': self.calibrate
            }
        }
        
        joblib.dump(model_data, model_file)
    
    def load(self, path: Path) -> 'TfidfLogisticClassifier':
        """
        Load a trained model from disk.
        
        Args:
            path: Directory path where model is saved
            
        Returns:
            self (for method chaining)
        """
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
        self.max_iter = config['max_iter']
        self.calibrate = config['calibrate']
        
        return self
