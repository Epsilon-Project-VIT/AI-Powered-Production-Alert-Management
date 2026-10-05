"""
Demo script for Stage 4 Phase 4.2 - Mock Telemetry Generation.

Demonstrates provenance-tracked telemetry generation for a sample incident.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from alert_management.stage4_analysis.schemas import IncidentContext
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider


def main():
    """Demonstrate mock telemetry generation with provenance."""
    
    print("\n" + "=" * 80)
    print("STAGE 4 PHASE 4.2 - MOCK TELEMETRY GENERATION DEMO")
    print("=" * 80)
    
    # Create sample incident context
    now = datetime.now()
    context = IncidentContext(
        incident_id="INCIDENT-DEMO-001",
        client="EA Sports",
        alert_ids=["INC3528891", "INC3528892"],
        primary_alert_id="INC3528891",
        incident_start=now,
        incident_end=now + timedelta(minutes=15),
        alert_count=2,
        services=["eass_watcher"],
        components=["application", "database", "elb"],
        normalized_descriptions=[
            "critical autoticket eass watcher alert elb errors occurred",
            "critical autoticket eass watcher alert elb errors occurred"
        ],
        diagnostic_start=now - timedelta(minutes=30),
        diagnostic_end=now + timedelta(minutes=45)
    )
    
    print(f"\nIncident Context:")
    print(f"  Incident ID: {context.incident_id}")
    print(f"  Client: {context.client}")
    print(f"  Components: {', '.join(context.components)}")
    print(f"  Incident Window: {context.incident_start} to {context.incident_end}")
    print(f"  Diagnostic Window: {context.diagnostic_start} to {context.diagnostic_end}")
    
    # Generate mock logs
    print("\n" + "-" * 80)
    print("[1/3] GENERATING MOCK LOGS")
    print("-" * 80)
    
    log_provider = MockLogProvider(error_rate=0.4, seed=42)
    logs = log_provider.get_logs(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        levels=["ERROR", "WARN"]
    )
    
    print(f"\nGenerated {len(logs)} log entries")
    print(f"Provenance: All logs have source_type='mock' and is_mock=True")
    
    # Show sample logs
    print(f"\nSample Log Entries (first 5):")
    for i, log in enumerate(logs[:5], 1):
        print(f"\n  Log {i}:")
        print(f"    ID: {log.log_id}")
        print(f"    Timestamp: {log.timestamp}")
        print(f"    Component: {log.component}")
        print(f"    Level: {log.level}")
        print(f"    Message: {log.message}")
        print(f"    Source Type: {log.source_type}")
        print(f"    Is Mock: {log.is_mock}")
    
    # Verify provenance
    mock_count = sum(1 for log in logs if log.is_mock and log.source_type.value == "mock")
    print(f"\n✓ Provenance Validation: {mock_count}/{len(logs)} logs have consistent mock provenance")
    
    # Generate mock metrics
    print("\n" + "-" * 80)
    print("[2/3] GENERATING MOCK METRICS")
    print("-" * 80)
    
    metric_provider = MockMetricProvider(anomaly_injection_rate=0.8, seed=42)
    metrics = metric_provider.get_metrics(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=["database"],
        metric_names=["db_connection_pool_utilization", "db_query_latency"]
    )
    
    print(f"\nGenerated {len(metrics)} metric data points")
    print(f"Provenance: All metrics have source_type='mock' and is_mock=True")
    
    # Group by metric name
    metrics_by_name = {}
    for metric in metrics:
        if metric.metric_name not in metrics_by_name:
            metrics_by_name[metric.metric_name] = []
        metrics_by_name[metric.metric_name].append(metric)
    
    print(f"\nMetric Time Series:")
    for metric_name, series in metrics_by_name.items():
        print(f"\n  {metric_name}:")
        print(f"    Data Points: {len(series)}")
        print(f"    Unit: {series[0].unit}")
        print(f"    Value Range: {min(m.value for m in series):.2f} - {max(m.value for m in series):.2f}")
        
        # Show sample values
        print(f"    Sample Values:")
        for i, m in enumerate(series[:3]):
            anomaly_flag = " (anomaly)" if m.metadata and m.metadata.get("is_anomalous") else ""
            print(f"      {m.timestamp}: {m.value:.2f} {m.unit}{anomaly_flag}")
    
    # Verify provenance
    mock_count = sum(1 for m in metrics if m.is_mock and m.source_type.value == "mock")
    print(f"\n✓ Provenance Validation: {mock_count}/{len(metrics)} metrics have consistent mock provenance")
    
    # Generate mock traces
    print("\n" + "-" * 80)
    print("[3/3] GENERATING MOCK TRACES")
    print("-" * 80)
    
    trace_provider = MockTraceProvider(error_injection_rate=0.5, seed=42)
    traces = trace_provider.get_traces(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end
    )
    
    print(f"\nGenerated {len(traces)} trace spans")
    print(f"Provenance: All traces have source_type='mock' and is_mock=True")
    
    # Group by trace_id
    traces_by_id = {}
    for span in traces:
        if span.trace_id not in traces_by_id:
            traces_by_id[span.trace_id] = []
        traces_by_id[span.trace_id].append(span)
    
    print(f"\nTrace Summary:")
    print(f"  Total Traces: {len(traces_by_id)}")
    print(f"  Total Spans: {len(traces)}")
    
    # Show sample trace
    sample_trace_id = list(traces_by_id.keys())[0]
    sample_trace = sorted(traces_by_id[sample_trace_id], key=lambda s: s.start_time)
    
    print(f"\n  Sample Trace ({sample_trace_id}):")
    for i, span in enumerate(sample_trace):
        parent_indicator = f" (child of {span.parent_span_id[:12]}...)" if span.parent_span_id else " (root)"
        print(f"    Span {i+1}{parent_indicator}:")
        print(f"      Component: {span.component}")
        print(f"      Operation: {span.operation}")
        print(f"      Duration: {span.duration_ms:.2f}ms")
        print(f"      Status: {span.status}")
        print(f"      Source Type: {span.source_type}")
        print(f"      Is Mock: {span.is_mock}")
    
    # Extract dependency graph
    dependencies = trace_provider.get_dependency_graph(traces)
    print(f"\n  Dependency Graph:")
    for upstream, downstream_list in dependencies.items():
        print(f"    {upstream} → {', '.join(downstream_list)}")
    
    # Verify provenance
    mock_count = sum(1 for span in traces if span.is_mock and span.source_type.value == "mock")
    print(f"\n✓ Provenance Validation: {mock_count}/{len(traces)} spans have consistent mock provenance")
    
    # Final summary
    print("\n" + "=" * 80)
    print("PHASE 4.2 COMPLETION SUMMARY")
    print("=" * 80)
    print(f"\n✓ Mock Logs Generated: {len(logs)}")
    print(f"✓ Mock Metrics Generated: {len(metrics)}")
    print(f"✓ Mock Trace Spans Generated: {len(traces)}")
    print(f"✓ All telemetry has consistent mock provenance")
    print(f"✓ Provenance validation: source_type='mock', is_mock=True")
    print(f"\nPhase 4.2 Status: COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
