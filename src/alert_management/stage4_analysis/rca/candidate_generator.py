"""
RCA Candidate Generator - Generate RCA hypotheses from evidence.
"""

from typing import List, Set
from collections import Counter

from alert_management.stage4_analysis.schemas import (
    Evidence,
    ProbableRootCause,
    IncidentContext
)


class RCACandidateGenerator:
    """Generate RCA candidates from evidence."""
    
    def generate_candidates(
        self,
        context: IncidentContext,
        evidence: List[Evidence]
    ) -> List[ProbableRootCause]:
        """
        Generate RCA candidates from evidence.
        
        Uses deterministic rules based on evidence signals.
        
        Args:
            context: Incident context
            evidence: Collected evidence
            
        Returns:
            List of RCA candidates
        """
        candidates = []
        
        # Extract components mentioned in evidence
        component_counts: Counter = Counter()
        failure_types: Set[str] = set()
        
        for ev in evidence:
            if ev.metadata and "component" in ev.metadata:
                component_counts[ev.metadata["component"]] += ev.weight
            
            # Extract failure types from descriptions
            desc_lower = ev.description.lower()
            if "connection" in desc_lower or "pool" in desc_lower:
                failure_types.add("connection_exhaustion")
            if "timeout" in desc_lower:
                failure_types.add("timeout")
            if "error" in desc_lower:
                failure_types.add("service_error")
            if "anomaly" in desc_lower or "degradation" in desc_lower:
                failure_types.add("performance_degradation")
        
        # Generate candidates for top components
        for component, weight_sum in component_counts.most_common(3):
            for failure_type in failure_types:
                candidate = ProbableRootCause(
                    component=component,
                    failure_type=failure_type,
                    description=f"{component} {failure_type.replace('_', ' ')}",
                    confidence=0.5,  # Will be updated by ranker
                    supporting_evidence_ids=[
                        ev.source_id for ev in evidence
                        if ev.metadata and ev.metadata.get("component") == component
                    ][:5]
                )
                candidates.append(candidate)
        
        # Fallback: generate from services if no component evidence
        if not candidates and context.services:
            for service in context.services[:2]:
                candidate = ProbableRootCause(
                    component=service,
                    failure_type="service_error",
                    description=f"{service} service error",
                    confidence=0.3,
                    supporting_evidence_ids=[ev.source_id for ev in evidence[:3]]
                )
                candidates.append(candidate)
        
        return candidates
