"""
Stage 4 Complete Pipeline - RCA and Incident Analysis.

Orchestrates:
- Context building
- Telemetry collection
- Evidence analysis
- RCA candidate generation and ranking
- Reasoning
- Remediation recommendations
- Policy gating
- Communications
"""

from typing import List, Optional
from datetime import datetime

from alert_management.stage3_correlation.schemas import IncidentGroup
from alert_management.stage2_classification.schemas import EnrichedAlert
from alert_management.stage4_analysis.schemas import RCAResult, Evidence
from alert_management.stage4_analysis.context import IncidentContextBuilder
from alert_management.stage4_analysis.telemetry.interfaces import (
    LogProvider,
    MetricProvider,
    TraceProvider
)
from alert_management.stage4_analysis.reasoning.interfaces import ReasoningProvider
from alert_management.stage4_analysis.evidence import EvidenceStore
from alert_management.stage4_analysis.analysis import (
    LogAnalyzer,
    AnomalyDetector,
    TraceAnalyzer
)
from alert_management.stage4_analysis.rca import (
    RCACandidateGenerator,
    RCACandidateRanker
)
from alert_management.stage4_analysis.policy import PolicyGate
from alert_management.stage4_analysis.communication import MessageGenerator


class Stage4Pipeline:
    """
    Complete Stage 4 pipeline for incident analysis and RCA.
    
    Provider-injected design allows switching between mock and real implementations.
    """
    
    def __init__(
        self,
        log_provider: LogProvider,
        metric_provider: MetricProvider,
        trace_provider: TraceProvider,
        reasoning_provider: ReasoningProvider,
        context_builder: Optional[IncidentContextBuilder] = None,
        policy_gate: Optional[PolicyGate] = None
    ):
        """
        Initialize Stage 4 pipeline with providers.
        
        Args:
            log_provider: Log telemetry provider
            metric_provider: Metric telemetry provider
            trace_provider: Trace telemetry provider
            reasoning_provider: Reasoning provider (mock or real)
            context_builder: Optional context builder
            policy_gate: Optional policy gate
        """
        self.log_provider = log_provider
        self.metric_provider = metric_provider
        self.trace_provider = trace_provider
        self.reasoning_provider = reasoning_provider
        
        self.context_builder = context_builder or IncidentContextBuilder()
        self.policy_gate = policy_gate or PolicyGate()
        
        # Analyzers
        self.log_analyzer = LogAnalyzer()
        self.anomaly_detector = AnomalyDetector()
        self.trace_analyzer = TraceAnalyzer()
        
        # RCA components
        self.candidate_generator = RCACandidateGenerator()
        self.candidate_ranker = RCACandidateRanker()
        
        # Communication
        self.message_generator = MessageGenerator()
    
    def analyze_incident(
        self,
        incident_group: IncidentGroup,
        enriched_alerts: List[EnrichedAlert]
    ) -> tuple[RCAResult, str, str]:
        """
        Run complete Stage 4 analysis pipeline.
        
        Args:
            incident_group: Stage 3 incident group
            enriched_alerts: All enriched alerts
            
        Returns:
            Tuple of (RCAResult, support_message, stakeholder_message)
        """
        # Phase 1: Build incident context
        context = self.context_builder.build_context(
            incident_group,
            enriched_alerts
        )
        
        # Phase 2: Collect telemetry
        logs = self.log_provider.get_logs(
            context=context,
            start_time=context.diagnostic_start,
            end_time=context.diagnostic_end,
            components=context.services
        )
        
        metrics = self.metric_provider.get_metrics(
            context=context,
            start_time=context.diagnostic_start,
            end_time=context.diagnostic_end,
            components=context.services
        )
        
        traces = self.trace_provider.get_traces(
            context=context,
            start_time=context.diagnostic_start,
            end_time=context.diagnostic_end,
            components=context.services
        )
        
        # Phase 3: Analyze telemetry and generate evidence
        evidence_store = EvidenceStore()
        
        # Log analysis - analyze full diagnostic window
        log_evidence = self.log_analyzer.analyze(
            logs,
            context.diagnostic_start,
            context.diagnostic_end,
            context.incident_start,
            context.incident_end
        )
        evidence_store.add_bulk(log_evidence)
        
        # Anomaly detection - analyze full diagnostic window
        anomalies = self.anomaly_detector.detect_anomalies(
            metrics,
            context.diagnostic_start,
            context.diagnostic_end,
            context.incident_start,
            context.incident_end
        )
        anomaly_evidence = self.anomaly_detector.generate_evidence(anomalies)
        evidence_store.add_bulk(anomaly_evidence)
        
        # Trace analysis - analyze full diagnostic window
        trace_evidence = self.trace_analyzer.analyze(
            traces,
            context.diagnostic_start,
            context.diagnostic_end,
            context.incident_start,
            context.incident_end
        )
        evidence_store.add_bulk(trace_evidence)
        
        # Phase 4: Generate and rank RCA candidates
        all_evidence = evidence_store.get_all()
        
        rca_candidates = self.candidate_generator.generate_candidates(
            context,
            all_evidence
        )
        
        ranked_candidates = self.candidate_ranker.rank_candidates(
            rca_candidates,
            all_evidence
        )
        
        # Phase 5: Reasoning
        missing_evidence = self._identify_missing_evidence(logs, metrics, traces)
        
        rca_result = self.reasoning_provider.analyze(
            context=context,
            evidence=all_evidence,
            rca_candidates=ranked_candidates,
            missing_evidence=missing_evidence if missing_evidence else None
        )
        
        # Phase 6: Policy gate evaluation
        action_decisions = []
        if rca_result.recommended_actions:
            action_decisions = self.policy_gate.evaluate_actions(
                rca_result.recommended_actions
            )
        
        # Phase 7: Generate communications
        support_message = self.message_generator.generate_support_message(
            context,
            rca_result,
            action_decisions
        )
        
        stakeholder_message = self.message_generator.generate_stakeholder_message(
            context,
            rca_result
        )
        
        # Update RCAResult with communications and evidence
        rca_result.support_communication = support_message
        rca_result.stakeholder_communication = stakeholder_message
        rca_result.evidence = all_evidence
        
        return rca_result, support_message, stakeholder_message
    
    def _identify_missing_evidence(
        self,
        logs: List,
        metrics: List,
        traces: List
    ) -> List[str]:
        """
        Identify missing evidence types.
        
        Args:
            logs: Collected logs
            metrics: Collected metrics
            traces: Collected traces
            
        Returns:
            List of missing evidence type names
        """
        missing = []
        
        if not logs:
            missing.append("logs")
        if not metrics:
            missing.append("metrics")
        if not traces:
            missing.append("traces")
        
        return missing
