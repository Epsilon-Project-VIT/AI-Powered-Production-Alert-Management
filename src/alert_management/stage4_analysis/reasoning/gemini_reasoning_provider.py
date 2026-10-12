"""
Google Gemini Reasoning Provider for Stage 4 RCA.

Implements the ReasoningProvider interface using Google Gemini LLM
via the validated OpenAI-compatible chat completions client.

CRITICAL SAFETY & VALIDATION FEATURES:
- Evidence-grounded reasoning (rejects hallucinated evidence IDs)
- Strict provenance tracking (mock vs real telemetry preserved)
- Mandatory human approval for all remediation actions
- Never executes remediation actions
- Bounded retries and rate limiting (avoids unbounded loops/bursts)
- Explicit fallback provenance (never silently substitutes mock data)
- Zero credential leakage in logs, errors, or communication
"""

import json
import logging
import hashlib
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from pydantic import BaseModel, Field

from alert_management.llm import (
    GeminiClient,
    GeminiConfig,
    GeminiError,
    GeminiAuthenticationError,
    GeminiConfigurationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiProviderError,
    GeminiStructuredOutputError,
)
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
    SourceType,
)

logger = logging.getLogger(__name__)

# Default prompt template embedded to ensure self-contained operation
DEFAULT_GEMINI_RCA_PROMPT = """You are an expert site reliability and root cause analysis engineer for production enterprise systems.
Analyze the following production incident context, telemetry evidence, and candidate hypotheses.
Produce a rigorous, structured RCA analysis.

INCIDENT CONTEXT:
- Incident ID: {incident_id}
- Client: {client}
- Impacted Alert Count: {alert_count}
- Incident Window: {incident_start} to {incident_end}
- Impacted Services: {services}
- Impacted Components: {components}
- Symptoms:
  - {normalized_descriptions}

COLLECTED TELEMETRY EVIDENCE:
{evidence_summary}

PRE-GENERATED CANDIDATE HYPOTHESES:
{rca_candidates}

MISSING TELEMETRY MODALITIES:
{missing_evidence}

HISTORICAL SIMILAR PATTERNS:
{historical_patterns}

STRICT ANALYSIS RULES:
1. Grounding & Citations:
   - In COLLECTED TELEMETRY EVIDENCE, each item has an exact identifier formatted as "[ID: <source_id>]".
   - For a "sufficient_evidence" diagnosis, you MUST populate probable_root_cause.supporting_evidence_ids with one or more exact evidence IDs cited directly from the COLLECTED TELEMETRY EVIDENCE list above.
   - You MUST cite ONLY evidence IDs that are explicitly present in the COLLECTED TELEMETRY EVIDENCE above. Do NOT invent or hallucinate evidence IDs.
   - If you cannot identify valid supporting evidence IDs from the provided evidence, you MUST NOT diagnose "sufficient_evidence". Set diagnosis_status to "insufficient_evidence" or "ambiguous" instead.
2. Uncertainty: If evidence is missing, contradictory, or insufficient, set diagnosis_status to "insufficient_evidence" or "ambiguous". Do NOT force an unsupported diagnosis.
3. If diagnosis_status is "insufficient_evidence", set probable_root_cause to null (or provide a tentative hypothesis with confidence <= 0.25 and is_tentative=true).
4. Remediation Safety: Recommend diagnostic or remediation actions. Consequential remediation actions MUST require human review (requires_human_approval: true).
5. Communications: Provide clear, concise technical communications for support engineers and non-technical stakeholder communications.
"""


class GeminiProbableRootCause(BaseModel):
    """Primary RCA candidate hypothesis."""
    component: str = Field(
        default="unknown",
        description="Component where failure occurred (e.g., 'database', 'application', 'network')"
    )
    failure_type: str = Field(
        default="unknown",
        description="Type of failure (e.g., 'connection_pool_exhaustion', 'memory_leak', 'timeout')"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Model-reported confidence score (0.0 to 1.0; NOT a calibrated probability)"
    )
    description: str = Field(
        default="Root cause hypothesis",
        description="Detailed explanation of the causal failure mechanism"
    )
    supporting_evidence_ids: List[str] = Field(
        default_factory=list,
        description=(
            "Exact source_ids of evidence items directly supporting this root cause, "
            "selected from COLLECTED TELEMETRY EVIDENCE. For 'sufficient_evidence', "
            "at least one valid evidence ID is REQUIRED."
        )
    )


class GeminiAlternativeHypothesis(BaseModel):
    """Alternative RCA hypothesis."""
    component: str = Field(
        default="unknown",
        description="Component where failure might have occurred"
    )
    failure_type: str = Field(
        default="unknown",
        description="Type of failure"
    )
    confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Model-reported confidence score (0.0 to 1.0)"
    )
    reason_for_lower_rank: str = Field(
        default="Lower confidence than primary",
        description="Why this hypothesis ranks lower than the primary"
    )


class GeminiRecommendedAction(BaseModel):
    """Suggested remediation or diagnostic action."""
    action: str = Field(
        default="Diagnostic investigation",
        description="Description of the recommended action"
    )
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Action priority (1=highest, 5=lowest)"
    )
    action_type: str = Field(
        default="diagnostic",
        description="Type of action: diagnostic, remediation, or escalation"
    )
    rationale: str = Field(
        default="Generated based on RCA reasoning",
        description="Why this action is recommended"
    )
    requires_human_approval: bool = Field(
        default=True,
        description="Whether action requires human approval (ALWAYS True for remediation)"
    )
    runbook_reference: Optional[str] = Field(
        default=None,
        description="Optional runbook reference"
    )


class GeminiRCAOutput(BaseModel):
    """Structured output schema for Gemini RCA reasoning."""
    diagnosis_status: str = Field(
        ...,
        description="Diagnosis status: 'sufficient_evidence', 'insufficient_evidence', or 'ambiguous'"
    )
    probable_root_cause: Optional[GeminiProbableRootCause] = Field(
        None,
        description="Primary root cause hypothesis. REQUIRED with supporting_evidence_ids if diagnosis_status is 'sufficient_evidence'. Null if insufficient evidence."
    )
    alternative_hypotheses: List[GeminiAlternativeHypothesis] = Field(
        default_factory=list,
        description="Alternative root cause candidates"
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Types of missing evidence modalities (e.g., ['traces'])"
    )
    recommended_actions: List[GeminiRecommendedAction] = Field(
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


class GeminiRCACache:
    """In-memory cache for avoiding duplicate LLM calls on identical incident/evidence sets."""

    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size

    @staticmethod
    def compute_key(context: IncidentContext, evidence: List[Evidence]) -> str:
        """Compute deterministic hash key from incident context and evidence IDs."""
        ev_ids = sorted(e.source_id for e in evidence)
        content = f"{context.incident_id}|{context.client}|{','.join(ev_ids)}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(key)

    def set(self, key: str, value: Dict[str, Any]) -> None:
        if len(self._cache) >= self._max_size:
            # Evict oldest entry
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key, None)
        self._cache[key] = value

    def clear(self) -> None:
        self._cache.clear()


class GeminiReasoningProvider(ReasoningProvider):
    """
    Google Gemini reasoning provider for Stage 4 RCA.
    
    Synthesizes incident evidence into validated, structured RCA results
    using Gemini while enforcing strict evidence grounding and remediation safety.
    """

    def __init__(
        self,
        config: Optional[GeminiConfig] = None,
        client: Optional[GeminiClient] = None,
        min_evidence_threshold: int = 3,
        cache: Optional[GeminiRCACache] = None,
        model: Optional[str] = None,
        enable_correction: bool = True,
    ):
        """
        Initialize Gemini reasoning provider.
        
        Args:
            config: Optional GeminiConfig instance; if omitted, loaded from env
            client: Optional pre-configured GeminiClient
            min_evidence_threshold: Minimum evidence items required for sufficient diagnosis
            cache: Optional GeminiRCACache for request deduplication
            model: Optional model override (e.g. 'gemini-3.5-flash-lite')
            enable_correction: Whether to attempt at most 1 correction request if citations are missing
        """
        if config is None:
            config = GeminiConfig.from_env(model=model)
        elif model:
            config = config.model_copy(update={"model": model})
        self.config = config
        self.client = client or GeminiClient(config)
        self.min_evidence_threshold = min_evidence_threshold
        self.enable_correction = enable_correction
        self.prompt_template = DEFAULT_GEMINI_RCA_PROMPT
        self.cache = cache if cache is not None else GeminiRCACache()
        self.request_count: int = 0
        self.correction_count: int = 0
        self.success_count: int = 0
        self.fallback_count: int = 0
        self.cache_hit_count: int = 0

        logger.info(f"GeminiReasoningProvider initialized with model: {config.model}")

    def get_provider_type(self) -> str:
        """Return provider type identifier."""
        return "gemini"

    def synthesize_rca(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        candidate_hypotheses: List[Dict[str, Any]],
        historical_patterns: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Synthesize RCA using Google Gemini LLM.
        
        Args:
            context: Incident context
            evidence: List of evidence items with provenance
            candidate_hypotheses: Pre-generated RCA candidates
            historical_patterns: Optional historical alert/ticket patterns
            
        Returns:
            Dict containing RCA diagnosis components
        """
        # Deduplication check
        cache_key = self.cache.compute_key(context, evidence)
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            self.cache_hit_count += 1
            logger.info(f"Returning cached Gemini RCA result for incident {context.incident_id}")
            return cached_result

        # Identify missing evidence modalities
        missing_evidence = self._identify_missing_evidence(evidence)

        # Insufficient evidence short-circuit if zero evidence exists
        if not evidence:
            fallback_res = self._fallback_result(
                context=context,
                evidence=evidence,
                missing_evidence=["logs", "metrics", "traces"],
                error_category="no_evidence_available"
            )
            return fallback_res

        # Format components for prompt
        evidence_summary = self._format_evidence(evidence)
        rca_candidates_str = self._format_candidates(candidate_hypotheses)
        historical_str = self._format_historical(historical_patterns)

        prompt = self.prompt_template.format(
            incident_id=context.incident_id,
            client=context.client,
            alert_count=context.alert_count,
            incident_start=context.incident_start.isoformat(),
            incident_end=context.incident_end.isoformat() if context.incident_end else "ongoing",
            services=", ".join(context.services) if context.services else "unknown",
            components=", ".join(context.components) if context.components else "unknown",
            normalized_descriptions="\n  - ".join(context.normalized_descriptions[:3]),
            evidence_summary=evidence_summary,
            rca_candidates=rca_candidates_str,
            historical_patterns=historical_str,
            missing_evidence=", ".join(missing_evidence) if missing_evidence else "None identified"
        )

        valid_evidence_ids: Set[str] = {ev.source_id for ev in evidence}
        messages = [{"role": "user", "content": prompt}]
        self.request_count += 1

        try:
            logger.info(f"Calling Gemini for RCA synthesis (incident: {context.incident_id})")
            gemini_output: GeminiRCAOutput = self.client.chat_completion_structured(
                messages=messages,
                schema=GeminiRCAOutput,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )

            # Check if Gemini diagnosed sufficient_evidence without citing valid evidence IDs
            raw_prc = gemini_output.probable_root_cause
            is_sufficient = (str(gemini_output.diagnosis_status).lower() in ("sufficient_evidence", "diagnosisstatus.sufficient_evidence"))

            needs_citation_correction = False
            if is_sufficient:
                if not raw_prc:
                    needs_citation_correction = True
                else:
                    if isinstance(raw_prc, BaseModel):
                        raw_ids = getattr(raw_prc, "supporting_evidence_ids", [])
                    elif isinstance(raw_prc, dict):
                        raw_ids = raw_prc.get("supporting_evidence_ids", [])
                    else:
                        raw_ids = []

                    cleaned_ids = []
                    for eid in raw_ids:
                        cid = str(eid).strip()
                        if cid.startswith("ID:"):
                            cid = cid[3:].strip()
                        if cid.startswith("[") and cid.endswith("]"):
                            cid = cid[1:-1].strip()
                        cleaned_ids.append(cid)

                    valid_cited = [eid for eid in cleaned_ids if eid in valid_evidence_ids]
                    if not valid_cited:
                        needs_citation_correction = True

            # Controlled correction request (at most 1 attempt)
            if needs_citation_correction and evidence and self.enable_correction:
                logger.warning(
                    f"Gemini returned 'sufficient_evidence' for incident {context.incident_id} "
                    f"without valid supporting evidence IDs. Attempting at most 1 controlled correction request."
                )
                self.correction_count += 1
                try:
                    self.request_count += 1
                    correction_messages = list(messages)
                    content_json = gemini_output.model_dump_json() if hasattr(gemini_output, "model_dump_json") else json.dumps(gemini_output)
                    correction_messages.append({
                        "role": "assistant",
                        "content": content_json
                    })
                    sample_valid_ids = sorted(list(valid_evidence_ids))[:15]
                    correction_messages.append({
                        "role": "user",
                        "content": (
                            f"EVIDENCE CITATION CORRECTION REQUIRED:\n"
                            f"You reported diagnosis_status='sufficient_evidence', but your probable_root_cause "
                            f"either lacked supporting_evidence_ids or cited invalid/unknown IDs.\n"
                            f"Available valid evidence IDs for this incident: {sample_valid_ids}.\n"
                            f"You MUST update probable_root_cause.supporting_evidence_ids to include one or more exact "
                            f"valid evidence IDs from the above list that directly support your conclusion.\n"
                            f"If the available evidence cannot substantiate a causal conclusion, change diagnosis_status "
                            f"to 'insufficient_evidence' (with probable_root_cause null or tentative) or 'ambiguous'."
                        )
                    })
                    corrected_output = self.client.chat_completion_structured(
                        messages=correction_messages,
                        schema=GeminiRCAOutput,
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens
                    )
                    gemini_output = corrected_output
                except Exception as corr_exc:
                    logger.warning(f"Controlled correction request failed ({corr_exc}); proceeding to safe validation.")

            validated_result = self._validate_and_convert(
                gemini_output=gemini_output,
                context=context,
                evidence=evidence
            )
            self.success_count += 1
            self.cache.set(cache_key, validated_result)
            return validated_result

        except GeminiAuthenticationError as e:
            logger.error(f"Gemini authentication failure: {e}")
            self.fallback_count += 1
            return self._fallback_result(context, evidence, missing_evidence, "authentication_error")
        except GeminiRateLimitError as e:
            logger.error(f"Gemini rate limit exceeded (HTTP 429): {e}")
            self.fallback_count += 1
            return self._fallback_result(context, evidence, missing_evidence, "rate_limit_exceeded")
        except GeminiTimeoutError as e:
            logger.error(f"Gemini request timed out: {e}")
            self.fallback_count += 1
            return self._fallback_result(context, evidence, missing_evidence, "timeout")
        except GeminiStructuredOutputError as e:
            logger.error(f"Gemini structured output validation error: {e}")
            self.fallback_count += 1
            return self._fallback_result(context, evidence, missing_evidence, "schema_validation_error")
        except GeminiProviderError as e:
            logger.error(f"Gemini provider error: {e}")
            self.fallback_count += 1
            return self._fallback_result(context, evidence, missing_evidence, "provider_error")
        except Exception as e:
            logger.error(f"Unexpected error calling Gemini: {e}")
            self.fallback_count += 1
            return self._fallback_result(context, evidence, missing_evidence, "unexpected_error")

    def analyze(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        rca_candidates: List[ProbableRootCause],
        missing_evidence: Optional[List[str]] = None
    ) -> RCAResult:
        """
        Execute end-to-end reasoning analysis using Google Gemini.
        
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

        is_fallback = synth_result.get("is_fallback", False)
        provider_name = "gemini_fallback" if is_fallback else "gemini"

        # Determine mock telemetry provenance
        telemetry_is_mock = any(e.is_mock for e in evidence) if evidence else True

        # Build review reasons
        review_reasons = []
        if is_fallback:
            review_reasons.append(f"Fallback triggered: {synth_result.get('fallback_reason', 'unknown')}")
        if synth_result["diagnosis_status"] == DiagnosisStatus.INSUFFICIENT_EVIDENCE:
            review_reasons.append("Insufficient evidence for automated root cause confirmation")
        elif synth_result["diagnosis_status"] == DiagnosisStatus.AMBIGUOUS:
            review_reasons.append("Ambiguous evidence: competing root cause hypotheses present")

        for act in synth_result.get("recommended_actions", []):
            if act.action_type == ActionType.REMEDIATION:
                review_reasons.append(f"Remediation action '{act.action}' requires mandatory human approval")

        return RCAResult(
            incident_id=context.incident_id,
            analysis_timestamp=datetime.now(),
            diagnosis_status=synth_result["diagnosis_status"],
            probable_root_cause=synth_result.get("probable_root_cause"),
            alternative_hypotheses=synth_result.get("alternative_hypotheses", []),
            evidence=evidence,
            missing_evidence=synth_result.get("missing_evidence", missing_evidence or []),
            recommended_actions=synth_result.get("recommended_actions", []),
            support_communication=synth_result.get("support_communication", ""),
            stakeholder_communication=synth_result.get("stakeholder_communication", ""),
            telemetry_is_mock=telemetry_is_mock,
            reasoning_provider=provider_name,
            human_review_required=True,
            review_reasons=review_reasons
        )

    def _validate_and_convert(
        self,
        gemini_output: GeminiRCAOutput,
        context: IncidentContext,
        evidence: List[Evidence]
    ) -> Dict[str, Any]:
        """
        Validate Gemini output and convert to verified domain structures.
        
        Enforces:
        - diagnosis_status matches known enum
        - supporting evidence IDs exist in input evidence (filters unknown IDs)
        - sufficient_evidence without valid evidence citations safely downgrades to ambiguous or insufficient_evidence
        - confidence is bounded between 0.0 and 1.0
        - remediation actions ALWAYS require human approval
        """
        # 1. Validate diagnosis status
        try:
            diagnosis_status = DiagnosisStatus(gemini_output.diagnosis_status)
        except ValueError:
            logger.warning(
                f"Invalid diagnosis status from Gemini: '{gemini_output.diagnosis_status}'. "
                "Defaulting to INSUFFICIENT_EVIDENCE."
            )
            diagnosis_status = DiagnosisStatus.INSUFFICIENT_EVIDENCE

        valid_evidence_ids: Set[str] = {ev.source_id for ev in evidence}

        # 2. Parse and validate probable root cause
        probable_root_cause: Optional[ProbableRootCause] = None
        raw_prc = gemini_output.probable_root_cause
        if raw_prc:
            if isinstance(raw_prc, BaseModel):
                prc_dict = raw_prc.model_dump()
            elif isinstance(raw_prc, dict):
                prc_dict = raw_prc
            else:
                prc_dict = {}

            raw_ids = prc_dict.get("supporting_evidence_ids", [])
            cleaned_ids = []
            for rid in raw_ids:
                cid = str(rid).strip()
                if cid.startswith("ID:"):
                    cid = cid[3:].strip()
                if cid.startswith("[") and cid.endswith("]"):
                    cid = cid[1:-1].strip()
                cleaned_ids.append(cid)

            # Filter unknown evidence IDs
            validated_ids = [eid for eid in cleaned_ids if eid in valid_evidence_ids]
            if len(validated_ids) < len(cleaned_ids):
                logger.warning(
                    f"Discarded {len(cleaned_ids) - len(validated_ids)} unverified evidence IDs "
                    f"from probable root cause for incident {context.incident_id}"
                )

            if diagnosis_status == DiagnosisStatus.SUFFICIENT_EVIDENCE:
                if not validated_ids:
                    # Safe downgrade: cannot declare sufficient evidence without valid supporting citations
                    logger.warning(
                        f"Incident {context.incident_id}: 'sufficient_evidence' diagnosis has 0 valid supporting evidence IDs. "
                        f"Safely downgrading to AMBIGUOUS or INSUFFICIENT_EVIDENCE."
                    )
                    if gemini_output.alternative_hypotheses:
                        diagnosis_status = DiagnosisStatus.AMBIGUOUS
                    else:
                        diagnosis_status = DiagnosisStatus.INSUFFICIENT_EVIDENCE

                    raw_conf = prc_dict.get("confidence", 0.3)
                    bounded_conf = min(0.35, max(0.0, float(raw_conf)))
                    probable_root_cause = ProbableRootCause(
                        component=prc_dict.get("component", "unknown"),
                        failure_type=prc_dict.get("failure_type", "unknown"),
                        confidence=bounded_conf,
                        description=f"Tentative hypothesis (unsubstantiated by evidence citations): {prc_dict.get('description', '')}",
                        supporting_evidence_ids=[],
                        is_tentative=True
                    )
                else:
                    raw_conf = prc_dict.get("confidence", 0.5)
                    bounded_conf = max(0.0, min(1.0, float(raw_conf)))
                    probable_root_cause = ProbableRootCause(
                        component=prc_dict.get("component", "unknown"),
                        failure_type=prc_dict.get("failure_type", "unknown"),
                        confidence=bounded_conf,
                        description=prc_dict.get("description", "No description provided"),
                        supporting_evidence_ids=validated_ids,
                        is_tentative=False
                    )
            elif diagnosis_status == DiagnosisStatus.AMBIGUOUS:
                raw_conf = prc_dict.get("confidence", 0.4)
                bounded_conf = max(0.0, min(1.0, float(raw_conf)))
                probable_root_cause = ProbableRootCause(
                    component=prc_dict.get("component", "unknown"),
                    failure_type=prc_dict.get("failure_type", "unknown"),
                    confidence=bounded_conf,
                    description=prc_dict.get("description", "Ambiguous hypothesis"),
                    supporting_evidence_ids=validated_ids,
                    is_tentative=True
                )
            elif diagnosis_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE:
                probable_root_cause = ProbableRootCause(
                    component=prc_dict.get("component", "unknown"),
                    failure_type=prc_dict.get("failure_type", "unknown"),
                    confidence=min(0.25, max(0.0, float(prc_dict.get("confidence", 0.2)))),
                    description=f"Tentative candidate (insufficient evidence): {prc_dict.get('description', '')}",
                    supporting_evidence_ids=validated_ids,
                    is_tentative=True
                )
        elif diagnosis_status == DiagnosisStatus.SUFFICIENT_EVIDENCE:
            # Output lacked probable_root_cause altogether
            logger.warning(f"Incident {context.incident_id}: sufficient_evidence reported without root cause; downgrading.")
            diagnosis_status = DiagnosisStatus.INSUFFICIENT_EVIDENCE

        # 3. Parse alternative hypotheses
        alternative_hypotheses: List[AlternativeHypothesis] = []
        for alt_item in gemini_output.alternative_hypotheses[:3]:
            if isinstance(alt_item, BaseModel):
                alt_dict = alt_item.model_dump()
            elif isinstance(alt_item, dict):
                alt_dict = alt_item
            else:
                alt_dict = {}
            conf = max(0.0, min(1.0, float(alt_dict.get("confidence", 0.3))))
            alt = AlternativeHypothesis(
                component=alt_dict.get("component", "unknown"),
                failure_type=alt_dict.get("failure_type", "unknown"),
                confidence=conf,
                reason_for_lower_rank=alt_dict.get("reason_for_lower_rank", "Lower confidence than primary")
            )
            alternative_hypotheses.append(alt)

        # 4. Parse and validate recommended actions (Enforce Policy Gate)
        recommended_actions: List[RecommendedAction] = []
        for act_item in gemini_output.recommended_actions[:5]:
            if isinstance(act_item, BaseModel):
                act_dict = act_item.model_dump()
            elif isinstance(act_item, dict):
                act_dict = act_item
            else:
                act_dict = {}

            act_type_str = str(act_dict.get("action_type", "diagnostic")).lower()
            try:
                action_type = ActionType(act_type_str)
            except ValueError:
                action_type = ActionType.DIAGNOSTIC

            # Consequential safety requirement:
            # Remediation ALWAYS requires human approval; diagnostic may be auto-approved
            requires_approval = True if action_type == ActionType.REMEDIATION else bool(act_dict.get("requires_human_approval", False))

            action = RecommendedAction(
                action=act_dict.get("action", "Perform diagnostic investigation"),
                priority=max(1, min(5, int(act_dict.get("priority", 3)))),
                action_type=action_type,
                rationale=act_dict.get("rationale", "Generated by RCA reasoning"),
                requires_human_approval=requires_approval,
                runbook_reference=act_dict.get("runbook_reference")
            )
            recommended_actions.append(action)

        return {
            "diagnosis_status": diagnosis_status,
            "probable_root_cause": probable_root_cause,
            "alternative_hypotheses": alternative_hypotheses,
            "missing_evidence": gemini_output.missing_evidence,
            "recommended_actions": recommended_actions,
            "support_communication": gemini_output.support_communication,
            "stakeholder_communication": gemini_output.stakeholder_communication,
            "is_fallback": False,
            "reasoning_explanation": ""
        }

    def _fallback_result(
        self,
        context: IncidentContext,
        evidence: List[Evidence],
        missing_evidence: List[str],
        error_category: str
    ) -> Dict[str, Any]:
        """
        Produce a safe, explicitly labeled fallback result when Gemini is unavailable or fails.
        
        Does NOT invent a root cause or claim mock data was produced by Gemini.
        """
        return {
            "diagnosis_status": DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            "probable_root_cause": None,
            "alternative_hypotheses": [],
            "missing_evidence": missing_evidence,
            "recommended_actions": [
                RecommendedAction(
                    action=f"Gemini analysis unavailable ({error_category}) - collect diagnostics manually",
                    priority=1,
                    action_type=ActionType.DIAGNOSTIC,
                    rationale=f"LLM request error: {error_category}",
                    requires_human_approval=False
                )
            ],
            "support_communication": (
                f"Automated RCA synthesis for incident {context.incident_id} is incomplete. "
                f"Reasoning provider (Gemini) reported: {error_category}. "
                f"Evidence items available for manual review: {len(evidence)}."
            ),
            "stakeholder_communication": (
                f"Incident {context.incident_id} investigation is currently in progress. "
                f"Operations and engineering teams are actively reviewing incident diagnostics."
            ),
            "is_fallback": True,
            "fallback_reason": error_category,
            "reasoning_explanation": ""
        }

    def _format_evidence(self, evidence: List[Evidence]) -> str:
        """Format evidence list into human-readable summary with explicit ID labels."""
        if not evidence:
            return "No evidence collected."

        lines = []
        for i, ev in enumerate(evidence[:30], 1):  # Cap to top 30 evidence items
            prov = "MOCK" if ev.is_mock else "REAL"
            weight_str = f"(weight={ev.weight:.2f})" if ev.weight else ""
            lines.append(f"{i}. [ID: {ev.source_id}] [{prov}] [{ev.source.upper()}] {ev.description} {weight_str}")

        if len(evidence) > 30:
            lines.append(f"... and {len(evidence) - 30} additional evidence items.")

        return "\n".join(lines)

    def _format_candidates(self, candidates: List[Dict[str, Any]]) -> str:
        """Format candidate hypotheses into string."""
        if not candidates:
            return "No pre-generated candidate hypotheses."

        lines = []
        for i, c in enumerate(candidates[:5], 1):
            comp = c.get("component", "unknown")
            ftype = c.get("failure_type", "unknown")
            conf = c.get("confidence", 0.0)
            desc = c.get("description", "")
            lines.append(f"{i}. {comp} / {ftype} (confidence: {conf:.2f}): {desc}")

        return "\n".join(lines)

    def _format_historical(self, patterns: Optional[List[Dict[str, Any]]]) -> str:
        """Format historical patterns into string."""
        if not patterns:
            return "No similar historical incidents identified."

        lines = []
        for p in patterns[:3]:
            lines.append(f"- Pattern: {p.get('pattern_name', 'Unknown')}, Matches: {p.get('match_count', 0)}")
        return "\n".join(lines)

    def _identify_missing_evidence(self, evidence: List[Evidence]) -> List[str]:
        """Identify missing evidence types from collected evidence."""
        expected = {"logs", "metrics", "traces"}
        available = {ev.source for ev in evidence}
        return sorted(list(expected - available))
