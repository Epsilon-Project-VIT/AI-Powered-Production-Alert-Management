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
        anomalies: List[AnomalyDetection],
        max_gap: timedelta = timedelta(minutes=10)
    ) -> List[Evidence]:
        """
        Generate bounded evidence episodes from detected metric anomalies.
        
        Aggregates contiguous anomalous points for the same metric and component
        into a single Evidence episode record, preserving raw samples in metadata.
        
        Args:
            anomalies: Detected anomaly points
            max_gap: Maximum gap between consecutive points to consider contiguous
            
        Returns:
            List of aggregated Evidence objects
        """
        evidence_list = []
        if not anomalies:
            return evidence_list

        # Group anomalies by (metric_name, component)
        grouped: dict = {}
        for anomaly in anomalies:
            key = (anomaly.metric_name, anomaly.component)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(anomaly)

        # Process each metric/component group into contiguous episodes
        for (metric_name, component), points in grouped.items():
            points.sort(key=lambda p: p.timestamp)
            clusters: List[List[AnomalyDetection]] = []
            curr_cluster: List[AnomalyDetection] = []

            for pt in points:
                if not curr_cluster:
                    curr_cluster.append(pt)
                else:
                    prev_pt = curr_cluster[-1]
                    if (pt.timestamp - prev_pt.timestamp) <= max_gap:
                        curr_cluster.append(pt)
                    else:
                        clusters.append(curr_cluster)
                        curr_cluster = [pt]
            if curr_cluster:
                clusters.append(curr_cluster)

            # Build single aggregated Evidence object per episode cluster
            for cluster in clusters:
                start_time = cluster[0].timestamp
                end_time = cluster[-1].timestamp
                sample_count = len(cluster)

                peak_pt = max(cluster, key=lambda p: p.anomaly_score)
                max_score = peak_pt.anomaly_score
                avg_score = statistics.mean(p.anomaly_score for p in cluster)
                expected_val = cluster[0].expected_value
                peak_observed = peak_pt.observed_value

                raw_samples = [
                    {
                        "timestamp": pt.timestamp.isoformat(),
                        "observed_value": pt.observed_value,
                        "expected_value": pt.expected_value,
                        "anomaly_score": pt.anomaly_score,
                    }
                    for pt in cluster
                ]

                if sample_count == 1:
                    desc = (
                        f"Metric anomaly in {metric_name} (component: {component}): "
                        f"observed={peak_observed:.2f}, expected={expected_val:.2f}, "
                        f"score={max_score:.2f} at {start_time.strftime('%H:%M:%S')}"
                    )
                else:
                    desc = (
                        f"Metric anomaly episode in {metric_name} (component: {component}): "
                        f"{sample_count} contiguous samples from {start_time.strftime('%H:%M:%S')} "
                        f"to {end_time.strftime('%H:%M:%S')} (peak={peak_observed:.2f}, "
                        f"expected={expected_val:.2f}, max_score={max_score:.2f})"
                    )

                source_ts = int(start_time.timestamp())
                evidence = Evidence(
                    source="metrics",
                    source_type=cluster[0].source_type,
                    source_id=f"anomaly_episode_{metric_name}_{component}_{source_ts}",
                    is_mock=cluster[0].is_mock,
                    timestamp=start_time,
                    description=desc,
                    weight=min(max_score, 0.95),
                    metadata={
                        "metric_name": metric_name,
                        "component": component,
                        "episode_start": start_time.isoformat(),
                        "episode_end": end_time.isoformat(),
                        "sample_count": sample_count,
                        "expected_value": expected_val,
                        "peak_observed": peak_observed,
                        "max_anomaly_score": max_score,
                        "avg_anomaly_score": avg_score,
                        "detection_method": cluster[0].detection_method,
                        "raw_samples": raw_samples,
                    }
                )
                evidence_list.append(evidence)

        return evidence_list

