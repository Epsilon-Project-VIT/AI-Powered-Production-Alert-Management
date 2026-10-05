"""
Abstract interfaces for telemetry providers.

These interfaces define the contract for log, metric, and trace providers.
Implementations can be mock (for development) or real (for production).
"""

from abc import ABC, abstractmethod
from typing import List
from datetime import datetime

from ..schemas import LogRecord, MetricRecord, TraceSpan, IncidentContext


class LogProvider(ABC):
    """
    Abstract interface for log data providers.
    
    Implementations must support querying logs by:
    - Incident context (time window, components, services)
    - Alert IDs
    - Component names
    """
    
    @abstractmethod
    def get_logs(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None,
        levels: List[str] = None
    ) -> List[LogRecord]:
        """
        Retrieve logs for the given context and time range.
        
        Args:
            context: Incident context with alert and component information
            start_time: Start of diagnostic window
            end_time: End of diagnostic window
            components: Optional filter by component names
            levels: Optional filter by log levels (e.g., ['ERROR', 'WARN'])
        
        Returns:
            List of LogRecord objects with provenance
        """
        pass


class MetricProvider(ABC):
    """
    Abstract interface for metric data providers.
    
    Implementations must support querying metrics by:
    - Time range
    - Component names
    - Metric names
    """
    
    @abstractmethod
    def get_metrics(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None,
        metric_names: List[str] = None
    ) -> List[MetricRecord]:
        """
        Retrieve metrics for the given context and time range.
        
        Args:
            context: Incident context
            start_time: Start of diagnostic window
            end_time: End of diagnostic window
            components: Optional filter by component names
            metric_names: Optional filter by specific metrics
        
        Returns:
            List of MetricRecord objects with provenance
        """
        pass


class TraceProvider(ABC):
    """
    Abstract interface for distributed trace providers.
    
    Implementations must support querying traces by:
    - Time range
    - Service/component names
    - Trace IDs
    """
    
    @abstractmethod
    def get_traces(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None
    ) -> List[TraceSpan]:
        """
        Retrieve trace spans for the given context and time range.
        
        Args:
            context: Incident context
            start_time: Start of diagnostic window
            end_time: End of diagnostic window
            components: Optional filter by component names
        
        Returns:
            List of TraceSpan objects with provenance
        """
        pass
