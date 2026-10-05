"""Test telemetry generation directly."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_management.stage4_analysis.schemas import IncidentContext
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider


def main():
    # Create a simple incident context
    base_time = datetime(2026, 8, 6, 10, 30, 0)
    
    context = IncidentContext(
        incident_id="TEST-001",
        client="Test Client",
        alert_ids=["INC1"],
        primary_alert_id="INC1",
        incident_start=base_time,
        incident_end=base_time + timedelta(minutes=15),  # 15 minute incident
        alert_count=1,
        services=["elb", "database", "application"],
        components=["elb", "database", "application"],
        normalized_descriptions=["test alert"],
        diagnostic_start=base_time - timedelta(minutes=30),
        diagnostic_end=base_time + timedelta(minutes=45),
        stage2_predictions={}
    )
    
    print("=" * 80)
    print("TELEMETRY GENERATION TEST")
    print("=" * 80)
    print()
    print(f"Incident: {context.incident_id}")
    print(f"Incident Time: {context.incident_start} to {context.incident_end}")
    print(f"Diagnostic Window: {context.diagnostic_start} to {context.diagnostic_end}")
    print(f"Components: {context.components}")
    print()
    
    # Test log provider
    print("🔍 Testing Log Provider...")
    log_provider = MockLogProvider()
    logs = log_provider.get_logs(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.components
    )
    print(f"   Generated {len(logs)} logs")
    if logs:
        print(f"   Sample: {logs[0].message}")
        print(f"   Provenance: source_type={logs[0].source_type}, is_mock={logs[0].is_mock}")
    print()
    
    # Test metric provider
    print("📊 Testing Metric Provider...")
    metric_provider = MockMetricProvider()
    metrics = metric_provider.get_metrics(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.components
    )
    print(f"   Generated {len(metrics)} metrics")
    if metrics:
        print(f"   Sample: {metrics[0].metric_name} = {metrics[0].value}")
        print(f"   Provenance: source_type={metrics[0].source_type}, is_mock={metrics[0].is_mock}")
    print()
    
    # Test trace provider
    print("🔗 Testing Trace Provider...")
    trace_provider = MockTraceProvider()
    traces = trace_provider.get_traces(
        context=context,
        start_time=context.diagnostic_start,
        end_time=context.diagnostic_end,
        components=context.components
    )
    print(f"   Generated {len(traces)} trace spans")
    if traces:
        print(f"   Sample: {traces[0].operation_name} ({traces[0].component})")
        print(f"   Provenance: source_type={traces[0].source_type}, is_mock={traces[0].is_mock}")
    print()
    
    print("=" * 80)
    if logs and metrics and traces:
        print("✅ All telemetry providers working")
    else:
        print("❌ Some providers not generating telemetry")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
