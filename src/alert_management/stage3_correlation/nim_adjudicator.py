"""
NVIDIA NIM-based correlation adjudicator for Stage 3.

Used ONLY for ambiguous/borderline correlation cases.
Does NOT replace the existing correlation system.
"""

import logging
from pathlib import Path
from typing import Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from alert_management.llm import NIMClient, NIMConfig, NIMStructuredOutputError

logger = logging.getLogger(__name__)

# Load prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


class CorrelationAdjudication(BaseModel):
    """Structured output for NIM correlation adjudication."""
    decision: Literal["related", "unrelated", "ambiguous"] = Field(
        ...,
        description="Whether alerts are related, unrelated, or still ambiguous"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the decision"
    )
    rationale: str = Field(
        ...,
        description="Explanation of the decision"
    )


class NIMCorrelationAdjudicator:
    """
    NVIDIA NIM-based correlation adjudicator.
    
    This adjudicator is used ONLY for ambiguous/borderline cases
    where the existing deterministic correlation system is uncertain.
    
    IMPORTANT:
    - Does NOT replace exact matching, semantic clustering, or temporal validation
    - No ground-truth incident labels exist
    - Agreement with rules is NOT accuracy (just agreement rate)
    - Adjudication decisions support human review, not automatic grouping
    """
    
    def __init__(self, config: NIMConfig):
        """
        Initialize NIM adjudicator.
        
        Args:
            config: NIM configuration
        """
        self.config = config
        self.client = NIMClient(config)
        
        # Load prompt template
        self.adjudication_prompt_template = self._load_prompt("stage3_adjudication_v1.txt")
        
        logger.info(f"NIM correlation adjudicator initialized with model: {config.model}")
    
    def _load_prompt(self, filename: str) -> str:
        """Load prompt template from prompts directory."""
        prompt_path = PROMPTS_DIR / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        return prompt_path.read_text()
    
    def adjudicate(
        self,
        alert_a: dict,
        alert_b: dict,
        semantic_similarity: float,
        temporal_gap: float,
        correlation_score: float
    ) -> CorrelationAdjudication:
        """
        Adjudicate whether two alerts are related (same incident) or unrelated.
        
        Args:
            alert_a: First alert dict with keys: client, timestamp, description, service, component, stage2_predictions
            alert_b: Second alert dict with keys: client, timestamp, description, service, component, stage2_predictions
            semantic_similarity: Cosine similarity of embeddings (0.0-1.0)
            temporal_gap: Time difference in seconds
            correlation_score: Overall correlation score from Stage 3
            
        Returns:
            CorrelationAdjudication with decision, confidence, rationale
            
        Raises:
            Various NIM exceptions if API call fails
        """
        # Build prompt
        prompt = self.adjudication_prompt_template.format(
            alert_a_client=alert_a.get("client", "Unknown"),
            alert_a_timestamp=alert_a.get("timestamp", "Unknown"),
            alert_a_description=alert_a.get("description", "Unknown"),
            alert_a_service=alert_a.get("service", "Unknown"),
            alert_a_component=alert_a.get("component", "Unknown"),
            alert_a_predictions=alert_a.get("stage2_predictions", "None"),
            alert_b_client=alert_b.get("client", "Unknown"),
            alert_b_timestamp=alert_b.get("timestamp", "Unknown"),
            alert_b_description=alert_b.get("description", "Unknown"),
            alert_b_service=alert_b.get("service", "Unknown"),
            alert_b_component=alert_b.get("component", "Unknown"),
            alert_b_predictions=alert_b.get("stage2_predictions", "None"),
            semantic_similarity=f"{semantic_similarity:.3f}",
            temporal_gap=f"{temporal_gap:.1f} seconds",
            correlation_score=f"{correlation_score:.3f}"
        )
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Call NIM with structured output
        try:
            adjudication = self.client.chat_completion_structured(
                messages=messages,
                schema=CorrelationAdjudication,
                temperature=self.config.temperature
            )
            
            logger.debug(
                f"NIM adjudication: {adjudication.decision} "
                f"(confidence: {adjudication.confidence:.3f})"
            )
            
            return adjudication
        
        except NIMStructuredOutputError as e:
            logger.error(f"NIM structured output error in adjudication: {e}")
            # Fallback: return ambiguous with low confidence
            return CorrelationAdjudication(
                decision="ambiguous",
                confidence=0.1,
                rationale="LLM adjudication failed, defaulting to ambiguous"
            )
    
    def adjudicate_batch(
        self,
        alert_pairs: list[tuple[dict, dict, float, float, float]]
    ) -> list[CorrelationAdjudication]:
        """
        Adjudicate a batch of alert pairs.
        
        Args:
            alert_pairs: List of (alert_a, alert_b, semantic_sim, temporal_gap, corr_score) tuples
            
        Returns:
            List of CorrelationAdjudication results
        """
        results = []
        for alert_a, alert_b, sem_sim, temp_gap, corr_score in alert_pairs:
            try:
                result = self.adjudicate(
                    alert_a=alert_a,
                    alert_b=alert_b,
                    semantic_similarity=sem_sim,
                    temporal_gap=temp_gap,
                    correlation_score=corr_score
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Adjudication failed for pair: {e}")
                # Fallback to ambiguous
                results.append(CorrelationAdjudication(
                    decision="ambiguous",
                    confidence=0.1,
                    rationale=f"Adjudication error: {str(e)}"
                ))
        
        return results
