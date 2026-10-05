"""
NVIDIA NIM-based alert classifier for Stage 2.

Operates in CHALLENGER MODE alongside existing TF-IDF models.
Does NOT replace the existing baseline models.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from alert_management.llm import NIMClient, NIMConfig, NIMStructuredOutputError
from alert_management.stage4_analysis.schemas import SourceType
from .schemas import ClassificationResult

logger = logging.getLogger(__name__)

# Load prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


class NIMClassificationPrediction(BaseModel):
    """Structured output for NIM classification."""
    predicted_label: str = Field(..., description="Predicted class label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    rationale: str = Field(..., description="Brief explanation of the prediction")
    uncertainty: Optional[str] = Field(None, description="Any uncertainty or ambiguity notes")
    source_type: str = Field(default="MODEL_PREDICTION", description="Always MODEL_PREDICTION")


class NIMClassifier:
    """
    NVIDIA NIM-based classifier for Priority and Routing.
    
    This is a CHALLENGER classifier that operates alongside the
    existing TF-IDF + Logistic Regression baseline.
    
    Features:
    - Priority classification (2 - High, 3 - Medium, 4 - Low)
    - Routing classification (Bridgestone, EA Sports, etc.)
    - Uses only arrival-time-safe alert information
    - Marks predictions as MODEL_PREDICTION (not ground truth)
    """
    
    def __init__(self, config: NIMConfig):
        """
        Initialize NIM classifier.
        
        Args:
            config: NIM configuration
        """
        self.config = config
        self.client = NIMClient(config)
        
        # Load prompt templates
        self.priority_prompt_template = self._load_prompt("stage2_priority_v1.txt")
        self.routing_prompt_template = self._load_prompt("stage2_routing_v1.txt")
        
        logger.info(f"NIM classifier initialized with model: {config.model}")
    
    def _load_prompt(self, filename: str) -> str:
        """Load prompt template from prompts directory."""
        prompt_path = PROMPTS_DIR / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        return prompt_path.read_text()
    
    def predict_priority(
        self,
        client: str,
        description: str
    ) -> ClassificationResult:
        """
        Predict Priority using NIM.
        
        Args:
            client: Client name
            description: Normalized alert description
            
        Returns:
            ClassificationResult with predicted priority
            
        Raises:
            Various NIM exceptions if API call fails
        """
        # Build prompt
        prompt = self.priority_prompt_template.format(
            client=client,
            description=description
        )
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Call NIM with structured output
        try:
            prediction = self.client.chat_completion_structured(
                messages=messages,
                schema=NIMClassificationPrediction,
                temperature=self.config.temperature
            )
            
            # Validate label is one of the expected Priority classes
            valid_labels = ["2 - High", "3 - Medium", "4 - Low"]
            if prediction.predicted_label not in valid_labels:
                logger.warning(
                    f"NIM predicted invalid priority label: {prediction.predicted_label}, "
                    f"using '3 - Medium' as fallback"
                )
                prediction.predicted_label = "3 - Medium"
                prediction.confidence = max(0.1, prediction.confidence - 0.3)  # Lower confidence
            
            logger.debug(
                f"NIM Priority prediction: {prediction.predicted_label} "
                f"(confidence: {prediction.confidence:.3f})"
            )
            
            return ClassificationResult(
                label=prediction.predicted_label,
                confidence=prediction.confidence
            )
        
        except NIMStructuredOutputError as e:
            logger.error(f"NIM structured output error in priority prediction: {e}")
            # Fallback: return low-confidence medium priority
            return ClassificationResult(
                label="3 - Medium",
                confidence=0.1
            )
    
    def predict_routing(
        self,
        client: str,
        description: str
    ) -> ClassificationResult:
        """
        Predict Routing (Assignment Group) using NIM.
        
        Args:
            client: Client name
            description: Normalized alert description
            
        Returns:
            ClassificationResult with predicted routing
            
        Raises:
            Various NIM exceptions if API call fails
        """
        # Build prompt
        prompt = self.routing_prompt_template.format(
            client=client,
            description=description
        )
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Call NIM with structured output
        try:
            prediction = self.client.chat_completion_structured(
                messages=messages,
                schema=NIMClassificationPrediction,
                temperature=self.config.temperature
            )
            
            # Validate label is one of the expected routing classes
            valid_labels = [
                "Bridgestone",
                "EA Sports",
                "Pizza Hut Brands",
                "Product Support - Agility Loyalty"
            ]
            if prediction.predicted_label not in valid_labels:
                logger.warning(
                    f"NIM predicted invalid routing label: {prediction.predicted_label}, "
                    f"checking for partial match"
                )
                # Try to match partial (e.g., "EA" -> "EA Sports")
                for valid_label in valid_labels:
                    if prediction.predicted_label.lower() in valid_label.lower():
                        logger.info(f"Mapped '{prediction.predicted_label}' to '{valid_label}'")
                        prediction.predicted_label = valid_label
                        break
                else:
                    # No match found - use client name as heuristic fallback
                    logger.warning(f"Using client-based fallback for routing")
                    if "ea" in client.lower():
                        prediction.predicted_label = "EA Sports"
                    elif "bridgestone" in client.lower():
                        prediction.predicted_label = "Bridgestone"
                    elif "pizza" in client.lower():
                        prediction.predicted_label = "Pizza Hut Brands"
                    else:
                        prediction.predicted_label = "Product Support - Agility Loyalty"
                    prediction.confidence = max(0.1, prediction.confidence - 0.3)
            
            logger.debug(
                f"NIM Routing prediction: {prediction.predicted_label} "
                f"(confidence: {prediction.confidence:.3f})"
            )
            
            return ClassificationResult(
                label=prediction.predicted_label,
                confidence=prediction.confidence
            )
        
        except NIMStructuredOutputError as e:
            logger.error(f"NIM structured output error in routing prediction: {e}")
            # Fallback: use client name heuristic
            if "ea" in client.lower():
                label = "EA Sports"
            elif "bridgestone" in client.lower():
                label = "Bridgestone"
            elif "pizza" in client.lower():
                label = "Pizza Hut Brands"
            else:
                label = "Product Support - Agility Loyalty"
            
            return ClassificationResult(
                label=label,
                confidence=0.1
            )
    
    def classify(
        self,
        client: str,
        description: str,
        classify_priority: bool = True,
        classify_routing: bool = True
    ) -> dict:
        """
        Classify alert using NIM for both Priority and Routing.
        
        Args:
            client: Client name
            description: Normalized alert description
            classify_priority: Whether to predict priority
            classify_routing: Whether to predict routing
            
        Returns:
            Dict with 'priority' and/or 'routing' ClassificationResult
        """
        results = {}
        
        if classify_priority:
            results["priority"] = self.predict_priority(client, description)
        
        if classify_routing:
            results["routing"] = self.predict_routing(client, description)
        
        return results
