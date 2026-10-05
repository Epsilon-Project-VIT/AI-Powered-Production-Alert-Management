"""
Unit tests for Stage 4 Incident Context Builder.
"""

import pytest
from datetime import datetime, timedelta

from alert_management.stage3_correlation.schemas import IncidentGroup
from alert_management.stage2_classification.schemas import (
    EnrichedAlert,
    ClassificationResult
)
from alert_management.stage4_analysis.context import (
    IncidentContextBuilder,
    ContextBuilderConfig
)
from alert_management.stage4_analysis.schemas import SourceType


class TestContextBuilderConfig:
    """Test configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ContextBuilderConfig()
        assert config.pre_window_minutes == 30
        assert config.post_window_minutes == 30
        assert config.require_all_alerts is False
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ContextBuilderConfig(
            pre_window_minutes=60,
            post_window_minutes=45,
            require_all_alerts=True
        )
        assert config.pre_window_minutes == 60
        assert config.post_window_minutes == 45
        assert config.require_all_alerts is True


class TestIncidentContextBuilder:
    """Test IncidentContextBuilder."""
    
    @pytest.fixture
    def sample_alerts(self):
        """Create sample enriched alerts."""
        base_time = datetime(2026, 8, 6, 10, 30, 0)
        
        alerts = []
        for i in range(3):
            alert = EnrichedAlert(
                alert_id=f"INC352889{i}",
                created_at=base_time + timedelta(minutes=i * 5),
                client="EA Sports",
                raw_description=f"Alert {i}: Database connection error",
                normalized_description=f"alert {i} database connection error",
                metadata={"service": "database"},
                alert_type=ClassificationResult(label="DATABASE", confidence=0.9),
                severity=ClassificationResult(label="HIGH", confidence=0.85),
                business_impact=ClassificationResult(label="HIGH", confidence=0.8),
                priority=ClassificationResult(label="2 - High", confidence=0.75),
                routing=ClassificationResult(
                    label="Database Support Team",
                    confidence=0.9
                )
            )
            alerts.append(alert)
        
        return alerts
    
    @pytest.fixture
    def sample_incident_group(self, sample_alerts):
        """Create sample incident group."""
        return IncidentGroup(
            incident_id="INCIDENT-1007",
            alert_ids=[alert.alert_id for alert in sample_alerts],
            primary_alert_id=sample_alerts[0].alert_id,
            client="EA Sports",
            incident_start=sample_alerts[0].created_at,
            incident_end=sample_alerts[-1].created_at,
            alert_count=3,
            normalized_signature="database connection error",
            correlation_method="semantic_clustering",
            avg_correlation_score=0.92
        )
    
    def test_build_context_success(self, sample_incident_group, sample_alerts):
        """Test successful context building."""
        builder = IncidentContextBuilder()
        context = builder.build_context(sample_incident_group, sample_alerts)
        
        assert context.incident_id == "INCIDENT-1007"
        assert context.client == "EA Sports"
        assert len(context.alert_ids) == 3
        assert context.alert_count == 3
        assert context.primary_alert_id == "INC3528890"
        assert len(context.normalized_descriptions) == 3
    
    def test_diagnostic_window_default(self, sample_incident_group, sample_alerts):
        """Test diagnostic window with default config."""
        builder = IncidentContextBuilder()
        context = builder.build_context(sample_incident_group, sample_alerts)
        
        # Incident: 10:30 to 10:40
        # Window: 10:00 to 11:10 (±30 minutes)
        expected_start = sample_alerts[0].created_at - timedelta(minutes=30)
        expected_end = sample_alerts[-1].created_at + timedelta(minutes=30)
        
        assert context.diagnostic_start == expected_start
        assert context.diagnostic_end == expected_end
    
    def test_diagnostic_window_custom(self, sample_incident_group, sample_alerts):
        """Test diagnostic window with custom config."""
        config = ContextBuilderConfig(
            pre_window_minutes=60,
            post_window_minutes=45
        )
        builder = IncidentContextBuilder(config)
        context = builder.build_context(sample_incident_group, sample_alerts)
        
        expected_start = sample_alerts[0].created_at - timedelta(minutes=60)
        expected_end = sample_alerts[-1].created_at + timedelta(minutes=45)
        
        assert context.diagnostic_start == expected_start
        assert context.diagnostic_end == expected_end
    
    def test_normalized_descriptions(self, sample_incident_group, sample_alerts):
        """Test normalized descriptions collection."""
        builder = IncidentContextBuilder()
        context = builder.build_context(sample_incident_group, sample_alerts)
        
        # Should contain all descriptions
        assert len(context.normalized_descriptions) == 3
        assert "alert 0 database connection error" in context.normalized_descriptions
        assert "alert 1 database connection error" in context.normalized_descriptions
        assert "alert 2 database connection error" in context.normalized_descriptions
    
    def test_service_extraction(self, sample_incident_group, sample_alerts):
        """Test service/component extraction."""
        builder = IncidentContextBuilder()
        context = builder.build_context(sample_incident_group, sample_alerts)
        
        # Should extract from metadata and description
        assert "database" in context.services
    
    def test_stage2_predictions_preserved(self, sample_incident_group, sample_alerts):
        """Test Stage 2 predictions are preserved with correct provenance."""
        builder = IncidentContextBuilder()
        context = builder.build_context(sample_incident_group, sample_alerts)
        
        # Should have Stage 2 predictions
        assert "priority" in context.stage2_predictions
        assert "routing" in context.stage2_predictions
        
        # Check provenance
        priority_pred = context.stage2_predictions["priority"]
        assert priority_pred["source_type"] == SourceType.MODEL_PREDICTION
        assert priority_pred["is_mock"] is False
        assert priority_pred["label"] == "2 - High"
        assert 0.0 <= priority_pred["confidence"] <= 1.0
    
    def test_missing_alerts_lenient(self, sample_incident_group, sample_alerts):
        """Test handling missing alerts in lenient mode."""
        # Only provide 2 of 3 alerts
        builder = IncidentContextBuilder()
        context = builder.build_context(
            sample_incident_group,
            sample_alerts[:2]
        )
        
        # Should succeed with partial alerts
        assert len(context.alert_ids) == 2
        assert context.alert_count == 2
    
    def test_missing_alerts_strict(self, sample_incident_group, sample_alerts):
        """Test handling missing alerts in strict mode."""
        config = ContextBuilderConfig(require_all_alerts=True)
        builder = IncidentContextBuilder(config)
        
        # Should fail when alerts are missing
        with pytest.raises(ValueError, match="Cannot resolve alert IDs"):
            builder.build_context(
                sample_incident_group,
                sample_alerts[:2]
            )
    
    def test_all_alerts_missing(self, sample_incident_group):
        """Test error when all alerts are missing."""
        builder = IncidentContextBuilder()
        
        with pytest.raises(ValueError, match="No alerts resolved"):
            builder.build_context(sample_incident_group, [])
    
    def test_client_inconsistency(self, sample_incident_group, sample_alerts):
        """Test error on client inconsistency."""
        # Change one alert's client
        inconsistent_alerts = sample_alerts.copy()
        inconsistent_alerts[1] = EnrichedAlert(
            alert_id="INC3528891",
            created_at=sample_alerts[1].created_at,
            client="Different Client",  # Inconsistent
            raw_description="Alert",
            normalized_description="alert",
            alert_type=ClassificationResult(label="DATABASE", confidence=0.9),
            severity=ClassificationResult(label="HIGH", confidence=0.85),
            business_impact=ClassificationResult(label="HIGH", confidence=0.8),
            priority=ClassificationResult(label="2 - High", confidence=0.75),
            routing=ClassificationResult(label="Support", confidence=0.9)
        )
        
        builder = IncidentContextBuilder()
        
        with pytest.raises(ValueError, match="inconsistent clients"):
            builder.build_context(sample_incident_group, inconsistent_alerts)
    
    def test_primary_alert_selection_suggested(
        self,
        sample_incident_group,
        sample_alerts
    ):
        """Test primary alert selection uses suggested ID."""
        builder = IncidentContextBuilder()
        context = builder.build_context(sample_incident_group, sample_alerts)
        
        # Should use suggested primary from incident_group
        assert context.primary_alert_id == sample_incident_group.primary_alert_id
    
    def test_primary_alert_selection_fallback(
        self,
        sample_incident_group,
        sample_alerts
    ):
        """Test primary alert selection falls back to earliest."""
        # Suggest a non-existent primary
        modified_group = IncidentGroup(
            incident_id=sample_incident_group.incident_id,
            alert_ids=sample_incident_group.alert_ids,
            primary_alert_id="NON_EXISTENT_ID",
            client=sample_incident_group.client,
            incident_start=sample_incident_group.incident_start,
            incident_end=sample_incident_group.incident_end,
            alert_count=sample_incident_group.alert_count,
            normalized_signature=sample_incident_group.normalized_signature,
            correlation_method=sample_incident_group.correlation_method
        )
        
        builder = IncidentContextBuilder()
        context = builder.build_context(modified_group, sample_alerts)
        
        # Should fall back to earliest alert
        earliest_alert = min(sample_alerts, key=lambda a: a.created_at)
        assert context.primary_alert_id == earliest_alert.alert_id
    
    def test_incident_timestamps(self, sample_incident_group, sample_alerts):
        """Test incident start/end timestamps."""
        builder = IncidentContextBuilder()
        context = builder.build_context(sample_incident_group, sample_alerts)
        
        # Should be earliest and latest alert timestamps
        assert context.incident_start == sample_alerts[0].created_at
        assert context.incident_end == sample_alerts[-1].created_at
    
    def test_service_extraction_from_multiple_sources(self):
        """Test service extraction from various sources."""
        base_time = datetime(2026, 8, 6, 10, 30, 0)
        
        alerts = [
            EnrichedAlert(
                alert_id="INC1",
                created_at=base_time,
                client="Test Client",
                raw_description="ELB error",
                normalized_description="elb error load balancer",
                metadata={"service": "elb", "component": "application"},
                alert_type=ClassificationResult(label="NETWORK", confidence=0.9),
                severity=ClassificationResult(label="HIGH", confidence=0.85),
                business_impact=ClassificationResult(label="HIGH", confidence=0.8),
                priority=ClassificationResult(label="2 - High", confidence=0.75),
                routing=ClassificationResult(label="Support", confidence=0.9)
            ),
            EnrichedAlert(
                alert_id="INC2",
                created_at=base_time + timedelta(minutes=5),
                client="Test Client",
                raw_description="Database connection timeout",
                normalized_description="database connection timeout",
                alert_type=ClassificationResult(label="DATABASE", confidence=0.9),
                severity=ClassificationResult(label="HIGH", confidence=0.85),
                business_impact=ClassificationResult(label="HIGH", confidence=0.8),
                priority=ClassificationResult(label="2 - High", confidence=0.75),
                routing=ClassificationResult(label="Support", confidence=0.9)
            )
        ]
        
        incident_group = IncidentGroup(
            incident_id="INCIDENT-TEST",
            alert_ids=["INC1", "INC2"],
            primary_alert_id="INC1",
            client="Test Client",
            incident_start=base_time,
            incident_end=base_time + timedelta(minutes=5),
            alert_count=2,
            normalized_signature="test",
            correlation_method="test"
        )
        
        builder = IncidentContextBuilder()
        context = builder.build_context(incident_group, alerts)
        
        # Should extract multiple services
        assert "elb" in context.services
        assert "application" in context.services
        assert "database" in context.services
        assert "network" in context.services
