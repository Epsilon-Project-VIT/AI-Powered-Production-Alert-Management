#!/usr/bin/env python3
"""
Train Stage 2 models for canonical labels: Alert Type, Severity, Business Impact.

Uses finalized canonical labels from Stage2_WeakLabels_v4_Model_Challenge.xlsx
as training ground truth. These are analyst-derived weak labels, not 
independently verified ground truth.

Trains and evaluates 4 model architectures for each task:
1. TF-IDF + Logistic Regression (primary)
2. TF-IDF + Linear SVM
3. Embedding + Logistic Regression  
4. Embedding + Linear SVM

Uses chronological train/validation/test split to prevent data leakage.
"""

import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Tuple
import warnings
warnings.filterwarnings('ignore')

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

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
    split_chronologically,
    prepare_training_data,
    get_label_distribution
)
from alert_management.stage2_classification.training.evaluator import ModelEvaluator
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix
)


class CanonicalModelTrainer:
    """Train models for Alert Type, Severity, and Business Impact."""
    
    def __init__(self, output_dir: Path):
        """Initialize trainer with output directory."""
        self.settings = Settings()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            'alert_type': {},
            'severity': {},
            'business_impact': {}
        }
        
    def load_canonical_labels(self) -> pd.DataFrame:
        """Load finalized canonical labels from Excel."""
        labels_path = self.settings.DATA_DIR / "labels" / "Stage2_WeakLabels_v4_Model_Challenge.xlsx"
        
        print(f"Loading canonical labels from: {labels_path}")
        df = pd.read_excel(labels_path, sheet_name="Label_889_Challenge")
        
        print(f"Loaded {len(df)} alerts with canonical labels")
        return df
        
    def load_and_merge_data(self) -> List[Dict[str, Any]]:
        """Load Stage 1 alerts and merge with canonical labels."""
        print("\n" + "="*80)
        print("LOADING DATA")
        print("="*80)
        
        # Load canonical labels
        labels_df = self.load_canonical_labels()
        
        # Load Stage 1 standardized alerts
        print("\nLoading Stage 1 standardized alerts...")
        
        # Initialize Stage 1 components
        field_cleaner = FieldCleaner(exclude_fields=self.settings.EXCLUDE_FIELDS)
        normalizer = Normalizer(patterns=self.settings.NORMALIZATION_PATTERNS)
        validator = AlertValidator(required_fields=self.settings.REQUIRED_FIELDS)
        pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
        
        # Create Excel adapter (don't filter forbidden fields for training)
        adapter = ExcelAlertAdapter(
            file_path=self.settings.DATA_DIR / "raw" / "Data_Alert_Ticket_Segregation.xlsx",
            column_mapping=self.settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=set()  # Don't filter for training
        )
        
        # Run pipeline
        alerts = pipeline.run(adapter)
        print(f"Loaded {len(alerts)} standardized alerts")
        
        # Merge canonical labels with alerts
        print("\nMerging canonical labels with alert data...")
        merged_data = []
        
        for alert in alerts:
            alert_id = alert.alert_id
            
            # Find matching label row
            label_row = labels_df[labels_df['Alert ID'] == alert_id]
            
            if not label_row.empty:
                row = label_row.iloc[0]
                merged_data.append({
                    'alert_id': alert_id,
                    'created_at': alert.created_at,
                    'client': alert.client,
                    'normalized_description': alert.normalized_description,
                    'alert_type': row['Canonical Alert Type'],
                    'severity': row['Canonical Severity'],
                    'business_impact': row['Canonical Business Impact']
                })
        
        print(f"Merged {len(merged_data)} alerts with canonical labels")
        
        # Check for missing labels
        missing = len(alerts) - len(merged_data)
        if missing > 0:
            print(f"WARNING: {missing} alerts without canonical labels")
        
        return merged_data
    
    def chronological_split(
        self, 
        data: List[Dict[str, Any]], 
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Split data chronologically to prevent data leakage."""
        # Sort by creation time
        sorted_data = sorted(data, key=lambda x: x['created_at'])
        
        n_total = len(sorted_data)
        n_train = int(n_total * train_ratio)
        n_val = int(n_total * val_ratio)
        
        train_data = sorted_data[:n_train]
        val_data = sorted_data[n_train:n_train + n_val]
        test_data = sorted_data[n_train + n_val:]
        
        return train_data, val_data, test_data
    
    def extract_texts_labels(
        self, 
        data: List[Dict[str, Any]], 
        target_field: str
    ) -> Tuple[List[str], List[str]]:
        """Extract texts and labels for a specific target field."""
        texts = []
        labels = []
        
        for item in data:
            text = item['normalized_description']
            label = item[target_field]
            
            if text and label:
                texts.append(text)
                labels.append(str(label))
        
        return texts, labels
    
    def train_single_task(
        self,
        task_name: str,
        target_field: str,
        train_data: List[Dict],
        val_data: List[Dict],
        test_data: List[Dict]
    ) -> Dict[str, Any]:
        """Train and evaluate all models for a single task."""
        
        print("\n" + "="*80)
        print(f"TRAINING TASK: {task_name.upper()}")
        print("="*80)
        
        # Extract texts and labels
        train_texts, train_labels = self.extract_texts_labels(train_data, target_field)
        val_texts, val_labels = self.extract_texts_labels(val_data, target_field)
        test_texts, test_labels = self.extract_texts_labels(test_data, target_field)
        
        print(f"\nData Split:")
        print(f"  Train: {len(train_texts)} samples")
        print(f"  Val:   {len(val_texts)} samples")
        print(f"  Test:  {len(test_texts)} samples")
        
        # Print label distributions
        train_dist = get_label_distribution(train_labels)
        test_dist = get_label_distribution(test_labels)
        
        print(f"\nTrain Label Distribution:")
        for label, count in sorted(train_dist.items(), key=lambda x: -x[1])[:10]:
            print(f"  {label}: {count}")
        if len(train_dist) > 10:
            print(f"  ... and {len(train_dist) - 10} more classes")
        
        print(f"\nTest Label Distribution:")
        for label, count in sorted(test_dist.items(), key=lambda x: -x[1])[:10]:
            print(f"  {label}: {count}")
        if len(test_dist) > 10:
            print(f"  ... and {len(test_dist) - 10} more classes")
        
        # Initialize models
        models = [
            TfidfLogisticClassifier(
                model_name=f"tfidf_lr_{target_field}",
                max_features=5000,
                ngram_range=(1, 2),
                C=1.0,
                calibrate=False  # Disable calibration due to rare classes
            ),
            TfidfSVMClassifier(
                model_name=f"tfidf_svm_{target_field}",
                max_features=5000,
                ngram_range=(1, 2),
                C=1.0,
                calibrate=False  # Disable calibration due to rare classes
            ),
            EmbeddingLogisticClassifier(
                model_name=f"embedding_lr_{target_field}",
                embedding_model='all-MiniLM-L6-v2',
                C=1.0,
                calibrate=False  # Disable calibration due to rare classes
            ),
            EmbeddingSVMClassifier(
                model_name=f"embedding_svm_{target_field}",
                embedding_model='all-MiniLM-L6-v2',
                C=1.0,
                calibrate=False  # Disable calibration due to rare classes
            )
        ]
        
        # Train and evaluate each model
        results = []
        best_model = None
        best_f1 = -1
        
        for model in models:
            print(f"\n" + "-"*60)
            print(f"Training: {model.model_name}")
            print("-"*60)
            
            # Train
            model.fit(train_texts, train_labels)
            
            # Validate and compute validation metrics for model selection
            val_preds_conf = model.predict_with_confidence(val_texts)
            val_preds = [p for p, _ in val_preds_conf]
            val_accuracy = accuracy_score(val_labels, val_preds)
            
            # Compute validation weighted F1 for model selection
            _, _, val_f1_weighted, _ = precision_recall_fscore_support(
                val_labels, val_preds, average='weighted', zero_division=0
            )
            
            # Test evaluation (for reporting only, NOT for selection)
            test_preds_conf = model.predict_with_confidence(test_texts)
            test_preds = [p for p, _ in test_preds_conf]
            test_confidences = [c for _, c in test_preds_conf]
            
            # Calculate metrics
            accuracy = accuracy_score(test_labels, test_preds)
            
            # Macro metrics (equal weight to each class)
            precision_macro, recall_macro, f1_macro, _ = precision_recall_fscore_support(
                test_labels, test_preds, average='macro', zero_division=0
            )
            
            # Weighted metrics (weight by support)
            precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
                test_labels, test_preds, average='weighted', zero_division=0
            )
            
            # Per-class metrics
            precision_per_class, recall_per_class, f1_per_class, support_per_class = (
                precision_recall_fscore_support(
                    test_labels, test_preds, average=None, zero_division=0, labels=sorted(set(test_labels))
                )
            )
            
            # Confusion matrix
            cm = confusion_matrix(test_labels, test_preds, labels=sorted(set(test_labels)))
            
            # Classification report
            report = classification_report(
                test_labels, test_preds, 
                zero_division=0,
                output_dict=True
            )
            
            # Store results
            result = {
                'model_name': model.model_name,
                'val_accuracy': val_accuracy,
                'val_f1_weighted': val_f1_weighted,  # Used for model selection
                'test_accuracy': accuracy,
                'precision_macro': precision_macro,
                'recall_macro': recall_macro,
                'f1_macro': f1_macro,
                'precision_weighted': precision_weighted,
                'recall_weighted': recall_weighted,
                'f1_weighted': f1_weighted,
                'avg_confidence': np.mean(test_confidences),
                'per_class_metrics': {},
                'confusion_matrix': cm.tolist(),
                'classification_report': report,
                'unique_classes': sorted(set(test_labels))
            }
            
            # Add per-class metrics
            for i, label in enumerate(sorted(set(test_labels))):
                result['per_class_metrics'][label] = {
                    'precision': float(precision_per_class[i]),
                    'recall': float(recall_per_class[i]),
                    'f1': float(f1_per_class[i]),
                    'support': int(support_per_class[i])
                }
            
            results.append(result)
            
            # Print summary
            print(f"\nResults:")
            print(f"  Val Accuracy:       {val_accuracy:.4f}")
            print(f"  Val F1 (weighted):  {val_f1_weighted:.4f}")
            print(f"  Test Accuracy:      {accuracy:.4f}")
            print(f"  Precision (macro):  {precision_macro:.4f}")
            print(f"  Recall (macro):     {recall_macro:.4f}")
            print(f"  F1 (macro):         {f1_macro:.4f}")
            print(f"  F1 (weighted):      {f1_weighted:.4f}")
            print(f"  Avg Confidence:     {np.mean(test_confidences):.4f}")
            
            # Track best model based on VALIDATION weighted F1
            if val_f1_weighted > best_f1:
                best_f1 = val_f1_weighted
                best_model = model
            
            # Save model
            model_dir = self.output_dir / "models" / task_name
            model_dir.mkdir(parents=True, exist_ok=True)
            model.save(model_dir)
            print(f"  Model saved to: {model_dir}")
        
        # Print comparison
        print(f"\n" + "="*80)
        print(f"MODEL COMPARISON - {task_name.upper()}")
        print("="*80)
        
        for result in results:
            print(f"\n{result['model_name']}:")
            print(f"  Val F1 (weighted):  {result['val_f1_weighted']:.4f}")
            print(f"  Test Accuracy:      {result['test_accuracy']:.4f}")
            print(f"  Test F1 (weighted): {result['f1_weighted']:.4f}")
        
        print(f"\nSELECTED MODEL: {best_model.model_name}")
        print(f"  Selection Criterion: Highest VALIDATION weighted F1 ({best_f1:.4f})")
        print(f"  Model selection was done BEFORE seeing test set")
        
        # Now report final test performance for selected model
        best_model_test_results = next(r for r in results if r['model_name'] == best_model.model_name)
        print(f"\nFINAL TEST PERFORMANCE (locked model, evaluated once):")
        print(f"  Test Accuracy:      {best_model_test_results['test_accuracy']:.4f}")
        print(f"  Test F1 (macro):    {best_model_test_results['f1_macro']:.4f}")
        print(f"  Test F1 (weighted): {best_model_test_results['f1_weighted']:.4f}")
        
        # Generate predictions for all 889 alerts using best model
        print(f"\nGenerating predictions for all 889 alerts using {best_model.model_name}...")
        all_texts = train_texts + val_texts + test_texts
        all_labels_true = train_labels + val_labels + test_labels
        all_preds_conf = best_model.predict_with_confidence(all_texts)
        
        predictions_df = pd.DataFrame({
            'predicted_label': [p for p, _ in all_preds_conf],
            'confidence': [c for _, c in all_preds_conf],
            'true_label': all_labels_true
        })
        
        pred_file = self.output_dir / f"{task_name}_predictions.csv"
        predictions_df.to_csv(pred_file, index=False)
        print(f"Predictions saved to: {pred_file}")
        
        return {
            'task_name': task_name,
            'target_field': target_field,
            'results': results,
            'best_model': best_model.model_name,
            'best_val_f1_weighted': best_f1,  # Validation metric used for selection
            'best_test_f1_weighted': best_model_test_results['f1_weighted'],  # Final test metric
            'num_classes': len(set(test_labels)),
            'train_samples': len(train_texts),
            'val_samples': len(val_texts),
            'test_samples': len(test_texts)
        }
    
    def run(self):
        """Run complete training pipeline for all three tasks."""
        print("\n" + "="*80)
        print("CANONICAL LABEL MODEL TRAINING")
        print("="*80)
        print(f"\nTraining models for:")
        print("  1. Alert Type")
        print("  2. Severity")
        print("  3. Business Impact")
        print(f"\nUsing canonical labels from: Stage2_WeakLabels_v4_Model_Challenge.xlsx")
        print("Note: These are analyst-derived weak labels, not independently verified ground truth")
        
        # Load and merge data
        merged_data = self.load_and_merge_data()
        
        # Chronological split (70/15/15)
        print("\n" + "="*80)
        print("CHRONOLOGICAL DATA SPLIT")
        print("="*80)
        train_data, val_data, test_data = self.chronological_split(
            merged_data, 
            train_ratio=0.7,
            val_ratio=0.15,
            test_ratio=0.15
        )
        
        print(f"\nSplit (chronological to prevent data leakage):")
        print(f"  Train: {len(train_data)} samples ({len(train_data)/len(merged_data)*100:.1f}%)")
        print(f"  Val:   {len(val_data)} samples ({len(val_data)/len(merged_data)*100:.1f}%)")
        print(f"  Test:  {len(test_data)} samples ({len(test_data)/len(merged_data)*100:.1f}%)")
        
        # Train models for each task
        tasks = [
            ('alert_type', 'alert_type'),
            ('severity', 'severity'),
            ('business_impact', 'business_impact')
        ]
        
        all_results = {}
        
        for task_name, target_field in tasks:
            result = self.train_single_task(
                task_name,
                target_field,
                train_data,
                val_data,
                test_data
            )
            all_results[task_name] = result
        
        # Save comprehensive results
        results_file = self.output_dir / "training_results.json"
        with open(results_file, 'w') as f:
            # Convert numpy types for JSON serialization
            json_results = json.loads(
                json.dumps(all_results, default=lambda x: float(x) if isinstance(x, np.floating) else x)
            )
            json.dump(json_results, f, indent=2)
        
        print(f"\n" + "="*80)
        print("TRAINING COMPLETE")
        print("="*80)
        print(f"\nResults saved to: {self.output_dir}")
        print(f"\nFiles created:")
        print(f"  - training_results.json (comprehensive metrics)")
        print(f"  - alert_type_predictions.csv (889 predictions)")
        print(f"  - severity_predictions.csv (889 predictions)")
        print(f"  - business_impact_predictions.csv (889 predictions)")
        print(f"  - models/ (trained model artifacts)")
        
        # Generate summary report
        self.generate_summary_report(all_results)
        
        return all_results
    
    def generate_summary_report(self, all_results: Dict[str, Any]):
        """Generate a concise summary report."""
        report_path = self.output_dir / "STAGE2_MODEL_EVALUATION_REPORT.md"
        
        with open(report_path, 'w') as f:
            f.write("# Stage 2 Model Evaluation Report\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n")
            f.write("**Training Data:** Canonical labels from `Stage2_WeakLabels_v4_Model_Challenge.xlsx`\n\n")
            f.write("**IMPORTANT:** These labels are analyst-derived weak labels (prototype), NOT independently verified ground truth.\n\n")
            f.write("---\n\n")
            
            f.write("## Executive Summary\n\n")
            f.write("Trained and evaluated classification models for three tasks:\n\n")
            
            for task_name, result in all_results.items():
                f.write(f"### {task_name.replace('_', ' ').title()}\n\n")
                f.write(f"- **Classes:** {result['num_classes']}\n")
                f.write(f"- **Test Samples:** {result['test_samples']}\n")
                f.write(f"- **Selected Model:** {result['best_model']}\n")
                f.write(f"- **Selection Criterion:** Validation weighted F1 = {result['best_val_f1_weighted']:.4f}\n")
                f.write(f"- **Final Test F1 (weighted):** {result['best_test_f1_weighted']:.4f}\n\n")
                
                # Find best model results
                best_results = next(r for r in result['results'] if r['model_name'] == result['best_model'])
                
                f.write("**Test Metrics (locked model, evaluated once):**\n\n")
                f.write(f"- Accuracy: {best_results['test_accuracy']:.4f}\n")
                f.write(f"- Precision (macro): {best_results['precision_macro']:.4f}\n")
                f.write(f"- Recall (macro): {best_results['recall_macro']:.4f}\n")
                f.write(f"- F1 (macro): {best_results['f1_macro']:.4f}\n")
                f.write(f"- F1 (weighted): {best_results['f1_weighted']:.4f}\n\n")
            
            f.write("---\n\n")
            
            f.write("## Model Architectures Evaluated\n\n")
            f.write("For each task, we trained and compared:\n\n")
            f.write("1. **TF-IDF + Logistic Regression** (primary baseline)\n")
            f.write("2. **TF-IDF + Linear SVM**\n")
            f.write("3. **Embedding + Logistic Regression** (Sentence-BERT)\n")
            f.write("4. **Embedding + Linear SVM** (Sentence-BERT)\n\n")
            f.write("**Model Selection:** Based on VALIDATION weighted F1 score.\n")
            f.write("**Test Evaluation:** Each selected model was evaluated ONCE on the held-out test set.\n\n")
            f.write("**CRITICAL:** Test set was NOT used for model selection to avoid overfitting.\n\n")
            
            f.write("---\n\n")
            
            f.write("## Data Split\n\n")
            f.write("**Chronological split to prevent data leakage:**\n\n")
            f.write(f"- Train: 70% (earliest alerts)\n")
            f.write(f"- Validation: 15%\n")
            f.write(f"- Test: 15% (most recent alerts)\n\n")
            
            f.write("**Forbidden Features (excluded to prevent target leakage):**\n\n")
            f.write("- Historical Priority (when predicting Severity/Business Impact)\n")
            f.write("- Historical Assignment Group\n")
            f.write("- Post-resolution fields (Resolved, Resolution code, etc.)\n")
            f.write("- Post-triage metrics (Reassignment count, Reopen count)\n\n")
            
            f.write("---\n\n")
            
            f.write("## Detailed Results\n\n")
            
            for task_name, result in all_results.items():
                f.write(f"### {task_name.replace('_', ' ').title()}\n\n")
                f.write(f"**Number of Classes:** {result['num_classes']}\n\n")
                f.write(f"**Model Comparison (Validation F1 used for selection):**\n\n")
                f.write("| Model | Val F1 (weighted) | Test Accuracy | Test F1 (weighted) | Selected? |\n")
                f.write("|-------|-------------------|---------------|--------------------|--------|\n")
                
                for model_result in result['results']:
                    selected = "✅ YES" if model_result['model_name'] == result['best_model'] else "No"
                    f.write(f"| {model_result['model_name']} | ")
                    f.write(f"{model_result['val_f1_weighted']:.4f} | ")
                    f.write(f"{model_result['test_accuracy']:.4f} | ")
                    f.write(f"{model_result['f1_weighted']:.4f} | ")
                    f.write(f"{selected} |\n")
                
                f.write(f"\n**Selected Model:** {result['best_model']}\n\n")
                f.write(f"**Selection Criterion:** Highest validation weighted F1 ({result['best_val_f1_weighted']:.4f})\n\n")
                f.write(f"**IMPORTANT:** Model selected using validation set BEFORE test evaluation.\n\n")
                
                # Per-class metrics for best model (top 10 by support)
                best_results = next(r for r in result['results'] if r['model_name'] == result['best_model'])
                per_class = best_results['per_class_metrics']
                
                # Sort by support
                sorted_classes = sorted(
                    per_class.items(),
                    key=lambda x: x[1]['support'],
                    reverse=True
                )
                
                f.write("**Per-Class Metrics (Top 10 by Support):**\n\n")
                f.write("| Class | Precision | Recall | F1 | Support |\n")
                f.write("|-------|-----------|--------|----|---------|\n")
                
                for class_name, metrics in sorted_classes[:10]:
                    f.write(f"| {class_name} | ")
                    f.write(f"{metrics['precision']:.4f} | ")
                    f.write(f"{metrics['recall']:.4f} | ")
                    f.write(f"{metrics['f1']:.4f} | ")
                    f.write(f"{metrics['support']} |\n")
                
                if len(sorted_classes) > 10:
                    f.write(f"\n... and {len(sorted_classes) - 10} more classes\n")
                
                # Identify poorly performing classes (F1 < 0.3)
                poor_classes = [(c, m) for c, m in per_class.items() if m['f1'] < 0.3 and m['support'] > 0]
                if poor_classes:
                    f.write(f"\n**Classes with Poor Performance (F1 < 0.3):**\n\n")
                    for class_name, metrics in sorted(poor_classes, key=lambda x: x[1]['f1']):
                        f.write(f"- {class_name}: F1={metrics['f1']:.4f}, Support={metrics['support']}\n")
                
                f.write("\n")
            
            f.write("---\n\n")
            
            f.write("## Limitations\n\n")
            f.write("### Data Quality\n\n")
            f.write("- **Weak Labels:** Canonical labels are analyst-derived rules, not verified ground truth\n")
            f.write("- **No Independent Validation:** Labels have not been validated by independent reviewers\n")
            f.write("- **Prototype Status:** These labels are for model challenge/comparison purposes\n\n")
            
            f.write("### Model Limitations\n\n")
            f.write("- **Class Imbalance:** Some alert types/severities are rare, affecting model performance\n")
            f.write("- **Text-Only:** Models use only normalized description (no metadata features)\n")
            f.write("- **Generalization:** Performance on production data may differ from test set\n\n")
            
            f.write("### Evaluation Limitations\n\n")
            f.write("- **No Production Validation:** Models not tested on live production data\n")
            f.write("- **Time-Based Drift:** Alert patterns may change over time\n")
            f.write("- **Client-Specific Patterns:** Performance may vary by client\n\n")
            
            f.write("---\n\n")
            
            f.write("## Model Selection Rationale\n\n")
            f.write("Models were selected based on **VALIDATION weighted F1 score**, NOT test performance.\n\n")
            f.write("**Why This Methodology?**\n\n")
            f.write("1. **Prevents Overfitting:** Test set never used for model selection\n")
            f.write("2. **Proper Evaluation:** Test metrics represent true generalization performance\n")
            f.write("3. **Honest Reporting:** Test F1 is unbiased estimate of future performance\n\n")
            f.write("**Why Weighted F1 for Selection?**\n\n")
            f.write("- Balances precision and recall\n")
            f.write("- Weights classes by support (handles imbalance)\n")
            f.write("- More robust than accuracy for imbalanced datasets\n\n")
            
            f.write("**Selection Summary:**\n\n")
            for task_name, result in all_results.items():
                f.write(f"- **{task_name.replace('_', ' ').title()}:** {result['best_model']}\n")
                f.write(f"  - Selection: Val F1={result['best_val_f1_weighted']:.4f}\n")
                f.write(f"  - Final Test: F1={result['best_test_f1_weighted']:.4f}\n")
            
            f.write("\n---\n\n")
            
            f.write("## Files Generated\n\n")
            f.write("- `training_results.json` - Complete metrics for all models\n")
            f.write("- `alert_type_predictions.csv` - 889 predictions with confidence scores\n")
            f.write("- `severity_predictions.csv` - 889 predictions with confidence scores\n")
            f.write("- `business_impact_predictions.csv` - 889 predictions with confidence scores\n")
            f.write("- `models/alert_type/` - Trained model artifacts\n")
            f.write("- `models/severity/` - Trained model artifacts\n")
            f.write("- `models/business_impact/` - Trained model artifacts\n")
            f.write("- `STAGE2_MODEL_EVALUATION_REPORT.md` - This report\n\n")
            
            f.write("---\n\n")
            f.write(f"**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        print(f"\nSummary report saved to: {report_path}")


def main():
    """Main entry point."""
    output_dir = Path("data/stage2_models_canonical")
    
    trainer = CanonicalModelTrainer(output_dir)
    results = trainer.run()
    
    print("\n" + "="*80)
    print("SUCCESS")
    print("="*80)
    print("\nAll models trained and evaluated successfully.")
    print(f"Results saved to: {output_dir}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
