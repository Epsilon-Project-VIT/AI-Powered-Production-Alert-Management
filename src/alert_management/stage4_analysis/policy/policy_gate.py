"""
Policy Gate - Human review routing for actions.
"""

from typing import List
from enum import Enum

from alert_management.stage4_analysis.schemas import RecommendedAction, ActionType


class PolicyDecision(str, Enum):
    """Policy decision outcomes."""
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class PolicyGate:
    """
    Policy gate for action approval.
    
    Routes consequential actions to human review.
    """
    
    def __init__(
        self,
        auto_approve_diagnostics: bool = True,
        auto_approve_escalations: bool = True
    ):
        """
        Initialize policy gate.
        
        Args:
            auto_approve_diagnostics: Auto-approve diagnostic actions
            auto_approve_escalations: Auto-approve escalations
        """
        self.auto_approve_diagnostics = auto_approve_diagnostics
        self.auto_approve_escalations = auto_approve_escalations
    
    def evaluate_action(self, action: RecommendedAction) -> PolicyDecision:
        """
        Evaluate single action against policy.
        
        Args:
            action: Action to evaluate
            
        Returns:
            Policy decision
        """
        # Always require review for actions marked as requiring approval
        if action.requires_human_approval:
            return PolicyDecision.REQUIRES_HUMAN_REVIEW
        
        # Remediation actions are consequential - require review
        if action.action_type == ActionType.REMEDIATION:
            return PolicyDecision.REQUIRES_HUMAN_REVIEW
        
        # Diagnostic actions can be auto-approved
        if action.action_type == ActionType.DIAGNOSTIC:
            if self.auto_approve_diagnostics:
                return PolicyDecision.APPROVED
            else:
                return PolicyDecision.REQUIRES_HUMAN_REVIEW
        
        # Escalations can be auto-approved
        if action.action_type == ActionType.ESCALATION:
            if self.auto_approve_escalations:
                return PolicyDecision.APPROVED
            else:
                return PolicyDecision.REQUIRES_HUMAN_REVIEW
        
        # Default to human review for unknown action types
        return PolicyDecision.REQUIRES_HUMAN_REVIEW
    
    def evaluate_actions(
        self,
        actions: List[RecommendedAction]
    ) -> List[tuple[RecommendedAction, PolicyDecision]]:
        """
        Evaluate multiple actions.
        
        Args:
            actions: List of actions
            
        Returns:
            List of (action, decision) tuples
        """
        return [(action, self.evaluate_action(action)) for action in actions]
