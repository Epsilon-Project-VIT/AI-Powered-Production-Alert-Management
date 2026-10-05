"""
Model evaluation utilities for Stage 2.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix
)

from ..models.base import BaseClassifier


class ModelEvaluator:
    """
    Evaluates Stage 2 classification models.
    
    Provides comprehensive metrics including accuracy, precision,
    recall, F1, and confusion matrix.
    """
    
    def __init__(self):
        """Initialize the model evaluator."""
        self.evaluation_results = []
    
    def evaluate_model(
        self,
        model: BaseClassifier,
        test_texts: List[str],
        test_labels: List[str],
        confidence_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a trained model on test data.
        
        Args:
            model: Trained classifier
            test_texts: Test texts
            test_labels: Ground truth labels
            confidence_threshold: Optional threshold for high-confidence predictions
        
        Returns:
            Dict with comprehensive evaluation metrics
        """
        if not model.is_trained:
            raise ValueError(f"Model {model.model_name} has not been trained")
        
        if len(test_texts) != len(test_labels):
            raise ValueError("test_texts and test_labels must have the same length")
        
        print(f"\n{'=' * 60}")
        print(f"Evaluating {model.model_name}")
        print(f"{'=' * 60}")
        print(f"Test samples: {len(test_texts)}")
        
        # Get predictions with confidence
        predictions_with_conf = model.predict_with_confidence(test_texts)
        predictions = [pred for pred, _ in predictions_with_conf]
        confidences = [conf for _, conf in predictions_with_conf]
        
        # Calculate metrics
        accuracy = accuracy_score(test_labels, predictions)
        
        precision, recall, f1, support = precision_recall_fscore_support(
            test_labels,
            predictions,
            average='weighted',
            zero_division=0
        )
        
        # Get per-class metrics
        precision_per_class, recall_per_class, f1_per_class, support_per_class = (
            precision_recall_fscore_support(
                test_labels,
                predictions,
                average=None,
                zero_division=0
            )
        )
        
        metrics = {
            'model_name': model.model_name,
            'test_samples': len(test_texts),
            'accuracy': accuracy,
            'precision_weighted': precision,
            'recall_weighted': recall,
            'f1_weighted': f1,
            'avg_confidence': np.mean(confidences),
            'min_confidence': np.min(confidences),
            'max_confidence': np.max(confidences)
        }
        
        # Add per-class metrics
        unique_labels = sorted(set(test_labels))
        metrics['per_class_metrics'] = {}
        for i, label in enumerate(unique_labels):
            metrics['per_class_metrics'][label] = {
                'precision': float(precision_per_class[i]),
                'recall': float(recall_per_class[i]),
                'f1': float(f1_per_class[i]),
                'support': int(support_per_class[i])
            }
        
        # Confidence threshold analysis
        if confidence_threshold is not None:
            high_conf_indices = [
                i for i, conf in enumerate(confidences)
                if conf >= confidence_threshold
            ]
            
            if len(high_conf_indices) > 0:
                high_conf_preds = [predictions[i] for i in high_conf_indices]
                high_conf_labels = [test_labels[i] for i in high_conf_indices]
                high_conf_accuracy = accuracy_score(high_conf_labels, high_conf_preds)
                
                metrics['high_confidence_threshold'] = confidence_threshold
                metrics['high_confidence_samples'] = len(high_conf_indices)
                metrics['high_confidence_ratio'] = len(high_conf_indices) / len(test_texts)
                metrics['high_confidence_accuracy'] = high_conf_accuracy
        
        # Print summary
        self._print_evaluation_summary(metrics)
        
        # Store results
        self.evaluation_results.append(metrics)
        
        return metrics
    
    def _print_evaluation_summary(self, metrics: Dict[str, Any]) -> None:
        """Print evaluation summary."""
        print(f"\nOverall Metrics:")
        print(f"  Accuracy:  {metrics['accuracy']:.4f}")
        print(f"  Precision: {metrics['precision_weighted']:.4f}")
        print(f"  Recall:    {metrics['recall_weighted']:.4f}")
        print(f"  F1 Score:  {metrics['f1_weighted']:.4f}")
        
        print(f"\nConfidence Statistics:")
        print(f"  Average:   {metrics['avg_confidence']:.4f}")
        print(f"  Min:       {metrics['min_confidence']:.4f}")
        print(f"  Max:       {metrics['max_confidence']:.4f}")
        
        if 'high_confidence_threshold' in metrics:
            print(f"\nHigh Confidence Analysis (threshold={metrics['high_confidence_threshold']}):")
            print(f"  Samples:   {metrics['high_confidence_samples']} ({metrics['high_confidence_ratio']:.1%})")
            print(f"  Accuracy:  {metrics['high_confidence_accuracy']:.4f}")
        
        print(f"\nPer-Class Metrics:")
        for label, class_metrics in metrics['per_class_metrics'].items():
            print(f"  {label}:")
            print(f"    Precision: {class_metrics['precision']:.4f}")
            print(f"    Recall:    {class_metrics['recall']:.4f}")
            print(f"    F1 Score:  {class_metrics['f1']:.4f}")
            print(f"    Support:   {class_metrics['support']}")
        
        print(f"{'=' * 60}\n")
    
    def generate_classification_report(
        self,
        model: BaseClassifier,
        test_texts: List[str],
        test_labels: List[str]
    ) -> str:
        """
        Generate a detailed classification report.
        
        Args:
            model: Trained classifier
            test_texts: Test texts
            test_labels: Ground truth labels
        
        Returns:
            Classification report as string
        """
        if not model.is_trained:
            raise ValueError(f"Model {model.model_name} has not been trained")
        
        predictions = model.predict(test_texts)
        report = classification_report(test_labels, predictions, zero_division=0)
        
        return report
    
    def get_confusion_matrix(
        self,
        model: BaseClassifier,
        test_texts: List[str],
        test_labels: List[str]
    ) -> np.ndarray:
        """
        Generate confusion matrix.
        
        Args:
            model: Trained classifier
            test_texts: Test texts
            test_labels: Ground truth labels
        
        Returns:
            Confusion matrix as numpy array
        """
        if not model.is_trained:
            raise ValueError(f"Model {model.model_name} has not been trained")
        
        predictions = model.predict(test_texts)
        cm = confusion_matrix(test_labels, predictions)
        
        return cm
    
    def compare_models(
        self,
        models: List[BaseClassifier],
        test_texts: List[str],
        test_labels: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Compare multiple models on the same test set.
        
        Args:
            models: List of trained classifiers
            test_texts: Test texts
            test_labels: Ground truth labels
        
        Returns:
            List of evaluation metrics for each model
        """
        results = []
        
        print(f"\n{'#' * 60}")
        print(f"Comparing {len(models)} models")
        print(f"{'#' * 60}\n")
        
        for model in models:
            metrics = self.evaluate_model(model, test_texts, test_labels)
            results.append(metrics)
        
        # Print comparison summary
        self._print_comparison_summary(results)
        
        return results
    
    def _print_comparison_summary(self, results: List[Dict[str, Any]]) -> None:
        """Print comparison summary of multiple models."""
        print(f"\n{'=' * 60}")
        print("MODEL COMPARISON SUMMARY")
        print(f"{'=' * 60}")
        
        for metrics in results:
            print(f"\n{metrics['model_name']}:")
            print(f"  Accuracy:  {metrics['accuracy']:.4f}")
            print(f"  F1 Score:  {metrics['f1_weighted']:.4f}")
            print(f"  Avg Conf:  {metrics['avg_confidence']:.4f}")
        
        # Find best model
        best_model = max(results, key=lambda x: x['f1_weighted'])
        
        print(f"\nBest Model: {best_model['model_name']}")
        print(f"  F1 Score: {best_model['f1_weighted']:.4f}")
        print(f"{'=' * 60}\n")
    
    def get_evaluation_history(self) -> List[Dict[str, Any]]:
        """
        Get the evaluation history for all evaluations in this session.
        
        Returns:
            List of evaluation metrics dicts
        """
        return self.evaluation_results
