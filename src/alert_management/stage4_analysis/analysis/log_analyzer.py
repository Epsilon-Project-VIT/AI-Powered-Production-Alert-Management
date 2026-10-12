"""
Log Analyzer - Extract patterns and evidence from logs.
"""

from typing import List, Dict
from collections import Counter
from datetime import datetime
import hashlib

from alert_management.stage4_analysis.schemas import LogRecord, Evidence, SourceType


class LogAnalyzer:
    """Analyze logs to extract error patterns and evidence."""
    
    def analyze(
        self,
        logs: List[LogRecord],
        diagnostic_start: datetime,
        diagnostic_end: datetime,
        incident_start: datetime,
        incident_end: datetime
    ) -> List[Evidence]:
        """
        Analyze logs and generate evidence.
        
        Args:
            logs: Log records to analyze
            diagnostic_start: Start of diagnostic window
            diagnostic_end: End of diagnostic window
            incident_start: Incident start time  
            incident_end: Incident end time
            
        Returns:
            List of evidence from logs
        """
        evidence_list = []
        
        if not logs:
            return evidence_list
        
        # Analyze all logs in diagnostic window (they're already filtered)
        # Focus on errors during incident timeframe for higher weight
        error_logs = [log for log in logs if log.level == "ERROR"]
        warn_logs = [log for log in logs if log.level == "WARN"]
        
        if error_logs:
            evidence_list.append(Evidence(
                source="logs",
                source_type=logs[0].source_type,
                source_id=f"log_error_count_{len(error_logs)}",
                is_mock=logs[0].is_mock,
                timestamp=diagnostic_start,
                description=f"{len(error_logs)} ERROR level logs during diagnostic window",
                weight=0.8,
                metadata={
                    "error_count": len(error_logs),
                    "warn_count": len(warn_logs),
                    "total_logs": len(logs)
                }
            ))
        
        # Find most common error messages and associate their primary component
        if error_logs:
            msg_components: Dict[str, Counter] = {}
            for log in error_logs:
                if log.message not in msg_components:
                    msg_components[log.message] = Counter()
                msg_components[log.message][log.component] += 1

            error_messages = [log.message for log in error_logs]
            message_counts = Counter(error_messages)
            most_common = message_counts.most_common(5)
            
            for idx, (message, count) in enumerate(most_common):
                comp = msg_components[message].most_common(1)[0][0]
                pattern_hash = int(hashlib.sha256(message.encode("utf-8")).hexdigest()[:8], 16) % 10000
                evidence_list.append(Evidence(
                    source="logs",
                    source_type=logs[0].source_type,
                    source_id=f"log_pattern_{idx}_{pattern_hash}",
                    is_mock=logs[0].is_mock,
                    timestamp=incident_start,
                    description=f"Recurring error ({count}x) in {comp}: {message[:100]}",
                    weight=0.8 - (idx * 0.05),
                    metadata={"occurrences": count, "pattern": message, "component": comp}
                ))

        
        # Component-specific errors
        component_errors: Dict[str, int] = {}
        for log in error_logs:
            comp = log.component
            component_errors[comp] = component_errors.get(comp, 0) + 1
        
        for component, count in component_errors.items():
            evidence_list.append(Evidence(
                source="logs",
                source_type=logs[0].source_type,
                source_id=f"log_component_{component}_{count}",
                is_mock=logs[0].is_mock,
                timestamp=incident_start,
                description=f"{count} errors in {component} component",
                weight=0.6,
                metadata={"component": component, "error_count": count}
            ))
        
        return evidence_list
