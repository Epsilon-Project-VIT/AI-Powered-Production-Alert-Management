"""
Unit tests for Stage 4 schemas and data contracts.

Tests validation, provenance tracking, and schema constraints.
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from alert_management.stage4_analysis.schemas import (
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


class TestDiagnosisStatus:
    """Test DiagnosisStatus enum."""
    
    def test_diagnosis_status_values(self):
        """Verify all diagnosis status values are defined."""
        assert DiagnosisStatus.SUFFICIENT_EVIDENCE == "sufficient_evidence"
        assert DiagnosisStatus.INSUFFICIENT_EVIDENCE == "insufficient_evidence"
        assert DiagnosisStatus.AMBIGUOUS == "ambiguous"


class TestSourceType:
    """Test SourceType enum."""
    
    def test_source_type_values(self):
        """Verify mock and real source types."""
        assert SourceType.MOCK == "mock"
        assert SourceType.REAL == "real"


class TestIncidentContext:
    """Test IncidentContext schema."""
    
    def test_valid_incident_context(self):
        """Create valid incident context."""
        now = datetime.now()
        context = IncidentContext(
            incident_id="INCIDENT-0001",
            client="EA Sports",
            alert_ids=["INC3528891", "INC3528892"],
            primary_alert_id="INC3528891",
            incident_start=now,
            incident_end=now + timedelta(hours=1),
            alert_count=2,
            services=["eass_watcher"],
            components=["application", "elb"],
            normalized_descriptions=["alert description 1", "alert description 2"],
            diagnostic_start=now - timedelta(minutes=30),
            diagnostic_end=now + timedelta(hours=1, minutes=30)
        )
        
        assert context.incident_id == "INCIDENT-0001"
        assert context.client == "EA Sports"
        assert len(context.alert_ids) == 2
        assert len(context.services) == 1
    
    def test_incident_context_requires_at_least_one_alert(self):
        """Incident context must have at least one alert."""
        now = datetime.now()
        
        with pytest.raises(ValidationError):
            IncidentContext(
                incident_id="INCIDENT-0001",
                client="EA Sports",
                alert_ids=[],  # Empty - should fail
                primary_alert_id="INC3528891",
                incident_start=now,
                alert_count=0,
                normalized_descriptions=[],
                diagnostic_start=now - timedelta(minutes=30),
                diagnostic_end=now + timedelta(hours=1)
            )


class TestEvidence:
    """Test Evidence schema with provenance."""
    
    def test_mock_evidence_with_provenance(self):
        """Mock evidence must have proper provenance flags."""
        evidence = Evidence(
            source="metrics",
            source_type=SourceType.MOCK,
            source_id="mock_metric_001",
            timestamp=datetime.now(),
            description="DB connection pool at 100%",
            weight=0.9,
            is_mock=True
        )
        
        assert evidence.source_type == SourceType.MOCK
        assert evidence.is_mock is True
        assert evidence.weight == 0.9
    
    def test_real_evidence_provenance(self):
        """Real evidence has different provenance flags."""
        evidence = Evidence(
            source="logs",
            source_type=SourceType.REAL,
            source_id="log_12345",
            timestamp=datetime.now(),
            description="Error connecting to database",
            weight=0.85,
            is_mock=False
        )
        
        assert evidence.source_type == SourceType.REAL
        assert evidence.is_mock is False
    
    def test_evidence_weight_validation(self):
        """Evidence weight must be between 0 and 1."""
        # Valid weights
        Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="test",
            timestamp=datetime.now(),
            description="Test",
            weight=0.0,
            is_mock=True
        )
        
        Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="test",
            timestamp=datetime.now(),
            description="Test",
            weight=1.0,
            is_mock=True
        )
        
        # Invalid weight > 1.0
        with pytest.raises(ValidationError):
            Evidence(
                source="logs",
                source_type=SourceType.MOCK,
                source_id="test",
                timestamp=datetime.now(),
                description="Test",
                weight=1.5,
                is_mock=True
            )
        
        # Invalid weight < 0.0
        with pytest.raises(ValidationError):
            Evidence(
                source="logs",
                source_type=SourceType.MOCK,
                source_id="test",
                timestamp=datetime.now(),
                description="Test",
                weight=-0.1,
                is_mock=True
            )


class TestProbableRootCause:
    """Test ProbableRootCause schema."""
    
    def test_valid_probable_root_cause(self):
        """Create valid probable root cause."""
        rca = ProbableRootCause(
            component="database",
            failure_type="connection_pool_exhaustion",
            confidence=0.82,
            description="Database connection pool reached capacity",
            supporting_evidence_ids=["mock_metric_001", "log_error_002"]
        )
        
        assert rca.component == "database"
        assert rca.failure_type == "connection_pool_exhaustion"
        assert 0.0 <= rca.confidence <= 1.0
        assert len(rca.supporting_evidence_ids) == 2
    
    def test_confidence_validation(self):
        """Confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ProbableRootCause(
                component="database",
                failure_type="timeout",
                confidence=1.5,  # Invalid
                description="Test"
            )


class TestRecommendedAction:
    """Test RecommendedAction schema."""
    
    def test_diagnostic_action_can_skip_approval(self):
        """Diagnostic actions may not require approval."""
        action = RecommendedAction(
            action="Review database connection pool metrics",
            priority=1,
            action_type=ActionType.DIAGNOSTIC,
            requires_human_approval=False,
            rationale="Non-consequential diagnostic check"
        )
        
        assert action.action_type == ActionType.DIAGNOSTIC
        assert action.requires_human_approval is False
    
    def test_remediation_action_requires_approval_by_default(self):
        """Remediation actions should require approval."""
        action = RecommendedAction(
            action="Restart database service",
            priority=1,
            action_type=ActionType.REMEDIATION,
            requires_human_approval=True,  # Default
            rationale="Consequential action requires approval"
        )
        
        assert action.action_type == ActionType.REMEDIATION
        assert action.requires_human_approval is True
    
    def test_escalation_action(self):
        """Escalation actions for human intervention."""
        action = RecommendedAction(
            action="Escalate to database team",
            priority=2,
            action_type=ActionType.ESCALATION,
            rationale="Requires DBA expertise"
        )
        
        assert action.action_type == ActionType.ESCALATION
    
    def test_priority_validation(self):
        """Priority must be between 1 and 5."""
        # Valid priorities
        for priority in [1, 2, 3, 4, 5]:
            RecommendedAction(
                action="Test",
                priority=priority,
                action_type=ActionType.DIAGNOSTIC,
                rationale="Test"
            )
        
        # Invalid priority
        with pytest.raises(ValidationError):
            RecommendedAction(
                action="Test",
                priority=0,  # Too low
                action_type=ActionType.DIAGNOSTIC,
                rationale="Test"
            )
        
        with pytest.raises(ValidationError):
            RecommendedAction(
                action="Test",
                priority=6,  # Too high
                action_type=ActionType.DIAGNOSTIC,
                rationale="Test"
            )


class TestRCAResult:
    """Test RCAResult schema."""
    
    def test_minimal_rca_result(self):
        """Create minimal RCA result with insufficient evidence."""
        result = RCAResult(
            incident_id="INCIDENT-0001",
            analysis_timestamp=datetime.now(),
            diagnosis_status=DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            support_communication="Insufficient evidence for RCA",
            stakeholder_communication="Investigation in progress",
            telemetry_is_mock=True,
            reasoning_provider="mock"
        )
        
        assert result.diagnosis_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
        assert result.probable_root_cause is None
        assert result.telemetry_is_mock is True
        assert result.reasoning_provider == "mock"
    
    def test_complete_rca_result_with_mock_data(self):
        """Create complete RCA result with mock telemetry."""
        result = RCAResult(
            incident_id="INCIDENT-0001",
            analysis_timestamp=datetime.now(),
            diagnosis_status=DiagnosisStatus.SUFFICIENT_EVIDENCE,
            probable_root_cause=ProbableRootCause(
                component="database",
                failure_type="connection_pool_exhaustion",
                confidence=0.82,
                description="Connection pool saturated"
            ),
            alternative_hypotheses=[
                AlternativeHypothesis(
                    component="application",
                    failure_type="timeout",
                    confidence=0.45,
                    reason_for_lower_rank="Lower correlation with timeline"
                )
            ],
            evidence=[
                Evidence(
                    source="metrics",
                    source_type=SourceType.MOCK,
                    source_id="mock_001",
                    timestamp=datetime.now(),
                    description="Mock metric",
                    weight=0.9,
                    is_mock=True
                )
            ],
            missing_evidence=["production_logs", "real_metrics"],
            recommended_actions=[
                RecommendedAction(
                    action="Review DB pool configuration",
                    priority=1,
                    action_type=ActionType.DIAGNOSTIC,
                    rationale="Verify current settings"
                )
            ],
            support_communication="RCA based on mock telemetry (prototype)",
            stakeholder_communication="Investigation complete (prototype)",
            human_review_required=True,
            review_reasons=["Mock telemetry used", "Experimental confidence scores"],
            telemetry_is_mock=True,
            retrieval_source="historical_alert_ticket_patterns",
            reasoning_provider="mock"
        )
        
        assert result.diagnosis_status == DiagnosisStatus.SUFFICIENT_EVIDENCE
        assert result.probable_root_cause is not None
        assert len(result.alternative_hypotheses) == 1
        assert len(result.evidence) == 1
        assert result.telemetry_is_mock is True
        assert "Mock telemetry used" in result.review_reasons


class TestLogRecord:
    """Test LogRecord schema."""
    
    def test_mock_log_record(self):
        """Create mock log record with provenance."""
        log = LogRecord(
            log_id="log_001",
            timestamp=datetime.now(),
            component="database",
            level="ERROR",
            message="Connection timeout",
            source_type=SourceType.MOCK,
            is_mock=True
        )
        
        assert log.source_type == SourceType.MOCK
        assert log.is_mock is True
        assert log.level == "ERROR"


class TestMetricRecord:
    """Test MetricRecord schema."""
    
    def test_mock_metric_record(self):
        """Create mock metric record with provenance."""
        metric = MetricRecord(
            metric_id="metric_001",
            timestamp=datetime.now(),
            metric_name="cpu_utilization",
            component="application",
            value=95.5,
            unit="percent",
            source_type=SourceType.MOCK,
            is_mock=True
        )
        
        assert metric.source_type == SourceType.MOCK
        assert metric.is_mock is True
        assert metric.value == 95.5


class TestTraceSpan:
    """Test TraceSpan schema."""
    
    def test_mock_trace_span(self):
        """Create mock trace span with provenance."""
        now = datetime.now()
        span = TraceSpan(
            span_id="span_001",
            parent_span_id=None,
            trace_id="trace_123",
            component="application",
            operation="http_request",
            start_time=now,
            end_time=now + timedelta(milliseconds=250),
            duration_ms=250.0,
            status="ok",
            source_type=SourceType.MOCK,
            is_mock=True
        )
        
        assert span.source_type == SourceType.MOCK
        assert span.is_mock is True
        assert span.duration_ms == 250.0
    
    def test_trace_span_duration_validation(self):
        """Duration must be non-negative."""
        now = datetime.now()
        
        with pytest.raises(ValidationError):
            TraceSpan(
                span_id="span_001",
                trace_id="trace_123",
                component="application",
                operation="http_request",
                start_time=now,
                end_time=now,
                duration_ms=-10.0,  # Invalid
                status="ok",
                source_type=SourceType.MOCK,
                is_mock=True
            )


class TestAnomalyDetection:
    """Test AnomalyDetection schema."""
    
    def test_anomaly_detection_result(self):
        """Create anomaly detection result."""
        anomaly = AnomalyDetection(
            metric_name="db_connection_pool_utilization",
            component="database",
            timestamp=datetime.now(),
            observed_value=100.0,
            expected_value=62.5,
            anomaly_score=0.96,
            detection_method="z_score",
            is_anomalous=True,
            source_type=SourceType.MOCK,
            is_mock=True
        )
        
        assert anomaly.is_anomalous is True
        assert anomaly.anomaly_score == 0.96
        assert anomaly.detection_method == "z_score"
        assert anomaly.source_type == SourceType.MOCK
        assert anomaly.is_mock is True
    
    def test_anomaly_score_validation(self):
        """Anomaly score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            AnomalyDetection(
                metric_name="cpu",
                component="app",
                timestamp=datetime.now(),
                observed_value=100,
                expected_value=50,
                anomaly_score=1.5,  # Invalid
                detection_method="z_score",
                is_anomalous=True
            )
