"""
Complete Stage 4 Demo using EA Sports INC3528891.

Demonstrates full pipeline with evidence tracing.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_management.stage3_correlation.schemas import IncidentGroup
from alert_management.stage2_classification.schemas import EnrichedAlert, ClassificationResult
from alert_management.stage4_analysis.pipeline import Stage4Pipeline
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider
from alert_management.stage4_analysis.reasoning.mock_reasoning_provider import MockReasoningProvider


def create_ea_sports_incident():
    """Create EA Sports incident from real data."""
    base_time = datetime(2026, 8, 6, 10, 30, 0)
    
    # Create enriched alerts (simulating EA Sports alerts)
    alerts = []
    for i in range(3):
        alert = EnrichedAlert(
            alert_id=f"INC352889{i}",
            created_at=base_time,
            client="EA Sports",
            raw_description="Critical AutoTicket EASS - EA Sports - EASS_Watcher_Alert alert: P1EASS_ELB_ErrCheck - 59 ELB Errors occurred",
            normalized_description="critical autoticket eass ea sports eass_watcher_alert alert p1eass_elb_errcheck 59 elb errors occurred",
            metadata={"service": "elb", "component": "load_balancer"},
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
        normalized_signature="elb errors infrastructure",
        correlation_method="semantic_clustering",
        avg_correlation_score=0.95
    )
    
    return incident_group, alerts


def main():
    print("=" * 80)
    print("STAGE 4 COMPLETE DEMO - EA SPORTS INC3528891")
    print("=" * 80)
    print()
    
    # Create incident
    incident_group, alerts = create_ea_sports_incident()
    
    print(f"📋 Incident: {incident_group.incident_id}")
    print(f"👤 Client: {incident_group.client}")
    print(f"📊 Alerts: {len(alerts)}")
    print(f"🕐 Time: {incident_group.incident_start}")
    print()
    
    # Initialize pipeline
    print("🔧 Initializing Stage 4 Pipeline...")
    pipeline = Stage4Pipeline(
        log_provider=MockLogProvider(),
        metric_provider=MockMetricProvider(),
        trace_provider=MockTraceProvider(),
        reasoning_provider=MockReasoningProvider()
    )
    print("✅ Pipeline initialized")
    print()
    
    # Run analysis
    print("🔍 Running complete analysis...")
    print("-" * 80)
    
    rca_result, support_msg, stakeholder_msg = pipeline.analyze_incident(
        incident_group,
        alerts
    )
    
    print()
    print("=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)
    print()
    
    # Evidence Summary
    print(f"📊 EVIDENCE COLLECTED: {len(rca_result.evidence)}")
    if rca_result.evidence:
        mock_count = sum(1 for e in rca_result.evidence if e.is_mock)
        real_count = len(rca_result.evidence) - mock_count
        print(f"   - Mock: {mock_count}")
        print(f"   - Real: {real_count}")
        print()
        
        print("Evidence by Source:")
        sources = {}
        for e in rca_result.evidence:
            sources[e.source] = sources.get(e.source, 0) + 1
        for source, count in sources.items():
            print(f"   - {source}: {count}")
        print()
        
        print("Sample Evidence (first 3):")
        for i, e in enumerate(rca_result.evidence[:3]):
            print(f"   {i+1}. [{e.source}] {e.description[:80]}...")
            print(f"      Source Type: {e.source_type}, Is Mock: {e.is_mock}, Weight: {e.weight}")
    else:
        print("   ⚠️  NO EVIDENCE GENERATED")
    print()
    
    # RCA Summary
    print(f"🎯 DIAGNOSIS: {rca_result.diagnosis_status.value.upper()}")
    if rca_result.probable_root_cause:
        print(f"   Component: {rca_result.probable_root_cause.component}")
        print(f"   Failure Type: {rca_result.probable_root_cause.failure_type}")
        print(f"   Confidence: {rca_result.probable_root_cause.confidence:.2%}")
        print(f"   Supporting Evidence: {len(rca_result.probable_root_cause.supporting_evidence_ids)}")
    print()
    
    # Alternatives
    if rca_result.alternative_hypotheses:
        print(f"🔄 ALTERNATIVES: {len(rca_result.alternative_hypotheses)}")
        for alt in rca_result.alternative_hypotheses[:2]:
            print(f"   - {alt.component} / {alt.failure_type} ({alt.confidence:.2%})")
        print()
    
    # Recommendations
    if rca_result.recommended_actions:
        print(f"💡 RECOMMENDATIONS: {len(rca_result.recommended_actions)}")
        for action in rca_result.recommended_actions:
            approval = "⚠️ REQUIRES APPROVAL" if action.requires_human_approval else "✅ AUTO-APPROVED"
            print(f"   [{action.action_type.value}] P{action.priority}: {action.action[:60]}...")
            print(f"      {approval}")
        print()
    
    # Provenance
    print(f"🔍 PROVENANCE:")
    print(f"   Telemetry is Mock: {rca_result.telemetry_is_mock}")
    print(f"   Reasoning Provider: {rca_result.reasoning_provider}")
    print(f"   Human Review Required: {rca_result.human_review_required}")
    print()
    
    # Communications
    print("=" * 80)
    print("SUPPORT COMMUNICATION (First 500 chars)")
    print("=" * 80)
    print(support_msg[:500] + "...")
    print()
    
    print("=" * 80)
    print("STAKEHOLDER COMMUNICATION")
    print("=" * 80)
    print(stakeholder_msg)
    print()
    
    # Final Status
    print("=" * 80)
    print("✅ STAGE 4 DEMO COMPLETE")
    print("=" * 80)
    
    return rca_result


if __name__ == "__main__":
    result = main()
    
    # Exit with error if no evidence
    if len(result.evidence) == 0:
        print("\n❌ ERROR: No evidence generated!")
        sys.exit(1)
