"""
Abstract base class for alert source adapters.

This interface allows the system to ingest alerts from various sources
(Excel, OpsRamp, ThousandEyes, Data Hub, etc.) using a consistent API.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class AlertSourceAdapter(ABC):
    """
    Abstract base class for alert source adapters.
    
    Each alert source (Excel, monitoring platform API, webhook, etc.)
    implements this interface to provide raw alert data.
    """
    
    @abstractmethod
    def read_alerts(self) -> List[Dict[str, Any]]:
        """
        Read raw alerts from the source.
        
        Returns:
            List of alert dictionaries with raw field names and values.
            
        Raises:
            Exception: If reading from source fails.
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """
        Get the name of this alert source.
        
        Returns:
            Human-readable source name (e.g., "Excel", "OpsRamp", "ThousandEyes").
        """
        pass
    
    @abstractmethod
    def get_total_count(self) -> int:
        """
        Get the total count of alerts available from this source.
        
        Returns:
            Total number of alerts.
        """
        pass
