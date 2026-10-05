"""
Mock metric provider for Stage 4 development.

Generates realistic time-series metric data with baseline and anomalies.
All generated metrics include provenance (source_type="mock", is_mock=True).
"""

import uuid
from typing import List, Dict
from datetime import datetime, timedelta
import random
import math

from ..schemas import MetricRecord, IncidentContext, SourceType
from .interfaces import MetricProvider


class MockMetricProvider(MetricProvider):
    """
    Mock metric provider that generates synthetic time-series metrics.
    
    Generates metrics with:
    - Realistic baselines
    - Normal variance
    - Injected anomalies during incident time
    - Proper provenance tracking
    
    IMPORTANT: Uses predefined illustrative scenarios, does NOT infer root cause
    and generate telemetry to prove it.
    """
    
    # Predefined illustrative metric scenarios
    METRIC_SCENARIOS = {
        "database": {
            "db_connection_pool_utilization": {
                "baseline": 60.0,
                "unit": "percent",
                "anomaly_value": 98.0,
                "variance": 5.0
            },
            "db_query_latency": {
                "baseline": 150.0,
                "unit": "milliseconds",
                "anomaly_value": 5000.0,
                "variance": 20.0
            },
            "db_active_connections": {
                "baseline": 45,
                "unit": "count",
                "anomaly_value": 100,
                "variance": 5
            },
        },
        "application": {
            "app_response_time": {
                "baseline": 200.0,
                "unit": "milliseconds",
                "anomaly_value": 3000.0,
                "variance": 30.0
            },
            "app_error_rate": {
                "baseline": 0.5,
                "unit": "percent",
                "anomaly_value": 15.0,
                "variance": 0.2
            },
            "app_memory_usage": {
                "baseline": 65.0,
                "unit": "percent",
                "anomaly_value": 92.0,
                "variance": 5.0
            },
        },
        "elb": {
            "elb_target_response_time": {
                "baseline": 180.0,
                "unit": "milliseconds",
                "anomaly_value": 2500.0,
                "variance": 25.0
            },
            "elb_healthy_targets": {
                "baseline": 10,
                "unit": "count",
                "anomaly_value": 2,
                "variance": 1
            },
            "elb_request_count": {
                "baseline": 1000,
                "unit": "per_minute",
                "anomaly_value": 450,
                "variance": 100
            },
        },
        "mulesoft": {
            "mulesoft_api_latency": {
                "baseline": 250.0,
                "unit": "milliseconds",
                "anomaly_value": 4000.0,
                "variance": 40.0
            },
            "mulesoft_error_rate": {
                "baseline": 1.0,
                "unit": "percent",
                "anomaly_value": 20.0,
                "variance": 0.5
            },
        },
    }
    
    def __init__(self, anomaly_injection_rate: float = 0.8, seed: int = None):
        """
        Initialize mock metric provider.
        
        Args:
            anomaly_injection_rate: Probability of injecting anomaly during incident (0.0-1.0)
            seed: Random seed for reproducibility
        """
        self.anomaly_injection_rate = anomaly_injection_rate
        if seed is not None:
            random.seed(seed)
    
    def get_metrics(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None,
        metric_names: List[str] = None
    ) -> List[MetricRecord]:
        """
        Generate mock metrics for the given context and time range.
        
        Uses predefined illustrative scenarios for each component.
        
        Args:
            context: Incident context
            start_time: Start of diagnostic window
            end_time: End of diagnostic window
            components: Optional filter by component names
            metric_names: Optional filter by specific metrics
        
        Returns:
            List of mock MetricRecord objects with provenance
        """
        metrics = []
        
        # Determine components to generate metrics for
        target_components = components if components else (context.components or ["application", "database"])
        
        # Ensure components we have scenarios for
        available_components = [c for c in target_components if c in self.METRIC_SCENARIOS]
        if not available_components:
            available_components = ["application", "database"]  # Fallback
        
        # Generate time series for each component
        duration_seconds = (end_time - start_time).total_seconds()
        sample_interval = 60  # 1 minute intervals
        num_samples = int(duration_seconds / sample_interval)
        
        for component in available_components:
            component_metrics = self.METRIC_SCENARIOS.get(component, {})
            
            for metric_name, config in component_metrics.items():
                # Skip if metric_names filter provided and this isn't in it
                if metric_names and metric_name not in metric_names:
                    continue
                
                # Generate time series
                metric_series = self._generate_time_series(
                    metric_name=metric_name,
                    component=component,
                    config=config,
                    start_time=start_time,
                    num_samples=num_samples,
                    sample_interval=sample_interval,
                    context=context
                )
                
                metrics.extend(metric_series)
        
        return metrics
    
    def _generate_time_series(
        self,
        metric_name: str,
        component: str,
        config: Dict,
        start_time: datetime,
        num_samples: int,
        sample_interval: int,
        context: IncidentContext
    ) -> List[MetricRecord]:
        """
        Generate time series for a single metric.
        
        Args:
            metric_name: Metric name
            component: Component name
            config: Metric configuration (baseline, anomaly_value, variance, unit)
            start_time: Series start time
            num_samples: Number of samples to generate
            sample_interval: Seconds between samples
            context: Incident context (for anomaly injection timing)
        
        Returns:
            List of MetricRecord objects
        """
        series = []
        baseline = config["baseline"]
        anomaly_value = config["anomaly_value"]
        variance = config["variance"]
        unit = config["unit"]
        
        for i in range(num_samples):
            timestamp = start_time + timedelta(seconds=i * sample_interval)
            
            # Determine if this point should be anomalous
            # If incident_start == incident_end (single timestamp), expand window for anomaly injection
            incident_window_end = context.incident_end
            if incident_window_end == context.incident_start:
                incident_window_end = context.incident_start + timedelta(minutes=10)
            
            is_during_incident = (
                context.incident_start <= timestamp <= incident_window_end
            )
            
            # Inject anomaly during incident with probability
            should_inject_anomaly = (
                is_during_incident and 
                random.random() < self.anomaly_injection_rate
            )
            
            if should_inject_anomaly:
                # Gradually transition to anomaly value
                progress = (timestamp - context.incident_start).total_seconds() / 600  # 10 min ramp
                progress = min(1.0, max(0.0, progress))
                value = baseline + (anomaly_value - baseline) * progress
                value += random.gauss(0, variance * 0.5)  # Less variance during anomaly
            else:
                # Normal baseline with variance
                value = baseline + random.gauss(0, variance)
            
            # Ensure non-negative for most metrics
            if unit in ["percent", "count", "milliseconds", "per_minute"]:
                value = max(0, value)
            
            # Cap percentages at 100
            if unit == "percent":
                value = min(100, value)
            
            metric = MetricRecord(
                metric_id=f"mock_metric_{uuid.uuid4().hex[:12]}",
                timestamp=timestamp,
                metric_name=metric_name,
                component=component,
                value=round(value, 2),
                unit=unit,
                source_type=SourceType.MOCK,
                is_mock=True,
                metadata={
                    "incident_id": context.incident_id,
                    "client": context.client,
                    "baseline": baseline,
                    "is_anomalous": should_inject_anomaly
                }
            )
            
            series.append(metric)
        
        return series
    
    def inject_specific_anomaly_pattern(
        self,
        metric_name: str,
        component: str,
        pattern: str = "spike"
    ) -> None:
        """
        Configure specific anomaly pattern for a metric.
        
        Patterns: spike, gradual_increase, oscillation, sudden_drop
        
        Args:
            metric_name: Metric to configure
            component: Component for the metric
            pattern: Anomaly pattern type
        
        Note: This is for future extensibility, not currently used.
        """
        # Placeholder for future pattern customization
        pass
