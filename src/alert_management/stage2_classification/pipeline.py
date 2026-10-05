"""
Stage 2 Classification Pipeline.

Orchestrates the classification of standardized alerts into enriched alerts.
"""

from typing import List, Dict, Optional
from pathlib import Path

from ..stage1_ingestion.schemas import StandardizedAlert
from ..config.settings import Settings
from .schemas import EnrichedAlert, ClassificationResult
from .models.base import BaseClassifier


class ClassificationPipeline:
    """
    Stage 2 pipeline that classifies standardized alerts.
    
    Takes StandardizedAlert objects from Stage 1 and produces EnrichedAlert
    objects with predictions for:
    - Alert Type
    - Severity
    - Business Impact
    - Priority
    - Routing (Assignment Group)
    """
    
    def __init__(
        self,
        priority_model: Optional[BaseClassifier] = None,
        routing_model: Optional[BaseClassifier] = None,
        alert_type_model: Optional[BaseClassifier] = None,
        severity_model: Optional[BaseClassifier] = None,
        business_impact_model: Optional[BaseClassifier] = None,
        classification_provider: str = Settings.CLASSIFICATION_PROVIDER,
        gemini_classifier: Optional[GeminiClassifier] = None
    ):
        """
        Initialize the classification pipeline.
        
        Args:
            priority_model: Trained classifier for priority prediction
            routing_model: Trained classifier for routing/assignment group
            alert_type_model: Trained classifier for alert type
            severity_model: Trained classifier for severity
            business_impact_model: Trained classifier for business impact
        """
        self.priority_model = priority_model
        self.routing_model = routing_model
        self.alert_type_model = alert_type_model
        self.severity_model = severity_model
        self.business_impact_model = business_impact_model
        if classification_provider not in {"ml", "gemini"}:
            raise ValueError("classification_provider must be 'ml' or 'gemini'")
        if classification_provider == "gemini" and gemini_classifier is None:
            raise ValueError("gemini_classifier is required when classification_provider='gemini'")
        self.classification_provider = classification_provider
        self.gemini_classifier = gemini_classifier
    
    def _predict_single(
        self,
        model: Optional[BaseClassifier],
        text: str,
        default_label: str = "UNKNOWN"
    ) -> ClassificationResult:
        """
        Make a single prediction using the provided model.
        
        Args:
            model: Trained classifier (or None)
            text: Normalized alert description
            default_label: Default label if model is not available
            
        Returns:
            ClassificationResult with label and confidence
        """
        if model is None or not model.is_trained:
            # Model not available - return default with low confidence
            return ClassificationResult(
                label=default_label,
                confidence=0.0
            )
        
        predictions = model.predict_with_confidence([text])
        label, confidence = predictions[0]
        
        return ClassificationResult(
            label=label,
            confidence=float(confidence)
        )
    
    def classify_alert(self, alert: StandardizedAlert) -> EnrichedAlert:
        """
        Classify a single standardized alert.
        
        Args:
            alert: StandardizedAlert from Stage 1
            
        Returns:
            EnrichedAlert with all Stage 2 classifications
        """
        text = alert.normalized_description
        
        # Predict all classifications
        alert_type = self._predict_single(
            self.alert_type_model,
            text,
            default_label="UNKNOWN"
        )
        
        severity = self._predict_single(
            self.severity_model,
            text,
            default_label="UNKNOWN"
        )
        
        business_impact = self._predict_single(
            self.business_impact_model,
            text,
            default_label="UNKNOWN"
        )
        
        priority = self._predict_single(
            self.priority_model,
            text,
            default_label="UNKNOWN"
        )
        
        routing = self._predict_single(
            self.routing_model,
            text,
            default_label="UNKNOWN"
        )
        
        if self.classification_provider == "gemini" and self.gemini_classifier:
            priority = self.gemini_classifier.predict_priority(alert.client, text, fallback=lambda: priority)
            routing = self.gemini_classifier.predict_routing(alert.client, text, fallback=lambda: routing)

        # Create enriched alert
        enriched = EnrichedAlert(
            alert_id=alert.alert_id,
            created_at=alert.created_at,
            client=alert.client,
            raw_description=alert.raw_description,
            normalized_description=alert.normalized_description,
            metadata=alert.metadata,
            alert_type=alert_type,
            severity=severity,
            business_impact=business_impact,
            priority=priority,
            routing=routing
        )
        
        return enriched
    
    def classify_batch(self, alerts: List[StandardizedAlert]) -> List[EnrichedAlert]:
        """
        Classify a batch of standardized alerts.
        
        Args:
            alerts: List of StandardizedAlert objects from Stage 1
            
        Returns:
            List of EnrichedAlert objects with Stage 2 classifications
        """
        return [self.classify_alert(alert) for alert in alerts]
    
    def set_model(self, task: str, model: BaseClassifier) -> None:
        """
        Set or replace a model for a specific classification task.
        
        Args:
            task: One of 'priority', 'routing', 'alert_type', 'severity', 'business_impact'
            model: Trained classifier
        """
        task_map = {
            'priority': 'priority_model',
            'routing': 'routing_model',
            'alert_type': 'alert_type_model',
            'severity': 'severity_model',
            'business_impact': 'business_impact_model'
        }
        
        if task not in task_map:
            raise ValueError(f"Invalid task: {task}. Must be one of {list(task_map.keys())}")
        
        setattr(self, task_map[task], model)
    
    def get_model(self, task: str) -> Optional[BaseClassifier]:
        """
        Get the model for a specific classification task.
        
        Args:
            task: One of 'priority', 'routing', 'alert_type', 'severity', 'business_impact'
            
        Returns:
            The classifier for that task (or None if not set)
        """
        task_map = {
            'priority': 'priority_model',
            'routing': 'routing_model',
            'alert_type': 'alert_type_model',
            'severity': 'severity_model',
            'business_impact': 'business_impact_model'
        }
        
        if task not in task_map:
            raise ValueError(f"Invalid task: {task}. Must be one of {list(task_map.keys())}")
        
        return getattr(self, task_map[task])
    
    def save_models(self, path: Path) -> None:
        """
        Save all trained models to disk.
        
        Args:
            path: Directory path where models should be saved
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        models = {
            'priority': self.priority_model,
            'routing': self.routing_model,
            'alert_type': self.alert_type_model,
            'severity': self.severity_model,
            'business_impact': self.business_impact_model
        }
        
        for task_name, model in models.items():
            if model is not None and model.is_trained:
                model.save(path)
    
    def load_models(self, path: Path, model_configs: Dict[str, BaseClassifier]) -> None:
        """
        Load trained models from disk.
        
        Args:
            path: Directory path where models are saved
            model_configs: Dict mapping task names to initialized (but untrained) model instances
        """
        path = Path(path)
        
        for task_name, model in model_configs.items():
            try:
                model.load(path)
                self.set_model(task_name, model)
            except FileNotFoundError:
                print(f"Warning: Model file for {task_name} not found at {path}")
    
    def get_status(self) -> Dict[str, bool]:
        """
        Get the training status of all models.
        
        Returns:
            Dict mapping task names to training status
        """
        return {
            'priority': self.priority_model is not None and self.priority_model.is_trained,
            'routing': self.routing_model is not None and self.routing_model.is_trained,
            'alert_type': self.alert_type_model is not None and self.alert_type_model.is_trained,
            'severity': self.severity_model is not None and self.severity_model.is_trained,
            'business_impact': self.business_impact_model is not None and self.business_impact_model.is_trained
        }
