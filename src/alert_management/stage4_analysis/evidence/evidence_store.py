"""
Evidence Store - Central repository for RCA evidence.

Manages all evidence collected during Stage 4 analysis with full provenance tracking.
"""

from typing import List, Dict, Optional, Set
from datetime import datetime

from alert_management.stage4_analysis.schemas import Evidence, SourceType


class EvidenceStore:
    """
    Central evidence store for RCA analysis.
    
    Maintains provenance, supports filtering, deduplication, and sorting.
    """
    
    def __init__(self):
        """Initialize empty evidence store."""
        self._evidence: List[Evidence] = []
        self._evidence_ids: Set[str] = set()
    
    def add_evidence(self, evidence: Evidence) -> None:
        """
        Add single piece of evidence.
        
        Args:
            evidence: Evidence to add
        """
        # Check for duplicate source_id
        if evidence.source_id in self._evidence_ids:
            # Already exists, skip
            return
        
        self._evidence.append(evidence)
        self._evidence_ids.add(evidence.source_id)
    
    def add_bulk(self, evidence_list: List[Evidence]) -> None:
        """
        Add multiple pieces of evidence.
        
        Args:
            evidence_list: List of evidence to add
        """
        for evidence in evidence_list:
            self.add_evidence(evidence)
    
    def get_all(self) -> List[Evidence]:
        """
        Get all evidence.
        
        Returns:
            List of all evidence
        """
        return self._evidence.copy()
    
    def filter_by_source(self, source: str) -> List[Evidence]:
        """
        Filter evidence by source type.
        
        Args:
            source: Source to filter (e.g., "logs", "metrics", "traces")
            
        Returns:
            Filtered evidence list
        """
        return [e for e in self._evidence if e.source == source]
    
    def filter_by_source_type(self, source_type: SourceType) -> List[Evidence]:
        """
        Filter evidence by source_type provenance.
        
        Args:
            source_type: Source type to filter
            
        Returns:
            Filtered evidence list
        """
        return [e for e in self._evidence if e.source_type == source_type]
    
    def filter_by_component(self, component: str) -> List[Evidence]:
        """
        Filter evidence by component.
        
        Args:
            component: Component name
            
        Returns:
            Filtered evidence list
        """
        result = []
        for e in self._evidence:
            if e.metadata and "component" in e.metadata:
                if e.metadata["component"] == component:
                    result.append(e)
        return result
    
    def filter_by_timestamp_range(
        self,
        start: datetime,
        end: datetime
    ) -> List[Evidence]:
        """
        Filter evidence by timestamp range.
        
        Args:
            start: Start timestamp
            end: End timestamp
            
        Returns:
            Evidence within time range
        """
        return [
            e for e in self._evidence
            if e.timestamp and start <= e.timestamp <= end
        ]
    
    def get_mock_evidence(self) -> List[Evidence]:
        """
        Get all mock evidence.
        
        Returns:
            List of mock evidence
        """
        return [e for e in self._evidence if e.is_mock]
    
    def get_real_evidence(self) -> List[Evidence]:
        """
        Get all real evidence (non-mock).
        
        Returns:
            List of real evidence
        """
        return [e for e in self._evidence if not e.is_mock]
    
    def sort_by_weight(self, descending: bool = True) -> List[Evidence]:
        """
        Sort evidence by weight.
        
        Args:
            descending: If True, highest weight first
            
        Returns:
            Sorted evidence list
        """
        return sorted(
            self._evidence,
            key=lambda e: e.weight,
            reverse=descending
        )
    
    def sort_by_timestamp(self, ascending: bool = True) -> List[Evidence]:
        """
        Sort evidence by timestamp.
        
        Args:
            ascending: If True, earliest first
            
        Returns:
            Sorted evidence list (evidence without timestamps last)
        """
        with_timestamp = [e for e in self._evidence if e.timestamp]
        without_timestamp = [e for e in self._evidence if not e.timestamp]
        
        sorted_with_timestamp = sorted(
            with_timestamp,
            key=lambda e: e.timestamp,
            reverse=not ascending
        )
        
        return sorted_with_timestamp + without_timestamp
    
    def get_summary(self) -> Dict[str, any]:
        """
        Get summary statistics.
        
        Returns:
            Dictionary with counts and breakdowns
        """
        total = len(self._evidence)
        mock_count = len(self.get_mock_evidence())
        real_count = len(self.get_real_evidence())
        
        # Count by source
        source_counts: Dict[str, int] = {}
        for e in self._evidence:
            source_counts[e.source] = source_counts.get(e.source, 0) + 1
        
        # Count by source_type
        source_type_counts: Dict[str, int] = {}
        for e in self._evidence:
            st = e.source_type.value
            source_type_counts[st] = source_type_counts.get(st, 0) + 1
        
        return {
            "total_evidence": total,
            "mock_evidence": mock_count,
            "real_evidence": real_count,
            "by_source": source_counts,
            "by_source_type": source_type_counts
        }
    
    def clear(self) -> None:
        """Clear all evidence."""
        self._evidence.clear()
        self._evidence_ids.clear()
    
    def __len__(self) -> int:
        """Return number of evidence items."""
        return len(self._evidence)
