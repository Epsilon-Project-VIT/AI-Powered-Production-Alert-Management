"""
Stage 4: Incident Analysis, RCA, Remediation & Communication.

This stage performs root cause analysis on candidate incident groups from Stage 3.

Components:
- Context: Incident context building and diagnostic window definition
- Telemetry: Log/metric/trace providers (mock and real)
- Analysis: Log pattern extraction, anomaly detection, trace analysis
- Evidence: Evidence aggregation and provenance tracking
- Retrieval: Historical alert/ticket pattern retrieval
- RCA: Root cause candidate generation and ranking
- Reasoning: Claude-style reasoning (mock and Bedrock)
- Remediation: Action recommendation with approval requirements
- Policy: Human/policy gate for consequential actions
- Communication: Support and stakeholder message generation
"""

from .schemas import (
    DiagnosisStatus,
    SourceType,
    ActionType,
    IncidentContext,
    Evidence,
    ProbableRootCause,
    AlternativeHypothesis,
    RecommendedAction,
    RCAResult,
    LogRecord,
    MetricRecord,
    TraceSpan,
    AnomalyDetection,
)

__all__ = [
    'DiagnosisStatus',
    'SourceType',
    'ActionType',
    'IncidentContext',
    'Evidence',
    'ProbableRootCause',
    'AlternativeHypothesis',
    'RecommendedAction',
    'RCAResult',
    'LogRecord',
    'MetricRecord',
    'TraceSpan',
    'AnomalyDetection',
]
