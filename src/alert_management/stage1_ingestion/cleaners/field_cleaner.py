"""
Field cleaner for removing empty, null, and useless fields from raw alerts.
"""

from typing import Dict, Any, List


class FieldCleaner:
    """
    Cleans raw alert dictionaries by removing empty and useless fields.
    """
    
    def __init__(self, exclude_fields: List[str] = None):
        """
        Initialize field cleaner.
        
        Args:
            exclude_fields: List of field names to always exclude.
        """
        self.exclude_fields = set(exclude_fields or [])
    
    def clean(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean a single alert by removing empty/null/excluded fields.
        
        Args:
            alert: Raw alert dictionary.
            
        Returns:
            Cleaned alert dictionary.
        """
        cleaned = {}
        
        for key, value in alert.items():
            # Skip excluded fields
            if key in self.exclude_fields:
                continue
            
            # Skip None values
            if value is None:
                continue
            
            # Skip empty strings
            if isinstance(value, str) and not value.strip():
                continue
            
            # Skip empty lists/dicts
            if isinstance(value, (list, dict)) and len(value) == 0:
                continue
            
            # Keep the field
            cleaned[key] = value
        
        # Clean nested metadata if present
        if 'metadata' in cleaned and isinstance(cleaned['metadata'], dict):
            cleaned_metadata = {}
            for key, value in cleaned['metadata'].items():
                # Skip excluded fields
                if key in self.exclude_fields:
                    continue
                # Skip None/empty
                if value is None:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                cleaned_metadata[key] = value
            
            if cleaned_metadata:
                cleaned['metadata'] = cleaned_metadata
            else:
                # Remove empty metadata dict
                del cleaned['metadata']
        
        return cleaned
    
    def clean_batch(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean a batch of alerts.
        
        Args:
            alerts: List of raw alert dictionaries.
            
        Returns:
            List of cleaned alert dictionaries.
        """
        return [self.clean(alert) for alert in alerts]
