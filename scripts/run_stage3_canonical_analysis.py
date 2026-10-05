#!/usr/bin/env python3
"""
Run Stage 3 correlation analysis with Stage 2 canonical predictions.

Analyzes the full 889-alert dataset using the upgraded Stage 3 pipeline
that consumes Alert Type, Severity, and Business Impact from trained models.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
import pandas as pd
import numpy as np

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from alert_management.config.settings import Settings
from alert_management.stage1_ingestion.pipeline import Stage1Pipeline
from alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from alert_management.stage1_ingestion.cleaners.field_cleaner import FieldCleaner
from alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
from alert_management.stage1_ingestion.validators.alert_validator import AlertValidator
from alert_management.stage2_classification.pipeline import ClassificationPipeline
from alert_management.stage2_classification.models.tfidf_lr import TfidfLogisticClassifier
from alert_management.stage2_classification.schemas import EnrichedAlert, ClassificationResult
from alert_management.stage3_correlation.pipeline import CorrelationPipeline
from alert_management.stage3_correlation.clustering.signature_matcher import SignatureMatcher
from alert_management.stage3_correlation.clustering.semantic_clusterer import SemanticClusterer
from alert_management.stage3_correlation.validation.service_validator import ServiceValidator
from alert_management.stage3_correlation.validation.stage2_validator import Stage2CompatibilityValidator
from alert_management.stage3_correlation.grouping.graph_grouper import GraphGrouper


def load_canonical_predictions(data_dir: Path):
    """Load Stage 2 canonical model predictions."""
    canonical_dir = data_dir / "stage2_models_canonical"
    
    print("Loading canonical predictions...")
    alert_type_df = pd.read_csv(canonical_dir / "alert_type_predictions.csv")
    severity_df = pd.read_csv(canonical_dir / "severity_predictions.csv")
    business_impact_df = pd.read_csv(canonical_dir / "business_impact_predictions.csv")
    
    print(f"  Alert Type: {len(alert_type_df)} predictions")
    print(f"  Severity: {len(severity_df)} predictions")
    print(f"  Business Impact: {len(business_impact_df)} predictions")
    
    return {
        'alert_type': alert_type_df,
        'severity': severity_df,
        'business_impact': business_impact_df
    }


def enrich_with_canonical_predictions(standardized_alerts, canonical_preds_df, stage2_models):
    """Enrich alerts with Stage 2 canonical predictions from CSVs."""
    
    # The canonical predictions CSVs are in order (889 rows matching alerts)
    # We can use index-based matching
    enriched_alerts = []
    
    print(f"\nEnriching {len(standardized_alerts)} alerts with canonical predictions...")
    
    for idx, alert in enumerate(standardized_alerts):
        text = alert.normalized_description
        
        # Get canonical predictions from CSVs (same order as alerts)
        alert_type_label = canonical_preds_df['alert_type'].iloc[idx]['predicted_label']
        alert_type_conf = canonical_preds_df['alert_type'].iloc[idx]['confidence']
        
        severity_label = canonical_preds_df['severity'].iloc[idx]['predicted_label']
        severity_conf = canonical_preds_df['severity'].iloc[idx]['confidence']
        
        business_impact_label = canonical_preds_df['business_impact'].iloc[idx]['predicted_label']
        business_impact_conf = canonical_preds_df['business_impact'].iloc[idx]['confidence']
        
        # Priority and Routing (existing models - run on-the-fly)
        priority_preds = stage2_models['priority'].predict_with_confidence([text])
        priority_label, priority_conf = priority_preds[0]
        
        routing_preds = stage2_models['routing'].predict_with_confidence([text])
        routing_label, routing_conf = routing_preds[0]
        
        enriched = EnrichedAlert(
            alert_id=alert.alert_id,
            created_at=alert.created_at,
            client=alert.client,
            raw_description=alert.raw_description,
            normalized_description=alert.normalized_description,
            metadata=alert.metadata,
            alert_type=ClassificationResult(
                label=str(alert_type_label),
                confidence=float(alert_type_conf),
                provider="ml",
                model="tfidf_lr_alert_type"
            ),
            severity=ClassificationResult(
                label=str(severity_label),
                confidence=float(severity_conf),
                provider="ml",
                model="embedding_svm_severity"
            ),
            business_impact=ClassificationResult(
                label=str(business_impact_label),
                confidence=float(business_impact_conf),
                provider="ml",
                model="embedding_svm_business_impact"
            ),
            priority=ClassificationResult(
                label=str(priority_label),
                confidence=float(priority_conf),
                provider="ml",
                model="tfidf_lr_priority"
            ),
            routing=ClassificationResult(
                label=str(routing_label),
                confidence=float(routing_conf),
                provider="ml",
                model="tfidf_lr_routing"
            )
        )
        
        enriched_alerts.append(enriched)
    
    return enriched_alerts


def analyze_pizza_hut_family(incident_groups, standardized_alerts):
    """Analyze Pizza Hut recurring alert family."""
    print("\n" + "=" * 80)
    print("PIZZA HUT RECURRING ALERT ANALYSIS")
    print("=" * 80)
    
    # Exact 97-alert recurring family signature
    exact_signature = "critical autot icket pzht pizza hut pzht_watcher_alert alert p<priority>pzht_elb_errcheck <id> elb errors occurred"
    
    # Find alerts matching exact signature
    exact_matches = [a for a in standardized_alerts if a.normalized_description == exact_signature]
    
    print(f"\nExact 97-Alert Recurring Family:")
    print(f"  Signature: {exact_signature[:80]}...")
    print(f"  Total Alerts: {len(exact_matches)}")
    
    # Find which incident groups contain these alerts
    exact_alert_ids = {a.alert_id for a in exact_matches}
    groups_with_exact = []
    
    for incident in incident_groups:
        intersection = exact_alert_ids & set(incident.alert_ids)
        if intersection:
            groups_with_exact.append({
                'incident': incident,
                'count': len(intersection),
                'percentage': len(intersection) / len(exact_alert_ids) * 100
            })
    
    print(f"\nIncident Groups Containing Exact Family Alerts:")
    print(f"  Number of Groups: {len(groups_with_exact)}")
    
    if groups_with_exact:
        # Sort by count
        groups_with_exact.sort(key=lambda x: x['count'], reverse=True)
        
        print(f"\n  Largest Group:")
        largest = groups_with_exact[0]
        print(f"    Incident ID: {largest['incident'].incident_id}")
        print(f"    Contains: {largest['count']}/{len(exact_matches)} alerts ({largest['percentage']:.1f}%)")
        print(f"    Total Size: {largest['incident'].alert_count} alerts")
        print(f"    Method: {largest['incident'].correlation_method}")
        
        if len(groups_with_exact) > 1:
            print(f"\n  Fragmentation:")
            for i, group in enumerate(groups_with_exact[:5], 1):
                print(f"    Group {i}: {group['count']} alerts ({group['percentage']:.1f}%)")
    
    # Broader taxonomy match (109 alerts)
    # Alerts containing "pzht" and "elb" keywords
    broader_matches = [
        a for a in standardized_alerts
        if a.client == "Pizza Hut" and "pzht" in a.normalized_description.lower() and "elb" in a.normalized_description.lower()
    ]
    
    print(f"\n\nBroader 109-Alert Taxonomy Match (PZHT + ELB):")
    print(f"  Total Alerts: {len(broader_matches)}")
    
    broader_alert_ids = {a.alert_id for a in broader_matches}
    groups_with_broader = []
    
    for incident in incident_groups:
        intersection = broader_alert_ids & set(incident.alert_ids)
        if intersection:
            groups_with_broader.append({
                'incident': incident,
                'count': len(intersection),
                'percentage': len(intersection) / len(broader_alert_ids) * 100
            })
    
    print(f"\nIncident Groups Containing Broader Match:")
    print(f"  Number of Groups: {len(groups_with_broader)}")
    
    if groups_with_broader:
        groups_with_broader.sort(key=lambda x: x['count'], reverse=True)
        
        print(f"\n  Largest Group:")
        largest = groups_with_broader[0]
        print(f"    Incident ID: {largest['incident'].incident_id}")
        print(f"    Contains: {largest['count']}/{len(broader_matches)} alerts ({largest['percentage']:.1f}%)")
        print(f"    Total Size: {largest['incident'].alert_count} alerts")
        print(f"    Method: {largest['incident'].correlation_method}")


def main():
    """Run comprehensive Stage 3 analysis with canonical predictions."""
    
    print("\n" + "=" * 80)
    print("STAGE 3 CANONICAL CORRELATION ANALYSIS")
    print("=" * 80)
    print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Dataset: 889 alerts")
    print(f"Stage 2: Alert Type, Severity, Business Impact (canonical models)")
    
    # Configuration
    config = {
        'temporal_window_hours': 24.0,
        'min_correlation_score': 0.7,
        'correlation_weights': {
            'semantic': 0.30,
            'temporal': 0.20,
            'client': 0.15,
            'family': 0.10,
            'service': 0.15,
            'stage2': 0.10
        },
        'stage2_weights': {
            'alert_type_weight': 0.30,
            'severity_weight': 0.25,
            'business_impact_weight': 0.20,
            'priority_weight': 0.15,
            'routing_weight': 0.10
        }
    }
    
    print(f"\nConfiguration (Experimental):")
    print(f"  Temporal Window: {config['temporal_window_hours']} hours")
    print(f"  Min Correlation Score: {config['min_correlation_score']}")
    print(f"\n  Correlation Weights:")
    for signal, weight in config['correlation_weights'].items():
        print(f"    {signal}: {weight:.2f}")
    print(f"\n  Stage 2 Compatibility Weights:")
    for field, weight in config['stage2_weights'].items():
        field_name = field.replace('_weight', '')
        print(f"    {field_name}: {weight:.2f}")
    
    # Step 1: Run Stage 1 Pipeline
    print("\n" + "=" * 80)
    print("[STAGE 1] INGESTION & NORMALIZATION")
    print("=" * 80)
    
    field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
    normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
    validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
    stage1_pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
    
    adapter = ExcelAlertAdapter(
        file_path=Settings.DATA_DIR / "raw" / "Data_Alert_Ticket_Segregation.xlsx",
        column_mapping=Settings.EXCEL_COLUMN_MAPPING,
        forbidden_metadata_fields=set(Settings.FORBIDDEN_METADATA_FIELDS)
    )
    
    standardized_alerts = stage1_pipeline.run(adapter)
    print(f"✓ Standardized {len(standardized_alerts)} alerts")
    
    # Step 2: Load Stage 2 Canonical Predictions
    print("\n" + "=" * 80)
    print("[STAGE 2] LOADING CANONICAL PREDICTIONS")
    print("=" * 80)
    
    # Load canonical predictions from CSVs (already computed)
    canonical_preds_df = load_canonical_predictions(Settings.DATA_DIR)
    
    # For now, we'll create enriched alerts with canonical predictions only
    # Priority and Routing will use placeholder values since we're focusing on canonical fields
    print("✓ Loaded all canonical predictions")
    
    # Enrich alerts (using canonical predictions from CSV)
    # Note: Priority and Routing will use placeholders since we're focusing on canonical fields
    enriched_alerts = []
    
    print(f"\nEnriching {len(standardized_alerts)} alerts with canonical predictions...")
    
    for idx, alert in enumerate(standardized_alerts):
        # Get canonical predictions from CSVs (same order as alerts)
        alert_type_label = canonical_preds_df['alert_type'].iloc[idx]['predicted_label']
        alert_type_conf = canonical_preds_df['alert_type'].iloc[idx]['confidence']
        
        severity_label = canonical_preds_df['severity'].iloc[idx]['predicted_label']
        severity_conf = canonical_preds_df['severity'].iloc[idx]['confidence']
        
        business_impact_label = canonical_preds_df['business_impact'].iloc[idx]['predicted_label']
        business_impact_conf = canonical_preds_df['business_impact'].iloc[idx]['confidence']
        
        # Priority and Routing: use default placeholders for now
        # (focus is on canonical Alert Type, Severity, Business Impact)
        priority_label = "2 - High"
        priority_conf = 0.5
        routing_label = "Default Team"
        routing_conf = 0.5
        
        enriched = EnrichedAlert(
            alert_id=alert.alert_id,
            created_at=alert.created_at,
            client=alert.client,
            raw_description=alert.raw_description,
            normalized_description=alert.normalized_description,
            metadata=alert.metadata,
            alert_type=ClassificationResult(
                label=str(alert_type_label),
                confidence=float(alert_type_conf),
                provider="ml",
                model="tfidf_lr_alert_type"
            ),
            severity=ClassificationResult(
                label=str(severity_label),
                confidence=float(severity_conf),
                provider="ml",
                model="embedding_svm_severity"
            ),
            business_impact=ClassificationResult(
                label=str(business_impact_label),
                confidence=float(business_impact_conf),
                provider="ml",
                model="embedding_svm_business_impact"
            ),
            priority=ClassificationResult(
                label=str(priority_label),
                confidence=float(priority_conf),
                provider="placeholder",
                model="placeholder"
            ),
            routing=ClassificationResult(
                label=str(routing_label),
                confidence=float(routing_conf),
                provider="placeholder",
                model="placeholder"
            )
        )
        
        enriched_alerts.append(enriched)
    
    print(f"✓ Enriched {len(enriched_alerts)} alerts with Stage 2 predictions")
    
    # Step 3: Run Stage 3 Correlation
    print("\n" + "=" * 80)
    print("[STAGE 3] CORRELATION WITH CANONICAL FIELDS")
    print("=" * 80)
    
    # Initialize components with configuration
    signature_matcher = SignatureMatcher(min_group_size=2)
    semantic_clusterer = SemanticClusterer(
        embedding_model='all-MiniLM-L6-v2',
        min_cluster_size=2,
        min_samples=1
    )
    service_validator = ServiceValidator()
    stage2_validator = Stage2CompatibilityValidator(
        **config['stage2_weights']
    )
    graph_grouper = GraphGrouper()
    
    correlation_pipeline = CorrelationPipeline(
        signature_matcher=signature_matcher,
        semantic_clusterer=semantic_clusterer,
        service_validator=service_validator,
        stage2_validator=stage2_validator,
        graph_grouper=graph_grouper,
        max_time_gap_hours=config['temporal_window_hours'],
        min_correlation_score=config['min_correlation_score'],
        correlation_weights=config['correlation_weights']
    )
    
    # Run correlation
    incident_groups, uncorrelated_alerts = correlation_pipeline.correlate_alerts(
        standardized_alerts,
        use_graph_grouping=True
    )
    
    # Step 4: Analyze Results
    print("\n" + "=" * 80)
    print("[RESULTS] INCIDENT GROUPS")
    print("=" * 80)
    
    stats = correlation_pipeline.get_incident_statistics(incident_groups)
    
    total_correlated = stats['total_alerts_in_incidents']
    grouping_rate = total_correlated / len(standardized_alerts) * 100
    
    print(f"\nOverall Statistics:")
    print(f"  Total Alerts: {len(standardized_alerts)}")
    print(f"  Candidate Incident Groups: {stats['total_incidents']}")
    print(f"  Grouped Alerts: {total_correlated}")
    print(f"  Uncorrelated Alerts: {len(uncorrelated_alerts)}")
    print(f"  Grouping Rate: {grouping_rate:.1f}%")
    
    # Group size statistics
    group_sizes = [inc.alert_count for inc in incident_groups]
    if group_sizes:
        print(f"\nGroup Size Statistics:")
        print(f"  Average: {np.mean(group_sizes):.2f} alerts")
        print(f"  Median: {np.median(group_sizes):.1f} alerts")
        print(f"  Max: {np.max(group_sizes)} alerts")
        print(f"  Min: {np.min(group_sizes)} alerts")
    
    # Duration statistics
    durations = []
    for inc in incident_groups:
        if inc.incident_end and inc.incident_start:
            duration_hours = (inc.incident_end - inc.incident_start).total_seconds() / 3600
            durations.append(duration_hours)
    
    if durations:
        print(f"\nDuration Statistics (hours):")
        print(f"  Average: {np.mean(durations):.2f} hours")
        print(f"  Median: {np.median(durations):.2f} hours")
        print(f"  Max: {np.max(durations):.2f} hours")
        print(f"  Min: {np.min(durations):.2f} hours")
    
    print(f"\nIncidents by Correlation Method:")
    for method, count in stats['incidents_by_method'].items():
        pct = count / stats['total_incidents'] * 100
        print(f"  {method}: {count} ({pct:.1f}%)")
    
    print(f"\nIncidents by Client:")
    for client, count in sorted(stats['incidents_by_client'].items(), key=lambda x: x[1], reverse=True):
        pct = count / stats['total_incidents'] * 100
        print(f"  {client}: {count} ({pct:.1f}%)")
    
    # Pizza Hut Analysis
    analyze_pizza_hut_family(incident_groups, standardized_alerts)
    
    # Show top incidents
    print("\n" + "=" * 80)
    print("TOP 10 INCIDENT GROUPS (by alert count)")
    print("=" * 80)
    
    sorted_incidents = sorted(incident_groups, key=lambda x: x.alert_count, reverse=True)
    
    for i, incident in enumerate(sorted_incidents[:10], 1):
        duration = 0
        if incident.incident_end:
            duration = (incident.incident_end - incident.incident_start).total_seconds() / 3600
        
        print(f"\n[{i}] {incident.incident_id}")
        print(f"  Client: {incident.client}")
        print(f"  Alerts: {incident.alert_count}")
        print(f"  Duration: {duration:.2f} hours")
        print(f"  Method: {incident.correlation_method}")
        if incident.avg_correlation_score:
            print(f"  Avg Score: {incident.avg_correlation_score:.4f}")
        print(f"  Alert IDs: {', '.join(incident.alert_ids[:5])}")
        if len(incident.alert_ids) > 5:
            print(f"             ... and {len(incident.alert_ids) - 5} more")
    
    # Save results
    output_dir = Settings.DATA_DIR / "stage3_canonical_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    
    # Save incident groups
    incidents_data = []
    for inc in incident_groups:
        incidents_data.append({
            'incident_id': inc.incident_id,
            'client': inc.client,
            'alert_count': inc.alert_count,
            'alert_ids': inc.alert_ids,
            'incident_start': inc.incident_start.isoformat(),
            'incident_end': inc.incident_end.isoformat() if inc.incident_end else None,
            'correlation_method': inc.correlation_method,
            'avg_correlation_score': inc.avg_correlation_score
        })
    
    with open(output_dir / "incident_groups.json", 'w') as f:
        json.dump(incidents_data, f, indent=2)
    print(f"✓ Saved incident_groups.json")
    
    # Save statistics
    results_summary = {
        'timestamp': datetime.now().isoformat(),
        'configuration': config,
        'statistics': {
            'total_alerts': len(standardized_alerts),
            'total_incidents': stats['total_incidents'],
            'grouped_alerts': total_correlated,
            'uncorrelated_alerts': len(uncorrelated_alerts),
            'grouping_rate': grouping_rate,
            'group_size_stats': {
                'mean': float(np.mean(group_sizes)) if group_sizes else 0,
                'median': float(np.median(group_sizes)) if group_sizes else 0,
                'max': int(np.max(group_sizes)) if group_sizes else 0,
                'min': int(np.min(group_sizes)) if group_sizes else 0
            },
            'duration_stats': {
                'mean_hours': float(np.mean(durations)) if durations else 0,
                'median_hours': float(np.median(durations)) if durations else 0,
                'max_hours': float(np.max(durations)) if durations else 0,
                'min_hours': float(np.min(durations)) if durations else 0
            },
            'incidents_by_method': stats['incidents_by_method'],
            'incidents_by_client': stats['incidents_by_client']
        }
    }
    
    with open(output_dir / "results_summary.json", 'w') as f:
        json.dump(results_summary, f, indent=2)
    print(f"✓ Saved results_summary.json")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nResults saved to: {output_dir}")
    
    return {
        'standardized_alerts': standardized_alerts,
        'enriched_alerts': enriched_alerts,
        'incident_groups': incident_groups,
        'uncorrelated_alerts': uncorrelated_alerts,
        'statistics': stats,
        'configuration': config
    }


if __name__ == '__main__':
    results = main()
