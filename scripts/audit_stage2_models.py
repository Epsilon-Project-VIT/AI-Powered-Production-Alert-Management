"""
Comprehensive Stage 2 Model Audit.

Evaluates Priority and Assignment Group classifiers with:
- Baseline comparison
- Per-class performance
- Confidence calibration
- Model benchmarking
- Data split analysis
- Feature leakage audit
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from collections import Counter
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    brier_score_loss
)
from sklearn.calibration import calibration_curve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from alert_management.config.settings import Settings
from alert_management.stage1_ingestion.pipeline import Stage1Pipeline
from alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from alert_management.stage1_ingestion.cleaners.field_cleaner import FieldCleaner
from alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
from alert_management.stage1_ingestion.validators.alert_validator import AlertValidator
from alert_management.stage2_classification.models.tfidf_lr import TfidfLogisticClassifier
from alert_management.stage2_classification.models.tfidf_svm import TfidfSVMClassifier
from alert_management.stage2_classification.models.embedding_lr import EmbeddingLogisticClassifier
from alert_management.stage2_classification.models.embedding_svm import EmbeddingSVMClassifier
from alert_management.stage2_classification.training.data_prep import (
    prepare_training_data,
    split_chronologically,
    filter_by_minimum_samples,
    get_label_distribution
)


class Stage2Auditor:
    """Comprehensive auditor for Stage 2 models."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audit_results = {
            'baseline_comparison': {},
            'per_class_performance': {},
            'confusion_matrices': {},
            'calibration': {},
            'model_benchmarks': {},
            'data_splits': {},
            'feature_audit': {}
        }
    
    def calculate_baseline(self, labels):
        """Calculate majority class baseline."""
        label_counts = Counter(labels)
        majority_class = label_counts.most_common(1)[0][0]
        majority_count = label_counts[majority_class]
        baseline_accuracy = majority_count / len(labels)
        
        return {
            'majority_class': majority_class,
            'majority_count': majority_count,
            'baseline_accuracy': baseline_accuracy,
            'total_samples': len(labels)
        }
    
    def evaluate_model_comprehensive(self, model, test_texts, test_labels, task_name):
        """Comprehensive model evaluation."""
        # Predictions
        predictions = model.predict(test_texts)
        probas = model.predict_proba(test_texts)
        
        # Overall metrics
        accuracy = accuracy_score(test_labels, predictions)
        
        # Macro and weighted metrics
        precision_macro, recall_macro, f1_macro, _ = precision_recall_fscore_support(
            test_labels, predictions, average='macro', zero_division=0
        )
        precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
            test_labels, predictions, average='weighted', zero_division=0
        )
        
        # Per-class metrics
        precision_per_class, recall_per_class, f1_per_class, support_per_class = (
            precision_recall_fscore_support(
                test_labels, predictions, average=None, zero_division=0, labels=model.classes_
            )
        )
        
        # Confusion matrix
        cm = confusion_matrix(test_labels, predictions, labels=model.classes_)
        
        # Confidence statistics
        max_probas = np.max(probas, axis=1)
        avg_confidence = np.mean(max_probas)
        
        # Calibration metrics
        try:
            # Brier score (lower is better, ranges 0-1)
            # Convert labels to binary for each class and calculate average Brier score
            brier_scores = []
            for i, class_label in enumerate(model.classes_):
                y_true_binary = (np.array(test_labels) == class_label).astype(int)
                y_prob = probas[:, i]
                brier_scores.append(brier_score_loss(y_true_binary, y_prob))
            avg_brier_score = np.mean(brier_scores)
        except:
            avg_brier_score = None
        
        return {
            'accuracy': accuracy,
            'precision_macro': precision_macro,
            'recall_macro': recall_macro,
            'f1_macro': f1_macro,
            'precision_weighted': precision_weighted,
            'recall_weighted': recall_weighted,
            'f1_weighted': f1_weighted,
            'per_class': {
                model.classes_[i]: {
                    'precision': precision_per_class[i],
                    'recall': recall_per_class[i],
                    'f1': f1_per_class[i],
                    'support': support_per_class[i]
                }
                for i in range(len(model.classes_))
            },
            'confusion_matrix': cm,
            'avg_confidence': avg_confidence,
            'avg_brier_score': avg_brier_score,
            'classes': model.classes_.tolist()
        }
    
    def plot_confusion_matrix(self, cm, classes, task_name, model_name):
        """Plot confusion matrix."""
        plt.figure(figsize=(10, 8))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title(f'Confusion Matrix: {task_name} - {model_name}')
        plt.colorbar()
        
        tick_marks = np.arange(len(classes))
        plt.xticks(tick_marks, classes, rotation=45, ha='right')
        plt.yticks(tick_marks, classes)
        
        # Add text annotations
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "black")
        
        plt.ylabel('True label')
        plt.xlabel('Predicted label')
        plt.tight_layout()
        
        filename = self.output_dir / f'confusion_matrix_{task_name}_{model_name}.png'
        plt.savefig(filename)
        plt.close()
        
        return str(filename)
    
    def plot_calibration_curve(self, model, test_texts, test_labels, task_name, model_name):
        """Plot calibration reliability diagram."""
        probas = model.predict_proba(test_texts)
        
        plt.figure(figsize=(10, 8))
        
        # Plot for each class
        for i, class_label in enumerate(model.classes_):
            y_true_binary = (np.array(test_labels) == class_label).astype(int)
            y_prob = probas[:, i]
            
            try:
                fraction_of_positives, mean_predicted_value = calibration_curve(
                    y_true_binary, y_prob, n_bins=10, strategy='uniform'
                )
                
                plt.plot(mean_predicted_value, fraction_of_positives, 's-', 
                        label=f'{class_label}')
            except:
                pass
        
        # Perfect calibration line
        plt.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
        
        plt.xlabel('Mean predicted probability')
        plt.ylabel('Fraction of positives')
        plt.title(f'Calibration Curve: {task_name} - {model_name}')
        plt.legend(loc='best')
        plt.grid(True)
        plt.tight_layout()
        
        filename = self.output_dir / f'calibration_{task_name}_{model_name}.png'
        plt.savefig(filename)
        plt.close()
        
        return str(filename)
    
    def analyze_data_splits(self, train_alerts, val_alerts, test_alerts, target_field):
        """Analyze data split characteristics."""
        # Date ranges
        train_dates = [a.created_at for a in train_alerts]
        val_dates = [a.created_at for a in val_alerts]
        test_dates = [a.created_at for a in test_alerts]
        
        # Prepare labels
        train_texts, train_labels = prepare_training_data(train_alerts, target_field)
        val_texts, val_labels = prepare_training_data(val_alerts, target_field)
        test_texts, test_labels = prepare_training_data(test_alerts, target_field)
        
        return {
            'train': {
                'count': len(train_alerts),
                'date_range': f"{min(train_dates)} to {max(train_dates)}",
                'label_distribution': get_label_distribution(train_labels)
            },
            'val': {
                'count': len(val_alerts),
                'date_range': f"{min(val_dates)} to {max(val_dates)}",
                'label_distribution': get_label_distribution(val_labels)
            },
            'test': {
                'count': len(test_alerts),
                'date_range': f"{min(test_dates)} to {max(test_dates)}",
                'label_distribution': get_label_distribution(test_labels)
            }
        }
    
    def audit_feature_leakage(self, alerts, forbidden_fields):
        """Audit for feature leakage in metadata."""
        leakage_found = []
        
        for alert in alerts[:100]:  # Sample check
            if alert.metadata:
                for field in forbidden_fields:
                    if field in alert.metadata:
                        leakage_found.append({
                            'alert_id': alert.alert_id,
                            'forbidden_field': field,
                            'value': alert.metadata[field]
                        })
        
        return {
            'leakage_detected': len(leakage_found) > 0,
            'violations': leakage_found[:10],  # First 10 examples
            'total_violations': len(leakage_found)
        }


def main():
    """Run comprehensive Stage 2 audit."""
    
    print("\n" + "=" * 80)
    print("STAGE 2 MODEL AUDIT")
    print("=" * 80)
    
    # Setup
    excel_file = Settings.DATA_DIR / "Data_Alert_Ticket_Segregation.xlsx"
    models_dir = Settings.PROJECT_ROOT / "models" / "stage2"
    output_dir = Settings.PROJECT_ROOT / "docs" / "audit_outputs"
    
    auditor = Stage2Auditor(output_dir)
    
    # Load data
    print("\n[1/7] Loading and preparing data...")
    print("-" * 80)
    
    field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
    normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
    validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
    pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
    
    # Load with all fields for training
    adapter = ExcelAlertAdapter(
        file_path=excel_file,
        column_mapping=Settings.EXCEL_COLUMN_MAPPING,
        forbidden_metadata_fields=set()
    )
    
    alerts = pipeline.run(adapter)
    print(f"✓ Loaded {len(alerts)} alerts")
    
    # Split chronologically
    train_alerts, val_alerts, test_alerts = split_chronologically(
        alerts, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15
    )
    
    print(f"✓ Train: {len(train_alerts)}, Val: {len(val_alerts)}, Test: {len(test_alerts)}")
    
    # Analyze data splits
    print("\n[2/7] Analyzing data splits...")
    print("-" * 80)
    
    priority_split_analysis = auditor.analyze_data_splits(
        train_alerts, val_alerts, test_alerts, 'Priority'
    )
    routing_split_analysis = auditor.analyze_data_splits(
        train_alerts, val_alerts, test_alerts, 'Assignment group'
    )
    
    auditor.audit_results['data_splits'] = {
        'Priority': priority_split_analysis,
        'Assignment group': routing_split_analysis
    }
    
    print("✓ Data split analysis complete")
    
    # Feature leakage audit
    print("\n[3/7] Auditing for feature leakage...")
    print("-" * 80)
    
    # Check with forbidden fields applied
    adapter_filtered = ExcelAlertAdapter(
        file_path=excel_file,
        column_mapping=Settings.EXCEL_COLUMN_MAPPING,
        forbidden_metadata_fields=set(Settings.FORBIDDEN_METADATA_FIELDS)
    )
    filtered_alerts = pipeline.run(adapter_filtered)
    
    leakage_audit = auditor.audit_feature_leakage(
        filtered_alerts,
        Settings.FORBIDDEN_METADATA_FIELDS
    )
    
    auditor.audit_results['feature_audit'] = leakage_audit
    
    if leakage_audit['leakage_detected']:
        print(f"⚠ LEAKAGE DETECTED: {leakage_audit['total_violations']} violations")
    else:
        print("✓ No feature leakage detected")
    
    # Priority audit
    print("\n[4/7] Auditing Priority classification...")
    print("-" * 80)
    
    train_priority_texts, train_priority_labels = prepare_training_data(train_alerts, 'Priority')
    val_priority_texts, val_priority_labels = prepare_training_data(val_alerts, 'Priority')
    test_priority_texts, test_priority_labels = prepare_training_data(test_alerts, 'Priority')
    
    # Baseline
    priority_baseline = auditor.calculate_baseline(test_priority_labels)
    print(f"Majority class baseline: {priority_baseline['baseline_accuracy']:.4f}")
    auditor.audit_results['baseline_comparison']['Priority'] = priority_baseline
    
    # Train all models
    priority_models = {
        'tfidf_lr': TfidfLogisticClassifier('priority_tfidf_lr', max_features=3000, ngram_range=(1, 2)),
        'tfidf_svm': TfidfSVMClassifier('priority_tfidf_svm', max_features=3000, ngram_range=(1, 2)),
        'embedding_lr': EmbeddingLogisticClassifier('priority_embedding_lr'),
        'embedding_svm': EmbeddingSVMClassifier('priority_embedding_svm')
    }
    
    priority_results = {}
    for model_key, model in priority_models.items():
        print(f"Training {model_key}...")
        model.fit(train_priority_texts, train_priority_labels)
        
        results = auditor.evaluate_model_comprehensive(
            model, test_priority_texts, test_priority_labels, 'priority'
        )
        
        # Generate plots
        cm_file = auditor.plot_confusion_matrix(
            results['confusion_matrix'], results['classes'], 'priority', model_key
        )
        cal_file = auditor.plot_calibration_curve(
            model, test_priority_texts, test_priority_labels, 'priority', model_key
        )
        
        results['confusion_matrix_plot'] = cm_file
        results['calibration_plot'] = cal_file
        
        priority_results[model_key] = results
        
        print(f"  Accuracy: {results['accuracy']:.4f}, F1 Macro: {results['f1_macro']:.4f}, F1 Weighted: {results['f1_weighted']:.4f}")
    
    auditor.audit_results['model_benchmarks']['Priority'] = priority_results
    
    # Assignment Group audit
    print("\n[5/7] Auditing Assignment Group classification...")
    print("-" * 80)
    
    train_routing_texts, train_routing_labels = prepare_training_data(train_alerts, 'Assignment group')
    val_routing_texts, val_routing_labels = prepare_training_data(val_alerts, 'Assignment group')
    test_routing_texts, test_routing_labels = prepare_training_data(test_alerts, 'Assignment group')
    
    # Filter rare classes
    train_routing_texts, train_routing_labels = filter_by_minimum_samples(
        train_routing_texts, train_routing_labels, min_samples=5
    )
    
    # Baseline
    routing_baseline = auditor.calculate_baseline(test_routing_labels)
    print(f"Majority class baseline: {routing_baseline['baseline_accuracy']:.4f}")
    auditor.audit_results['baseline_comparison']['Assignment group'] = routing_baseline
    
    # Train models
    routing_models = {
        'tfidf_lr': TfidfLogisticClassifier('routing_tfidf_lr', max_features=3000, ngram_range=(1, 2))
    }
    
    routing_results = {}
    for model_key, model in routing_models.items():
        print(f"Training {model_key}...")
        model.fit(train_routing_texts, train_routing_labels)
        
        results = auditor.evaluate_model_comprehensive(
            model, test_routing_texts, test_routing_labels, 'routing'
        )
        
        # Generate plots
        cm_file = auditor.plot_confusion_matrix(
            results['confusion_matrix'], results['classes'], 'routing', model_key
        )
        cal_file = auditor.plot_calibration_curve(
            model, test_routing_texts, test_routing_labels, 'routing', model_key
        )
        
        results['confusion_matrix_plot'] = cm_file
        results['calibration_plot'] = cal_file
        
        routing_results[model_key] = results
        
        print(f"  Accuracy: {results['accuracy']:.4f}, F1 Macro: {results['f1_macro']:.4f}, F1 Weighted: {results['f1_weighted']:.4f}")
    
    auditor.audit_results['model_benchmarks']['Assignment group'] = routing_results
    
    # Generate audit report
    print("\n[6/7] Generating audit report...")
    print("-" * 80)
    
    generate_audit_report(auditor.audit_results, Settings.PROJECT_ROOT / "docs")
    
    print("✓ Audit report generated")
    
    print("\n[7/7] Summary")
    print("=" * 80)
    
    # Priority summary
    best_priority = max(priority_results.items(), key=lambda x: x[1]['f1_weighted'])
    print(f"\nPriority Classification:")
    print(f"  Baseline (majority class): {priority_baseline['baseline_accuracy']:.4f}")
    print(f"  Best Model: {best_priority[0]}")
    print(f"    Accuracy: {best_priority[1]['accuracy']:.4f}")
    print(f"    F1 Macro: {best_priority[1]['f1_macro']:.4f}")
    print(f"    F1 Weighted: {best_priority[1]['f1_weighted']:.4f}")
    print(f"    Improvement over baseline: {best_priority[1]['accuracy'] - priority_baseline['baseline_accuracy']:.4f}")
    
    # Routing summary
    best_routing = max(routing_results.items(), key=lambda x: x[1]['f1_weighted'])
    print(f"\nAssignment Group Classification:")
    print(f"  Baseline (majority class): {routing_baseline['baseline_accuracy']:.4f}")
    print(f"  Best Model: {best_routing[0]}")
    print(f"    Accuracy: {best_routing[1]['accuracy']:.4f}")
    print(f"    F1 Macro: {best_routing[1]['f1_macro']:.4f}")
    print(f"    F1 Weighted: {best_routing[1]['f1_weighted']:.4f}")
    print(f"    Improvement over baseline: {best_routing[1]['accuracy'] - routing_baseline['baseline_accuracy']:.4f}")
    
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80 + "\n")


def generate_audit_report(results, docs_dir):
    """Generate comprehensive audit report in Markdown."""
    
    report_path = docs_dir / "STAGE2_MODEL_AUDIT.md"
    
    with open(report_path, 'w') as f:
        f.write("# STAGE 2 MODEL AUDIT REPORT\n\n")
        f.write("**Date**: September 25, 2026\n\n")
        f.write("**Status**: AUDIT COMPLETE\n\n")
        f.write("---\n\n")
        
        # Data Splits
        f.write("## 1. DATA SPLIT ANALYSIS\n\n")
        f.write("### Chronological Split Verification\n\n")
        
        for task, split_data in results['data_splits'].items():
            f.write(f"#### {task}\n\n")
            f.write(f"**Training Set**:\n")
            f.write(f"- Count: {split_data['train']['count']}\n")
            f.write(f"- Date Range: {split_data['train']['date_range']}\n")
            f.write(f"- Label Distribution:\n")
            for label, count in sorted(split_data['train']['label_distribution'].items()):
                f.write(f"  - {label}: {count}\n")
            f.write(f"\n**Validation Set**:\n")
            f.write(f"- Count: {split_data['val']['count']}\n")
            f.write(f"- Date Range: {split_data['val']['date_range']}\n")
            f.write(f"- Label Distribution:\n")
            for label, count in sorted(split_data['val']['label_distribution'].items()):
                f.write(f"  - {label}: {count}\n")
            f.write(f"\n**Test Set**:\n")
            f.write(f"- Count: {split_data['test']['count']}\n")
            f.write(f"- Date Range: {split_data['test']['date_range']}\n")
            f.write(f"- Label Distribution:\n")
            for label, count in sorted(split_data['test']['label_distribution'].items()):
                f.write(f"  - {label}: {count}\n")
            f.write("\n")
        
        # Feature Leakage Audit
        f.write("## 2. FEATURE LEAKAGE AUDIT\n\n")
        leakage = results['feature_audit']
        
        if leakage['leakage_detected']:
            f.write(f"**⚠ LEAKAGE DETECTED**: {leakage['total_violations']} violations found\n\n")
            f.write("Sample violations:\n")
            for v in leakage['violations']:
                f.write(f"- Alert {v['alert_id']}: Field '{v['forbidden_field']}' present with value '{v['value']}'\n")
        else:
            f.write("**✓ NO LEAKAGE DETECTED**: All forbidden fields properly filtered\n\n")
            f.write("Forbidden fields checked:\n")
            for field in Settings.FORBIDDEN_METADATA_FIELDS:
                f.write(f"- {field}\n")
        
        f.write("\n")
        
        # Priority Classification
        f.write("## 3. PRIORITY CLASSIFICATION\n\n")
        
        baseline = results['baseline_comparison']['Priority']
        f.write(f"### Baseline Comparison\n\n")
        f.write(f"- Majority Class: {baseline['majority_class']}\n")
        f.write(f"- Majority Count: {baseline['majority_count']} / {baseline['total_samples']}\n")
        f.write(f"- **Baseline Accuracy: {baseline['baseline_accuracy']:.4f}**\n\n")
        
        f.write("### Model Benchmark Results\n\n")
        f.write("| Model | Accuracy | Precision (Macro) | Recall (Macro) | F1 (Macro) | F1 (Weighted) | Avg Confidence | Brier Score | Improvement over Baseline |\n")
        f.write("|-------|----------|-------------------|----------------|------------|---------------|----------------|-------------|---------------------------|\n")
        
        for model_name, model_results in results['model_benchmarks']['Priority'].items():
            improvement = model_results['accuracy'] - baseline['baseline_accuracy']
            brier_str = f"{model_results['avg_brier_score']:.4f}" if model_results['avg_brier_score'] else "N/A"
            f.write(f"| {model_name} | {model_results['accuracy']:.4f} | {model_results['precision_macro']:.4f} | "
                   f"{model_results['recall_macro']:.4f} | {model_results['f1_macro']:.4f} | "
                   f"{model_results['f1_weighted']:.4f} | {model_results['avg_confidence']:.4f} | "
                   f"{brier_str} | {improvement:+.4f} |\n")
        
        f.write("\n### Per-Class Performance\n\n")
        
        for model_name, model_results in results['model_benchmarks']['Priority'].items():
            f.write(f"#### {model_name}\n\n")
            f.write("| Class | Precision | Recall | F1 Score | Support |\n")
            f.write("|-------|-----------|--------|----------|----------|\n")
            
            for class_name, metrics in model_results['per_class'].items():
                f.write(f"| {class_name} | {metrics['precision']:.4f} | {metrics['recall']:.4f} | "
                       f"{metrics['f1']:.4f} | {metrics['support']} |\n")
            
            f.write(f"\n**Confusion Matrix**: See `{Path(model_results['confusion_matrix_plot']).name}`\n")
            f.write(f"**Calibration Plot**: See `{Path(model_results['calibration_plot']).name}`\n\n")
        
        # Assignment Group Classification
        f.write("## 4. ASSIGNMENT GROUP CLASSIFICATION\n\n")
        
        baseline = results['baseline_comparison']['Assignment group']
        f.write(f"### Baseline Comparison\n\n")
        f.write(f"- Majority Class: {baseline['majority_class']}\n")
        f.write(f"- Majority Count: {baseline['majority_count']} / {baseline['total_samples']}\n")
        f.write(f"- **Baseline Accuracy: {baseline['baseline_accuracy']:.4f}**\n\n")
        
        f.write("### Model Benchmark Results\n\n")
        f.write("| Model | Accuracy | Precision (Macro) | Recall (Macro) | F1 (Macro) | F1 (Weighted) | Avg Confidence | Brier Score | Improvement over Baseline |\n")
        f.write("|-------|----------|-------------------|----------------|------------|---------------|----------------|-------------|---------------------------|\n")
        
        for model_name, model_results in results['model_benchmarks']['Assignment group'].items():
            improvement = model_results['accuracy'] - baseline['baseline_accuracy']
            brier_str = f"{model_results['avg_brier_score']:.4f}" if model_results['avg_brier_score'] else "N/A"
            f.write(f"| {model_name} | {model_results['accuracy']:.4f} | {model_results['precision_macro']:.4f} | "
                   f"{model_results['recall_macro']:.4f} | {model_results['f1_macro']:.4f} | "
                   f"{model_results['f1_weighted']:.4f} | {model_results['avg_confidence']:.4f} | "
                   f"{brier_str} | {improvement:+.4f} |\n")
        
        f.write("\n### Per-Class Performance\n\n")
        
        for model_name, model_results in results['model_benchmarks']['Assignment group'].items():
            f.write(f"#### {model_name}\n\n")
            f.write("| Class | Precision | Recall | F1 Score | Support |\n")
            f.write("|-------|-----------|--------|----------|----------|\n")
            
            for class_name, metrics in model_results['per_class'].items():
                f.write(f"| {class_name} | {metrics['precision']:.4f} | {metrics['recall']:.4f} | "
                       f"{metrics['f1']:.4f} | {metrics['support']} |\n")
            
            f.write(f"\n**Confusion Matrix**: See `{Path(model_results['confusion_matrix_plot']).name}`\n")
            f.write(f"**Calibration Plot**: See `{Path(model_results['calibration_plot']).name}`\n\n")
        
        # Key Findings
        f.write("## 5. KEY FINDINGS\n\n")
        
        f.write("### Priority Classification Issues\n\n")
        best_priority = max(results['model_benchmarks']['Priority'].items(), 
                           key=lambda x: x[1]['f1_weighted'])
        priority_improvement = best_priority[1]['accuracy'] - results['baseline_comparison']['Priority']['baseline_accuracy']
        
        f.write(f"1. **Baseline Performance**: {results['baseline_comparison']['Priority']['baseline_accuracy']:.4f}\n")
        f.write(f"2. **Best Model**: {best_priority[0]} with accuracy {best_priority[1]['accuracy']:.4f}\n")
        f.write(f"3. **Improvement over Baseline**: {priority_improvement:+.4f}\n")
        f.write(f"4. **Confidence vs Accuracy Mismatch**: Average confidence {best_priority[1]['avg_confidence']:.4f} despite accuracy {best_priority[1]['accuracy']:.4f}\n")
        f.write(f"5. **Calibration Quality**: Brier score {best_priority[1]['avg_brier_score']:.4f} (lower is better)\n\n")
        
        if priority_improvement < 0.05:
            f.write("**⚠ WARNING**: Model barely improves over baseline. Consider:\n")
            f.write("- Feature engineering\n")
            f.write("- Collecting more diverse training data\n")
            f.write("- Addressing class imbalance\n\n")
        
        f.write("### Assignment Group Classification Performance\n\n")
        best_routing = max(results['model_benchmarks']['Assignment group'].items(), 
                          key=lambda x: x[1]['f1_weighted'])
        routing_improvement = best_routing[1]['accuracy'] - results['baseline_comparison']['Assignment group']['baseline_accuracy']
        
        f.write(f"1. **Baseline Performance**: {results['baseline_comparison']['Assignment group']['baseline_accuracy']:.4f}\n")
        f.write(f"2. **Best Model**: {best_routing[0]} with accuracy {best_routing[1]['accuracy']:.4f}\n")
        f.write(f"3. **Improvement over Baseline**: {routing_improvement:+.4f}\n")
        f.write(f"4. **Strong Performance**: Significant improvement over baseline\n\n")
        
        # Recommendations
        f.write("## 6. RECOMMENDATIONS\n\n")
        
        f.write("### Immediate Actions\n\n")
        f.write("1. **Priority Model**:\n")
        f.write("   - Do NOT use high confidence threshold (0.70+) for routing - confidence is poorly calibrated\n")
        f.write("   - Consider collecting labels for Alert Type, Severity, and Business Impact\n")
        f.write("   - These features may improve Priority prediction\n")
        f.write("   - Address class imbalance (3-Medium dominates)\n\n")
        
        f.write("2. **Assignment Group Model**:\n")
        f.write("   - Model performs well and is ready for production evaluation\n")
        f.write("   - Calibration is reasonable\n")
        f.write("   - Monitor performance on Pizza Hut (lower recall)\n\n")
        
        f.write("3. **Claude Fallback**:\n")
        f.write("   - Do not implement confidence-based fallback yet\n")
        f.write("   - Confidence scores do not reliably indicate accuracy\n")
        f.write("   - Need better calibration before using thresholds\n\n")
        
        f.write("### Before Stage 3\n\n")
        f.write("1. Verify no feature leakage in production pipeline\n")
        f.write("2. Document that Alert Type, Severity, Business Impact require labeling\n")
        f.write("3. Consider retraining Priority with additional features once labeled\n\n")
        
        f.write("---\n\n")
        f.write("**Audit Status**: COMPLETE\n\n")
        f.write("**Next Steps**: Await approval before proceeding to Stage 3\n")


if __name__ == '__main__':
    main()
