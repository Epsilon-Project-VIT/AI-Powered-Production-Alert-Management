"""
Message Generator - Generate support and stakeholder communications.
"""

from typing import List
from datetime import datetime

from alert_management.stage4_analysis.schemas import (
    RCAResult,
    IncidentContext,
    DiagnosisStatus,
    RecommendedAction
)
from alert_management.stage4_analysis.policy.policy_gate import PolicyDecision


class MessageGenerator:
    """Generate communications for different audiences."""
    
    def generate_support_message(
        self,
        context: IncidentContext,
        result: RCAResult,
        action_decisions: List[tuple[RecommendedAction, PolicyDecision]]
    ) -> str:
        """
        Generate technical support team message.
        
        Args:
            context: Incident context
            result: RCA result
            action_decisions: Action policy decisions
            
        Returns:
            Technical support message
        """
        lines = [
            "=" * 80,
            "INCIDENT ANALYSIS REPORT - TECHNICAL",
            "=" * 80,
            "",
            f"Incident ID: {result.incident_id}",
            f"Client: {context.client}",
            f"Analysis Time: {result.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Incident Window: {context.incident_start.strftime('%Y-%m-%d %H:%M:%S')} to {context.incident_end.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "SYMPTOMS:",
            f"  - {len(context.alert_ids)} alerts generated",
            f"  - Affected services: {', '.join(context.services) if context.services else 'Unknown'}",
            "",
            "ROOT CAUSE ANALYSIS:",
            f"  Status: {result.diagnosis_status.value.upper()}",
            f"  Component: {result.probable_root_cause.component}",
            f"  Failure Type: {result.probable_root_cause.failure_type}",
            f"  Confidence: {result.probable_root_cause.confidence:.2%}",
            f"  Description: {result.probable_root_cause.description}",
            "",
            "SUPPORTING EVIDENCE:",
            f"  Total evidence items: {len(result.evidence)}",
            f"  Evidence supporting primary RCA: {len(result.probable_root_cause.supporting_evidence_ids) if result.probable_root_cause else 0}",
        ]
        
        # Add alternative hypotheses
        if result.alternative_hypotheses:
            lines.extend([
                "",
                "ALTERNATIVE HYPOTHESES:",
            ])
            for alt in result.alternative_hypotheses[:3]:
                lines.append(
                    f"  - {alt.component} / {alt.failure_type} "
                    f"(confidence: {alt.confidence:.2%}) - {alt.reason_for_lower_rank}"
                )
        
        # Add reasoning
        if result.probable_root_cause:
            lines.extend([
                "",
                "REASONING:",
                f"  Analysis based on {len(result.evidence)} pieces of evidence.",
                f"  Primary hypothesis: {result.probable_root_cause.description}",
            ])
        
        # Add missing evidence
        if result.missing_evidence:
            lines.extend([
                "",
                "MISSING EVIDENCE:",
                f"  {', '.join(result.missing_evidence)}",
            ])
        
        # Add recommended actions
        if result.recommended_actions:
            lines.extend([
                "",
                "RECOMMENDED ACTIONS:",
            ])
            for action, decision in action_decisions:
                status_str = f"[{decision.value.upper()}]"
                lines.append(
                    f"  {status_str} [{action.action_type.value}] "
                    f"P{action.priority}: {action.action}"
                )
        
        lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def generate_stakeholder_message(
        self,
        context: IncidentContext,
        result: RCAResult
    ) -> str:
        """
        Generate business stakeholder message.
        
        Args:
            context: Incident context
            result: RCA result
            
        Returns:
            Stakeholder-friendly message
        """
        # Determine status message
        if result.diagnosis_status == DiagnosisStatus.SUFFICIENT_EVIDENCE:
            status_msg = "Root cause identified"
        elif result.diagnosis_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE:
            status_msg = "Investigation ongoing - additional data needed"
        else:
            status_msg = "Multiple possible causes under investigation"
        
        # Determine impact message
        if len(context.alert_ids) >= 10:
            impact = "significant service disruption"
        elif len(context.alert_ids) >= 5:
            impact = "moderate service impact"
        else:
            impact = "minor service impact"
        
        lines = [
            f"Incident Update - {context.client}",
            "",
            f"Incident ID: {result.incident_id}",
            f"Time: {context.incident_start.strftime('%Y-%m-%d %H:%M')} - {context.incident_end.strftime('%H:%M')}",
            "",
            f"Status: {status_msg}",
            "",
            f"Impact: {len(context.alert_ids)} alerts detected, indicating {impact}.",
            "",
            "Current Understanding:",
        ]
        
        if result.diagnosis_status == DiagnosisStatus.SUFFICIENT_EVIDENCE:
            lines.append(
                f"Analysis indicates issue with {result.probable_root_cause.component} component. "
                f"Support team is implementing corrective actions."
            )
        elif result.diagnosis_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE:
            lines.append(
                "Technical teams are gathering additional diagnostic information "
                "to determine root cause."
            )
        else:
            lines.append(
                "Analysis has identified multiple possible causes. "
                "Support teams are conducting targeted diagnostics."
            )
        
        lines.extend([
            "",
            "Next Steps:",
            "- Continue monitoring for resolution",
            "- Technical team conducting root cause investigation",
            "- Updates will be provided as analysis progresses",
            "",
            "For technical details, please contact the support team.",
        ])
        
        return "\n".join(lines)
