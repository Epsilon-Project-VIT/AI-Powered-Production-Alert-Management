"""
Embedding + SVM classifier.

Benchmark model using sentence embeddings for Stage 2 classification.
"""

from typing import List
import numpy as np
from pathlib import Path
import joblib

from sentence_transformers import SentenceTransformer
from sklearn.svm import SVC
from sklearn.calibration import CalibratedClassifierCV

from .base import BaseClassifier


class EmbeddingSVMClassifier(BaseClassifier):
    """
    Sentence Embedding + Support Vector Machine classifier.
    
    Uses pre-trained sentence transformers to generate embeddings,
    then trains an SVM classifier on top.
    """
    
    def __init__(
        self,
        model_name: str,
        embedding_model: str = 'all-MiniLM-L6-v2',
        C: float = 1.0,
        kernel: str = 'rbf',
        calibrate: bool = True
    ):
        """
        Initialize Embedding + SVM classifier.
        
        Args:
            model_name: Descriptive name for the model
            embedding_model: Name of sentence-transformers model
            C: Regularization parameter
            kernel: SVM kernel type
            calibrate: Whether to calibrate probabilities
        """
        super().__init__(model_name)
        
        self.embedding_model_name = embedding_model
        self.C = C
        self.kernel = kernel
        self.calibrate = calibrate
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Initialize classifier
        self.classifier = SVC(
            C=C,
            kernel=kernel,
            probability=True,
            random_state=42,
            class_weight='balanced'
        )
        
        self.calibrated_classifier = None
    
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return embeddings
    
    def fit(self, texts: List[str], labels: List[str]) -> 'EmbeddingSVMClassifier':
        """Train the Embedding + SVM model."""
        if len(texts) != len(labels):
            raise ValueError("texts and labels must have the same length")
        
        if len(texts) == 0:
            raise ValueError("Cannot train on empty dataset")
        
        # Generate embeddings
        embeddings = self._get_embeddings(texts)
        
        # Train classifier
        self.classifier.fit(embeddings, labels)
        
        # Optionally calibrate probabilities
        if self.calibrate and len(set(labels)) > 1:
            self.calibrated_classifier = CalibratedClassifierCV(
                self.classifier,
                cv=3,
                method='sigmoid'
            )
            self.calibrated_classifier.fit(embeddings, labels)
        
        self.classes_ = self.classifier.classes_
        self.is_trained = True
        
        return self
    
    def predict(self, texts: List[str]) -> List[str]:
        """Predict labels for the provided texts."""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_name} has not been trained")
        
        embeddings = self._get_embeddings(texts)
        
        if self.calibrate and self.calibrated_classifier is not None:
            predictions = self.calibrated_classifier.predict(embeddings)
        else:
            predictions = self.classifier.predict(embeddings)
        
        return predictions.tolist()
    
    def predict_proba(self, texts: List[str]) -> np.ndarray:
        """Predict class probabilities for the provided texts."""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_name} has not been trained")
        
        embeddings = self._get_embeddings(texts)
        
        if self.calibrate and self.calibrated_classifier is not None:
            probas = self.calibrated_classifier.predict_proba(embeddings)
        else:
            probas = self.classifier.predict_proba(embeddings)
        
        return probas
    
    def save(self, path: Path) -> None:
        """Save the trained model to disk."""
        if not self.is_trained:
            raise ValueError(f"Cannot save untrained model {self.model_name}")
        
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        model_file = path / f"{self.model_name}.joblib"
        
        model_data = {
            'classifier': self.classifier,
            'calibrated_classifier': self.calibrated_classifier,
            'is_trained': self.is_trained,
            'classes_': self.classes_,
            'config': {
                'embedding_model_name': self.embedding_model_name,
                'C': self.C,
                'kernel': self.kernel,
                'calibrate': self.calibrate
            }
        }
        
        joblib.dump(model_data, model_file)
    
    def load(self, path: Path) -> 'EmbeddingSVMClassifier':
        """Load a trained model from disk."""
        path = Path(path)
        model_file = path / f"{self.model_name}.joblib"
        
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        
        model_data = joblib.load(model_file)
        
        self.classifier = model_data['classifier']
        self.calibrated_classifier = model_data['calibrated_classifier']
        self.is_trained = model_data['is_trained']
        self.classes_ = model_data['classes_']
        
        config = model_data['config']
        self.embedding_model_name = config['embedding_model_name']
        self.C = config['C']
        self.kernel = config['kernel']
        self.calibrate = config['calibrate']
        
        # Re-initialize embedding model
        self.embedding_model = SentenceTransformer(self.embedding_model_name)
        
        return self
