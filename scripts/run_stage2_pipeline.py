"""
Run Stage 1 + Stage 2 end-to-end pipeline.

Demonstrates the complete flow from raw alerts to enriched alerts.
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from alert_management.config.settings import Settings
from alert_management.stage1_ingestion.pipeline import Stage1Pipeline
from alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from alert_management.stage2_classification.pipeline import ClassificationPipeline
from alert_management.stage2_classification.models.tfidf_lr import TfidfLogisticClassifier


def main():
    """Run Stage 1 + Stage 2 pipeline demonstration."""
    
    print("\n" + "=" * 70)
    print("STAGE 1 + STAGE 2 END-TO-END PIPELINE")
    print("=" * 70)
    
    # Paths
    excel_file = Settings.DATA_DIR / "Data_Alert_Ticket_Segregation.xlsx"
    models_dir = Settings.PROJECT_ROOT / "models" / "stage2"
    
    # Step 1: Run Stage 1 Pipeline
    print("\n[Stage 1] Ingestion & Normalization")
    print("-" * 70)
    
    # Initialize Stage 1 components
    from alert_management.stage1_ingestion.cleaners.field_cleaner import FieldCleaner
    from alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
    from alert_management.stage1_ingestion.validators.alert_validator import AlertValidator
    
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
    
    # Step 2: Load Stage 2 Models
    print("\n[Stage 2] Loading Classification Models")
    print("-" * 70)
    
    # Initialize models
    priority_model = TfidfLogisticClassifier(model_name='priority_tfidf_lr')
    routing_model = TfidfLogisticClassifier(model_name='routing_tfidf_lr')
    
    # Try to load trained models
    try:
        priority_model.load(models_dir)
        print(f"✓ Loaded Priority model: {priority_model.model_name}")
    except FileNotFoundError:
        print("⚠ Priority model not found - please run train_stage2_models.py first")
        priority_model = None
    
    try:
        routing_model.load(models_dir)
        print(f"✓ Loaded Routing model: {routing_model.model_name}")
    except FileNotFoundError:
        print("⚠ Routing model not found - please run train_stage2_models.py first")
        routing_model = None
    
    # Step 3: Initialize Stage 2 Pipeline
    print("\n[Stage 2] Initializing Classification Pipeline")
    print("-" * 70)
    
    stage2_pipeline = ClassificationPipeline(
        priority_model=priority_model,
        routing_model=routing_model
    )
    
    status = stage2_pipeline.get_status()
    print("Model Status:")
    for task, is_trained in status.items():
        status_icon = "✓" if is_trained else "✗"
        print(f"  {status_icon} {task}: {'trained' if is_trained else 'not available'}")
    
    # Step 4: Classify Alerts
    print("\n[Stage 2] Classifying Alerts")
    print("-" * 70)
    
    # Process a subset of alerts for demonstration
    demo_alerts = standardized_alerts[:10]
    enriched_alerts = stage2_pipeline.classify_batch(demo_alerts)
    
    print(f"✓ Classified {len(enriched_alerts)} alerts")
    
    # Step 5: Display Results
    print("\n[Results] Sample Enriched Alerts")
    print("=" * 70)
    
    for i, enriched in enumerate(enriched_alerts[:5], 1):
        print(f"\n[Alert {i}] {enriched.alert_id}")
        print(f"Client:      {enriched.client}")
        print(f"Description: {enriched.raw_description[:80]}...")
        print(f"\nClassifications:")
        print(f"  Alert Type:       {enriched.alert_type.label} (conf: {enriched.alert_type.confidence:.2f})")
        print(f"  Severity:         {enriched.severity.label} (conf: {enriched.severity.confidence:.2f})")
        print(f"  Business Impact:  {enriched.business_impact.label} (conf: {enriched.business_impact.confidence:.2f})")
        print(f"  Priority:         {enriched.priority.label} (conf: {enriched.priority.confidence:.2f})")
        print(f"  Routing:          {enriched.routing.label[:50]}... (conf: {enriched.routing.confidence:.2f})")
        print("-" * 70)
    
    # Step 6: Summary Statistics
    print("\n[Summary] Classification Statistics")
    print("=" * 70)
    
    # Calculate average confidences
    priority_confs = [e.priority.confidence for e in enriched_alerts if e.priority.confidence > 0]
    routing_confs = [e.routing.confidence for e in enriched_alerts if e.routing.confidence > 0]
    
    if priority_confs:
        print(f"\nPriority Model:")
        print(f"  Average Confidence: {sum(priority_confs) / len(priority_confs):.4f}")
        print(f"  Min Confidence:     {min(priority_confs):.4f}")
        print(f"  Max Confidence:     {max(priority_confs):.4f}")
    
    if routing_confs:
        print(f"\nRouting Model:")
        print(f"  Average Confidence: {sum(routing_confs) / len(routing_confs):.4f}")
        print(f"  Min Confidence:     {min(routing_confs):.4f}")
        print(f"  Max Confidence:     {max(routing_confs):.4f}")
    
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
