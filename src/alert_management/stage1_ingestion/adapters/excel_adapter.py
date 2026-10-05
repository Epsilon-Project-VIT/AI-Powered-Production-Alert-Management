"""
Excel adapter for reading historical ServiceNow alert/ticket data.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Set
from .base import AlertSourceAdapter


class ExcelAlertAdapter(AlertSourceAdapter):
    """
    Adapter for reading alerts from Excel files.
    
    Designed for the historical ServiceNow Data_Alert_Ticket_Segregation.xlsx
    dataset, but can be used for any Excel file with similar structure.
    """
    
    def __init__(
        self,
        file_path: Path,
        column_mapping: Dict[str, str],
        forbidden_metadata_fields: Set[str] = None
    ):
        """
        Initialize Excel adapter.
        
        Args:
            file_path: Path to Excel file.
            column_mapping: Mapping of Excel columns to standardized field names.
                Example: {"Number": "alert_id", "Created": "created_at", ...}
            forbidden_metadata_fields: Set of field names to exclude from metadata
                (e.g., target fields, post-resolution outcomes).
        """
        self.file_path = file_path
        self.column_mapping = column_mapping
        self.forbidden_metadata_fields = forbidden_metadata_fields or set()
        self._df: pd.DataFrame = None
        self._total_count: int = 0
        
    def read_alerts(self) -> List[Dict[str, Any]]:
        """
        Read alerts from Excel file.
        
        Returns:
            List of alert dictionaries with mapped field names.
            
        Raises:
            FileNotFoundError: If Excel file doesn't exist.
            ValueError: If required columns are missing.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {self.file_path}")
        
        # Read Excel file
        self._df = pd.read_excel(self.file_path)
        self._total_count = len(self._df)
        
        # Verify required columns exist
        missing_columns = set(self.column_mapping.keys()) - set(self._df.columns)
        if missing_columns:
            raise ValueError(
                f"Required columns missing from Excel: {missing_columns}"
            )
        
        # Convert to list of dictionaries
        # Keep all columns, but rename mapped ones
        alerts = []
        for _, row in self._df.iterrows():
            alert_dict = {}
            
            # Map specified columns
            for excel_col, std_col in self.column_mapping.items():
                value = row[excel_col]
                # Convert pandas NaT and NaN to None
                if pd.isna(value):
                    alert_dict[std_col] = None
                else:
                    alert_dict[std_col] = value
            
            # Add remaining columns to metadata (excluding forbidden fields)
            metadata = {}
            for col in self._df.columns:
                if col not in self.column_mapping:
                    # Skip forbidden target/post-resolution fields
                    if col in self.forbidden_metadata_fields:
                        continue
                    
                    value = row[col]
                    if not pd.isna(value):
                        metadata[col] = value
            
            if metadata:
                alert_dict['metadata'] = metadata
            
            alerts.append(alert_dict)
        
        return alerts
    
    def get_source_name(self) -> str:
        """Get source name."""
        return f"Excel:{self.file_path.name}"
    
    def get_total_count(self) -> int:
        """Get total alert count."""
        if self._df is None:
            # Read just to get count
            df = pd.read_excel(self.file_path)
            return len(df)
        return self._total_count
