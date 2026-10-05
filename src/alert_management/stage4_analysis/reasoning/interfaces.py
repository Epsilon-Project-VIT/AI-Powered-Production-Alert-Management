"""
Abstract interface for reasoning providers.

Reasoning providers synthesize evidence and hypotheses to produce
structured RCA results. Implementations can be:
- Mock (emulates Claude-style reasoning without API)
- Bedrock Claude (real Amazon Bedrock integration)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..schemas import (
    IncidentContext,
    Evidence,
    ProbableRootCause,
    AlternativeHypothesis,
    DiagnosisStatus
)


class ReasoningProvider(ABC):
    """
    Abstract interface for RCA reasoning providers.
    
    Reasoning providers receive:
    - Incident context
    - Evidence (logs, metrics, traces, historical patterns)
    - Candidate hypotheses (pre-generated)
    
    And produce:
    - Probable root cause (or None if insufficient evidence)
    - Alternative hypotheses (ranked)
    - Diagnosis status
    - Missing evidence identification
    """
    
    @abstractmethod
    def synthesize_rca(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        candidate_hypotheses: List[Dict[str, Any]],
        historical_patterns: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synthesize RCA from evidence and candidate hypotheses.
        
        Args:
            context: Incident context
            evidence: List of evidence items with provenance
            candidate_hypotheses: Pre-generated RCA candidates
            historical_patterns: Optional historical alert/ticket patterns
        
        Returns:
            Dict containing:
                - diagnosis_status: DiagnosisStatus
                - probable_root_cause: Optional[ProbableRootCause]
                - alternative_hypotheses: List[AlternativeHypothesis]
                - missing_evidence: List[str]
                - reasoning_explanation: str
        
        Notes:
            - Must handle insufficient evidence gracefully
            - Must identify ambiguous cases
            - Must not invent telemetry or evidence
            - Must not claim mock data is real
            - Must preserve evidence provenance
        """
        pass
    
    @abstractmethod
    def get_provider_type(self) -> str:
        """
        Return provider type identifier.
        
        Returns:
            String identifying provider: "mock" or "bedrock_claude"
        """
        pass
