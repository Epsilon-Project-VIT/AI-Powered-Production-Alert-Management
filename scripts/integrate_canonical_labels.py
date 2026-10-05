#!/usr/bin/env python
"""
Integrate finalized canonical Stage 2 labels and run complete pipeline.

Steps:
1. Load canonical labels from Stage2_WeakLabels_v4_Model_Challenge.xlsx
2. Create EnrichedAlerts with canonical labels
3. Run Stage 3 correlation
4. Run Stage 4 RCA
5. Generate final artifacts
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import json
from datetime import datetime
from typing import List, Dict

from alert_management.stage1_ingestion.schemas import StandardizedAlert
from alert_management.stage2_classification.schemas import EnrichedAlert, ClassificationResult
from alert_management.stage3_correlation.pipeline import CorrelationPipeline
from alert_management.stage4_analysis.pipeline import Stage4Pipeline
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider
from alert_management.stage4_analysis.reasoning.mock_reasoning_provider import MockReasoningProvider


def load_canonical_labels() -> pd.DataFrame:
    """Load canonical labels from Excel file."""
    print("[Step 1] Loading canonical labels...")
    df = pd.read_excel(
        "data/labels/Stage2_WeakLabels_v4_Model_Challenge.xlsx",
        sheet_name="Label_889_Challenge"
    )
    print(f"  Loaded {len(df)} alerts with canonical labels")
    print(f"  Canonical Alert Types: {df['Canonical Alert Type'].nunique()}")
    print(f"  Canonical Business Impact: {df['Canonical Business Impact'].nunique()}")
    print(f"  Canonical Severity: {df['Canonical Severity'].nunique()}")
    return df


def load_stage1_alerts() -> List[StandardizedAlert]:
    """Load Stage 1 standardized alerts."""
    print("\n[Step 2] Loading Stage 1 alerts...")
    with open("data/processed/stage1_standardized_alerts.json", "r") as f:
        data = json.load(f)
    
    alerts = []
    for item in data['alerts']:
        alert = StandardizedAlert(
            alert_id=item['alert_id'],
            created_at=datetime.fromisoformat(item['created_at'].replace('Z', '+00:00')),
            client=item['client'],
            raw_description=item['raw_description'],
            normalized_description=item['normalized_description'],
            metadata=item.get('metadata', {})
        )
        alerts.append(alert)
    
    print(f"  Loaded {len(alerts)} standardized alerts")
    return alerts


def create_enriched_alerts_with_canonical_labels(
    stage1_alerts: List[StandardizedAlert],
    canonical_df: pd.DataFrame
) -> List[EnrichedAlert]:
    """
    Create EnrichedAlerts using canonical labels.
    
    IMPORTANT: Uses canonical labels as ground truth, NOT as model predictions.
    These are the "source of truth" labels for model training/evaluation.
    """
    print("\n[Step 3] Creating EnrichedAlerts with canonical labels...")
    
    # Create lookup dict
    canonical_lookup = {}
    for _, row in canonical_df.iterrows():
        canonical_lookup[row['Alert ID']] = {
            'alert_type': row['Canonical Alert Type'],
            'business_impact': row['Canonical Business Impact'],
            'severity': row['Canonical Severity'],
            # ML predictions (for comparison)
            'ml_alert_type': row['ML Alert Type'],
            'ml_business_impact': row['ML Business Impact'],
            'ml_severity': row['ML Severity']
        }
    
    enriched_alerts = []
    missing_count = 0
    
    for alert in stage1_alerts:
        canonical = canonical_lookup.get(alert.alert_id)
        
        if canonical is None:
            print(f"  WARNING: No canonical labels for {alert.alert_id}")
            missing_count += 1
            continue
        
        # Create EnrichedAlert with canonical labels
        # Note: Priority and Routing remain as ML predictions (no canonical labels provided)
        enriched = EnrichedAlert(
            alert_id=alert.alert_id,
            created_at=alert.created_at,
            client=alert.client,
            raw_description=alert.raw_description,
            normalized_description=alert.normalized_description,
            metadata=alert.metadata,
            
            # Canonical labels (source of truth)
            alert_type=ClassificationResult(
                label=canonical['alert_type'],
                confidence=1.0,  # Canonical = 100% confidence
                provider="canonical",
                model="human_analyst_rules_v4"
            ),
            business_impact=ClassificationResult(
                label=canonical['business_impact'],
                confidence=1.0,
                provider="canonical",
                model="human_analyst_rules_v4"
            ),
            severity=ClassificationResult(
                label=canonical['severity'],
                confidence=1.0,
                provider="canonical",
                model="human_analyst_rules_v4"
            ),
            
            # Priority and Routing: use defaults (no canonical labels available)
            # These would normally come from trained models
            priority=ClassificationResult(
                label="UNKNOWN",
                confidence=0.0,
                provider="none",
                model="none"
            ),
            routing=ClassificationResult(
                label="UNKNOWN",
                confidence=0.0,
                provider="none",
                model="none"
            )
        )
        
        enriched_alerts.append(enriched)
    
    print(f"  Created {len(enriched_alerts)} EnrichedAlerts with canonical labels")
    if missing_count > 0:
        print(f"  WARNING: {missing_count} alerts without canonical labels")
    
    return enriched_alerts


def run_stage3_correlation(
    stage1_alerts: List[StandardizedAlert],
    enriched_alerts: List[EnrichedAlert]
) -> tuple:
    """Run Stage 3 correlation pipeline."""
    print("\n[Step 4] Running Stage 3 correlation...")
    print("-" * 70)
    
    pipeline = CorrelationPipeline(
        max_time_gap_hours=24.0,
        min_correlation_score=0.7,
        correlation_weights={
            'semantic': 0.30,
            'temporal': 0.20,
            'client': 0.15,
            'family': 0.10,
            'service': 0.15,
            'stage2': 0.10
        }
    )
    
    incident_groups, uncorrelated = pipeline.correlate_alerts(
        stage1_alerts,
        use_graph_grouping=True
    )
    
    print(f"\n[Stage 3] Results:")
    print(f"  Candidate incidents: {len(incident_groups)}")
    print(f"  Correlated alerts: {sum(inc.alert_count for inc in incident_groups)}")
    print(f"  Uncorrelated alerts: {len(uncorrelated)}")
    print(f"  Grouping rate: {sum(inc.alert_count for inc in incident_groups) / len(stage1_alerts) * 100:.1f}%")
    
    return incident_groups, uncorrelated


def run_stage4_rca(
    incident_groups: List,
    enriched_alerts: List[EnrichedAlert]
) -> List:
    """Run Stage 4 RCA pipeline."""
    print("\n[Step 5] Running Stage 4 RCA...")
    print("-" * 70)
    
    # Initialize with mock providers
    pipeline = Stage4Pipeline(
        log_provider=MockLogProvider(),
        metric_provider=MockMetricProvider(),
        trace_provider=MockTraceProvider(),
        reasoning_provider=MockReasoningProvider()
    )
    
    rca_results = []
    
    for i, incident in enumerate(incident_groups, 1):
        if i <= 5 or i % 50 == 0:
            print(f"  Processing incident {i}/{len(incident_groups)}: {incident.incident_id}")
        
        try:
            rca_result, support_msg, stakeholder_msg = pipeline.analyze_incident(
                incident,
                enriched_alerts
            )
            rca_results.append(rca_result)
        except Exception as e:
            print(f"    ERROR processing {incident.incident_id}: {e}")
            continue
    
    print(f"\n[Stage 4] Results:")
    print(f"  RCA analyses completed: {len(rca_results)}")
    
    # Summarize diagnosis status
    status_counts = {}
    for rca in rca_results:
        status = rca.diagnosis_status.value
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"  Diagnosis status:")
    for status, count in sorted(status_counts.items()):
        print(f"    {status}: {count}")
    
    return rca_results


def save_stage2_results(enriched_alerts: List[EnrichedAlert]):
    """Save Stage 2 results with canonical labels."""
    print("\n[Step 6] Saving Stage 2 results...")
    
    output_dir = Path("data/final_outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Save as JSON
    stage2_data = {
        'metadata': {
            'total_alerts': len(enriched_alerts),
            'generation_timestamp': datetime.utcnow().isoformat(),
            'label_source': 'canonical_labels_v4',
            'label_file': 'Stage2_WeakLabels_v4_Model_Challenge.xlsx',
            'note': 'Alert Type, Business Impact, and Severity are canonical labels (source of truth). Priority and Routing are placeholder values.'
        },
        'alerts': []
    }
    
    for alert in enriched_alerts:
        stage2_data['alerts'].append({
            'alert_id': alert.alert_id,
            'created_at': alert.created_at.isoformat(),
            'client': alert.client,
            'normalized_description': alert.normalized_description,
            'alert_type': alert.alert_type.label,
            'alert_type_confidence': alert.alert_type.confidence,
            'business_impact': alert.business_impact.label,
            'business_impact_confidence': alert.business_impact.confidence,
            'severity': alert.severity.label,
            'severity_confidence': alert.severity.confidence,
            'priority': alert.priority.label,
            'priority_confidence': alert.priority.confidence,
            'routing': alert.routing.label,
            'routing_confidence': alert.routing.confidence
        })
    
    with open(output_dir / "stage2_canonical_labels.json", "w") as f:
        json.dump(stage2_data, f, indent=2)
    
    # Save as CSV for easy viewing
    df = pd.DataFrame([
        {
            'alert_id': alert.alert_id,
            'created_at': alert.created_at.isoformat(),
            'client': alert.client,
            'alert_type': alert.alert_type.label,
            'business_impact': alert.business_impact.label,
            'severity': alert.severity.label,
            'alert_type_confidence': alert.alert_type.confidence,
            'business_impact_confidence': alert.business_impact.confidence,
            'severity_confidence': alert.severity.confidence
        }
        for alert in enriched_alerts
    ])
    df.to_csv(output_dir / "stage2_canonical_labels.csv", index=False)
    
    print(f"  Saved to: {output_dir}/stage2_canonical_labels.json")
    print(f"  Saved to: {output_dir}/stage2_canonical_labels.csv")


def save_stage3_results(incident_groups: List, uncorrelated: List):
    """Save Stage 3 correlation results."""
    print("\n[Step 7] Saving Stage 3 results...")
    
    output_dir = Path("data/final_outputs")
    
    # Save as JSON
    stage3_data = {
        'metadata': {
            'total_incidents': len(incident_groups),
            'total_alerts': sum(inc.alert_count for inc in incident_groups),
            'uncorrelated_alerts': len(uncorrelated),
            'generation_timestamp': datetime.utcnow().isoformat(),
            'correlation_method': 'graph_connected_components',
            'note': 'Candidate incident groups using exact matching, semantic clustering, and service validation'
        },
        'incidents': []
    }
    
    for incident in incident_groups:
        stage3_data['incidents'].append({
            'incident_id': incident.incident_id,
            'alert_ids': incident.alert_ids,
            'alert_count': incident.alert_count,
            'client': incident.client,
            'incident_start': incident.incident_start.isoformat(),
            'incident_end': incident.incident_end.isoformat() if incident.incident_end else None,
            'correlation_method': incident.correlation_method,
            'avg_correlation_score': incident.avg_correlation_score
        })
    
    with open(output_dir / "stage3_candidate_incidents.json", "w") as f:
        json.dump(stage3_data, f, indent=2)
    
    # Save summary CSV
    df = pd.DataFrame([
        {
            'incident_id': inc.incident_id,
            'client': inc.client,
            'alert_count': inc.alert_count,
            'incident_start': inc.incident_start.isoformat(),
            'correlation_method': inc.correlation_method,
            'avg_correlation_score': inc.avg_correlation_score
        }
        for inc in incident_groups
    ])
    df.to_csv(output_dir / "stage3_candidate_incidents.csv", index=False)
    
    print(f"  Saved to: {output_dir}/stage3_candidate_incidents.json")
    print(f"  Saved to: {output_dir}/stage3_candidate_incidents.csv")


def save_stage4_results(rca_results: List):
    """Save Stage 4 RCA results."""
    print("\n[Step 8] Saving Stage 4 results...")
    
    output_dir = Path("data/final_outputs")
    
    # Save as JSON
    stage4_data = {
        'metadata': {
            'total_rca_analyses': len(rca_results),
            'generation_timestamp': datetime.utcnow().isoformat(),
            'rca_scope': 'historical_alert_text_only',
            'note': 'RCA based on mock telemetry and historical alert descriptions. No real logs, metrics, or traces available.'
        },
        'rca_analyses': []
    }
    
    for rca in rca_results:
        stage4_data['rca_analyses'].append({
            'incident_id': rca.incident_id,
            'client': rca.client,
            'alert_count': rca.alert_count,
            'diagnosis_status': rca.diagnosis_status.value,
            'probable_root_cause': {
                'component': rca.probable_root_cause.component if rca.probable_root_cause else None,
                'failure_type': rca.probable_root_cause.failure_type if rca.probable_root_cause else None,
                'confidence': rca.probable_root_cause.confidence if rca.probable_root_cause else None,
                'description': rca.probable_root_cause.description if rca.probable_root_cause else None
            } if rca.probable_root_cause else None,
            'evidence_count': len(rca.evidence),
            'alternative_hypotheses_count': len(rca.alternative_hypotheses),
            'recommended_actions_count': len(rca.recommended_actions)
        })
    
    with open(output_dir / "stage4_rca_results.json", "w") as f:
        json.dump(stage4_data, f, indent=2)
    
    # Save summary CSV
    df = pd.DataFrame([
        {
            'incident_id': rca.incident_id,
            'client': rca.client,
            'alert_count': rca.alert_count,
            'diagnosis_status': rca.diagnosis_status.value,
            'component': rca.probable_root_cause.component if rca.probable_root_cause else 'N/A',
            'failure_type': rca.probable_root_cause.failure_type if rca.probable_root_cause else 'N/A',
            'confidence': rca.probable_root_cause.confidence if rca.probable_root_cause else 0.0,
            'evidence_count': len(rca.evidence)
        }
        for rca in rca_results
    ])
    df.to_csv(output_dir / "stage4_rca_results.csv", index=False)
    
    print(f"  Saved to: {output_dir}/stage4_rca_results.json")
    print(f"  Saved to: {output_dir}/stage4_rca_results.csv")


def analyze_pizza_hut_97_alerts(
    enriched_alerts: List[EnrichedAlert],
    incident_groups: List
):
    """Analyze the Pizza Hut 97-alert family."""
    print("\n[Pizza Hut Analysis] Analyzing 97-alert family...")
    
    # Find Pizza Hut Extract/Report Delivery Delay alerts
    pizza_hut_extract_alerts = [
        alert for alert in enriched_alerts
        if alert.client == "Pizza Hut" 
        and "Extract / Report Delivery Delay" in alert.alert_type.label
    ]
    
    print(f"  Total Pizza Hut Extract/Report Delivery Delay alerts: {len(pizza_hut_extract_alerts)}")
    
    # Find which incidents these are in
    pizza_hut_incidents = []
    for incident in incident_groups:
        alert_ids_in_incident = set(incident.alert_ids)
        matching_alerts = [
            alert for alert in pizza_hut_extract_alerts
            if alert.alert_id in alert_ids_in_incident
        ]
        if matching_alerts:
            pizza_hut_incidents.append({
                'incident_id': incident.incident_id,
                'alert_count': len(matching_alerts),
                'total_alerts': incident.alert_count,
                'method': incident.correlation_method
            })
    
    print(f"  Pizza Hut alerts grouped into {len(pizza_hut_incidents)} incidents")
    for inc in sorted(pizza_hut_incidents, key=lambda x: x['alert_count'], reverse=True)[:5]:
        print(f"    {inc['incident_id']}: {inc['alert_count']} Pizza Hut alerts (of {inc['total_alerts']} total)")
    
    # Check if all 97 ended up in one incident (should NOT happen)
    if any(inc['alert_count'] > 90 for inc in pizza_hut_incidents):
        print(f"  ⚠ WARNING: Found a single incident with >90 Pizza Hut alerts - likely incorrect grouping!")
    else:
        print(f"  ✓ Pizza Hut alerts properly distributed across multiple incidents")


def main():
    """Main execution."""
    print("="*70)
    print("CANONICAL LABEL INTEGRATION - STAGE 2 → 3 → 4 PIPELINE")
    print("="*70)
    
    # Load data
    canonical_df = load_canonical_labels()
    stage1_alerts = load_stage1_alerts()
    
    # Create enriched alerts with canonical labels
    enriched_alerts = create_enriched_alerts_with_canonical_labels(
        stage1_alerts,
        canonical_df
    )
    
    # Run Stage 3 correlation
    incident_groups, uncorrelated = run_stage3_correlation(
        stage1_alerts,
        enriched_alerts
    )
    
    # Run Stage 4 RCA
    rca_results = run_stage4_rca(incident_groups, enriched_alerts)
    
    # Save all results
    save_stage2_results(enriched_alerts)
    save_stage3_results(incident_groups, uncorrelated)
    save_stage4_results(rca_results)
    
    # Pizza Hut analysis
    analyze_pizza_hut_97_alerts(enriched_alerts, incident_groups)
    
    print("\n" + "="*70)
    print("PIPELINE COMPLETE")
    print("="*70)
    print(f"Final artifacts saved to: data/final_outputs/")
    print(f"  - stage2_canonical_labels.json/csv")
    print(f"  - stage3_candidate_incidents.json/csv")
    print(f"  - stage4_rca_results.json/csv")


if __name__ == "__main__":
    main()
