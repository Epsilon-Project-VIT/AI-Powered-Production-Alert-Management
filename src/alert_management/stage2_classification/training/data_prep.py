"""
Data preparation utilities for Stage 2 training.
"""

from typing import List, Tuple, Dict, Any
import pandas as pd
from datetime import datetime

from ...stage1_ingestion.schemas import StandardizedAlert


def prepare_training_data(
    alerts: List[StandardizedAlert],
    target_field: str
) -> Tuple[List[str], List[str]]:
    """
    Prepare training data from standardized alerts.
    
    Args:
        alerts: List of StandardizedAlert objects
        target_field: Name of the target field in metadata
                     (e.g., 'Priority', 'Assignment group')
    
    Returns:
        Tuple of (texts, labels) where:
        - texts: List of normalized alert descriptions
        - labels: List of target labels
    """
    texts = []
    labels = []
    
    for alert in alerts:
        # Use normalized description as input
        text = alert.normalized_description
        
        # Extract target label from metadata
        if alert.metadata and target_field in alert.metadata:
            label = alert.metadata[target_field]
            
            # Only include if we have both text and label
            if text and label:
                texts.append(text)
                labels.append(str(label))
    
    return texts, labels


def split_chronologically(
    alerts: List[StandardizedAlert],
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15
) -> Tuple[List[StandardizedAlert], List[StandardizedAlert], List[StandardizedAlert]]:
    """
    Split alerts chronologically into train/val/test sets.
    
    CRITICAL: Chronological splitting prevents data leakage by ensuring
    the model is evaluated on future alerts it hasn't seen during training.
    
    Args:
        alerts: List of StandardizedAlert objects
        train_ratio: Proportion of data for training
        val_ratio: Proportion of data for validation
        test_ratio: Proportion of data for testing
    
    Returns:
        Tuple of (train_alerts, val_alerts, test_alerts)
    """
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.001:
        raise ValueError("Ratios must sum to 1.0")
    
    # Sort alerts by creation time
    sorted_alerts = sorted(alerts, key=lambda a: a.created_at)
    
    n_total = len(sorted_alerts)
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)
    
    # Split chronologically
    train_alerts = sorted_alerts[:n_train]
    val_alerts = sorted_alerts[n_train:n_train + n_val]
    test_alerts = sorted_alerts[n_train + n_val:]
    
    return train_alerts, val_alerts, test_alerts


def get_label_distribution(labels: List[str]) -> Dict[str, int]:
    """
    Get the distribution of labels in a dataset.
    
    Args:
        labels: List of labels
    
    Returns:
        Dict mapping label to count
    """
    distribution = {}
    for label in labels:
        distribution[label] = distribution.get(label, 0) + 1
    
    return distribution


def filter_by_minimum_samples(
    texts: List[str],
    labels: List[str],
    min_samples: int = 5
) -> Tuple[List[str], List[str]]:
    """
    Filter out labels with fewer than min_samples examples.
    
    This prevents training issues with very rare classes.
    
    Args:
        texts: List of text samples
        labels: List of corresponding labels
        min_samples: Minimum number of samples required per label
    
    Returns:
        Tuple of (filtered_texts, filtered_labels)
    """
    # Count label occurrences
    label_counts = get_label_distribution(labels)
    
    # Filter labels with sufficient samples
    valid_labels = {label for label, count in label_counts.items() if count >= min_samples}
    
    # Filter the dataset
    filtered_texts = []
    filtered_labels = []
    
    for text, label in zip(texts, labels):
        if label in valid_labels:
            filtered_texts.append(text)
            filtered_labels.append(label)
    
    return filtered_texts, filtered_labels


def prepare_excel_training_data(
    excel_path: str,
    target_column: str,
    description_column: str = 'Short description'
) -> pd.DataFrame:
    """
    Prepare training data directly from Excel file.
    
    This is a convenience function for quick experimentation.
    For production, use Stage 1 pipeline to get StandardizedAlert objects.
    
    Args:
        excel_path: Path to Excel file
        target_column: Name of target column
        description_column: Name of description column
    
    Returns:
        DataFrame with 'text' and 'label' columns
    """
    df = pd.read_excel(excel_path)
    
    # Extract relevant columns
    if description_column not in df.columns:
        raise ValueError(f"Column '{description_column}' not found in Excel")
    
    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in Excel")
    
    # Create clean dataset
    data = df[[description_column, target_column]].copy()
    data.columns = ['text', 'label']
    
    # Remove rows with missing values
    data = data.dropna()
    
    # Remove empty strings
    data = data[data['text'].str.strip() != '']
    data = data[data['label'].astype(str).str.strip() != '']
    
    return data
