"""
Debug script to trace evidence generation flow.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_management.stage4_analysis.schemas import IncidentContext
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider
from alert_management.stage4_analysis.analysis.log_analyzer import LogAnalyzer
from alert_management.stage4_analysis.analysis.anomaly_detector import AnomalyDetector
from alert_management.stage4_analysis.analysis.trace_analyzer import TraceAnalyzer


def main():
    print("=" * 80)
    print("DEBUG: Evidence Generation Flow")
    print("=" * 80)
    print()
    
    # Create test context
    base_time = datetime(2026, 8, 6, 10, 30, 0)
    
    context = IncidentContext(
        incident_id="TEST-001",
        alert_ids=["INC001"],
        client="Test Client",
        incident_start=base_time,
        incident_end=base_time,
        primary_alert_id="INC001",
        alert_count=1,
        services=["elb", "application"],
        components=["elb", "application"],
        normalized_descriptions=["test error"],
        diagnostic_start=base_time - timedelta(minutes=30),
        diagnostic_end=base_time + timedelta(minutes=30),
        stage2_predictions={}
    )
    
    print(f"Context Created:")
    print(f"  Incident: {context.incident_start} to {context.incident_end}")
    print(f"  Diagnostic: {context.diagnostic_start} to {context.diagnostic_end}")
    print(f"  Services: {context.services}")
    print()
    
    # Test log provider
    print("=" * 80)
    print("STEP 1: Collecting Logs")
    print("=" * 80)
    log_provider = MockLogProvider()
    logs = log_provider.get_logs(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.services
    )
    print(f"✅ Logs collected: {len(logs)}")
    if logs:
        print(f"   Sample log: {logs[0]}")
        print(f"   Time range: {min(l.timestamp for l in logs)} to {max(l.timestamp for l in logs)}")
        error_logs = [l for l in logs if l.level == "ERROR"]
        print(f"   Error logs: {len(error_logs)}")
    print()
    
    # Test log analyzer
    print("=" * 80)
    print("STEP 2: Analyzing Logs")
    print("=" * 80)
    log_analyzer = LogAnalyzer()
    log_evidence = log_analyzer.analyze(
        logs,
        context.diagnostic_start,
        context.diagnostic_end,
        context.incident_start,
        context.incident_end
    )
    print(f"✅ Log evidence generated: {len(log_evidence)}")
    for i, ev in enumerate(log_evidence[:3]):
        print(f"   {i+1}. {ev.description}")
        print(f"      Source: {ev.source}, Type: {ev.source_type}, Mock: {ev.is_mock}, Weight: {ev.weight}")
    print()
    
    # Test metric provider
    print("=" * 80)
    print("STEP 3: Collecting Metrics")
    print("=" * 80)
    metric_provider = MockMetricProvider()
    metrics = metric_provider.get_metrics(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.services
    )
    print(f"✅ Metrics collected: {len(metrics)}")
    if metrics:
        print(f"   Sample metric: {metrics[0]}")
        print(f"   Time range: {min(m.timestamp for m in metrics)} to {max(m.timestamp for m in metrics)}")
        metric_names = set(m.metric_name for m in metrics)
        print(f"   Unique metrics: {metric_names}")
    print()
    
    # Test anomaly detector
    print("=" * 80)
    print("STEP 4: Detecting Anomalies")
    print("=" * 80)
    anomaly_detector = AnomalyDetector()
    anomalies = anomaly_detector.detect_anomalies(
        metrics,
        context.diagnostic_start,
        context.diagnostic_end,
        context.incident_start,
        context.incident_end
    )
    print(f"✅ Anomalies detected: {len(anomalies)}")
    for i, anom in enumerate(anomalies[:3]):
        print(f"   {i+1}. {anom.metric_name} in {anom.component}")
        print(f"      Observed: {anom.observed_value:.2f}, Expected: {anom.expected_value:.2f}, Score: {anom.anomaly_score:.2f}")
    
    metric_evidence = anomaly_detector.generate_evidence(anomalies)
    print(f"✅ Metric evidence generated: {len(metric_evidence)}")
    for i, ev in enumerate(metric_evidence[:3]):
        print(f"   {i+1}. {ev.description}")
        print(f"      Source: {ev.source}, Type: {ev.source_type}, Mock: {ev.is_mock}, Weight: {ev.weight}")
    print()
    
    # Test trace provider
    print("=" * 80)
    print("STEP 5: Collecting Traces")
    print("=" * 80)
    trace_provider = MockTraceProvider()
    traces = trace_provider.get_traces(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.services
    )
    print(f"✅ Traces collected: {len(traces)}")
    if traces:
        print(f"   Sample trace: {traces[0]}")
        print(f"   Time range: {min(t.start_time for t in traces)} to {max(t.start_time for t in traces)}")
        error_traces = [t for t in traces if t.status == "error"]
        print(f"   Error traces: {len(error_traces)}")
    print()
    
    # Test trace analyzer
    print("=" * 80)
    print("STEP 6: Analyzing Traces")
    print("=" * 80)
    trace_analyzer = TraceAnalyzer()
    trace_evidence = trace_analyzer.analyze(
        traces,
        context.diagnostic_start,
        context.diagnostic_end,
        context.incident_start,
        context.incident_end
    )
    print(f"✅ Trace evidence generated: {len(trace_evidence)}")
    for i, ev in enumerate(trace_evidence[:3]):
        print(f"   {i+1}. {ev.description}")
        print(f"      Source: {ev.source}, Type: {ev.source_type}, Mock: {ev.is_mock}, Weight: {ev.weight}")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_evidence = len(log_evidence) + len(metric_evidence) + len(trace_evidence)
    print(f"Total Evidence: {total_evidence}")
    print(f"  - Log: {len(log_evidence)}")
    print(f"  - Metric: {len(metric_evidence)}")
    print(f"  - Trace: {len(trace_evidence)}")
    print()
    
    if total_evidence == 0:
        print("❌ ERROR: No evidence generated!")
        return 1
    else:
        print("✅ SUCCESS: Evidence pipeline working!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
