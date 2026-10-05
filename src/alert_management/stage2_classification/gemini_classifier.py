"""Gemini challenger classifier for arrival-time-safe Stage 2 tasks."""

import time
from typing import Any, Callable, Dict, Iterable, Optional

from pydantic import BaseModel, Field

from alert_management.config.settings import Settings
from alert_management.llm import GeminiClient, GeminiConfig
from alert_management.llm.exceptions import NIMError
from .schemas import ClassificationResult

PRIORITY_LABELS = ("2 - High", "3 - Medium", "4 - Low")
ROUTING_LABELS = ("Client Support Subscription Services - Bridgestone", "Client Support Subscription Services - EA Sports", "Client Support Subscription Services - Pizza Hut Brands", "Product Support - Agility Loyalty")


class GeminiClassificationPrediction(BaseModel):
    predicted_label: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, description="Model-reported experimental score")
    reason: str = Field(min_length=1)
    provider: str = "gemini"
    model: str = Field(min_length=1)


class GeminiClassifier:
    """Classifies priority/routing without exposing outcome or target fields."""

    def __init__(self, config: GeminiConfig, client: Optional[GeminiClient] = None):
        self.config = config
        self.client = client or GeminiClient(config)
        self.request_count = self.success_count = self.schema_failure_count = self.api_failure_count = 0
        self.latencies_ms: list[float] = []

    @staticmethod
    def arrival_time_input(client: str, description: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build the only payload shape Stage 2 is allowed to send to an LLM."""
        forbidden_found = set((metadata or {}).keys()) & set(Settings.FORBIDDEN_METADATA_FIELDS)
        if forbidden_found:
            raise ValueError("Forbidden Stage 2 fields cannot be sent to Gemini")
        safe_metadata = {key: value for key, value in (metadata or {}).items() if key in Settings.ALLOWED_METADATA_FIELDS}
        return {"client": client, "normalized_description": description, "metadata": safe_metadata}

    def _predict(self, task: str, labels: Iterable[str], client: str, description: str, fallback: Callable[[], ClassificationResult]) -> ClassificationResult:
        safe_input = self.arrival_time_input(client, description)
        prompt = f"Classify this arrival-time alert for {task}. Allowed labels: {list(labels)}. Use only supplied fields; do not infer outcomes. Alert: {safe_input}"
        self.request_count += 1
        started = time.monotonic()
        try:
            prediction = self.client.chat_completion_structured([{"role": "user", "content": prompt}], GeminiClassificationPrediction, temperature=self.config.temperature)
            latency_ms = (time.monotonic() - started) * 1000
            self.latencies_ms.append(latency_ms)
            if prediction.provider != "gemini" or prediction.model != self.config.model or prediction.predicted_label not in labels:
                self.schema_failure_count += 1
                return self._fallback(fallback)
            self.success_count += 1
            return ClassificationResult(label=prediction.predicted_label, confidence=prediction.confidence, provider="gemini", model=self.config.model, latency_ms=latency_ms)
        except NIMError:
            self.api_failure_count += 1
            return self._fallback(fallback)

    @staticmethod
    def _fallback(fallback: Callable[[], ClassificationResult]) -> ClassificationResult:
        return fallback().model_copy(update={"is_fallback": True})

    def predict_priority(self, client: str, description: str, fallback: Callable[[], ClassificationResult]) -> ClassificationResult:
        return self._predict("priority", PRIORITY_LABELS, client, description, fallback)

    def predict_routing(self, client: str, description: str, fallback: Callable[[], ClassificationResult]) -> ClassificationResult:
        return self._predict("assignment group / routing", ROUTING_LABELS, client, description, fallback)
