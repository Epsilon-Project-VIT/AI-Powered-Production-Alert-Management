"""
Model training orchestration for Stage 2.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import time

from ..models.base import BaseClassifier


class ModelTrainer:
    """
    Orchestrates the training of Stage 2 classification models.
    
    Handles training, validation, and saving of models with
    experiment tracking support.
    """
    
    def __init__(self, experiment_name: Optional[str] = None):
        """
        Initialize the model trainer.
        
        Args:
            experiment_name: Optional name for MLflow experiment tracking
        """
        self.experiment_name = experiment_name or "stage2_classification"
        self.training_history = []
    
    def train_model(
        self,
        model: BaseClassifier,
        train_texts: List[str],
        train_labels: List[str],
        val_texts: Optional[List[str]] = None,
        val_labels: Optional[List[str]] = None,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Train a single classification model.
        
        Args:
            model: Initialized model to train
            train_texts: Training texts
            train_labels: Training labels
            val_texts: Optional validation texts
            val_labels: Optional validation labels
            save_path: Optional path to save trained model
        
        Returns:
            Dict with training metrics and metadata
        """
        if len(train_texts) != len(train_labels):
            raise ValueError("train_texts and train_labels must have the same length")
        
        if val_texts is not None and val_labels is not None:
            if len(val_texts) != len(val_labels):
                raise ValueError("val_texts and val_labels must have the same length")
        
        print(f"\n{'=' * 60}")
        print(f"Training {model.model_name}")
        print(f"{'=' * 60}")
        print(f"Training samples: {len(train_texts)}")
        print(f"Unique labels: {len(set(train_labels))}")
        
        # Train the model
        start_time = time.time()
        model.fit(train_texts, train_labels)
        training_time = time.time() - start_time
        
        print(f"Training completed in {training_time:.2f} seconds")
        
        # Prepare metrics
        metrics = {
            'model_name': model.model_name,
            'training_samples': len(train_texts),
            'unique_labels': len(set(train_labels)),
            'training_time_seconds': training_time,
            'is_trained': model.is_trained
        }
        
        # Evaluate on training data
        train_predictions = model.predict_with_confidence(train_texts)
        train_accuracy = sum(
            pred == true for (pred, _), true in zip(train_predictions, train_labels)
        ) / len(train_labels)
        metrics['train_accuracy'] = train_accuracy
        print(f"Training accuracy: {train_accuracy:.4f}")
        
        # Evaluate on validation data if provided
        if val_texts is not None and val_labels is not None:
            val_predictions = model.predict_with_confidence(val_texts)
            val_accuracy = sum(
                pred == true for (pred, _), true in zip(val_predictions, val_labels)
            ) / len(val_labels)
            metrics['val_accuracy'] = val_accuracy
            metrics['val_samples'] = len(val_texts)
            print(f"Validation accuracy: {val_accuracy:.4f}")
        
        # Save model if path provided
        if save_path is not None:
            model.save(save_path)
            metrics['saved_to'] = str(save_path)
            print(f"Model saved to: {save_path}")
        
        # Store in training history
        self.training_history.append(metrics)
        
        print(f"{'=' * 60}\n")
        
        return metrics
    
    def train_multiple_models(
        self,
        models: List[BaseClassifier],
        train_texts: List[str],
        train_labels: List[str],
        val_texts: Optional[List[str]] = None,
        val_labels: Optional[List[str]] = None,
        save_path: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """
        Train multiple models on the same data for benchmarking.
        
        Args:
            models: List of initialized models to train
            train_texts: Training texts
            train_labels: Training labels
            val_texts: Optional validation texts
            val_labels: Optional validation labels
            save_path: Optional path to save trained models
        
        Returns:
            List of training metrics for each model
        """
        results = []
        
        print(f"\n{'#' * 60}")
        print(f"Training {len(models)} models for benchmarking")
        print(f"{'#' * 60}\n")
        
        for model in models:
            metrics = self.train_model(
                model,
                train_texts,
                train_labels,
                val_texts,
                val_labels,
                save_path
            )
            results.append(metrics)
        
        # Print comparison summary
        self._print_comparison_summary(results)
        
        return results
    
    def _print_comparison_summary(self, results: List[Dict[str, Any]]) -> None:
        """Print a comparison summary of multiple model training runs."""
        print(f"\n{'=' * 60}")
        print("MODEL COMPARISON SUMMARY")
        print(f"{'=' * 60}")
        
        for metrics in results:
            print(f"\n{metrics['model_name']}:")
            print(f"  Train Accuracy: {metrics['train_accuracy']:.4f}")
            if 'val_accuracy' in metrics:
                print(f"  Val Accuracy:   {metrics['val_accuracy']:.4f}")
            print(f"  Training Time:  {metrics['training_time_seconds']:.2f}s")
        
        # Find best model based on validation accuracy (or training if no val)
        if 'val_accuracy' in results[0]:
            best_model = max(results, key=lambda x: x['val_accuracy'])
            metric_name = 'val_accuracy'
        else:
            best_model = max(results, key=lambda x: x['train_accuracy'])
            metric_name = 'train_accuracy'
        
        print(f"\nBest Model: {best_model['model_name']}")
        print(f"  {metric_name}: {best_model[metric_name]:.4f}")
        print(f"{'=' * 60}\n")
    
    def get_training_history(self) -> List[Dict[str, Any]]:
        """
        Get the training history for all models trained in this session.
        
        Returns:
            List of training metrics dicts
        """
        return self.training_history
