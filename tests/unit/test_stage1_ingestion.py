"""
Unit tests for Stage 1: Alert Ingestion & Normalization
"""

import pytest
from datetime import datetime
from pathlib import Path
import pandas as pd

from src.alert_management.config.settings import Settings
from src.alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from src.alert_management.stage1_ingestion.cleaners.field_cleaner import FieldCleaner
from src.alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
from src.alert_management.stage1_ingestion.validators.alert_validator import (
    AlertValidator,
    AlertValidationError
)
from src.alert_management.stage1_ingestion.schemas import StandardizedAlert
from src.alert_management.stage1_ingestion.pipeline import Stage1Pipeline


class TestExcelAdapter:
    """Test Excel alert adapter."""
    
    def test_excel_adapter_reads_alerts(self):
        """Test that Excel adapter can read alerts from real dataset."""
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        alerts = adapter.read_alerts()
        
        assert len(alerts) == 889, "Should read 889 alerts from dataset"
        assert adapter.get_total_count() == 889
        assert "Excel:" in adapter.get_source_name()
    
    def test_excel_adapter_maps_columns(self):
        """Test that Excel adapter correctly maps columns."""
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        alerts = adapter.read_alerts()
        first_alert = alerts[0]
        
        # Check mapped fields exist
        assert 'alert_id' in first_alert
        assert 'created_at' in first_alert
        assert 'client' in first_alert
        assert 'raw_description' in first_alert
        
        # Check metadata exists and is safe
        assert 'metadata' in first_alert
        
        # CRITICAL: Verify NO forbidden fields in metadata
        if first_alert['metadata']:
            for forbidden_field in Settings.FORBIDDEN_METADATA_FIELDS:
                assert forbidden_field not in first_alert['metadata'], \
                    f"LEAKAGE: Forbidden field '{forbidden_field}' found in metadata"
    
    def test_excel_adapter_blocks_target_fields(self):
        """CRITICAL TEST: Verify that target/outcome fields are blocked from metadata."""
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        alerts = adapter.read_alerts()
        
        # Check all alerts for forbidden fields
        forbidden_found = set()
        for alert in alerts:
            if 'metadata' in alert and alert['metadata']:
                for forbidden_field in Settings.FORBIDDEN_METADATA_FIELDS:
                    if forbidden_field in alert['metadata']:
                        forbidden_found.add(forbidden_field)
        
        assert len(forbidden_found) == 0, \
            f"DATA LEAKAGE: Forbidden fields found in metadata: {forbidden_found}"
    
    def test_excel_adapter_missing_file(self):
        """Test that Excel adapter raises error for missing file."""
        adapter = ExcelAlertAdapter(
            file_path=Path("/nonexistent/file.xlsx"),
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        with pytest.raises(FileNotFoundError):
            adapter.read_alerts()


class TestFieldCleaner:
    """Test field cleaner."""
    
    def test_removes_none_values(self):
        """Test that cleaner removes None values."""
        cleaner = FieldCleaner()
        alert = {
            'alert_id': 'INC001',
            'client': 'TestClient',
            'empty_field': None
        }
        
        cleaned = cleaner.clean(alert)
        
        assert 'empty_field' not in cleaned
        assert 'alert_id' in cleaned
        assert 'client' in cleaned
    
    def test_removes_empty_strings(self):
        """Test that cleaner removes empty strings."""
        cleaner = FieldCleaner()
        alert = {
            'alert_id': 'INC001',
            'client': 'TestClient',
            'empty_string': '',
            'whitespace': '   '
        }
        
        cleaned = cleaner.clean(alert)
        
        assert 'empty_string' not in cleaned
        assert 'whitespace' not in cleaned
        assert 'alert_id' in cleaned
    
    def test_removes_excluded_fields(self):
        """Test that cleaner removes excluded fields."""
        cleaner = FieldCleaner(exclude_fields=['Activity due', 'Approval history'])
        alert = {
            'alert_id': 'INC001',
            'Activity due': 'some_value',
            'Approval history': 'some_value'
        }
        
        cleaned = cleaner.clean(alert)
        
        assert 'Activity due' not in cleaned
        assert 'Approval history' not in cleaned
        assert 'alert_id' in cleaned
    
    def test_cleans_nested_metadata(self):
        """Test that cleaner cleans nested metadata."""
        cleaner = FieldCleaner()
        alert = {
            'alert_id': 'INC001',
            'metadata': {
                'valid_field': 'value',
                'empty_field': None,
                'empty_string': ''
            }
        }
        
        cleaned = cleaner.clean(alert)
        
        assert 'metadata' in cleaned
        assert 'valid_field' in cleaned['metadata']
        assert 'empty_field' not in cleaned['metadata']
        assert 'empty_string' not in cleaned['metadata']


class TestNormalizer:
    """Test text normalizer."""
    
    def test_normalizes_timestamps(self):
        """Test that normalizer replaces timestamps."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        text = "Alert at 2026-08-06T11:06:00.412405759Z UTC"
        
        normalized = normalizer.normalize(text)
        
        assert '<timestamp>' in normalized
        assert '2026-08-06' not in normalized
    
    def test_normalizes_timestamps_various_formats(self):
        """Test normalizer handles various timestamp formats."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        
        timestamps = [
            "2026-08-06T11:06:00.412405759Z",
            "2026-08-06 11:06:00",
            "24-JUL-2026",
            "23-JUL-2026"
        ]
        
        for ts in timestamps:
            normalized = normalizer.normalize(f"Alert at {ts}")
            assert '<timestamp>' in normalized, f"Failed to normalize: {ts}"
            assert ts not in normalized
    
    def test_normalizes_ip_addresses(self):
        """Test that normalizer replaces IP addresses."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        
        # Test standard IP format
        text1 = "Server 192.168.1.100 is down"
        normalized1 = normalizer.normalize(text1)
        assert '<ip>' in normalized1
        assert '192.168.1.100' not in normalized1
        
        # Test dash-separated IP format
        text2 = "ip-10-226-100-18 is Unreachable"
        normalized2 = normalizer.normalize(text2)
        assert '<ip>' in normalized2
        assert '10-226-100-18' not in normalized2
    
    def test_normalizes_uuids(self):
        """Test that normalizer replaces UUIDs."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        text = "Request 7f3c8b1d-4a2e-4f6c-9d3a-1e8f7c2b5a9d failed"
        
        normalized = normalizer.normalize(text)
        
        assert '<uuid>' in normalized
        assert '7f3c8b1d' not in normalized
    
    def test_normalizes_large_numeric_ids(self):
        """Test that normalizer replaces large numeric IDs."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        text = "Transaction ID 12345678901234 failed"
        
        normalized = normalizer.normalize(text)
        
        assert '<id>' in normalized
        assert '12345678901234' not in normalized
    
    def test_normalizes_request_ids(self):
        """Test that normalizer replaces request IDs."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        text = "Request_ID: abc123xyz failed"
        
        normalized = normalizer.normalize(text)
        
        assert '<id>' in normalized
    
    def test_normalizes_priority_markers(self):
        """Test that normalizer standardizes priority markers while preserving distinction."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        text = "P1BGSN_API_ERR_CRITICAL"
        
        normalized = normalizer.normalize(text)
        
        # Should normalize to lowercase p1 (preserving the "1")
        assert 'p1' in normalized
        assert 'P1' not in normalized.upper() or normalized == normalized.lower()
    
    def test_preserves_priority_distinctions(self):
        """Test that normalizer preserves distinction between P1, P2, P3, P4."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        
        # Test each priority level
        tests = [
            ("P1 alert critical", "p1"),
            ("P2 alert high", "p2"),
            ("P3 alert medium", "p3"),
            ("P4 alert low", "p4"),
            ("P1BGSN service down", "p1bgsn"),
            ("P2EASS error", "p2eass"),
        ]
        
        for original, expected_token in tests:
            normalized = normalizer.normalize(original)
            assert expected_token in normalized, f"Expected '{expected_token}' in '{normalized}' for input '{original}'"
    
    def test_preserves_technical_identifiers(self):
        """Test that normalizer preserves meaningful technical identifiers."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        
        # Service names should be preserved
        text = "BGSN_Batch_Extract_Point_Redemption service failed"
        normalized = normalizer.normalize(text)
        assert 'bgsn_batch_extract_point_redemption' in normalized
        
        # API names should be preserved
        text2 = "EASS_ELB_ERRCHECK alert triggered"
        normalized2 = normalizer.normalize(text2)
        assert 'eass_elb_errcheck' in normalized2
    
    def test_preserves_semantic_business_signals(self):
        """Test that normalizer preserves semantic business/technical signals."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        
        # Words like CRITICAL, FAILURE, WARNING should be preserved
        text = "CRITICAL FAILURE in WARNING system"
        normalized = normalizer.normalize(text)
        assert 'critical' in normalized
        assert 'failure' in normalized
        assert 'warning' in normalized
    
    def test_converts_to_lowercase(self):
        """Test that normalizer converts to lowercase."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        text = "CRITICAL AutoTicket ALERT"
        
        normalized = normalizer.normalize(text)
        
        assert normalized.islower()
    
    def test_real_dataset_examples(self):
        """Test normalizer with real dataset examples."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        
        # Example 1: Bridgestone batch failure
        text1 = "Data Hub Alert (Workflow) : P1BGSN - BGSN_Batch_Extract_Point_Redemption_Delta_AZREWARDS - FAILURE"
        normalized1 = normalizer.normalize(text1)
        assert 'p1' in normalized1  # Preserves P1 distinction
        assert 'bgsn_batch_extract' in normalized1
        
        # Example 2: EA Sports ELB error with timestamp
        text2 = "ALERT - P1EASS_ELB_ERRCHECK - 2026-08-06T11:06:00.412405759Z UTC - 8 ELB errors"
        normalized2 = normalizer.normalize(text2)
        assert '<timestamp>' in normalized2
        assert 'p1' in normalized2  # Preserves P1 distinction
        assert '2026-08-06' not in normalized2


class TestAlertValidator:
    """Test alert validator."""
    
    def test_validates_required_fields(self):
        """Test that validator checks required fields."""
        validator = AlertValidator(required_fields=['alert_id', 'created_at', 'client', 'raw_description'])
        
        valid_alert = {
            'alert_id': 'INC001',
            'created_at': datetime.now(),
            'client': 'TestClient',
            'raw_description': 'Test alert'
        }
        
        # Should not raise
        validator.validate(valid_alert)
    
    def test_raises_on_missing_fields(self):
        """Test that validator raises error for missing fields."""
        validator = AlertValidator(required_fields=['alert_id', 'created_at', 'client', 'raw_description'])
        
        invalid_alert = {
            'alert_id': 'INC001',
            'client': 'TestClient'
            # missing created_at and raw_description
        }
        
        with pytest.raises(AlertValidationError) as exc_info:
            validator.validate(invalid_alert)
        
        assert 'Missing required fields' in str(exc_info.value)
    
    def test_raises_on_empty_alert_id(self):
        """Test that validator raises error for empty alert_id."""
        validator = AlertValidator(required_fields=['alert_id'])
        
        invalid_alert = {'alert_id': '   '}
        
        with pytest.raises(AlertValidationError) as exc_info:
            validator.validate(invalid_alert)
        
        assert 'alert_id is empty' in str(exc_info.value)
    
    def test_validates_datetime(self):
        """Test that validator accepts valid datetime."""
        validator = AlertValidator(required_fields=['alert_id', 'created_at', 'client', 'raw_description'])
        
        # Valid with datetime object
        alert1 = {
            'alert_id': 'INC001',
            'created_at': datetime.now(),
            'client': 'TestClient',
            'raw_description': 'Test alert'
        }
        validator.validate(alert1)
        
        # Valid with pandas Timestamp
        alert2 = {
            'alert_id': 'INC002',
            'created_at': pd.Timestamp.now(),
            'client': 'TestClient',
            'raw_description': 'Test alert'
        }
        validator.validate(alert2)


class TestStandardizedAlert:
    """Test StandardizedAlert Pydantic model."""
    
    def test_creates_valid_alert(self):
        """Test that StandardizedAlert can be created with valid data."""
        alert = StandardizedAlert(
            alert_id="INC3528892",
            created_at=datetime(2026, 8, 6, 2, 30, 2),
            client="Bridgestone",
            raw_description="Data Hub Alert (Workflow) : P1BGSN - FAILURE",
            normalized_description="data hub alert workflow p<priority>bgsn failure",
            metadata={"priority": "3 - Medium"}
        )
        
        assert alert.alert_id == "INC3528892"
        assert alert.client == "Bridgestone"
        assert alert.metadata['priority'] == "3 - Medium"
    
    def test_validates_empty_strings(self):
        """Test that StandardizedAlert validates empty strings."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            StandardizedAlert(
                alert_id="",  # Empty string
                created_at=datetime.now(),
                client="TestClient",
                raw_description="Test",
                normalized_description="test"
            )
    
    def test_strips_whitespace(self):
        """Test that StandardizedAlert strips whitespace."""
        alert = StandardizedAlert(
            alert_id="  INC001  ",
            created_at=datetime.now(),
            client="  TestClient  ",
            raw_description="  Test  ",
            normalized_description="  test  "
        )
        
        assert alert.alert_id == "INC001"
        assert alert.client == "TestClient"
        assert alert.raw_description == "Test"


class TestStage1Pipeline:
    """Test Stage 1 complete pipeline."""
    
    def test_pipeline_end_to_end(self):
        """Test complete pipeline with real dataset."""
        # Create pipeline components
        field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
        normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
        validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
        pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
        
        # Create adapter with forbidden fields filter
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        # Run pipeline
        standardized_alerts = pipeline.run(adapter)
        
        # Assertions
        assert len(standardized_alerts) == 889, "Should process all 889 alerts"
        assert all(isinstance(alert, StandardizedAlert) for alert in standardized_alerts)
        assert all(alert.normalized_description != alert.raw_description for alert in standardized_alerts)
    
    def test_pipeline_real_examples(self):
        """Test pipeline with specific real dataset examples."""
        # Create pipeline
        field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
        normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
        validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
        pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
        
        # Create adapter with forbidden fields filter
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        # Run pipeline
        standardized_alerts = pipeline.run(adapter)
        
        # Find specific examples by alert_id
        alerts_by_id = {alert.alert_id: alert for alert in standardized_alerts}
        
        # Test INC3528892 (Bridgestone)
        if 'INC3528892' in alerts_by_id:
            bridgestone_alert = alerts_by_id['INC3528892']
            assert bridgestone_alert.client == 'Bridgestone'
            assert 'p1' in bridgestone_alert.normalized_description  # P1 preserved
            assert 'batch' in bridgestone_alert.normalized_description.lower()
        
        # Test INC3528891 (EA Sports)
        if 'INC3528891' in alerts_by_id:
            ea_alert = alerts_by_id['INC3528891']
            assert ea_alert.client == 'EA Sports'
            assert 'p1' in ea_alert.normalized_description  # P1 preserved
        
        # Test INC3528890 (Pizza Hut)
        if 'INC3528890' in alerts_by_id:
            pizza_alert = alerts_by_id['INC3528890']
            assert pizza_alert.client == 'Pizza Hut'
    
    def test_end_to_end_contract(self):
        """
        INTEGRATION TEST: End-to-end contract validation.
        
        Proves:
        - Excel 889 rows → Stage1Pipeline
        - 889 StandardizedAlert objects produced
        - All objects satisfy Pydantic contract
        - NO target/post-resolution leakage in metadata
        """
        # Create pipeline
        field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
        normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
        validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
        pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
        
        # Create adapter with forbidden fields filter
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        # Run pipeline
        standardized_alerts = pipeline.run(adapter)
        
        # Contract verification
        assert len(standardized_alerts) == 889, "Must process exactly 889 alerts"
        
        # Verify every alert
        for alert in standardized_alerts:
            # 1. Must be StandardizedAlert instance (Pydantic validation)
            assert isinstance(alert, StandardizedAlert)
            
            # 2. Required fields present
            assert alert.alert_id
            assert alert.created_at
            assert alert.client
            assert alert.raw_description
            assert alert.normalized_description
            
            # 3. Normalization happened
            assert alert.normalized_description.islower()
            assert alert.normalized_description != alert.raw_description
            
            # 4. CRITICAL: NO target/post-resolution leakage
            if alert.metadata:
                for forbidden_field in Settings.FORBIDDEN_METADATA_FIELDS:
                    assert forbidden_field not in alert.metadata, \
                        f"DATA LEAKAGE: Alert {alert.alert_id} has forbidden field '{forbidden_field}' in metadata"
    
    def test_client_coverage_pizza_hut(self):
        """Verify representative Pizza Hut alerts are processed correctly."""
        # Create pipeline
        field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
        normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
        validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
        pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
        
        # Create adapter
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        # Run pipeline
        standardized_alerts = pipeline.run(adapter)
        
        # Filter Pizza Hut alerts
        pizza_hut_alerts = [a for a in standardized_alerts if a.client == 'Pizza Hut']
        
        # Verify count matches dataset (427 Pizza Hut alerts)
        assert len(pizza_hut_alerts) == 427
        
        # Verify representative example (INC3528890)
        alerts_by_id = {a.alert_id: a for a in pizza_hut_alerts}
        if 'INC3528890' in alerts_by_id:
            alert = alerts_by_id['INC3528890']
            assert 'pzht' in alert.normalized_description
            assert 'unified' in alert.normalized_description or 'alert' in alert.normalized_description
    
    def test_client_coverage_ea_sports(self):
        """Verify representative EA Sports alerts are processed correctly."""
        # Create pipeline
        field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
        normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
        validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
        pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
        
        # Create adapter
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        # Run pipeline
        standardized_alerts = pipeline.run(adapter)
        
        # Filter EA Sports alerts
        ea_alerts = [a for a in standardized_alerts if a.client == 'EA Sports']
        
        # Verify count matches dataset (243 EA Sports alerts)
        assert len(ea_alerts) == 243
        
        # Verify representative example (INC3528891)
        alerts_by_id = {a.alert_id: a for a in ea_alerts}
        if 'INC3528891' in alerts_by_id:
            alert = alerts_by_id['INC3528891']
            assert 'eass' in alert.normalized_description
            assert 'elb' in alert.normalized_description or 'err' in alert.normalized_description
    
    def test_client_coverage_bridgestone(self):
        """Verify representative Bridgestone alerts are processed correctly."""
        # Create pipeline
        field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
        normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
        validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
        pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
        
        # Create adapter
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        # Run pipeline
        standardized_alerts = pipeline.run(adapter)
        
        # Filter Bridgestone alerts
        bridgestone_alerts = [a for a in standardized_alerts if a.client == 'Bridgestone']
        
        # Verify count matches dataset (219 Bridgestone alerts)
        assert len(bridgestone_alerts) == 219
        
        # Verify representative example (INC3528892)
        alerts_by_id = {a.alert_id: a for a in bridgestone_alerts}
        if 'INC3528892' in alerts_by_id:
            alert = alerts_by_id['INC3528892']
            assert 'bgsn' in alert.normalized_description
            assert 'batch' in alert.normalized_description or 'extract' in alert.normalized_description



class TestAdapterBaseClass:
    """Test abstract base class methods."""
    
    def test_adapter_interface_compliance(self):
        """Test that Excel adapter implements all required interface methods."""
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        # Verify all abstract methods are implemented
        assert hasattr(adapter, 'read_alerts')
        assert hasattr(adapter, 'get_source_name')
        assert hasattr(adapter, 'get_total_count')
        
        # Test get_total_count before reading
        count = adapter.get_total_count()
        assert count == 889
        
        # Test get_source_name
        source = adapter.get_source_name()
        assert 'Excel' in source
        assert 'Data_Alert_Ticket_Segregation.xlsx' in source


class TestFieldCleanerEdgeCases:
    """Test field cleaner edge cases."""
    
    def test_cleaner_with_empty_metadata(self):
        """Test that cleaner removes empty metadata dict."""
        cleaner = FieldCleaner()
        alert = {
            'alert_id': 'INC001',
            'metadata': {}
        }
        
        cleaned = cleaner.clean(alert)
        
        assert 'metadata' not in cleaned or cleaned.get('metadata') is None
    
    def test_cleaner_batch_processing(self):
        """Test that cleaner processes batches correctly."""
        cleaner = FieldCleaner()
        alerts = [
            {'alert_id': 'INC001', 'empty': None, 'valid': 'data'},
            {'alert_id': 'INC002', 'empty': '', 'valid': 'data'},
            {'alert_id': 'INC003', 'valid': 'data'}
        ]
        
        cleaned = cleaner.clean_batch(alerts)
        
        assert len(cleaned) == 3
        assert all('valid' in alert for alert in cleaned)
        assert all('empty' not in alert for alert in cleaned)


class TestNormalizerBatchProcessing:
    """Test normalizer batch operations."""
    
    def test_normalizer_batch(self):
        """Test that normalizer processes batches correctly."""
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        texts = [
            "Alert at 2026-08-06T11:06:00Z",
            "Server 192.168.1.1 down",
            "P1 CRITICAL alert"
        ]
        
        normalized = normalizer.normalize_batch(texts)
        
        assert len(normalized) == 3
        assert '<timestamp>' in normalized[0]
        assert '<ip>' in normalized[1]
        assert 'p1' in normalized[2]  # P1 preserved as p1


class TestValidatorBatchErrors:
    """Test validator batch error handling."""
    
    def test_validator_reports_multiple_errors(self):
        """Test that validator reports all batch errors."""
        validator = AlertValidator(required_fields=['alert_id', 'created_at', 'client', 'raw_description'])
        
        # Multiple invalid alerts
        alerts = [
            {'alert_id': 'INC001'},  # Missing fields
            {'alert_id': 'INC002'},  # Missing fields
            {'alert_id': '', 'created_at': datetime.now(), 'client': 'Test', 'raw_description': 'Test'}  # Empty alert_id
        ]
        
        with pytest.raises(AlertValidationError) as exc_info:
            validator.validate_batch(alerts)
        
        error_message = str(exc_info.value)
        assert 'Alert 0' in error_message or 'Alert 1' in error_message or 'Alert 2' in error_message
    
    def test_validator_invalid_datetime_string(self):
        """Test validator handles invalid datetime strings."""
        validator = AlertValidator(required_fields=['alert_id', 'created_at', 'client', 'raw_description'])
        
        alert = {
            'alert_id': 'INC001',
            'created_at': 'not-a-date',
            'client': 'Test',
            'raw_description': 'Test'
        }
        
        with pytest.raises(AlertValidationError) as exc_info:
            validator.validate(alert)
        
        assert 'not a valid datetime' in str(exc_info.value)
    
    def test_validator_none_created_at(self):
        """Test validator catches None created_at."""
        validator = AlertValidator(required_fields=['alert_id', 'created_at', 'client', 'raw_description'])
        
        alert = {
            'alert_id': 'INC001',
            'created_at': None,
            'client': 'Test',
            'raw_description': 'Test'
        }
        
        with pytest.raises(AlertValidationError) as exc_info:
            validator.validate(alert)
        
        assert 'created_at is None' in str(exc_info.value)
    
    def test_validator_empty_client(self):
        """Test validator catches empty client."""
        validator = AlertValidator(required_fields=['alert_id', 'created_at', 'client', 'raw_description'])
        
        alert = {
            'alert_id': 'INC001',
            'created_at': datetime.now(),
            'client': '   ',
            'raw_description': 'Test'
        }
        
        with pytest.raises(AlertValidationError) as exc_info:
            validator.validate(alert)
        
        assert 'client is empty' in str(exc_info.value)
    
    def test_validator_empty_raw_description(self):
        """Test validator catches empty raw_description."""
        validator = AlertValidator(required_fields=['alert_id', 'created_at', 'client', 'raw_description'])
        
        alert = {
            'alert_id': 'INC001',
            'created_at': datetime.now(),
            'client': 'Test',
            'raw_description': ''
        }
        
        with pytest.raises(AlertValidationError) as exc_info:
            validator.validate(alert)
        
        assert 'raw_description is empty' in str(exc_info.value)


class TestPipelineLogging:
    """Test pipeline logging and progress tracking."""
    
    def test_pipeline_step_by_step(self):
        """Test each pipeline step individually."""
        # Create components
        field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
        normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
        validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
        pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
        
        # Create adapter
        adapter = ExcelAlertAdapter(
            file_path=Settings.EXCEL_FILE_PATH,
            column_mapping=Settings.EXCEL_COLUMN_MAPPING,
            forbidden_metadata_fields=Settings.FORBIDDEN_METADATA_FIELDS
        )
        
        # Test individual steps
        raw_alerts = pipeline.ingest(adapter)
        assert len(raw_alerts) == 889
        
        cleaned_alerts = pipeline.clean(raw_alerts)
        assert len(cleaned_alerts) == 889
        
        validated_alerts = pipeline.validate(cleaned_alerts)
        assert len(validated_alerts) == 889
        
        standardized_alerts = pipeline.normalize(validated_alerts)
        assert len(standardized_alerts) == 889
        assert all(isinstance(a, StandardizedAlert) for a in standardized_alerts)


class TestNormalizationDocumentation:
    """Test and document normalization behavior."""
    
    def test_normalization_rules_documented(self):
        """
        Document which dynamic values are normalized and which signals are preserved.
        
        NORMALIZED (replaced with placeholders):
        - Timestamps (ISO, date-time, abbreviated dates)
        - IP addresses (dotted notation, dash-separated)
        - UUIDs (8-4-4-4-12 format)
        - Request IDs (request_id: xxx patterns)
        - Large numeric IDs (7+ digits)
        - Priority markers (P1, P2, P3, P4) - standardized to lowercase (p1, p2, p3, p4)
        
        PRESERVED (semantic/technical signals):
        - Service names (BGSN, EASS, PZHT)
        - Technical identifiers (API names, component names)
        - Business/technical severity words (CRITICAL, HIGH, WARNING, FAILURE)
        - Priority distinctions (p1 vs p2 vs p3 vs p4)
        - Client names
        - Error types
        - Domain-specific terminology
        """
        normalizer = Normalizer(Settings.NORMALIZATION_PATTERNS)
        
        # Test: Timestamps normalized
        assert '<timestamp>' in normalizer.normalize("Alert at 2026-08-06T11:06:00Z")
        
        # Test: IPs normalized
        assert '<ip>' in normalizer.normalize("Server 192.168.1.1 failed")
        
        # Test: UUIDs normalized
        assert '<uuid>' in normalizer.normalize("Request a1b2c3d4-e5f6-7890-abcd-ef1234567890 failed")
        
        # Test: Large IDs normalized
        assert '<id>' in normalizer.normalize("Transaction 12345678901234")
        
        # Test: Priority markers standardized (preserving distinction)
        assert 'p1' in normalizer.normalize("P1 alert triggered")
        assert 'p2' in normalizer.normalize("P2 alert triggered")
        assert 'p3' in normalizer.normalize("P3 alert triggered")
        assert 'p4' in normalizer.normalize("P4 alert triggered")
        
        # Test: Service names PRESERVED
        text = normalizer.normalize("BGSN service failed")
        assert 'bgsn' in text
        assert 'service' in text
        
        # Test: Technical terms PRESERVED
        text2 = normalizer.normalize("CRITICAL FAILURE in ELB")
        assert 'critical' in text2
        assert 'failure' in text2
        assert 'elb' in text2
        
        # Test: API names PRESERVED
        text3 = normalizer.normalize("EASS_API_ERR_CRITICAL")
        assert 'eass' in text3
        assert 'api' in text3
        assert 'err' in text3
        assert 'critical' in text3
