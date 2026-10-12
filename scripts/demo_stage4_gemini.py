#!/usr/bin/env python3
"""
Stage 4 Google Gemini Integration Demo - EA Sports Incident

Demonstrates Google Gemini (OpenAI-compatible endpoint) integration for RCA reasoning.
Compares MockReasoningProvider vs GeminiReasoningProvider on INCIDENT-EA-001.

Input: REAL HISTORICAL ALERTS (from dataset)
Telemetry: MOCK (illustrative scenarios)
Reasoning: MOCK or GEMINI (configurable via GEMINI_API_KEY)
Output: ILLUSTRATIVE RCA (not production validated)
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from datetime import datetime, timedelta
from alert_management.stage4_analysis.reasoning import (
    MockReasoningProvider,
    GeminiReasoningProvider,
    get_reasoning_provider
)
from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    Evidence,
    SourceType,
    ProbableRootCause
)
from alert_management.llm import GeminiConfig


def create_ea_sports_context():
    """Create EA Sports incident context (INCIDENT-EA-001)."""
    now = datetime(2026, 8, 6, 10, 30, 0)
    return IncidentContext(
        incident_id="INCIDENT-EA-001",
        client="EA Sports",
        alert_ids=["INC3528854", "INC3528855", "INC3528856"],
        primary_alert_id="INC3528854",
        incident_start=now,
        incident_end=now + timedelta(minutes=15),
        alert_count=3,
        services=["game-service", "elb"],
        components=["elb", "application"],
        normalized_descriptions=[
            "ea sports service elb unhealthy targets",
            "ea sports application timeout",
            "ea sports performance degradation"
        ],
        diagnostic_start=now - timedelta(minutes=10),
        diagnostic_end=now + timedelta(minutes=20)
    )


def create_mock_evidence():
    """Create mock evidence for EA Sports incident."""
    base_time = datetime(2026, 8, 6, 10, 30, 0)
    evidence = []
    
    # Mock logs
    for i in range(5):
        evidence.append(Evidence(
            source="logs",
            source_type=SourceType.MOCK,
            source_id=f"mock_log_{i:03d}",
            timestamp=base_time - timedelta(minutes=i),
            description=f"ELB health check failed for target {i+1}/5",
            weight=0.8,
            is_mock=True
        ))
    
    # Mock metrics
    for i in range(5):
        evidence.append(Evidence(
            source="metrics",
            source_type=SourceType.MOCK,
            source_id=f"mock_metric_{i:03d}",
            timestamp=base_time - timedelta(minutes=i),
            description=f"ELB unhealthy target count: {i + 1}",
            weight=0.9,
            is_mock=True
        ))
    
    # Mock trace
    evidence.append(Evidence(
        source="traces",
        source_type=SourceType.MOCK,
        source_id="mock_trace_001",
        timestamp=base_time,
        description="Request timeout at ELB->application boundary",
        weight=0.85,
        is_mock=True
    ))
    
    return evidence


def create_rca_candidates():
    """Create RCA candidates for EA Sports incident."""
    return [
        {
            "component": "elb",
            "failure_type": "timeout",
            "confidence": 0.90,
            "description": "ELB timeout due to unhealthy application targets",
            "supporting_evidence_ids": ["mock_log_000", "mock_log_001", "mock_metric_000", "mock_trace_001"]
        },
        {
            "component": "application",
            "failure_type": "service_error",
            "confidence": 0.65,
            "description": "Application backend slow responses",
            "supporting_evidence_ids": ["mock_trace_001"]
        }
    ]


def run_with_provider(provider_name):
    """Run EA Sports incident analysis with specified provider."""
    print(f"\n{'='*70}")
    print(f"Provider: {provider_name.upper()}")
    print(f"{'='*70}")
    
    context = create_ea_sports_context()
    evidence = create_mock_evidence()
    candidates = create_rca_candidates()
    
    if provider_name == "mock":
        provider = MockReasoningProvider()
    elif provider_name == "gemini":
        try:
            config = GeminiConfig.from_env()
            provider = GeminiReasoningProvider(config)
        except ValueError as e:
            print(f"✗ Cannot initialize Gemini provider: {e}")
            print("  Ensure GEMINI_API_KEY is configured in .env or environment")
            return None
    else:
        print(f"✗ Unknown provider: {provider_name}")
        return None
    
    print(f"\nIncident: {context.incident_id}")
    print(f"Client: {context.client}")
    print(f"Alerts: {context.alert_count}")
    print(f"Time: {context.incident_start}")
    print(f"\nEvidence: {len(evidence)} items")
    print(f"  - Logs: {len([e for e in evidence if e.source == 'logs'])}")
    print(f"  - Metrics: {len([e for e in evidence if e.source == 'metrics'])}")
    print(f"  - Traces: {len([e for e in evidence if e.source == 'traces'])}")
    print(f"  - Mock: 100.0%")
    print(f"\nRCA Candidates: {len(candidates)}")
    
    try:
        print(f"\nCalling {provider_name} reasoning provider...")
        result = provider.synthesize_rca(
            context=context,
            evidence=evidence,
            candidate_hypotheses=candidates,
            historical_patterns=[]
        )
        
        diagnosis_status = result.get('diagnosis_status')
        probable_rca = result.get('probable_root_cause')
        alternatives = result.get('alternative_hypotheses', [])
        missing = result.get('missing_evidence', [])
        actions = result.get('recommended_actions', [])
        
        print(f"\n✓ Reasoning completed successfully")
        print(f"Diagnosis Status: {diagnosis_status}")
        
        if probable_rca:
            if isinstance(probable_rca, dict):
                print(f"Probable Root Cause:")
                print(f"  Component: {probable_rca.get('component', 'unknown')}")
                print(f"  Failure Type: {probable_rca.get('failure_type', 'unknown')}")
                print(f"  Confidence: {probable_rca.get('confidence', 0.0):.2%}")
                print(f"  Description: {probable_rca.get('description', 'N/A')[:80]}...")
                print(f"  Supporting Evidence: {len(probable_rca.get('supporting_evidence_ids', []))} items")
            else:
                print(f"Probable Root Cause:")
                print(f"  Component: {probable_rca.component}")
                print(f"  Failure Type: {probable_rca.failure_type}")
                print(f"  Confidence: {probable_rca.confidence:.2%}")
                print(f"  Description: {probable_rca.description[:80]}...")
                print(f"  Supporting Evidence: {len(probable_rca.supporting_evidence_ids)} items")
        else:
            print(f"Probable Root Cause: None (insufficient evidence or ambiguous)")
        
        print(f"Alternative Hypotheses: {len(alternatives)}")
        print(f"Missing Evidence: {', '.join(missing) if missing else 'None identified'}")
        print(f"Recommended Actions: {len(actions)}")
        
        if actions:
            print(f"\nActions:")
            for i, action in enumerate(actions[:2], 1):
                if isinstance(action, dict):
                    print(f"  {i}. [{action.get('action_type', 'unknown')}] {action.get('action', 'N/A')[:60]}...")
                    print(f"     Requires Approval: {action.get('requires_human_approval', True)}")
                else:
                    print(f"  {i}. [{action.action_type.value}] {action.action[:60]}...")
                    print(f"     Requires Approval: {action.requires_human_approval}")
        
        print(f"\nProvenance:")
        print(f"  Telemetry is Mock: True (100%)")
        print(f"  Reasoning Provider: {provider_name}")
        print(f"  Human Review Required: True")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Reasoning failed: {type(e).__name__}")
        print(f"  {str(e)[:200]}")
        return None


def main():
    print("\n" + "="*70)
    print("Google Gemini - Stage 4 RCA Integration Demo")
    print("="*70)
    print("\nIncident: INCIDENT-EA-001 (EA Sports)")
    print("Input: REAL HISTORICAL ALERTS")
    print("Telemetry: MOCK (illustrative)")
    print("Output: ILLUSTRATIVE RCA (not production validated)")
    
    # 1. Run with Mock provider
    mock_result = run_with_provider("mock")
    
    # 2. Run with Gemini provider
    gemini_result = run_with_provider("gemini")
    
    # Summary
    print(f"\n{'='*70}")
    print("COMPARISON SUMMARY")
    print(f"{'='*70}")
    
    print(f"Mock Provider:   {'✓ Success' if mock_result else '✗ Failed'}")
    print(f"Gemini Provider: {'✓ Success' if gemini_result else '⚠ Not configured / failed'}")
    
    if mock_result and gemini_result:
        print(f"\n✓ Both providers successfully generated RCA results")
        print(f"✓ Gemini Stage 4 integration verified operational")
    elif gemini_result:
        print(f"\n✓ Gemini provider operational")
    elif mock_result:
        print(f"\nℹ Gemini provider not active (GEMINI_API_KEY not configured).")
        print(f"  Mock provider is functional for deterministic testing.")
    
    print(f"\n{'='*70}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
