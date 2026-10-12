"""
NVIDIA NIM Reasoning Provider for Stage 4 RCA.

Implements the ReasoningProvider interface using NVIDIA NIM LLM.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from alert_management.llm import NIMClient, NIMConfig, NIMStructuredOutputError
from alert_management.stage4_analysis.reasoning.interfaces import ReasoningProvider
from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    Evidence,
    ProbableRootCause,
    AlternativeHypothesis,
    DiagnosisStatus,
    RecommendedAction,
    ActionType,
    RCAResult,
    SourceType
)

logger = logging.getLogger(__name__)

# Load prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "prompts"


class NIMRCAOutput(BaseModel):
    """Structured output schema for NIM RCA reasoning."""
    diagnosis_status: str = Field(
        ...,
        description="One of: sufficient_evidence, insufficient_evidence, ambiguous"
    )
    probable_root_cause: Optional[Dict[str, Any]] = Field(
        None,
        description="Primary root cause (null if insufficient evidence)"
    )
    alternative_hypotheses: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Alternative root cause candidates"
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Types of missing evidence"
    )
    recommended_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recommended diagnostic/remediation actions"
    )
    support_communication: str = Field(
        ...,
        description="Technical communication for support engineers"
    )
    stakeholder_communication: str = Field(
        ...,
        description="Business-friendly communication for stakeholders"
    )


class NIMReasoningProvider(ReasoningProvider):
    """
    NVIDIA NIM-based reasoning provider for RCA.
    
    This provider uses LLM to synthesize evidence and generate
    structured RCA results. It implements the same interface as
    MockReasoningProvider.
    
    CRITICAL SAFETY FEATURES:
    - Evidence-grounded reasoning (no invented telemetry)
    - Provenance preservation (mock vs real)
    - Human approval for consequential actions
    - Uncertainty preservation in communications
    - Evidence ID validation
    """
    
    def __init__(self, config: NIMConfig, min_evidence_threshold: int = 3):
        """
        Initialize NIM reasoning provider.
        
        Args:
            config: NIM configuration
            min_evidence_threshold: Minimum evidence pieces for sufficient diagnosis
        """
        self.config = config
        self.client = NIMClient(config)
        self.min_evidence_threshold = min_evidence_threshold
        
        # Load prompt template
        self.rca_prompt_template = self._load_prompt("stage4_rca_v1.txt")
        
        logger.info(f"NIM reasoning provider initialized with model: {config.model}")
    
    def _load_prompt(self, filename: str) -> str:
        """Load prompt template from prompts directory."""
        prompt_path = PROMPTS_DIR / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        return prompt_path.read_text()
    
    def get_provider_type(self) -> str:
        """Return provider type."""
        return "nim"
    
    def synthesize_rca(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        candidate_hypotheses: List[Dict[str, Any]],
        historical_patterns: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synthesize RCA using NVIDIA NIM LLM.
        
        Args:
            context: Incident context
            evidence: List of evidence items with provenance
            candidate_hypotheses: Pre-generated RCA candidates
            historical_patterns: Optional historical alert/ticket patterns
        
        Returns:
            Dict containing RCA components
        """
        # Build evidence summary with provenance
        evidence_summary = self._format_evidence(evidence)
        
        # Format RCA candidates
        rca_candidates_str = self._format_candidates(candidate_hypotheses)
        
        # Format historical patterns
        historical_str = self._format_historical(historical_patterns)
        
        # Identify missing evidence
        missing_evidence = self._identify_missing_evidence(evidence)
        
        # Build prompt
        prompt = self.rca_prompt_template.format(
            incident_id=context.incident_id,
            client=context.client,
            alert_count=context.alert_count,
            incident_start=context.incident_start.isoformat(),
            incident_end=context.incident_end.isoformat() if context.incident_end else "ongoing",
            services=", ".join(context.services) if context.services else "unknown",
            components=", ".join(context.components) if context.components else "unknown",
            normalized_descriptions="\n  - ".join(context.normalized_descriptions[:3]),  # First 3
            evidence_summary=evidence_summary,
            rca_candidates=rca_candidates_str,
            historical_patterns=historical_str,
            missing_evidence=", ".join(missing_evidence) if missing_evidence else "None identified"
        )
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Call NIM with structured output
        try:
            logger.info(f"Calling NIM for RCA synthesis (incident: {context.incident_id})")
            nim_output = self.client.chat_completion_structured(
                messages=messages,
                schema=NIMRCAOutput,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            # Validate and convert to expected format
            validated_result = self._validate_and_convert(
                nim_output=nim_output,
                context=context,
                evidence=evidence
            )
            
            logger.info(
                f"NIM RCA completed: status={validated_result['diagnosis_status']}, "
                f"evidence_count={len(evidence)}"
            )
            
            return validated_result
        
        except NIMStructuredOutputError as e:
            logger.error(f"NIM structured output error in RCA: {e}")
            # Fallback to insufficient evidence
            return self._fallback_insufficient_evidence(context, evidence, missing_evidence)
        
        except Exception as e:
            logger.error(f"NIM RCA failed with unexpected error: {e}")
            return self._fallback_insufficient_evidence(context, evidence, missing_evidence)
    
    def _format_evidence(self, evidence: List[Evidence]) -> str:
        """Format evidence list with provenance for prompt."""
        if not evidence:
            return "No evidence available."
        
        lines = []
        for i, ev in enumerate(evidence[:20], 1):  # Limit to first 20 to fit in context
            provenance_flag = f"[{ev.source_type.value}]"
            mock_flag = "[MOCK]" if ev.is_mock else "[REAL]"
            lines.append(
                f"{i}. {provenance_flag} {mock_flag} {ev.source} | "
                f"{ev.timestamp.isoformat()} | {ev.description} | "
                f"weight={ev.weight:.2f} | id={ev.source_id}"
            )
        
        if len(evidence) > 20:
            lines.append(f"... and {len(evidence) - 20} more evidence items")
        
        return "\n".join(lines)
    
    def _format_candidates(self, candidates: List[Dict[str, Any]]) -> str:
        """Format RCA candidates for prompt."""
        if not candidates:
            return "No pre-generated candidates available."
        
        lines = []
        for i, cand in enumerate(candidates[:5], 1):  # Top 5 candidates
            if isinstance(cand, dict):
                component = cand.get("component", "unknown")
                failure_type = cand.get("failure_type", "unknown")
                confidence = cand.get("confidence", 0.0)
                description = cand.get("description", "No description")
                lines.append(
                    f"{i}. {component} / {failure_type} (confidence: {confidence:.2f})\n"
                    f"   {description}"
                )
        
        return "\n".join(lines)
    
    def _format_historical(self, patterns: Optional[List[Dict[str, Any]]]) -> str:
        """Format historical patterns for prompt."""
        if not patterns:
            return "No historical patterns available."
        
        lines = []
        for i, pattern in enumerate(patterns[:5], 1):  # Top 5 patterns
            if isinstance(pattern, dict):
                description = pattern.get("description", "No description")
                lines.append(f"{i}. {description}")
        
        return "\n".join(lines)
    
    def _identify_missing_evidence(self, evidence: List[Evidence]) -> List[str]:
        """Identify missing evidence types."""
        available_sources = {ev.source for ev in evidence}
        expected_sources = {"logs", "metrics", "traces"}
        missing = expected_sources - available_sources
        return list(missing)
    
    def _validate_and_convert(
        self,
        nim_output: NIMRCAOutput,
        context: IncidentContext,
        evidence: List[Evidence]
    ) -> Dict[str, Any]:
        """
        Validate NIM output and convert to expected format.
        
        Validates:
        - diagnosis_status is valid enum
        - evidence IDs exist
        - confidence values are 0.0-1.0
        - required fields present
        """
        # Validate diagnosis status
        try:
            diagnosis_status = DiagnosisStatus(nim_output.diagnosis_status)
        except ValueError:
            logger.warning(f"Invalid diagnosis status: {nim_output.diagnosis_status}, using INSUFFICIENT_EVIDENCE")
            diagnosis_status = DiagnosisStatus.INSUFFICIENT_EVIDENCE
        
        # Build evidence ID set for validation
        valid_evidence_ids = {ev.source_id for ev in evidence}
        
        # Parse probable root cause
        probable_root_cause = None
        if nim_output.probable_root_cause:
            prc_dict = nim_output.probable_root_cause
            # Validate evidence IDs
            supporting_ids = prc_dict.get("supporting_evidence_ids", [])
            validated_ids = [eid for eid in supporting_ids if eid in valid_evidence_ids]
            if len(validated_ids) < len(supporting_ids):
                logger.warning(
                    f"Removed {len(supporting_ids) - len(validated_ids)} "
                    "invalid evidence IDs from probable_root_cause"
                )
            
            # Clamp confidence
            confidence = max(0.0, min(1.0, prc_dict.get("confidence", 0.5)))
            
            probable_root_cause = ProbableRootCause(
                component=prc_dict.get("component", "unknown"),
                failure_type=prc_dict.get("failure_type", "unknown"),
                confidence=confidence,
                description=prc_dict.get("description", "No description provided"),
                supporting_evidence_ids=validated_ids
            )
        
        # Parse alternative hypotheses
        alternative_hypotheses = []
        for alt_dict in nim_output.alternative_hypotheses[:3]:  # Max 3 alternatives
            confidence = max(0.0, min(1.0, alt_dict.get("confidence", 0.3)))
            alt = AlternativeHypothesis(
                component=alt_dict.get("component", "unknown"),
                failure_type=alt_dict.get("failure_type", "unknown"),
                confidence=confidence,
                reason_for_lower_rank=alt_dict.get("reason_for_lower_rank", "Lower confidence")
            )
            alternative_hypotheses.append(alt)
        
        # Parse recommended actions
        recommended_actions = []
        for action_dict in nim_output.recommended_actions[:5]:  # Max 5 actions
            action_type_str = action_dict.get("action_type", "diagnostic")
            try:
                action_type = ActionType(action_type_str)
            except ValueError:
                logger.warning(f"Invalid action type: {action_type_str}, using DIAGNOSTIC")
                action_type = ActionType.DIAGNOSTIC
            
            # Ensure consequential actions require approval
            requires_approval = action_dict.get("requires_human_approval", True)
            if action_type == ActionType.REMEDIATION:
                requires_approval = True  # ALWAYS require approval for remediation
            
            action = RecommendedAction(
                action=action_dict.get("action", "No action specified"),
                priority=max(1, min(5, action_dict.get("priority", 3))),
                action_type=action_type,
                rationale=action_dict.get("rationale", "No rationale provided"),
                requires_human_approval=requires_approval,
                runbook_reference=action_dict.get("runbook_reference")
            )
            recommended_actions.append(action)
        
        return {
            "diagnosis_status": diagnosis_status,
            "probable_root_cause": probable_root_cause,
            "alternative_hypotheses": alternative_hypotheses,
            "missing_evidence": nim_output.missing_evidence,
            "recommended_actions": recommended_actions,
            "support_communication": nim_output.support_communication,
            "stakeholder_communication": nim_output.stakeholder_communication,
            "reasoning_explanation": ""  # Not in NIM output
        }
    
    def _fallback_insufficient_evidence(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        missing_evidence: List[str]
    ) -> Dict[str, Any]:
        """Fallback when NIM fails: return insufficient evidence status."""
        return {
            "diagnosis_status": DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            "probable_root_cause": None,
            "alternative_hypotheses": [],
            "missing_evidence": missing_evidence,
            "recommended_actions": [
                RecommendedAction(
                    action="NIM reasoning failed - collect additional diagnostic data",
                    priority=1,
                    action_type=ActionType.DIAGNOSTIC,
                    rationale="LLM synthesis failed, manual investigation required",
                    requires_human_approval=False
                )
            ],
            "support_communication": (
                f"RCA analysis failed for incident {context.incident_id}. "
                f"LLM reasoning provider encountered an error. "
                f"Manual investigation required. Evidence count: {len(evidence)}."
            ),
            "stakeholder_communication": (
                f"Incident {context.incident_id} investigation in progress. "
                f"Automated analysis incomplete - engineering team investigating manually."
            ),
            "reasoning_explanation": ""
        }

    def analyze(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        rca_candidates: List[ProbableRootCause],
        missing_evidence: Optional[List[str]] = None
    ) -> RCAResult:
        """
        Perform reasoning analysis using NVIDIA NIM.
        
        Converts inputs to synthesize_rca format and packages
        result into standard RCAResult.
        """
        cand_dicts = [
            {
                "component": c.component,
                "failure_type": c.failure_type,
                "confidence": c.confidence,
                "description": c.description,
                "supporting_evidence_ids": c.supporting_evidence_ids
            }
            for c in rca_candidates
        ] if rca_candidates else []

        synth_result = self.synthesize_rca(
            context=context,
            evidence=evidence,
            candidate_hypotheses=cand_dicts
        )

        return RCAResult(
            incident_id=context.incident_id,
            analysis_timestamp=datetime.now(),
            diagnosis_status=synth_result["diagnosis_status"],
            probable_root_cause=synth_result.get("probable_root_cause"),
            alternative_hypotheses=synth_result.get("alternative_hypotheses", []),
            evidence=[],  # Populated by pipeline
            missing_evidence=synth_result.get("missing_evidence", missing_evidence or []),
            recommended_actions=synth_result.get("recommended_actions", []),
            support_communication=synth_result.get("support_communication", ""),
            stakeholder_communication=synth_result.get("stakeholder_communication", ""),
            telemetry_is_mock=True,
            human_review_required=True,
            review_reasons=[]
        )
