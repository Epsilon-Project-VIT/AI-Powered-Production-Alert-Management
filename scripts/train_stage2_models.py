"""
Train Stage 2 classification models.

This script trains models for Priority and Assignment Group classification
using the historical data from the Excel file.
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from alert_management.config.settings import Settings
from alert_management.stage1_ingestion.pipeline import Stage1Pipeline
from alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from alert_management.stage2_classification.models.tfidf_lr import TfidfLogisticClassifier
from alert_management.stage2_classification.models.tfidf_svm import TfidfSVMClassifier
from alert_management.stage2_classification.models.embedding_lr import EmbeddingLogisticClassifier
from alert_management.stage2_classification.training.data_prep import (
    prepare_training_data,
    split_chronologically,
    filter_by_minimum_samples,
    get_label_distribution
)
from alert_management.stage2_classification.training.trainer import ModelTrainer
from alert_management.stage2_classification.training.evaluator import ModelEvaluator


def main():
    """Train Stage 2 classification models."""
    
    print("\n" + "=" * 70)
    print("STAGE 2 MODEL TRAINING")
    print("=" * 70)
    
    # Paths
    excel_file = Settings.DATA_DIR / "Data_Alert_Ticket_Segregation.xlsx"
    models_dir = Settings.PROJECT_ROOT / "models" / "stage2"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Run Stage 1 pipeline to get standardized alerts
    # NOTE: For training, we need the target labels (Priority, Assignment group)
    # So we'll load them separately and NOT filter them from metadata during training
    print("\n[1/6] Running Stage 1 pipeline...")
    print("-" * 70)
    
    # Initialize Stage 1 components
    from alert_management.stage1_ingestion.cleaners.field_cleaner import FieldCleaner
    from alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
    from alert_management.stage1_ingestion.validators.alert_validator import AlertValidator
    
    field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
    normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
    validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
    pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
    
    # For TRAINING ONLY: Don't filter target fields so we can access ground truth labels
    # In production Stage 2, these fields won't be present in incoming alerts
    adapter = ExcelAlertAdapter(
        file_path=excel_file,
        column_mapping=Settings.EXCEL_COLUMN_MAPPING,
        forbidden_metadata_fields=set()  # Empty set for training - we need the labels!
    )
    
    alerts = pipeline.run(adapter)
    
    print(f"✓ Loaded {len(alerts)} standardized alerts")
    
    # Step 2: Split data chronologically
    print("\n[2/6] Splitting data chronologically...")
    print("-" * 70)
    
    train_alerts, val_alerts, test_alerts = split_chronologically(
        alerts,
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15
    )
    
    print(f"✓ Training set:   {len(train_alerts)} alerts")
    print(f"✓ Validation set: {len(val_alerts)} alerts")
    print(f"✓ Test set:       {len(test_alerts)} alerts")
    
    # Step 3: Train Priority model
    print("\n[3/6] Training Priority classification models...")
    print("-" * 70)
    
    train_priority_texts, train_priority_labels = prepare_training_data(
        train_alerts, 'Priority'
    )
    val_priority_texts, val_priority_labels = prepare_training_data(
        val_alerts, 'Priority'
    )
    test_priority_texts, test_priority_labels = prepare_training_data(
        test_alerts, 'Priority'
    )
    
    print(f"Priority training samples: {len(train_priority_texts)}")
    print(f"Priority label distribution:")
    priority_dist = get_label_distribution(train_priority_labels)
    for label, count in sorted(priority_dist.items()):
        print(f"  {label}: {count}")
    
    # Initialize Priority models for benchmarking
    priority_models = [
        TfidfLogisticClassifier(
            model_name='priority_tfidf_lr',
            max_features=3000,
            ngram_range=(1, 2)
        ),
        TfidfSVMClassifier(
            model_name='priority_tfidf_svm',
            max_features=3000,
            ngram_range=(1, 2),
            kernel='linear'
        ),
        EmbeddingLogisticClassifier(
            model_name='priority_embedding_lr',
            embedding_model='all-MiniLM-L6-v2'
        )
    ]
    
    # Train Priority models
    trainer = ModelTrainer(experiment_name='priority_classification')
    priority_results = trainer.train_multiple_models(
        priority_models,
        train_priority_texts,
        train_priority_labels,
        val_priority_texts,
        val_priority_labels,
        save_path=models_dir
    )
    
    # Step 4: Evaluate Priority models
    print("\n[4/6] Evaluating Priority models on test set...")
    print("-" * 70)
    
    evaluator = ModelEvaluator()
    priority_eval_results = evaluator.compare_models(
        priority_models,
        test_priority_texts,
        test_priority_labels
    )
    
    # Step 5: Train Assignment Group (Routing) model
    print("\n[5/6] Training Assignment Group (Routing) models...")
    print("-" * 70)
    
    train_routing_texts, train_routing_labels = prepare_training_data(
        train_alerts, 'Assignment group'
    )
    val_routing_texts, val_routing_labels = prepare_training_data(
        val_alerts, 'Assignment group'
    )
    test_routing_texts, test_routing_labels = prepare_training_data(
        test_alerts, 'Assignment group'
    )
    
    # Filter out rare assignment groups
    train_routing_texts, train_routing_labels = filter_by_minimum_samples(
        train_routing_texts,
        train_routing_labels,
        min_samples=5
    )
    
    print(f"Routing training samples: {len(train_routing_texts)}")
    print(f"Routing label distribution:")
    routing_dist = get_label_distribution(train_routing_labels)
    for label, count in sorted(routing_dist.items()):
        print(f"  {label}: {count}")
    
    # Initialize Routing models (only TF-IDF+LR for speed)
    routing_models = [
        TfidfLogisticClassifier(
            model_name='routing_tfidf_lr',
            max_features=3000,
            ngram_range=(1, 2)
        )
    ]
    
    # Train Routing models
    routing_results = trainer.train_multiple_models(
        routing_models,
        train_routing_texts,
        train_routing_labels,
        val_routing_texts,
        val_routing_labels,
        save_path=models_dir
    )
    
    # Step 6: Evaluate Routing models
    print("\n[6/6] Evaluating Routing models on test set...")
    print("-" * 70)
    
    routing_eval_results = evaluator.compare_models(
        routing_models,
        test_routing_texts,
        test_routing_labels
    )
    
    # Final Summary
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)
    
    print("\nPriority Classification:")
    best_priority = max(priority_eval_results, key=lambda x: x['f1_weighted'])
    print(f"  Best Model: {best_priority['model_name']}")
    print(f"  Test F1:    {best_priority['f1_weighted']:.4f}")
    print(f"  Test Acc:   {best_priority['accuracy']:.4f}")
    
    print("\nAssignment Group (Routing) Classification:")
    best_routing = max(routing_eval_results, key=lambda x: x['f1_weighted'])
    print(f"  Best Model: {best_routing['model_name']}")
    print(f"  Test F1:    {best_routing['f1_weighted']:.4f}")
    print(f"  Test Acc:   {best_routing['accuracy']:.4f}")
    
    print(f"\nModels saved to: {models_dir}")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
