"""
Alert validator for ensuring required fields are present and valid.
"""

from typing import Dict, Any, List
from datetime import datetime
import pandas as pd


class AlertValidationError(Exception):
    """Raised when alert validation fails."""
    pass


class AlertValidator:
    """
    Validates that alerts contain all required fields with valid values.
    """
    
    def __init__(self, required_fields: List[str]):
        """
        Initialize validator with required fields.
        
        Args:
            required_fields: List of field names that must be present and non-empty.
        """
        self.required_fields = required_fields
    
    def validate(self, alert: Dict[str, Any]) -> None:
        """
        Validate a single alert.
        
        Args:
            alert: Alert dictionary to validate.
            
        Raises:
            AlertValidationError: If validation fails.
        """
        # Check required fields exist
        missing_fields = []
        for field in self.required_fields:
            if field not in alert:
                missing_fields.append(field)
        
        if missing_fields:
            raise AlertValidationError(
                f"Missing required fields: {missing_fields} in alert: {alert.get('alert_id', 'unknown')}"
            )
        
        # Validate alert_id
        alert_id = alert.get('alert_id')
        if not alert_id or (isinstance(alert_id, str) and not alert_id.strip()):
            raise AlertValidationError(
                f"alert_id is empty or invalid: {alert_id}"
            )
        
        # Validate created_at (must be valid datetime)
        created_at = alert.get('created_at')
        if created_at is None:
            raise AlertValidationError(
                f"created_at is None for alert: {alert_id}"
            )
        
        # Handle pandas Timestamp or datetime
        if isinstance(created_at, (pd.Timestamp, datetime)):
            # Valid timestamp
            pass
        else:
            # Try to parse as datetime
            try:
                if isinstance(created_at, str):
                    pd.to_datetime(created_at)
            except Exception as e:
                raise AlertValidationError(
                    f"created_at is not a valid datetime for alert {alert_id}: {created_at}. Error: {e}"
                )
        
        # Validate client
        client = alert.get('client')
        if not client or (isinstance(client, str) and not client.strip()):
            raise AlertValidationError(
                f"client is empty or invalid for alert: {alert_id}"
            )
        
        # Validate raw_description
        raw_description = alert.get('raw_description')
        if not raw_description or (isinstance(raw_description, str) and not raw_description.strip()):
            raise AlertValidationError(
                f"raw_description is empty or invalid for alert: {alert_id}"
            )
    
    def validate_batch(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate a batch of alerts.
        
        Args:
            alerts: List of alert dictionaries.
            
        Returns:
            List of validated alerts (only valid alerts are returned).
            
        Raises:
            AlertValidationError: If any alert fails validation.
        """
        validated = []
        errors = []
        
        for i, alert in enumerate(alerts):
            try:
                self.validate(alert)
                validated.append(alert)
            except AlertValidationError as e:
                errors.append(f"Alert {i}: {str(e)}")
        
        if errors:
            error_msg = "\n".join(errors)
            raise AlertValidationError(
                f"Validation failed for {len(errors)} alerts:\n{error_msg}"
            )
        
        return validated
