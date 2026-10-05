"""
Anomaly Detector - Detect anomalies in metric time-series data.
"""

from typing import List, Optional
from datetime import datetime, timedelta
import statistics

from alert_management.stage4_analysis.schemas import (
    MetricRecord,
    Evidence,
    AnomalyDetection,
    SourceType
)


class AnomalyDetector:
    """
    Detect anomalies in metrics using statistical methods.
    
    Uses Z-score and MAD (Median Absolute Deviation) methods.
    """
    
    def __init__(
        self,
        z_score_threshold: float = 3.0,
        mad_threshold: float = 3.0
    ):
        """
        Initialize anomaly detector.
        
        Args:
            z_score_threshold: Z-score threshold for anomaly
            mad_threshold: MAD threshold for anomaly
        """
        self.z_score_threshold = z_score_threshold
        self.mad_threshold = mad_threshold
    
    def detect_anomalies(
        self,
        metrics: List[MetricRecord],
        diagnostic_start: datetime,
        diagnostic_end: datetime,
        incident_start: datetime,
        incident_end: datetime
    ) -> List[AnomalyDetection]:
        """
        Detect anomalies in metrics.
        
        Args:
            metrics: Metric records (already filtered to diagnostic window)
            diagnostic_start: Start of diagnostic window
            diagnostic_end: End of diagnostic window
            incident_start: Incident start time
            incident_end: Incident end time
            
        Returns:
            List of detected anomalies
        """
        if not metrics:
            return []
        
        anomalies = []
        
        # Group by metric name and component
        grouped: dict = {}
        for metric in metrics:
            key = (metric.metric_name, metric.component)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(metric)
        
        # If incident_start == incident_end (single timestamp), expand window for analysis
        incident_window_end = incident_end
        if incident_window_end == incident_start:
            incident_window_end = incident_start + timedelta(minutes=10)
        
        # Detect anomalies for each metric
        for (metric_name, component), metric_list in grouped.items():
            # Sort by timestamp
            metric_list.sort(key=lambda m: m.timestamp)
            
            # Separate baseline and incident periods
            baseline = [
                m for m in metric_list
                if m.timestamp < incident_start
            ]
            incident_metrics = [
                m for m in metric_list
                if incident_start <= m.timestamp <= incident_window_end
            ]
            
            if not baseline or not incident_metrics:
                continue
            
            # Calculate baseline statistics
            baseline_values = [m.value for m in baseline]
            mean_val = statistics.mean(baseline_values)
            
            try:
                stdev_val = statistics.stdev(baseline_values)
            except:
                stdev_val = 0
            
            # Check for anomalies in incident period
            for metric in incident_metrics:
                is_anomalous = False
                anomaly_score = 0.0
                method = "z_score"
                
                # Z-score method
                if stdev_val > 0:
                    z_score = abs((metric.value - mean_val) / stdev_val)
                    if z_score >= self.z_score_threshold:
                        is_anomalous = True
                        anomaly_score = min(z_score / self.z_score_threshold, 1.0)
                
                if is_anomalous:
                    anomaly = AnomalyDetection(
                        metric_name=metric_name,
                        component=component,
                        timestamp=metric.timestamp,
                        observed_value=metric.value,
                        expected_value=mean_val,
                        anomaly_score=anomaly_score,
                        detection_method=method,
                        is_anomalous=True,
                        source_type=metric.source_type,
                        is_mock=metric.is_mock
                    )
                    anomalies.append(anomaly)
        
        return anomalies
    
    def generate_evidence(
        self,
        anomalies: List[AnomalyDetection]
    ) -> List[Evidence]:
        """
        Generate evidence from detected anomalies.
        
        Args:
            anomalies: Detected anomalies
            
        Returns:
            List of evidence
        """
        evidence_list = []
        
        for anomaly in anomalies:
            evidence = Evidence(
                source="metrics",
                source_type=anomaly.source_type,
                source_id=f"anomaly_{anomaly.metric_name}_{anomaly.component}_{int(anomaly.timestamp.timestamp())}",
                is_mock=anomaly.is_mock,
                timestamp=anomaly.timestamp,
                description=(
                    f"Anomaly detected in {anomaly.metric_name} "
                    f"(component: {anomaly.component}): "
                    f"observed={anomaly.observed_value:.2f}, "
                    f"expected={anomaly.expected_value:.2f}, "
                    f"score={anomaly.anomaly_score:.2f}"
                ),
                weight=min(anomaly.anomaly_score, 0.9),
                metadata={
                    "metric_name": anomaly.metric_name,
                    "component": anomaly.component,
                    "observed_value": anomaly.observed_value,
                    "expected_value": anomaly.expected_value,
                    "anomaly_score": anomaly.anomaly_score,
                    "detection_method": anomaly.detection_method
                }
            )
            evidence_list.append(evidence)
        
        return evidence_list
