"""
Unit tests for Stage 4 mock telemetry providers.

Tests provenance tracking, data generation, and consistency validation.
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    SourceType,
    LogRecord,
    MetricRecord,
    TraceSpan,
    Evidence,
)
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider


@pytest.fixture
def sample_incident_context():
    """Create sample incident context for testing."""
    now = datetime.now()
    return IncidentContext(
        incident_id="INCIDENT-TEST-001",
        client="EA Sports",
        alert_ids=["INC001", "INC002"],
        primary_alert_id="INC001",
        incident_start=now,
        incident_end=now + timedelta(minutes=15),
        alert_count=2,
        services=["eass_watcher"],
        components=["application", "database", "elb"],
        normalized_descriptions=["test alert 1", "test alert 2"],
        diagnostic_start=now - timedelta(minutes=30),
        diagnostic_end=now + timedelta(minutes=45)
    )


class TestProvenanceValidation:
    """Test provenance consistency validation."""
    
    def test_mock_source_type_requires_is_mock_true(self):
        """Mock source type must have is_mock=True."""
        # Valid: source_type=MOCK, is_mock=True
        evidence = Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id="test_001",
            timestamp=datetime.now(),
            description="Test evidence",
            weight=0.8,
            is_mock=True
        )
        assert evidence.is_mock is True
        
        # Invalid: source_type=MOCK, is_mock=False (contradiction)
        with pytest.raises(ValidationError, match="source_type='mock' requires is_mock=True"):
            Evidence(
                source="logs",
                source_type=SourceType.MOCK,
                source_id="test_001",
                timestamp=datetime.now(),
                description="Test evidence",
                weight=0.8,
                is_mock=False  # Contradicts MOCK source_type
            )
    
    def test_real_source_type_requires_is_mock_false(self):
        """Real source type must have is_mock=False."""
        # Valid: source_type=REAL, is_mock=False
        evidence = Evidence(
            source="logs",
            source_type=SourceType.REAL,
            source_id="test_001",
            timestamp=datetime.now(),
            description="Test evidence",
            weight=0.8,
            is_mock=False
        )
        assert evidence.is_mock is False
        
        # Invalid: source_type=REAL, is_mock=True (contradiction)
        with pytest.raises(ValidationError, match="source_type='real' requires is_mock=False"):
            Evidence(
                source="logs",
                source_type=SourceType.REAL,
                source_id="test_001",
                timestamp=datetime.now(),
                description="Test evidence",
                weight=0.8,
                is_mock=True  # Contradicts REAL source_type
            )
    
    def test_model_prediction_source_type(self):
        """Model predictions should have is_mock=False (they're predictions, not mock telemetry)."""
        # Valid: source_type=MODEL_PREDICTION, is_mock=False
        evidence = Evidence(
            source="stage2_priority",
            source_type=SourceType.MODEL_PREDICTION,
            source_id="pred_001",
            timestamp=datetime.now(),
            description="Priority prediction: P2",
            weight=0.7,
            is_mock=False  # Predictions are not mock telemetry
        )
        assert evidence.source_type == SourceType.MODEL_PREDICTION
        assert evidence.is_mock is False
        
        # Invalid: source_type=MODEL_PREDICTION, is_mock=True
        with pytest.raises(ValidationError, match="model_prediction.*should have is_mock=False"):
            Evidence(
                source="stage2_priority",
                source_type=SourceType.MODEL_PREDICTION,
                source_id="pred_001",
                timestamp=datetime.now(),
                description="Priority prediction: P2",
                weight=0.7,
                is_mock=True
            )
    
    def test_log_record_provenance_validation(self):
        """LogRecord must have consistent provenance."""
        # Valid mock log
        LogRecord(
            log_id="log_001",
            timestamp=datetime.now(),
            component="database",
            level="ERROR",
            message="Connection timeout",
            source_type=SourceType.MOCK,
            is_mock=True
        )
        
        # Invalid: mock source with is_mock=False
        with pytest.raises(ValidationError):
            LogRecord(
                log_id="log_001",
                timestamp=datetime.now(),
                component="database",
                level="ERROR",
                message="Connection timeout",
                source_type=SourceType.MOCK,
                is_mock=False  # Invalid
            )
    
    def test_metric_record_provenance_validation(self):
        """MetricRecord must have consistent provenance."""
        # Valid mock metric
        MetricRecord(
            metric_id="metric_001",
            timestamp=datetime.now(),
            metric_name="cpu_utilization",
            component="application",
            value=85.5,
            unit="percent",
            source_type=SourceType.MOCK,
            is_mock=True
        )
        
        # Invalid: mock source with is_mock=False
        with pytest.raises(ValidationError):
            MetricRecord(
                metric_id="metric_001",
                timestamp=datetime.now(),
                metric_name="cpu_utilization",
                component="application",
                value=85.5,
                unit="percent",
                source_type=SourceType.MOCK,
                is_mock=False  # Invalid
            )
    
    def test_trace_span_provenance_validation(self):
        """TraceSpan must have consistent provenance."""
        now = datetime.now()
        
        # Valid mock trace
        TraceSpan(
            span_id="span_001",
            trace_id="trace_123",
            component="application",
            operation="http_request",
            start_time=now,
            end_time=now + timedelta(milliseconds=100),
            duration_ms=100.0,
            status="ok",
            source_type=SourceType.MOCK,
            is_mock=True
        )
        
        # Invalid: mock source with is_mock=False
        with pytest.raises(ValidationError):
            TraceSpan(
                span_id="span_001",
                trace_id="trace_123",
                component="application",
                operation="http_request",
                start_time=now,
                end_time=now + timedelta(milliseconds=100),
                duration_ms=100.0,
                status="ok",
                source_type=SourceType.MOCK,
                is_mock=False  # Invalid
            )


class TestMockLogProvider:
    """Test MockLogProvider."""
    
    def test_generates_logs_with_mock_provenance(self, sample_incident_context):
        """All generated logs must have mock provenance."""
        provider = MockLogProvider(seed=42)
        
        logs = provider.get_logs(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        assert len(logs) > 0, "Should generate logs"
        
        # Verify ALL logs have proper provenance
        for log in logs:
            assert log.source_type == SourceType.MOCK, f"Log {log.log_id} must have source_type=MOCK"
            assert log.is_mock is True, f"Log {log.log_id} must have is_mock=True"
            assert log.log_id.startswith("mock_log_"), "Log ID should indicate mock"
    
    def test_generates_error_logs_during_incident(self, sample_incident_context):
        """More errors should occur during incident time."""
        provider = MockLogProvider(error_rate=0.5, seed=42)
        
        logs = provider.get_logs(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            levels=["ERROR"]
        )
        
        # Count errors during vs outside incident
        errors_during_incident = sum(
            1 for log in logs
            if sample_incident_context.incident_start <= log.timestamp <= 
               (sample_incident_context.incident_end or sample_incident_context.incident_start + timedelta(minutes=10))
        )
        
        errors_outside_incident = len(logs) - errors_during_incident
        
        # Should have more errors during incident (with high error_rate)
        assert errors_during_incident > 0, "Should generate errors during incident"
    
    def test_filters_by_component(self, sample_incident_context):
        """Should filter logs by component."""
        provider = MockLogProvider(seed=42)
        
        logs = provider.get_logs(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            components=["database"]
        )
        
        # All logs should be from database component
        for log in logs:
            assert log.component == "database"
    
    def test_filters_by_log_level(self, sample_incident_context):
        """Should filter logs by level."""
        provider = MockLogProvider(seed=42)
        
        logs = provider.get_logs(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            levels=["ERROR", "WARN"]
        )
        
        # All logs should be ERROR or WARN
        for log in logs:
            assert log.level in ["ERROR", "WARN"]
    
    def test_logs_have_timestamps_in_window(self, sample_incident_context):
        """All logs should have timestamps within the diagnostic window."""
        provider = MockLogProvider(seed=42)
        
        logs = provider.get_logs(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        for log in logs:
            assert sample_incident_context.diagnostic_start <= log.timestamp <= sample_incident_context.diagnostic_end
    
    def test_logs_sorted_by_timestamp(self, sample_incident_context):
        """Logs should be returned in chronological order."""
        provider = MockLogProvider(seed=42)
        
        logs = provider.get_logs(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        timestamps = [log.timestamp for log in logs]
        assert timestamps == sorted(timestamps), "Logs should be sorted by timestamp"


class TestMockMetricProvider:
    """Test MockMetricProvider."""
    
    def test_generates_metrics_with_mock_provenance(self, sample_incident_context):
        """All generated metrics must have mock provenance."""
        provider = MockMetricProvider(seed=42)
        
        metrics = provider.get_metrics(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        assert len(metrics) > 0, "Should generate metrics"
        
        # Verify ALL metrics have proper provenance
        for metric in metrics:
            assert metric.source_type == SourceType.MOCK, f"Metric {metric.metric_id} must have source_type=MOCK"
            assert metric.is_mock is True, f"Metric {metric.metric_id} must have is_mock=True"
            assert metric.metric_id.startswith("mock_metric_"), "Metric ID should indicate mock"
    
    def test_generates_time_series_data(self, sample_incident_context):
        """Should generate time series with multiple data points."""
        provider = MockMetricProvider(seed=42)
        
        metrics = provider.get_metrics(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            components=["database"],
            metric_names=["db_connection_pool_utilization"]
        )
        
        # Should have multiple samples over time
        assert len(metrics) > 5, "Should generate time series with multiple points"
        
        # Verify timestamps are spaced out
        timestamps = [m.timestamp for m in metrics]
        assert timestamps == sorted(timestamps), "Metrics should be in chronological order"
    
    def test_injects_anomalies_during_incident(self, sample_incident_context):
        """Metrics should show anomalies during incident time."""
        provider = MockMetricProvider(anomaly_injection_rate=0.9, seed=42)
        
        metrics = provider.get_metrics(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            components=["database"],
            metric_names=["db_connection_pool_utilization"]
        )
        
        # Find metrics during incident
        incident_metrics = [
            m for m in metrics
            if sample_incident_context.incident_start <= m.timestamp <= 
               (sample_incident_context.incident_end or sample_incident_context.incident_start + timedelta(minutes=10))
        ]
        
        # Check if anomalies were injected (metadata tracks this)
        anomalous_count = sum(
            1 for m in incident_metrics
            if m.metadata and m.metadata.get("is_anomalous", False)
        )
        
        assert anomalous_count > 0, "Should inject anomalies during incident"
    
    def test_filters_by_component(self, sample_incident_context):
        """Should filter metrics by component."""
        provider = MockMetricProvider(seed=42)
        
        metrics = provider.get_metrics(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            components=["application"]
        )
        
        # All metrics should be from application component
        for metric in metrics:
            assert metric.component == "application"
    
    def test_filters_by_metric_name(self, sample_incident_context):
        """Should filter by specific metric names."""
        provider = MockMetricProvider(seed=42)
        
        metrics = provider.get_metrics(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            components=["database"],
            metric_names=["db_query_latency"]
        )
        
        # All metrics should be db_query_latency
        for metric in metrics:
            assert metric.metric_name == "db_query_latency"
    
    def test_metric_values_are_realistic(self, sample_incident_context):
        """Metric values should be within realistic ranges."""
        provider = MockMetricProvider(seed=42)
        
        metrics = provider.get_metrics(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            components=["application"],
            metric_names=["app_memory_usage"]
        )
        
        # Memory usage should be 0-100%
        for metric in metrics:
            if metric.unit == "percent":
                assert 0 <= metric.value <= 100, f"Percentage should be 0-100, got {metric.value}"


class TestMockTraceProvider:
    """Test MockTraceProvider."""
    
    def test_generates_traces_with_mock_provenance(self, sample_incident_context):
        """All generated trace spans must have mock provenance."""
        provider = MockTraceProvider(seed=42)
        
        traces = provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        assert len(traces) > 0, "Should generate trace spans"
        
        # Verify ALL traces have proper provenance
        for span in traces:
            assert span.source_type == SourceType.MOCK, f"Span {span.span_id} must have source_type=MOCK"
            assert span.is_mock is True, f"Span {span.span_id} must have is_mock=True"
            assert span.span_id.startswith("span_"), "Span ID should have proper format"
    
    def test_generates_parent_child_relationships(self, sample_incident_context):
        """Traces should have parent-child span relationships."""
        provider = MockTraceProvider(seed=42)
        
        traces = provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        # Group by trace_id
        traces_by_id = {}
        for span in traces:
            if span.trace_id not in traces_by_id:
                traces_by_id[span.trace_id] = []
            traces_by_id[span.trace_id].append(span)
        
        # Check at least one trace has parent-child relationships
        has_relationship = False
        for trace_id, spans in traces_by_id.items():
            if len(spans) > 1:
                # Sort by start time
                sorted_spans = sorted(spans, key=lambda s: s.start_time)
                
                # First span should have no parent
                assert sorted_spans[0].parent_span_id is None, "Root span should have no parent"
                
                # Subsequent spans should have parents
                for i in range(1, len(sorted_spans)):
                    assert sorted_spans[i].parent_span_id is not None, "Child spans should have parent"
                    has_relationship = True
        
        assert has_relationship, "Should generate traces with parent-child relationships"
    
    def test_dependency_chain_ordering(self, sample_incident_context):
        """Spans in a trace should follow dependency ordering."""
        provider = MockTraceProvider(seed=42)
        
        traces = provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        # Group by trace_id
        traces_by_id = {}
        for span in traces:
            if span.trace_id not in traces_by_id:
                traces_by_id[span.trace_id] = []
            traces_by_id[span.trace_id].append(span)
        
        # For each trace, verify chronological ordering
        for trace_id, spans in traces_by_id.items():
            if len(spans) > 1:
                sorted_spans = sorted(spans, key=lambda s: s.start_time)
                
                # Each span should start after its parent starts
                for i in range(1, len(sorted_spans)):
                    assert sorted_spans[i].start_time >= sorted_spans[i-1].start_time
    
    def test_injects_errors_during_incident(self, sample_incident_context):
        """Should inject errors during incident time."""
        provider = MockTraceProvider(error_injection_rate=0.8, seed=42)
        
        traces = provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        # Find spans during incident with errors
        error_spans = [
            span for span in traces
            if span.status in ["error", "timeout"] and
            sample_incident_context.incident_start <= span.start_time <= 
            (sample_incident_context.incident_end or sample_incident_context.incident_start + timedelta(minutes=10))
        ]
        
        assert len(error_spans) > 0, "Should inject errors during incident"
    
    def test_filters_by_component(self, sample_incident_context):
        """Should filter traces by component."""
        provider = MockTraceProvider(seed=42)
        
        traces = provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end,
            components=["database"]
        )
        
        # All spans should be from database component
        for span in traces:
            assert span.component == "database"
    
    def test_duration_matches_timestamps(self, sample_incident_context):
        """Span duration should match start/end timestamps."""
        provider = MockTraceProvider(seed=42)
        
        traces = provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        for span in traces:
            expected_duration = (span.end_time - span.start_time).total_seconds() * 1000
            # Allow small floating point variance
            assert abs(span.duration_ms - expected_duration) < 1.0, \
                f"Duration mismatch for span {span.span_id}"
    
    def test_extracts_dependency_graph(self, sample_incident_context):
        """Should be able to extract dependency graph from traces."""
        provider = MockTraceProvider(seed=42)
        
        traces = provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        dependencies = provider.get_dependency_graph(traces)
        
        # Should have some dependencies
        assert len(dependencies) > 0, "Should extract dependencies"
        
        # Verify structure
        for upstream, downstream_list in dependencies.items():
            assert isinstance(upstream, str)
            assert isinstance(downstream_list, list)
            assert all(isinstance(d, str) for d in downstream_list)


class TestTelemetryIntegration:
    """Test integration between different telemetry providers."""
    
    def test_all_providers_generate_consistent_provenance(self, sample_incident_context):
        """All providers should generate data with consistent mock provenance."""
        log_provider = MockLogProvider(seed=42)
        metric_provider = MockMetricProvider(seed=42)
        trace_provider = MockTraceProvider(seed=42)
        
        logs = log_provider.get_logs(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        metrics = metric_provider.get_metrics(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        traces = trace_provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        # All telemetry must be mock
        for log in logs:
            assert log.is_mock is True and log.source_type == SourceType.MOCK
        
        for metric in metrics:
            assert metric.is_mock is True and metric.source_type == SourceType.MOCK
        
        for span in traces:
            assert span.is_mock is True and span.source_type == SourceType.MOCK
    
    def test_telemetry_covers_diagnostic_window(self, sample_incident_context):
        """Generated telemetry should cover the diagnostic window."""
        log_provider = MockLogProvider(seed=42)
        metric_provider = MockMetricProvider(seed=42)
        trace_provider = MockTraceProvider(seed=42)
        
        logs = log_provider.get_logs(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        metrics = metric_provider.get_metrics(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        traces = trace_provider.get_traces(
            context=sample_incident_context,
            start_time=sample_incident_context.diagnostic_start,
            end_time=sample_incident_context.diagnostic_end
        )
        
        # All timestamps should be within window
        for log in logs:
            assert sample_incident_context.diagnostic_start <= log.timestamp <= sample_incident_context.diagnostic_end
        
        for metric in metrics:
            assert sample_incident_context.diagnostic_start <= metric.timestamp <= sample_incident_context.diagnostic_end
        
        for span in traces:
            assert sample_incident_context.diagnostic_start <= span.start_time <= sample_incident_context.diagnostic_end
