"""
Run Stage 1 + Stage 2 + Stage 3 end-to-end pipeline.

Demonstrates complete flow from raw alerts to incident groups.
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from alert_management.config.settings import Settings
from alert_management.stage1_ingestion.pipeline import Stage1Pipeline
from alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from alert_management.stage1_ingestion.cleaners.field_cleaner import FieldCleaner
from alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
from alert_management.stage1_ingestion.validators.alert_validator import AlertValidator
from alert_management.stage3_correlation.pipeline import CorrelationPipeline
from alert_management.stage3_correlation.clustering.signature_matcher import SignatureMatcher
from alert_management.stage3_correlation.clustering.semantic_clusterer import SemanticClusterer


def main():
    """Run Stage 1 + Stage 2 + Stage 3 pipeline demonstration."""
    
    print("\n" + "=" * 80)
    print("STAGE 1 + STAGE 2 + STAGE 3 END-TO-END PIPELINE")
    print("=" * 80)
    
    # Paths
    excel_file = Settings.DATA_DIR / "Data_Alert_Ticket_Segregation.xlsx"
    
    # Step 1: Run Stage 1 Pipeline
    print("\n[Stage 1] Ingestion & Normalization")
    print("-" * 80)
    
    # Initialize Stage 1 components
    field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
    normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
    validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
    stage1_pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
    
    adapter = ExcelAlertAdapter(
        file_path=excel_file,
        column_mapping=Settings.EXCEL_COLUMN_MAPPING,
        forbidden_metadata_fields=set(Settings.FORBIDDEN_METADATA_FIELDS)
    )
    
    standardized_alerts = stage1_pipeline.run(adapter)
    
    print(f"✓ Ingested and standardized {len(standardized_alerts)} alerts")
    
    # Step 2: Stage 3 Correlation Analysis
    print("\n[Stage 3] Alert Correlation & Incident Grouping")
    print("-" * 80)
    
    # Get signature statistics first
    signature_matcher = SignatureMatcher(min_group_size=2)
    sig_stats = signature_matcher.get_signature_statistics(standardized_alerts)
    
    print("\nSignature Analysis:")
    print(f"  Total alerts: {sig_stats['total_alerts']}")
    print(f"  Unique signatures: {sig_stats['unique_signatures']}")
    print(f"  Repeated signatures: {sig_stats['repeated_signatures']}")
    print(f"  Alerts in repeated groups: {sig_stats['alerts_in_repeated_groups']} ({sig_stats['repeat_percentage']:.1%})")
    
    print("\nTop 5 Repeated Alert Patterns:")
    for i, group in enumerate(sig_stats['largest_groups'][:5], 1):
        print(f"  {i}. Count: {group['count']}, Clients: {', '.join(group['clients'])}")
        print(f"     Signature: {group['signature'][:80]}...")
    
    # Step 3: Run correlation pipeline
    print("\n[Stage 3] Running Correlation Pipeline")
    print("-" * 80)
    
    semantic_clusterer = SemanticClusterer(
        embedding_model='all-MiniLM-L6-v2',
        min_cluster_size=2,
        min_samples=1
    )
    
    correlation_pipeline = CorrelationPipeline(
        signature_matcher=signature_matcher,
        semantic_clusterer=semantic_clusterer,
        max_time_gap_hours=24.0,
        min_correlation_score=0.7
    )
    
    incident_groups, uncorrelated_alerts = correlation_pipeline.correlate_alerts(
        standardized_alerts
    )
    
    # Step 4: Display Results
    print("\n[Results] Incident Groups")
    print("=" * 80)
    
    # Statistics
    stats = correlation_pipeline.get_incident_statistics(incident_groups)
    
    print(f"\nOverall Statistics:")
    print(f"  Total Incidents: {stats['total_incidents']}")
    print(f"  Total Alerts in Incidents: {stats['total_alerts_in_incidents']}")
    print(f"  Average Alerts per Incident: {stats['avg_alerts_per_incident']:.2f}")
    print(f"  Max Alerts in Single Incident: {stats['max_alerts_in_incident']}")
    print(f"  Uncorrelated (Singleton) Alerts: {len(uncorrelated_alerts)}")
    
    print(f"\nIncidents by Correlation Method:")
    for method, count in stats['incidents_by_method'].items():
        print(f"  {method}: {count}")
    
    print(f"\nIncidents by Client:")
    for client, count in sorted(stats['incidents_by_client'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {client}: {count}")
    
    # Show sample incidents
    print("\n" + "=" * 80)
    print("Sample Incident Groups (Top 5 by alert count)")
    print("=" * 80)
    
    # Sort by alert count
    sorted_incidents = sorted(incident_groups, key=lambda x: x.alert_count, reverse=True)
    
    for i, incident in enumerate(sorted_incidents[:5], 1):
        print(f"\n[Incident {i}] {incident.incident_id}")
        print(f"  Client:          {incident.client}")
        print(f"  Alert Count:     {incident.alert_count}")
        print(f"  Time Range:      {incident.incident_start} to {incident.incident_end}")
        
        if incident.incident_end:
            duration = (incident.incident_end - incident.incident_start).total_seconds() / 3600
            print(f"  Duration:        {duration:.2f} hours")
        
        print(f"  Method:          {incident.correlation_method}")
        
        if incident.avg_correlation_score:
            print(f"  Avg Correlation: {incident.avg_correlation_score:.4f}")
        
        print(f"  Alert IDs:       {', '.join(incident.alert_ids[:5])}")
        if len(incident.alert_ids) > 5:
            print(f"                   ... and {len(incident.alert_ids) - 5} more")
        
        print(f"  Signature:       {incident.normalized_signature[:100]}...")
        print("-" * 80)
    
    # Client-specific analysis
    print("\n" + "=" * 80)
    print("Client-Specific Analysis")
    print("=" * 80)
    
    for client in sorted(stats['incidents_by_client'].keys()):
        client_incidents = [inc for inc in incident_groups if inc.client == client]
        client_alerts_count = sum(inc.alert_count for inc in client_incidents)
        
        print(f"\n{client}:")
        print(f"  Incidents: {len(client_incidents)}")
        print(f"  Total Alerts: {client_alerts_count}")
        print(f"  Avg Alerts/Incident: {client_alerts_count / len(client_incidents):.2f}")
        
        # Largest incident for this client
        if client_incidents:
            largest = max(client_incidents, key=lambda x: x.alert_count)
            print(f"  Largest Incident: {largest.incident_id} ({largest.alert_count} alerts)")
    
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80 + "\n")
    
    # Return for potential further analysis
    return {
        'standardized_alerts': standardized_alerts,
        'incident_groups': incident_groups,
        'uncorrelated_alerts': uncorrelated_alerts,
        'statistics': stats
    }


if __name__ == '__main__':
    results = main()
