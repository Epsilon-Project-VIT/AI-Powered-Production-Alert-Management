"""
Mock Reasoning Provider - Emulates structured reasoning without LLM.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from alert_management.stage4_analysis.reasoning.interfaces import ReasoningProvider
from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    Evidence,
    ProbableRootCause,
    AlternativeHypothesis,
    RCAResult,
    DiagnosisStatus,
    RecommendedAction,
    ActionType
)


class MockReasoningProvider(ReasoningProvider):
    """
    Mock reasoning provider for testing and development.
    
    Emulates Claude-style reasoning using deterministic logic.
    Does NOT invent evidence or claim certainty beyond available data.
    """
    
    def __init__(self, min_evidence_threshold: int = 3):
        """
        Initialize mock reasoning provider.
        
        Args:
            min_evidence_threshold: Minimum evidence pieces for sufficient diagnosis
        """
        self.min_evidence_threshold = min_evidence_threshold
    
    def get_provider_type(self) -> str:
        """Return provider type."""
        return "mock"
    
    def synthesize_rca(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        candidate_hypotheses: List[Dict[Any, Any]],
        historical_patterns: List[Dict[Any, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synthesize RCA using mock reasoning.
        
        This is a wrapper around the internal analyze method.
        """
        # Convert candidate hypotheses dicts to ProbableRootCause objects if needed
        rca_candidates = []
        if candidate_hypotheses:
            for hyp in candidate_hypotheses:
                if isinstance(hyp, ProbableRootCause):
                    rca_candidates.append(hyp)
        
        result = self.analyze(context, evidence, rca_candidates)
        
        # Convert to dict format expected by interface
        return {
            "diagnosis_status": result.diagnosis_status,
            "probable_root_cause": result.probable_root_cause,
            "alternative_hypotheses": result.alternative_hypotheses or [],
            "missing_evidence": result.missing_evidence or [],
            "reasoning_explanation": ""  # Not in schema
        }
    
    def analyze(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        rca_candidates: List[ProbableRootCause],
        missing_evidence: Optional[List[str]] = None
    ) -> RCAResult:
        """
        Perform mock reasoning analysis.
        
        Args:
            context: Incident context
            evidence: Collected evidence
            rca_candidates: Ranked RCA candidates
            missing_evidence: List of missing evidence types
            
        Returns:
            Complete RCA result
        """
        # Determine diagnosis status
        status = self._determine_status(evidence, rca_candidates, missing_evidence)
        
        # Select primary RCA
        if rca_candidates:
            primary_rca = rca_candidates[0]
            
            # Generate alternatives
            alternatives = []
            for candidate in rca_candidates[1:4]:  # Top 3 alternatives
                alt = AlternativeHypothesis(
                    component=candidate.component,
                    failure_type=candidate.failure_type,
                    description=candidate.description,
                    confidence=candidate.confidence,
                    reason_for_lower_rank=self._explain_why_not_primary(
                        primary_rca,
                        candidate
                    )
                )
                alternatives.append(alt)
        else:
            # No candidates - insufficient evidence
            primary_rca = ProbableRootCause(
                component="unknown",
                failure_type="insufficient_evidence",
                description="Unable to determine root cause from available evidence",
                confidence=0.0,
                supporting_evidence_ids=[]
            )
            alternatives = []
            status = DiagnosisStatus.INSUFFICIENT_EVIDENCE
        
        # Generate reasoning explanation
        reasoning = self._generate_reasoning(
            context,
            evidence,
            primary_rca,
            status
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            primary_rca,
            status
        )
        
        # Build result
        result = RCAResult(
            incident_id=context.incident_id,
            analysis_timestamp=datetime.now(),
            diagnosis_status=status,
            probable_root_cause=primary_rca,
            alternative_hypotheses=alternatives if alternatives else [],
            evidence=[],  # Pipeline will populate
            missing_evidence=missing_evidence if missing_evidence else [],
            recommended_actions=recommendations if recommendations else [],
            support_communication="",  # Pipeline will populate
            stakeholder_communication="",  # Pipeline will populate
            telemetry_is_mock=True,  # All telemetry providers are mock (even if evidence list is empty)
            human_review_required=True,
            review_reasons=[]
        )
        
        return result
    
    def _determine_status(
        self,
        evidence: List[Evidence],
        rca_candidates: List[ProbableRootCause],
        missing_evidence: Optional[List[str]]
    ) -> DiagnosisStatus:
        """
        Determine diagnosis status based on evidence and candidates.
        
        Args:
            evidence: Available evidence
            rca_candidates: RCA candidates
            missing_evidence: Missing evidence types
            
        Returns:
            Diagnosis status
        """
        if len(evidence) < self.min_evidence_threshold:
            return DiagnosisStatus.INSUFFICIENT_EVIDENCE
        
        if not rca_candidates:
            return DiagnosisStatus.INSUFFICIENT_EVIDENCE
        
        # Check if top candidates have similar confidence
        if len(rca_candidates) >= 2:
            top_confidence = rca_candidates[0].confidence
            second_confidence = rca_candidates[1].confidence
            
            if abs(top_confidence - second_confidence) < 0.15:
                return DiagnosisStatus.AMBIGUOUS
        
        # Check confidence threshold
        if rca_candidates[0].confidence < 0.4:
            return DiagnosisStatus.INSUFFICIENT_EVIDENCE
        
        return DiagnosisStatus.SUFFICIENT_EVIDENCE
    
    def _explain_why_not_primary(
        self,
        primary: ProbableRootCause,
        alternative: ProbableRootCause
    ) -> str:
        """
        Explain why alternative is not the primary hypothesis.
        
        Args:
            primary: Primary RCA
            alternative: Alternative hypothesis
            
        Returns:
            Explanation string
        """
        confidence_diff = primary.confidence - alternative.confidence
        
        if confidence_diff > 0.2:
            return f"Lower confidence ({alternative.confidence:.2f} vs {primary.confidence:.2f})"
        elif len(alternative.supporting_evidence_ids) < len(primary.supporting_evidence_ids):
            return f"Fewer supporting evidence items ({len(alternative.supporting_evidence_ids)} vs {len(primary.supporting_evidence_ids)})"
        else:
            return "Lower temporal precedence or evidence weight"
    
    def _generate_reasoning(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        primary_rca: ProbableRootCause,
        status: DiagnosisStatus
    ) -> str:
        """
        Generate reasoning summary.
        
        Args:
            context: Incident context
            evidence: Evidence
            primary_rca: Primary RCA
            status: Diagnosis status
            
        Returns:
            Reasoning summary
        """
        mock_count = len([e for e in evidence if e.is_mock])
        real_count = len([e for e in evidence if not e.is_mock])
        
        reasoning_parts = [
            f"Analysis of incident {context.incident_id} for {context.client}.",
            f"Examined {len(evidence)} pieces of evidence ({mock_count} mock, {real_count} real).",
        ]
        
        if status == DiagnosisStatus.SUFFICIENT_EVIDENCE:
            reasoning_parts.append(
                f"Primary hypothesis: {primary_rca.description} "
                f"(confidence: {primary_rca.confidence:.2f}). "
                f"Supported by {len(primary_rca.supporting_evidence_ids)} evidence items."
            )
        elif status == DiagnosisStatus.INSUFFICIENT_EVIDENCE:
            reasoning_parts.append(
                "Insufficient evidence to determine root cause with confidence."
            )
        else:  # AMBIGUOUS
            reasoning_parts.append(
                "Multiple competing hypotheses with similar confidence. "
                "Additional evidence needed for definitive conclusion."
            )
        
        # Add mock telemetry disclaimer
        if mock_count > 0:
            reasoning_parts.append(
                f"NOTE: {mock_count} evidence items are from mock/illustrative telemetry. "
                "These represent predefined scenarios, not actual production observations."
            )
        
        return " ".join(reasoning_parts)
    
    def _generate_recommendations(
        self,
        primary_rca: ProbableRootCause,
        status: DiagnosisStatus
    ) -> List[RecommendedAction]:
        """
        Generate recommended actions.
        
        Args:
            primary_rca: Primary RCA
            status: Diagnosis status
            
        Returns:
            List of recommended actions
        """
        recommendations = []
        
        if status == DiagnosisStatus.INSUFFICIENT_EVIDENCE:
            # Diagnostic actions
            recommendations.append(RecommendedAction(
                action="Collect additional telemetry data (logs, metrics, traces)",
                action_type=ActionType.DIAGNOSTIC,
                rationale="Insufficient evidence for root cause determination",
                requires_human_approval=False,
                priority=1
            ))
            recommendations.append(RecommendedAction(
                action=f"Escalate to {primary_rca.component} support team for investigation",
                action_type=ActionType.ESCALATION,
                rationale="Unable to determine root cause from available evidence",
                requires_human_approval=False,
                priority=2
            ))
        else:
            # Component-specific diagnostic
            recommendations.append(RecommendedAction(
                action=f"Review {primary_rca.component} component health and recent changes",
                action_type=ActionType.DIAGNOSTIC,
                rationale=f"Primary hypothesis points to {primary_rca.component}",
                requires_human_approval=False,
                priority=1
            ))
            
            # Remediation suggestion (requires approval)
            recommendations.append(RecommendedAction(
                action=f"Review approved remediation procedures for {primary_rca.failure_type}",
                action_type=ActionType.REMEDIATION,
                rationale="Standard remediation for identified failure type",
                requires_human_approval=True,
                priority=2
            ))
        
        return recommendations
