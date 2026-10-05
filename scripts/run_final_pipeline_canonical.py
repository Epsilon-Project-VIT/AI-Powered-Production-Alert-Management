#!/usr/bin/env python
"""
Complete pipeline with canonical labels integration.

Runs Stage 1 → Stage 2 (canonical) → Stage 3 → Stage 4
"""
import json
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alert_management.config.settings import Settings
from alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from alert_management.stage1_ingestion.cleaners.field_cleaner import FieldCleaner
from alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
from alert_management.stage1_ingestion.pipeline import Stage1Pipeline
from alert_management.stage1_ingestion.validators.alert_validator import AlertValidator
from alert_management.stage2_classification.schemas import EnrichedAlert, ClassificationResult
from alert_management.stage3_correlation.pipeline import CorrelationPipeline
from alert_management.stage4_analysis.pipeline import Stage4Pipeline
from alert_management.stage4_analysis.reasoning.mock_reasoning_provider import MockReasoningProvider
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider


print("="*80)
print("CANONICAL LABELS PIPELINE: STAGE 1 → 2 → 3 → 4")
print("="*80)

# ============================================================================
# STAGE 1: Ingestion
# ============================================================================
print("\n[STAGE 1] Ingesting alerts...")
print("-"*80)

stage1 = Stage1Pipeline(
    FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS),
    Normalizer(patterns=Settings.NORMALIZATION_PATTERNS),
    AlertValidator(required_fields=Settings.REQUIRED_FIELDS),
)

alerts = stage1.run(ExcelAlertAdapter(
    PROJECT_ROOT / "data" / "raw" / "Data_Alert_Ticket_Segregation.xlsx",
    Settings.EXCEL_COLUMN_MAPPING,
    forbidden_metadata_fields=set(Settings.FORBIDDEN_METADATA_FIELDS),
))

print(f"✓ Standardized {len(alerts)} alerts")

# ============================================================================
# STAGE 2: Load Canonical Labels
# ============================================================================
print("\n[STAGE 2] Loading canonical labels...")
print("-"*80)

canonical_df = pd.read_excel(
    "data/labels/Stage2_WeakLabels_v4_Model_Challenge.xlsx",
    sheet_name="Label_889_Challenge"
)

print(f"✓ Loaded {len(canonical_df)} canonical labels")
print(f"  Alert Types: {canonical_df['Canonical Alert Type'].nunique()}")
print(f"  Business Impact distribution:")
for label, count in canonical_df['Canonical Business Impact'].value_counts().items():
    print(f"    {label}: {count}")
print(f"  Severity distribution:")
for label, count in canonical_df['Canonical Severity'].value_counts().items():
    print(f"    {label}: {count}")

# Create lookup
canonical_lookup = {}
for _, row in canonical_df.iterrows():
    # Map severity to short form
    severity_map = {
        'Sev1 - Critical': 'Sev1',
        'Sev2 - High': 'Sev2',
        'Sev3 - Medium': 'Sev3',
        'Sev4 - Low': 'Sev4'
    }
    canonical_lookup[row['Alert ID']] = {
        'alert_type': row['Canonical Alert Type'],
        'business_impact': row['Canonical Business Impact'],
        'severity': severity_map.get(row['Canonical Severity'], row['Canonical Severity'])
    }

# Create EnrichedAlerts with canonical labels
enriched_alerts = []
missing_count = 0

for alert in alerts:
    canonical = canonical_lookup.get(alert.alert_id)
    
    if canonical is None:
        print(f"  WARNING: No canonical labels for {alert.alert_id}")
        missing_count += 1
        continue
    
    enriched = EnrichedAlert(
        alert_id=alert.alert_id,
        created_at=alert.created_at,
        client=alert.client,
        raw_description=alert.raw_description,
        normalized_description=alert.normalized_description,
        metadata=alert.metadata,
        
        # Canonical labels (confidence=1.0 = source of truth)
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
            label=canonical['severity'],
            confidence=1.0,
            provider="canonical",
            model="human_analyst_rules_v4"
        ),
        
        # Priority and Routing: placeholders (no canonical labels)
        priority=ClassificationResult(
            label="UNKNOWN",
            confidence=0.0,
            provider="none"
        ),
        routing=ClassificationResult(
            label="UNKNOWN",
            confidence=0.0,
            provider="none"
        )
    )
    
    enriched_alerts.append(enriched)

print(f"✓ Created {len(enriched_alerts)} EnrichedAlerts with canonical labels")

# ============================================================================
# STAGE 3: Correlation
# ============================================================================
print("\n[STAGE 3] Running correlation pipeline...")
print("-"*80)

correlation = CorrelationPipeline(
    max_time_gap_hours=24.0,
    min_correlation_score=0.7,
)

incident_groups, uncorrelated = correlation.correlate_alerts(alerts, use_graph_grouping=True)

print(f"\n✓ Stage 3 complete:")
print(f"  Candidate incidents: {len(incident_groups)}")
print(f"  Correlated alerts: {sum(inc.alert_count for inc in incident_groups)}")
print(f"  Uncorrelated alerts: {len(uncorrelated)}")
grouping_rate = sum(inc.alert_count for inc in incident_groups) / len(alerts) * 100
print(f"  Grouping rate: {grouping_rate:.1f}%")

# ============================================================================
# STAGE 4: RCA
# ============================================================================
print("\n[STAGE 4] Running RCA pipeline...")
print("-"*80)

stage4 = Stage4Pipeline(
    log_provider=MockLogProvider(seed=42),
    metric_provider=MockMetricProvider(seed=42),
    trace_provider=MockTraceProvider(seed=42),
    reasoning_provider=MockReasoningProvider(),
)

rca_results = []
for i, incident in enumerate(incident_groups, 1):
    if i <= 10 or i % 25 == 0:
        print(f"  Processing {i}/{len(incident_groups)}: {incident.incident_id} ({incident.alert_count} alerts)")
    
    try:
        rca, support_msg, stakeholder_msg = stage4.analyze_incident(incident, enriched_alerts)
        rca_results.append(rca)
    except Exception as e:
        print(f"    ERROR: {e}")

print(f"\n✓ Stage 4 complete: {len(rca_results)} RCA analyses")

# Status distribution
status_counts = {}
for rca in rca_results:
    status = rca.diagnosis_status.value
    status_counts[status] = status_counts.get(status, 0) + 1

print(f"  Diagnosis status:")
for status, count in sorted(status_counts.items()):
    print(f"    {status}: {count}")

# ============================================================================
# SAVE ARTIFACTS
# ============================================================================
print("\n[SAVING] Generating final artifacts...")
print("-"*80)

output_dir = Path("data/final_outputs")
output_dir.mkdir(exist_ok=True, parents=True)

# Stage 2
stage2_json = {
    'metadata': {
        'total_alerts': len(enriched_alerts),
        'timestamp': datetime.utcnow().isoformat(),
        'label_source': 'canonical_v4',
        'note': 'Canonical Alert Type, Business Impact, Severity from human analyst rules'
    },
    'alerts': [
        {
            'alert_id': a.alert_id,
            'created_at': a.created_at.isoformat(),
            'client': a.client,
            'alert_type': a.alert_type.label,
            'business_impact': a.business_impact.label,
            'severity': a.severity.label
        }
        for a in enriched_alerts
    ]
}

with open(output_dir / "stage2_canonical_labels.json", "w") as f:
    json.dump(stage2_json, f, indent=2)

pd.DataFrame(stage2_json['alerts']).to_csv(
    output_dir / "stage2_canonical_labels.csv", index=False
)

print(f"  ✓ stage2_canonical_labels.json/.csv")

# Stage 3
stage3_json = {
    'metadata': {
        'total_incidents': len(incident_groups),
        'correlated_alerts': sum(inc.alert_count for inc in incident_groups),
        'uncorrelated_alerts': len(uncorrelated),
        'grouping_rate_percent': grouping_rate,
        'timestamp': datetime.utcnow().isoformat(),
        'note': 'Candidate incident groups (no ground truth incident labels for validation)'
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

with open(output_dir / "stage3_candidate_incidents.json", "w") as f:
    json.dump(stage3_json, f, indent=2)

pd.DataFrame([
    {
        'incident_id': inc.incident_id,
        'client': inc.client,
        'alert_count': inc.alert_count,
        'method': inc.correlation_method
    }
    for inc in incident_groups
]).to_csv(output_dir / "stage3_candidate_incidents.csv", index=False)

print(f"  ✓ stage3_candidate_incidents.json/.csv")

# Stage 4
stage4_json = {
    'metadata': {
        'total_analyses': len(rca_results),
        'diagnosis_status_counts': status_counts,
        'timestamp': datetime.utcnow().isoformat(),
        'rca_scope': 'historical_alert_text_only',
        'note': 'Mock telemetry RCA - no real logs/metrics/traces available'
    },
    'analyses': [
        {
            'incident_id': rca.incident_id,
            'diagnosis_status': rca.diagnosis_status.value,
            'probable_root_cause': {
                'component': rca.probable_root_cause.component if rca.probable_root_cause else None,
                'failure_type': rca.probable_root_cause.failure_type if rca.probable_root_cause else None
            } if rca.probable_root_cause else None,
            'evidence_count': len(rca.evidence),
            'recommended_actions_count': len(rca.recommended_actions)
        }
        for rca in rca_results
    ]
}

with open(output_dir / "stage4_rca_results.json", "w") as f:
    json.dump(stage4_json, f, indent=2)

print(f"  ✓ stage4_rca_results.json")

# ============================================================================
# PIZZA HUT 97-ALERT ANALYSIS
# ============================================================================
print("\n[ANALYSIS] Pizza Hut 97-alert family...")
print("-"*80)

pizza_hut_extract = [
    a for a in enriched_alerts
    if a.client == "Pizza Hut" and "Extract / Report Delivery Delay" in a.alert_type.label
]

print(f"  Total Pizza Hut Extract/Report Delivery Delay: {len(pizza_hut_extract)}")

# Find which incidents they're in
ph_incidents = []
for inc in incident_groups:
    alert_ids_set = set(inc.alert_ids)
    ph_count = sum(1 for a in pizza_hut_extract if a.alert_id in alert_ids_set)
    if ph_count > 0:
        ph_incidents.append({
            'incident_id': inc.incident_id,
            'ph_alerts': ph_count,
            'total_alerts': inc.alert_count,
            'method': inc.correlation_method
        })

print(f"  Distributed across {len(ph_incidents)} incidents:")
for inc in sorted(ph_incidents, key=lambda x: x['ph_alerts'], reverse=True)[:10]:
    print(f"    {inc['incident_id']}: {inc['ph_alerts']} PH (of {inc['total_alerts']} total)")

max_ph = max((inc['ph_alerts'] for inc in ph_incidents), default=0)
if max_ph > 50:
    print(f"  ⚠ WARNING: {max_ph} Pizza Hut alerts in single incident!")
else:
    print(f"  ✓ CORRECT: Max {max_ph} PH alerts in any incident (properly distributed)")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "="*80)
print("PIPELINE COMPLETE")
print("="*80)
print(f"\nResults:")
print(f"  Stage 1: {len(alerts)} alerts")
print(f"  Stage 2: {len(enriched_alerts)} with canonical labels")
print(f"  Stage 3: {len(incident_groups)} candidate incidents ({grouping_rate:.1f}% grouped)")
print(f"  Stage 4: {len(rca_results)} RCA analyses")
print(f"\nArtifacts: {output_dir}/")
print(f"  - stage2_canonical_labels.json/.csv")
print(f"  - stage3_candidate_incidents.json/.csv")
print(f"  - stage4_rca_results.json")
print(f"\n✓ Stage 5 NOT started")
print("="*80)
