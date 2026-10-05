"""
Mock log provider for Stage 4 development.

Generates realistic but synthetic log entries based on incident context.
All generated logs include provenance (source_type="mock", is_mock=True).
"""

import uuid
from typing import List
from datetime import datetime, timedelta
import random

from ..schemas import LogRecord, IncidentContext, SourceType
from .interfaces import LogProvider


class MockLogProvider(LogProvider):
    """
    Mock log provider that generates synthetic log entries.
    
    Generates logs based on incident context with:
    - Realistic temporal distribution
    - Component-aware messages
    - Error patterns matching incident symptoms
    - Proper provenance tracking
    """
    
    def __init__(self, error_rate: float = 0.3, seed: int = None):
        """
        Initialize mock log provider.
        
        Args:
            error_rate: Probability of generating ERROR level logs (0.0-1.0)
            seed: Random seed for reproducibility
        """
        self.error_rate = error_rate
        if seed is not None:
            random.seed(seed)
    
    def get_logs(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None,
        levels: List[str] = None
    ) -> List[LogRecord]:
        """
        Generate mock logs for the given context and time range.
        
        Args:
            context: Incident context
            start_time: Start of diagnostic window
            end_time: End of diagnostic window
            components: Optional filter by component names
            levels: Optional filter by log levels
        
        Returns:
            List of mock LogRecord objects with provenance
        """
        logs = []
        
        # Determine components to generate logs for
        target_components = components if components else (context.components or ["application", "database"])
        
        # Determine log levels to generate
        target_levels = levels if levels else ["ERROR", "WARN", "INFO", "DEBUG"]
        
        # Generate logs with temporal distribution
        duration_hours = (end_time - start_time).total_seconds() / 3600
        num_logs = int(duration_hours * 20)  # ~20 logs per hour
        
        for i in range(num_logs):
            # Random timestamp within window
            offset_seconds = random.uniform(0, (end_time - start_time).total_seconds())
            log_timestamp = start_time + timedelta(seconds=offset_seconds)
            
            # Select component
            component = random.choice(target_components)
            
            # Determine log level (bias toward errors during incident time)
            # If incident_start == incident_end (single timestamp), expand window for error generation
            incident_window_end = context.incident_end
            if incident_window_end == context.incident_start:
                incident_window_end = context.incident_start + timedelta(minutes=10)
            
            is_during_incident = (
                context.incident_start <= log_timestamp <= incident_window_end
            )
            
            if is_during_incident and random.random() < self.error_rate:
                level = "ERROR"
            elif is_during_incident and random.random() < 0.5:
                level = "WARN"
            else:
                level = random.choice(["INFO", "DEBUG"])
            
            # Only include if level is in filter
            if level not in target_levels:
                continue
            
            # Generate component-appropriate message
            message = self._generate_log_message(component, level, context)
            
            log = LogRecord(
                log_id=f"mock_log_{uuid.uuid4().hex[:12]}",
                timestamp=log_timestamp,
                component=component,
                level=level,
                message=message,
                source_type=SourceType.MOCK,
                is_mock=True,
                metadata={
                    "incident_id": context.incident_id,
                    "client": context.client
                }
            )
            
            logs.append(log)
        
        # Sort by timestamp
        logs.sort(key=lambda x: x.timestamp)
        
        return logs
    
    def _generate_log_message(self, component: str, level: str, context: IncidentContext) -> str:
        """
        Generate realistic log message based on component and level.
        
        Args:
            component: Component name
            level: Log level
            context: Incident context
        
        Returns:
            Log message string
        """
        if level == "ERROR":
            error_templates = {
                "database": [
                    "Connection timeout after 30000ms",
                    "Failed to acquire connection from pool",
                    "Connection pool exhausted: 0/100 available",
                    "Query execution timeout: waited 60000ms",
                    "Database connection refused: host unreachable",
                ],
                "application": [
                    f"Request failed for client {context.client}: timeout",
                    "Failed to process request: downstream service unavailable",
                    "HTTP 500 Internal Server Error",
                    "Unhandled exception in request handler",
                    "Service degradation detected: high error rate",
                ],
                "elb": [
                    "Target health check failed",
                    "Backend connection timeout",
                    "503 Service Unavailable: no healthy targets",
                    "Request routing failed: all targets unhealthy",
                ],
                "mulesoft": [
                    "API call failed: connection timeout",
                    "Downstream service not responding",
                    "Integration flow error: timeout waiting for response",
                ],
            }
            
            templates = error_templates.get(component, [
                f"Error in {component}: operation failed",
                f"{component} encountered unexpected error",
            ])
            
            return random.choice(templates)
        
        elif level == "WARN":
            warn_templates = {
                "database": [
                    "Connection pool utilization high: 85/100",
                    "Slow query detected: 5000ms",
                    "Connection pool near capacity",
                ],
                "application": [
                    f"Slow response for client {context.client}: 3000ms",
                    "Request queue depth increasing",
                    "Memory usage above threshold: 85%",
                ],
                "elb": [
                    "Target response time degraded",
                    "Intermittent health check failures",
                ],
            }
            
            templates = warn_templates.get(component, [
                f"Warning in {component}: performance degradation",
            ])
            
            return random.choice(templates)
        
        else:  # INFO or DEBUG
            info_templates = {
                "database": [
                    "Connection pool status: 45/100 active",
                    "Query executed successfully: 150ms",
                    "Database health check passed",
                ],
                "application": [
                    f"Processing request for client {context.client}",
                    "Request completed successfully",
                    "Service health check: OK",
                ],
            }
            
            templates = info_templates.get(component, [
                f"{component} operating normally",
            ])
            
            return random.choice(templates)
