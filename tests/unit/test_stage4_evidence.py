"""Tests for Evidence Store."""

import pytest
from datetime import datetime, timedelta

from alert_management.stage4_analysis.schemas import Evidence, SourceType
from alert_management.stage4_analysis.evidence import EvidenceStore


class TestEvidenceStore:
    """Test EvidenceStore."""
    
    @pytest.fixture
    def sample_evidence(self):
        """Create sample evidence."""
        base_time = datetime.now()
        
        return [
            Evidence(
                source="logs",
                source_type=SourceType.MOCK,
                source_id="ev1",
                is_mock=True,
                timestamp=base_time,
                description="Error in database",
                weight=0.8,
                metadata={"component": "database"}
            ),
            Evidence(
                source="metrics",
                source_type=SourceType.MOCK,
                source_id="ev2",
                is_mock=True,
                timestamp=base_time + timedelta(minutes=5),
                description="High CPU usage",
                weight=0.7,
                metadata={"component": "application"}
            ),
            Evidence(
                source="logs",
                source_type=SourceType.HISTORICAL_ALERT,
                source_id="ev3",
                is_mock=False,
                timestamp=base_time + timedelta(minutes=10),
                description="Connection timeout",
                weight=0.9,
                metadata={"component": "database"}
            )
        ]
    
    def test_add_evidence(self, sample_evidence):
        """Test adding evidence."""
        store = EvidenceStore()
        store.add_evidence(sample_evidence[0])
        
        assert len(store) == 1
        assert store.get_all()[0].source_id == "ev1"
    
    def test_add_bulk(self, sample_evidence):
        """Test bulk add."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        assert len(store) == 3
    
    def test_deduplication(self, sample_evidence):
        """Test evidence deduplication."""
        store = EvidenceStore()
        store.add_evidence(sample_evidence[0])
        store.add_evidence(sample_evidence[0])  # Duplicate
        
        assert len(store) == 1
    
    def test_filter_by_source(self, sample_evidence):
        """Test filtering by source."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        logs = store.filter_by_source("logs")
        assert len(logs) == 2
        assert all(e.source == "logs" for e in logs)
    
    def test_filter_by_source_type(self, sample_evidence):
        """Test filtering by source_type."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        mock_evidence = store.filter_by_source_type(SourceType.MOCK)
        assert len(mock_evidence) == 2
    
    def test_filter_by_component(self, sample_evidence):
        """Test filtering by component."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        db_evidence = store.filter_by_component("database")
        assert len(db_evidence) == 2
    
    def test_filter_by_timestamp_range(self, sample_evidence):
        """Test timestamp filtering."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        base_time = sample_evidence[0].timestamp
        end_time = base_time + timedelta(minutes=7)
        
        filtered = store.filter_by_timestamp_range(base_time, end_time)
        assert len(filtered) == 2
    
    def test_get_mock_evidence(self, sample_evidence):
        """Test getting mock evidence."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        mock = store.get_mock_evidence()
        assert len(mock) == 2
        assert all(e.is_mock for e in mock)
    
    def test_get_real_evidence(self, sample_evidence):
        """Test getting real evidence."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        real = store.get_real_evidence()
        assert len(real) == 1
        assert not real[0].is_mock
    
    def test_sort_by_weight(self, sample_evidence):
        """Test sorting by weight."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        sorted_evidence = store.sort_by_weight(descending=True)
        assert sorted_evidence[0].weight == 0.9
        assert sorted_evidence[-1].weight == 0.7
    
    def test_sort_by_timestamp(self, sample_evidence):
        """Test sorting by timestamp."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        sorted_evidence = store.sort_by_timestamp(ascending=True)
        assert sorted_evidence[0].source_id == "ev1"
        assert sorted_evidence[-1].source_id == "ev3"
    
    def test_get_summary(self, sample_evidence):
        """Test summary statistics."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        summary = store.get_summary()
        assert summary["total_evidence"] == 3
        assert summary["mock_evidence"] == 2
        assert summary["real_evidence"] == 1
        assert summary["by_source"]["logs"] == 2
        assert summary["by_source"]["metrics"] == 1
    
    def test_clear(self, sample_evidence):
        """Test clearing store."""
        store = EvidenceStore()
        store.add_bulk(sample_evidence)
        
        assert len(store) == 3
        store.clear()
        assert len(store) == 0
