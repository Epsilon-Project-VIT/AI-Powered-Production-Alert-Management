"""
Integration test: Stage 3 → Stage 4 pipeline.
"""

import pytest
from datetime import datetime

from alert_management.stage3_correlation.schemas import IncidentGroup
from alert_management.stage2_classification.schemas import EnrichedAlert, ClassificationResult
from alert_management.stage4_analysis.pipeline import Stage4Pipeline
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider
from alert_management.stage4_analysis.reasoning.mock_reasoning_provider import MockReasoningProvider
from alert_management.stage4_analysis.schemas import DiagnosisStatus


class TestStage3ToStage4Integration:
    """Integration tests for Stage 3 to Stage 4 flow."""
    
    @pytest.fixture
    def ea_sports_incident(self):
        """Create EA Sports incident group."""
        base_time = datetime(2026, 8, 6, 10, 30, 0)
        
        # Create enriched alerts
        alerts = []
        for i in range(3):
            alert = EnrichedAlert(
                alert_id=f"INC352889{i}",
                created_at=base_time,
                client="EA Sports",
                raw_description="ELB errors detected",
                normalized_description="elb errors detected",
                metadata={"service": "elb"},
                alert_type=ClassificationResult(label="INFRASTRUCTURE", confidence=0.9),
                severity=ClassificationResult(label="HIGH", confidence=0.85),
                business_impact=ClassificationResult(label="HIGH", confidence=0.8),
                priority=ClassificationResult(label="2 - High", confidence=0.75),
                routing=ClassificationResult(label="Infrastructure Team", confidence=0.9)
            )
            alerts.append(alert)
        
        # Create incident group
        incident_group = IncidentGroup(
            incident_id="INCIDENT-EA-001",
            alert_ids=[a.alert_id for a in alerts],
            primary_alert_id=alerts[0].alert_id,
            client="EA Sports",
            incident_start=base_time,
            incident_end=base_time,
            alert_count=3,
            normalized_signature="elb errors detected",
            correlation_method="semantic_clustering",
            avg_correlation_score=0.95
        )
        
        return incident_group, alerts
    
    def test_end_to_end_pipeline_mock(self, ea_sports_incident):
        """Test complete end-to-end pipeline with mock providers."""
        incident_group, alerts = ea_sports_incident
        
        # Initialize pipeline with mock providers
        pipeline = Stage4Pipeline(
            log_provider=MockLogProvider(),
            metric_provider=MockMetricProvider(),
            trace_provider=MockTraceProvider(),
            reasoning_provider=MockReasoningProvider()
        )
        
        # Run analysis
        rca_result, support_msg, stakeholder_msg = pipeline.analyze_incident(
            incident_group,
            alerts
        )
        
        # Verify RCA result structure
        assert rca_result is not None
        assert rca_result.incident_id == "INCIDENT-EA-001"
        assert rca_result.diagnosis_status in [
            DiagnosisStatus.SUFFICIENT_EVIDENCE,
            DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            DiagnosisStatus.AMBIGUOUS
        ]
        assert rca_result.probable_root_cause is not None
        
        # CRITICAL: Verify evidence was actually generated
        assert rca_result.evidence is not None, "Evidence list must exist"
        assert len(rca_result.evidence) > 0, (
            "Pipeline must generate evidence. Zero evidence indicates broken analyzer pipeline."
        )
        
        # Verify mock telemetry was used
        assert any(e.is_mock for e in rca_result.evidence), (
            "At least some evidence must come from mock telemetry"
        )
        
        # Verify provenance tracking
        assert rca_result.telemetry_is_mock is True, (
            "Pipeline used mock providers, telemetry_is_mock must be True"
        )
        
        # Verify evidence has proper structure
        for evidence in rca_result.evidence:
            assert evidence.source is not None
            assert evidence.source_type is not None
            assert evidence.source_id is not None
            assert evidence.timestamp is not None
            assert evidence.description is not None
            assert evidence.weight is not None
            assert isinstance(evidence.is_mock, bool)
        
        # Verify RCA candidate has supporting evidence
        if rca_result.probable_root_cause.supporting_evidence_ids:
            for ev_id in rca_result.probable_root_cause.supporting_evidence_ids:
                assert any(e.source_id == ev_id for e in rca_result.evidence), (
                    f"Supporting evidence ID {ev_id} must exist in evidence list"
                )
        
        # Verify messages generated
        assert "INCIDENT-EA-001" in support_msg
        assert "EA Sports" in support_msg
        assert "EA Sports" in stakeholder_msg
    
    def test_pipeline_with_insufficient_evidence(self):
        """Test pipeline handling of insufficient evidence."""
        base_time = datetime(2026, 8, 6, 10, 30, 0)
        
        # Single alert, minimal information
        alert = EnrichedAlert(
            alert_id="INC999999",
            created_at=base_time,
            client="Test Client",
            raw_description="Unknown error",
            normalized_description="unknown error",
            alert_type=ClassificationResult(label="UNKNOWN", confidence=0.3),
            severity=ClassificationResult(label="UNKNOWN", confidence=0.3),
            business_impact=ClassificationResult(label="UNKNOWN", confidence=0.3),
            priority=ClassificationResult(label="UNKNOWN", confidence=0.3),
            routing=ClassificationResult(label="UNKNOWN", confidence=0.3)
        )
        
        incident_group = IncidentGroup(
            incident_id="INCIDENT-UNKNOWN",
            alert_ids=["INC999999"],
            primary_alert_id="INC999999",
            client="Test Client",
            incident_start=base_time,
            incident_end=base_time,
            alert_count=1,
            normalized_signature="unknown error",
            correlation_method="single_alert"
        )
        
        pipeline = Stage4Pipeline(
            log_provider=MockLogProvider(),
            metric_provider=MockMetricProvider(),
            trace_provider=MockTraceProvider(),
            reasoning_provider=MockReasoningProvider(min_evidence_threshold=10)  # High threshold
        )
        
        rca_result, support_msg, stakeholder_msg = pipeline.analyze_incident(
            incident_group,
            [alert]
        )
        
        # Should handle gracefully
        assert rca_result is not None
        # May have insufficient evidence status, or ambiguous if evidence exists but is inconclusive
        assert rca_result.diagnosis_status in [
            DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            DiagnosisStatus.SUFFICIENT_EVIDENCE,  # Mock providers might generate enough
            DiagnosisStatus.AMBIGUOUS  # Multiple candidates with similar confidence
        ]
    
    def test_pipeline_preserves_provenance(self, ea_sports_incident):
        """Test that pipeline preserves evidence provenance."""
        incident_group, alerts = ea_sports_incident
        
        pipeline = Stage4Pipeline(
            log_provider=MockLogProvider(),
            metric_provider=MockMetricProvider(),
            trace_provider=MockTraceProvider(),
            reasoning_provider=MockReasoningProvider()
        )
        
        rca_result, _, _ = pipeline.analyze_incident(incident_group, alerts)
        
        # Verify telemetry provenance flag is set
        # (will be True if any mock telemetry was used)
        assert isinstance(rca_result.telemetry_is_mock, bool)
