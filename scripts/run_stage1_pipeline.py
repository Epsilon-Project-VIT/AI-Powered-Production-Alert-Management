#!/usr/bin/env python3
"""
Example script to run Stage 1 pipeline on the historical dataset.

This demonstrates the complete Stage 1 flow:
1. Ingest alerts from Excel
2. Clean fields
3. Validate required fields
4. Normalize descriptions
5. Output StandardizedAlert objects
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.alert_management.config.settings import Settings
from src.alert_management.stage1_ingestion import Stage1Pipeline
from src.alert_management.stage1_ingestion.adapters import ExcelAlertAdapter
from src.alert_management.stage1_ingestion.cleaners import FieldCleaner, Normalizer
from src.alert_management.stage1_ingestion.validators import AlertValidator


def main():
    """Run Stage 1 pipeline on historical dataset."""
    
    print("\n" + "=" * 80)
    print("STAGE 1 DEMO: Alert Ingestion & Normalization")
    print("=" * 80 + "\n")
    
    # Initialize pipeline components
    field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
    normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
    validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
    pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
    
    # Create Excel adapter with forbidden fields filter
    adapter = ExcelAlertAdapter(
        file_path=Settings.EXCEL_FILE_PATH,
        column_mapping=Settings.EXCEL_COLUMN_MAPPING,
        forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
    )
    
    # Run pipeline
    standardized_alerts = pipeline.run(adapter)
    
    # Display summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total alerts processed: {len(standardized_alerts)}")
    
    # Count by client
    client_counts = {}
    for alert in standardized_alerts:
        client_counts[alert.client] = client_counts.get(alert.client, 0) + 1
    
    print("\nAlerts by client:")
    for client, count in sorted(client_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {client}: {count}")
    
    # Show specific examples
    print("\n" + "=" * 80)
    print("EXAMPLE ALERTS")
    print("=" * 80)
    
    # Find specific examples
    examples = {
        'INC3528892': 'Bridgestone batch failure',
        'INC3528891': 'EA Sports ELB errors',
        'INC3528890': 'Pizza Hut SLA warning'
    }
    
    alerts_by_id = {alert.alert_id: alert for alert in standardized_alerts}
    
    for alert_id, description in examples.items():
        if alert_id in alerts_by_id:
            alert = alerts_by_id[alert_id]
            print(f"\n{description} ({alert_id}):")
            print(f"  Client: {alert.client}")
            print(f"  Created: {alert.created_at}")
            print(f"  Raw: {alert.raw_description[:80]}...")
            print(f"  Normalized: {alert.normalized_description[:80]}...")
            if alert.metadata:
                print(f"  Metadata fields: {list(alert.metadata.keys())}")
                print(f"  (Note: Target/outcome fields excluded per data leakage prevention)")
    
    print("\n" + "=" * 80)
    print("Stage 1 complete! Alerts ready for Stage 2 classification.")
    print("=" * 80 + "\n")
    
    return standardized_alerts


if __name__ == "__main__":
    alerts = main()
