"""
RCA Candidate Ranker - Rank and score RCA candidates.
"""

from typing import List

from alert_management.stage4_analysis.schemas import (
    ProbableRootCause,
    Evidence
)


class RCACandidateRanker:
    """
    Rank RCA candidates using weighted scoring.
    
    Scoring factors:
    - Number of supporting evidence
    - Evidence weights
    - Temporal precedence
    - Component consistency
    """
    
    def __init__(
        self,
        evidence_weight: float = 0.6,
        count_weight: float = 0.4
    ):
        """
        Initialize ranker with configurable weights.
        
        Args:
            evidence_weight: Weight for evidence quality
            count_weight: Weight for evidence count
        """
        self.evidence_weight = evidence_weight
        self.count_weight = count_weight
    
    def rank_candidates(
        self,
        candidates: List[ProbableRootCause],
        evidence: List[Evidence]
    ) -> List[ProbableRootCause]:
        """
        Rank candidates and update confidence scores.
        
        Args:
            candidates: RCA candidates
            evidence: All evidence
            
        Returns:
            Ranked candidates (descending confidence)
        """
        if not candidates:
            return []
        
        # Build evidence lookup
        evidence_map = {ev.source_id: ev for ev in evidence}
        
        # Score each candidate
        for candidate in candidates:
            # Evidence quality score
            supporting_evidence = [
                evidence_map[ev_id]
                for ev_id in candidate.supporting_evidence_ids
                if ev_id in evidence_map
            ]
            
            if supporting_evidence:
                avg_evidence_weight = sum(
                    ev.weight for ev in supporting_evidence
                ) / len(supporting_evidence)
            else:
                avg_evidence_weight = 0.0
            
            # Evidence count score (normalized)
            count_score = min(len(supporting_evidence) / 5.0, 1.0)
            
            # Combined confidence score
            confidence = (
                self.evidence_weight * avg_evidence_weight +
                self.count_weight * count_score
            )
            
            # Update candidate confidence
            candidate.confidence = min(confidence, 0.95)  # Cap at 0.95
        
        # Sort by confidence descending
        ranked = sorted(
            candidates,
            key=lambda c: c.confidence,
            reverse=True
        )
        
        return ranked
