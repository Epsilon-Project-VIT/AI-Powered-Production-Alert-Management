"""
Stage 1 Pipeline: End-to-end alert ingestion, cleaning, validation, and normalization.
"""

from typing import List, Dict, Any
from datetime import datetime
import pandas as pd

from .adapters.base import AlertSourceAdapter
from .cleaners.field_cleaner import FieldCleaner
from .cleaners.normalizer import Normalizer
from .validators.alert_validator import AlertValidator
from .schemas import StandardizedAlert


class Stage1Pipeline:
    """
    Orchestrates the complete Stage 1 pipeline:
    1. Ingest alerts from source
    2. Clean fields (remove empty/null)
    3. Validate required fields
    4. Normalize descriptions
    5. Create StandardizedAlert objects
    """
    
    def __init__(
        self,
        field_cleaner: FieldCleaner,
        normalizer: Normalizer,
        validator: AlertValidator
    ):
        """
        Initialize Stage 1 pipeline.
        
        Args:
            field_cleaner: Field cleaner instance.
            normalizer: Text normalizer instance.
            validator: Alert validator instance.
        """
        self.field_cleaner = field_cleaner
        self.normalizer = normalizer
        self.validator = validator
    
    def ingest(self, source_adapter: AlertSourceAdapter) -> List[Dict[str, Any]]:
        """
        Ingest raw alerts from source adapter.
        
        Args:
            source_adapter: Alert source adapter instance.
            
        Returns:
            List of raw alert dictionaries.
        """
        print(f"[Stage 1] Ingesting alerts from: {source_adapter.get_source_name()}")
        raw_alerts = source_adapter.read_alerts()
        print(f"[Stage 1] Ingested {len(raw_alerts)} raw alerts")
        return raw_alerts
    
    def clean(self, raw_alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean raw alerts by removing empty/null fields.
        
        Args:
            raw_alerts: List of raw alert dictionaries.
            
        Returns:
            List of cleaned alert dictionaries.
        """
        print(f"[Stage 1] Cleaning {len(raw_alerts)} alerts...")
        cleaned_alerts = self.field_cleaner.clean_batch(raw_alerts)
        print(f"[Stage 1] Cleaned {len(cleaned_alerts)} alerts")
        return cleaned_alerts
    
    def validate(self, cleaned_alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate cleaned alerts for required fields.
        
        Args:
            cleaned_alerts: List of cleaned alert dictionaries.
            
        Returns:
            List of validated alert dictionaries.
            
        Raises:
            AlertValidationError: If validation fails.
        """
        print(f"[Stage 1] Validating {len(cleaned_alerts)} alerts...")
        validated_alerts = self.validator.validate_batch(cleaned_alerts)
        print(f"[Stage 1] Validated {len(validated_alerts)} alerts")
        return validated_alerts
    
    def normalize(self, validated_alerts: List[Dict[str, Any]]) -> List[StandardizedAlert]:
        """
        Normalize validated alerts and create StandardizedAlert objects.
        
        Args:
            validated_alerts: List of validated alert dictionaries.
            
        Returns:
            List of StandardizedAlert objects.
        """
        print(f"[Stage 1] Normalizing {len(validated_alerts)} alerts...")
        standardized_alerts = []
        
        for alert in validated_alerts:
            # Normalize the description
            raw_description = alert['raw_description']
            normalized_description = self.normalizer.normalize(raw_description)
            
            # Convert created_at to datetime if needed
            created_at = alert['created_at']
            if isinstance(created_at, pd.Timestamp):
                created_at = created_at.to_pydatetime()
            elif not isinstance(created_at, datetime):
                created_at = pd.to_datetime(created_at).to_pydatetime()
            
            # Create StandardizedAlert
            standardized_alert = StandardizedAlert(
                alert_id=str(alert['alert_id']),
                created_at=created_at,
                client=str(alert['client']),
                raw_description=str(raw_description),
                normalized_description=normalized_description,
                metadata=alert.get('metadata')
            )
            
            standardized_alerts.append(standardized_alert)
        
        print(f"[Stage 1] Normalized {len(standardized_alerts)} alerts")
        return standardized_alerts
    
    def run(self, source_adapter: AlertSourceAdapter) -> List[StandardizedAlert]:
        """
        Run the complete Stage 1 pipeline end-to-end.
        
        Args:
            source_adapter: Alert source adapter instance.
            
        Returns:
            List of StandardizedAlert objects.
        """
        print("=" * 80)
        print("STAGE 1: ALERT INGESTION & NORMALIZATION")
        print("=" * 80)
        
        # Step 1: Ingest
        raw_alerts = self.ingest(source_adapter)
        
        # Step 2: Clean
        cleaned_alerts = self.clean(raw_alerts)
        
        # Step 3: Validate
        validated_alerts = self.validate(cleaned_alerts)
        
        # Step 4: Normalize
        standardized_alerts = self.normalize(validated_alerts)
        
        print("=" * 80)
        print(f"[Stage 1] Pipeline complete: {len(standardized_alerts)} standardized alerts")
        print("=" * 80)
        
        return standardized_alerts
