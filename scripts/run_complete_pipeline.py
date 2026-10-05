#!/usr/bin/env python
"""
Complete end-to-end pipeline: Stage 1 → Stage 2 (canonical labels) → Stage 3 → Stage 4

This script:
1. Loads raw alerts from Excel
2. Runs Stage 1 standardization
3. Integrates canonical labels into Stage 2
4. Runs Stage 3 correlation
5. Runs Stage 4 RCA
6. Saves all final artifacts
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import json
from datetime import datetime
from typing import List, Dict

from alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
from alert_management.stage1_ingestion.pipeline import Stage1Pipeline
from alert_management.stage1_ingestion.schemas import StandardizedAlert
from alert_management.stage2_classification.schemas import EnrichedAlert, ClassificationResult
from alert_management.stage3_correlation.pipeline import CorrelationPipeline
from alert_management.stage4_analysis.pipeline import Stage4Pipeline
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider
from alert_management.stage4_analysis.reasoning.mock_reasoning_provider import MockReasoningProvider


print("="*80)
print("COMPLETE PIPELINE: CANONICAL LABELS → STAGE 1-4")
print("="*80)

# =======================
# STEP 1: Stage 1 Ingestion
# =======================
print("\n[STEP 1] Running Stage 1 ingestion...")
print("-" * 80)

adapter = ExcelAlertAdapter()
normalizer = Normalizer.get_default()
pipeline = Stage1Pipeline(adapter=adapter, normalizer=normalizer)

raw_file = "data/raw/Data_Alert_Ticket_Segregation.xlsx"
stage1_alerts = pipeline.ingest(raw_file)

print(f"✓ Stage 1 complete: {len(stage1_alerts)} alerts standardized")

# Save Stage 1 output
output_dir = Path("data/processed")
output_dir.mkdir(exist_ok=True, parents=True)

stage1_data = {
    'metadata': {
        'total_alerts': len(stage1_alerts),
        'generation_timestamp': datetime.utcnow().isoformat(),
        'source_file': raw_file
    },
    'alerts': [
        {
            'alert_id': alert.alert_id,
            'created_at': alert.created_at.isoformat(),
            'client': alert.client,
            'raw_description': alert.raw_description,
            'normalized_description': alert.normalized_description,
            'metadata': alert.metadata
        }
        for alert in stage1_alerts
    ]
}

with open(output_dir / "stage1_standardized_alerts.json", "w") as f:
    json.dump(stage1_data, f, indent=2)

print(f"  Saved: {output_dir}/stage1_standardized_alerts.json")

# =======================
# STEP 2: Load Canonical Labels
# =======================
print("\n[STEP 2] Loading canonical Stage 2 labels...")
print("-" * 80)

canonical_df = pd.read_excel(
    "data/labels/Stage2_WeakLabels_v4_Model_Challenge.xlsx",
    sheet_name="Label_889_Challenge"
)

print(f"✓ Loaded {len(canonical_df)} canonical labels")
print(f"  Alert Types: {canonical_df['Canonical Alert Type'].nunique()} unique")
print(f"  Business Impact: {canonical_df['Canonical Business Impact'].value_counts().to_dict()}")
print(f"  Severity: {canonical_df['Canonical Severity'].value_counts().to_dict()}")

# =======================
# STEP 3: Create EnrichedAlerts with Canonical Labels
# =======================
print("\n[STEP 3] Creating EnrichedAlerts with canonical labels...")
print("-" * 80)

canonical_lookup = {}
for _, row in canonical_df.iterrows():
    canonical_lookup[row['Alert ID']] = {
        'alert_type': row['Canonical Alert Type'],
        'business_impact': row['Canonical Business Impact'],
        'severity': row['Canonical Severity']
    }

enriched_alerts = []
missing_count = 0

for alert in stage1_alerts:
    canonical = canonical_lookup.get(alert.alert_id)
    
    if canonical is None:
        print(f"  WARNING: No canonical labels for {alert.alert_id}")
        missing_count += 1
        continue
    
    # Map canonical severity to standard format
    severity_map = {
        'Sev1 - Critical': 'Sev1',
        'Sev2 - High': 'Sev2',
        'Sev3 - Medium': 'Sev3',
        'Sev4 - Low': 'Sev4'
    }
    severity = severity_map.get(canonical['severity'], canonical['severity'])
    
    enriched = EnrichedAlert(
        alert_id=alert.alert_id,
        created_at=alert.created_at,
        client=alert.client,
        raw_description=alert.raw_description,
        normalized_description=alert.normalized_description,
        metadata=alert.metadata,
        
        # Canonical labels (confidence=1.0 means "source of truth")
        alert_type=ClassificationResult(
            label=canonical['alert_type'],
            confidence=1.0,
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
            label=severity,
            confidence=1.0,
            provider="canonical",
            model="human_analyst_rules_v4"
        ),
        
        # Priority and Routing: placeholder (no canonical labels available)
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

print(f"✓ Created {len(enriched_alerts)} EnrichedAlerts")
if missing_count > 0:
    print(f"  WARNING: {missing_count} alerts without canonical labels")

# =======================
# STEP 4: Stage 3 Correlation
# =======================
print("\n[STEP 4] Running Stage 3 correlation...")
print("-" * 80)

correlation_pipeline = CorrelationPipeline(
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

incident_groups, uncorrelated = correlation_pipeline.correlate_alerts(
    stage1_alerts,
    use_graph_grouping=True
)

print(f"\n✓ Stage 3 complete:")
print(f"  Candidate incidents: {len(incident_groups)}")
print(f"  Correlated alerts: {sum(inc.alert_count for inc in incident_groups)}")
print(f"  Uncorrelated alerts: {len(uncorrelated)}")
print(f"  Grouping rate: {sum(inc.alert_count for inc in incident_groups) / len(stage1_alerts) * 100:.1f}%")

# =======================
# STEP 5: Stage 4 RCA
# =======================
print("\n[STEP 5] Running Stage 4 RCA...")
print("-" * 80)

rca_pipeline = Stage4Pipeline(
    log_provider=MockLogProvider(),
    metric_provider=MockMetricProvider(),
    trace_provider=MockTraceProvider(),
    reasoning_provider=MockReasoningProvider()
)

rca_results = []

for i, incident in enumerate(incident_groups, 1):
    if i <= 10 or i % 25 == 0:
        print(f"  Processing incident {i}/{len(incident_groups)}: {incident.incident_id} ({incident.alert_count} alerts)")
    
    try:
        rca_result, support_msg, stakeholder_msg = rca_pipeline.analyze_incident(
            incident,
            enriched_alerts
        )
        rca_results.append(rca_result)
    except Exception as e:
        print(f"    ERROR: {e}")
        continue

print(f"\n✓ Stage 4 complete:")
print(f"  RCA analyses: {len(rca_results)}")

# Summarize diagnosis status
status_counts = {}
for rca in rca_results:
    status = rca.diagnosis_status.value
    status_counts[status] = status_counts.get(status, 0) + 1

print(f"  Diagnosis status distribution:")
for status, count in sorted(status_counts.items()):
    print(f"    {status}: {count}")

# =======================
# STEP 6: Save Final Artifacts
# =======================
print("\n[STEP 6] Saving final artifacts...")
print("-" * 80)

final_output_dir = Path("data/final_outputs")
final_output_dir.mkdir(exist_ok=True, parents=True)

# Stage 2 artifacts
stage2_json = {
    'metadata': {
        'total_alerts': len(enriched_alerts),
        'generation_timestamp': datetime.utcnow().isoformat(),
        'label_source': 'canonical_labels_v4',
        'note': 'Alert Type, Business Impact, and Severity are canonical labels (ground truth)'
    },
    'alerts': [
        {
            'alert_id': alert.alert_id,
            'created_at': alert.created_at.isoformat(),
            'client': alert.client,
            'alert_type': alert.alert_type.label,
            'business_impact': alert.business_impact.label,
            'severity': alert.severity.label
        }
        for alert in enriched_alerts
    ]
}

with open(final_output_dir / "stage2_canonical_labels.json", "w") as f:
    json.dump(stage2_json, f, indent=2)

pd.DataFrame(stage2_json['alerts']).to_csv(
    final_output_dir / "stage2_canonical_labels.csv", index=False
)

print(f"  ✓ Stage 2: {final_output_dir}/stage2_canonical_labels.json/.csv")

# Stage 3 artifacts
stage3_json = {
    'metadata': {
        'total_incidents': len(incident_groups),
        'total_alerts_grouped': sum(inc.alert_count for inc in incident_groups),
        'uncorrelated_alerts': len(uncorrelated),
        'grouping_rate_percent': sum(inc.alert_count for inc in incident_groups) / len(stage1_alerts) * 100,
        'generation_timestamp': datetime.utcnow().isoformat(),
        'note': 'Candidate incident groups - no ground truth incident labels available for validation'
    },
    'incidents': [
        {
            'incident_id': inc.incident_id,
            'alert_ids': inc.alert_ids,
            'alert_count': inc.alert_count,
            'client': inc.client,
            'incident_start': inc.incident_start.isoformat(),
            'incident_end': inc.incident_end.isoformat() if inc.incident_end else None,
            'correlation_method': inc.correlation_method,
            'avg_correlation_score': inc.avg_correlation_score
        }
        for inc in incident_groups
    ]
}

with open(final_output_dir / "stage3_candidate_incidents.json", "w") as f:
    json.dump(stage3_json, f, indent=2)

pd.DataFrame([
    {
        'incident_id': inc.incident_id,
        'client': inc.client,
        'alert_count': inc.alert_count,
        'correlation_method': inc.correlation_method
    }
    for inc in incident_groups
]).to_csv(final_output_dir / "stage3_candidate_incidents.csv", index=False)

print(f"  ✓ Stage 3: {final_output_dir}/stage3_candidate_incidents.json/.csv")

# Stage 4 artifacts
stage4_json = {
    'metadata': {
        'total_rca_analyses': len(rca_results),
        'generation_timestamp': datetime.utcnow().isoformat(),
        'rca_scope': 'historical_alert_text_only',
        'diagnosis_status_counts': status_counts,
        'note': 'RCA based on mock telemetry. No real logs, metrics, or traces available.'
    },
    'rca_analyses': [
        {
            'incident_id': rca.incident_id,
            'client': rca.client,
            'alert_count': rca.alert_count,
            'diagnosis_status': rca.diagnosis_status.value,
            'probable_root_cause': {
                'component': rca.probable_root_cause.component if rca.probable_root_cause else None,
                'failure_type': rca.probable_root_cause.failure_type if rca.probable_root_cause else None
            } if rca.probable_root_cause else None
        }
        for rca in rca_results
    ]
}

with open(final_output_dir / "stage4_rca_results.json", "w") as f:
    json.dump(stage4_json, f, indent=2)

print(f"  ✓ Stage 4: {final_output_dir}/stage4_rca_results.json")

# =======================
# STEP 7: Pizza Hut 97-Alert Analysis
# =======================
print("\n[STEP 7] Analyzing Pizza Hut 97-alert family...")
print("-" * 80)

pizza_hut_extract_alerts = [
    alert for alert in enriched_alerts
    if alert.client == "Pizza Hut" 
    and "Extract / Report Delivery Delay" in alert.alert_type.label
]

print(f"  Total Pizza Hut 'Extract / Report Delivery Delay' alerts: {len(pizza_hut_extract_alerts)}")

# Find which incidents these are in
pizza_hut_incidents = []
for incident in incident_groups:
    alert_ids_in_incident = set(incident.alert_ids)
    matching_count = sum(1 for alert in pizza_hut_extract_alerts if alert.alert_id in alert_ids_in_incident)
    if matching_count > 0:
        pizza_hut_incidents.append({
            'incident_id': incident.incident_id,
            'pizza_hut_alerts': matching_count,
            'total_alerts': incident.alert_count,
            'method': incident.correlation_method
        })

print(f"  Pizza Hut alerts distributed across {len(pizza_hut_incidents)} incidents:")
for inc in sorted(pizza_hut_incidents, key=lambda x: x['pizza_hut_alerts'], reverse=True)[:10]:
    print(f"    {inc['incident_id']}: {inc['pizza_hut_alerts']} Pizza Hut (of {inc['total_alerts']} total) - {inc['method']}")

# Check if they all ended up in one incident (should NOT happen)
max_in_single_incident = max((inc['pizza_hut_alerts'] for inc in pizza_hut_incidents), default=0)
if max_in_single_incident > 50:
    print(f"  ⚠ WARNING: {max_in_single_incident} Pizza Hut alerts in a single incident!")
else:
    print(f"  ✓ CORRECT: Maximum {max_in_single_incident} Pizza Hut alerts in any single incident")
    print(f"  ✓ Pizza Hut alerts properly distributed (not all grouped together)")

# =======================
# FINAL SUMMARY
# =======================
print("\n" + "="*80)
print("PIPELINE EXECUTION COMPLETE")
print("="*80)
print(f"\nFinal Results:")
print(f"  Stage 1: {len(stage1_alerts)} alerts standardized")
print(f"  Stage 2: {len(enriched_alerts)} alerts with canonical labels")
print(f"  Stage 3: {len(incident_groups)} candidate incident groups")
print(f"  Stage 4: {len(rca_results)} RCA analyses")
print(f"\nArtifacts saved to: {final_output_dir}/")
print(f"  - stage2_canonical_labels.json/.csv")
print(f"  - stage3_candidate_incidents.json/.csv")
print(f"  - stage4_rca_results.json")
print("\n✓ Stage 5 NOT started (as required)")
print("="*80)
