"""
Mock trace provider for Stage 4 development.

Generates realistic distributed trace spans with dependency relationships.
All generated traces include provenance (source_type="mock", is_mock=True).
"""

import uuid
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import random

from ..schemas import TraceSpan, IncidentContext, SourceType
from .interfaces import TraceProvider


class MockTraceProvider(TraceProvider):
    """
    Mock trace provider that generates synthetic distributed traces.
    
    Generates traces with:
    - Realistic dependency chains
    - Parent-child relationships
    - Latency propagation
    - Error propagation from upstream to downstream
    - Proper provenance tracking
    
    IMPORTANT: Uses predefined illustrative dependency chains. Does NOT imply
    these dependencies actually exist in the real Epsilon environment.
    """
    
    # Predefined illustrative dependency scenarios
    DEPENDENCY_SCENARIOS = {
        "eass": {
            "name": "EA Sports",
            "chain": [
                {"component": "application", "operation": "http_request", "base_duration_ms": 50},
                {"component": "mulesoft", "operation": "api_call", "base_duration_ms": 100},
                {"component": "elb", "operation": "route_request", "base_duration_ms": 20},
                {"component": "database", "operation": "query", "base_duration_ms": 80},
            ]
        },
        "pzht": {
            "name": "Pizza Hut",
            "chain": [
                {"component": "application", "operation": "batch_job", "base_duration_ms": 100},
                {"component": "database", "operation": "bulk_insert", "base_duration_ms": 200},
            ]
        },
        "bgsn": {
            "name": "Bridgestone",
            "chain": [
                {"component": "application", "operation": "api_request", "base_duration_ms": 60},
                {"component": "mulesoft", "operation": "integration_flow", "base_duration_ms": 150},
                {"component": "database", "operation": "transaction", "base_duration_ms": 90},
            ]
        },
        "default": {
            "name": "Generic",
            "chain": [
                {"component": "application", "operation": "request", "base_duration_ms": 50},
                {"component": "database", "operation": "query", "base_duration_ms": 100},
            ]
        },
    }
    
    def __init__(self, error_injection_rate: float = 0.4, seed: int = None):
        """
        Initialize mock trace provider.
        
        Args:
            error_injection_rate: Probability of injecting errors during incident (0.0-1.0)
            seed: Random seed for reproducibility
        """
        self.error_injection_rate = error_injection_rate
        if seed is not None:
            random.seed(seed)
    
    def get_traces(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None
    ) -> List[TraceSpan]:
        """
        Generate mock traces for the given context and time range.
        
        Uses predefined illustrative dependency chains based on client.
        
        Args:
            context: Incident context
            start_time: Start of diagnostic window
            end_time: End of diagnostic window
            components: Optional filter by component names
        
        Returns:
            List of mock TraceSpan objects with provenance
        """
        traces = []
        
        # Select dependency scenario based on client
        scenario_key = self._select_scenario(context.client, context.services)
        scenario = self.DEPENDENCY_SCENARIOS.get(scenario_key, self.DEPENDENCY_SCENARIOS["default"])
        
        # Filter chain by components if specified
        if components:
            chain = [step for step in scenario["chain"] if step["component"] in components]
        else:
            chain = scenario["chain"]
        
        if not chain:
            return []
        
        # Generate traces over time window
        duration_seconds = (end_time - start_time).total_seconds()
        num_traces = int(duration_seconds / 300)  # One trace every 5 minutes
        
        for i in range(num_traces):
            # Random start time within window
            offset_seconds = random.uniform(0, duration_seconds)
            trace_start = start_time + timedelta(seconds=offset_seconds)
            
            # Determine if this trace should show errors
            # If incident_start == incident_end (single timestamp), expand window for error injection
            incident_window_end = context.incident_end
            if incident_window_end == context.incident_start:
                incident_window_end = context.incident_start + timedelta(minutes=10)
            
            is_during_incident = (
                context.incident_start <= trace_start <= incident_window_end
            )
            
            should_inject_error = (
                is_during_incident and 
                random.random() < self.error_injection_rate
            )
            
            # Generate trace chain
            trace_spans = self._generate_trace_chain(
                chain=chain,
                trace_start=trace_start,
                context=context,
                inject_error=should_inject_error
            )
            
            traces.extend(trace_spans)
        
        return traces
    
    def _select_scenario(self, client: str, services: List[str]) -> str:
        """
        Select appropriate dependency scenario based on client/services.
        
        Args:
            client: Client name
            services: Extracted service names
        
        Returns:
            Scenario key
        """
        client_lower = client.lower()
        
        if "ea sports" in client_lower or any("eass" in s.lower() for s in services):
            return "eass"
        elif "pizza hut" in client_lower or any("pzht" in s.lower() for s in services):
            return "pzht"
        elif "bridgestone" in client_lower or any("bgsn" in s.lower() for s in services):
            return "bgsn"
        else:
            return "default"
    
    def _generate_trace_chain(
        self,
        chain: List[Dict],
        trace_start: datetime,
        context: IncidentContext,
        inject_error: bool
    ) -> List[TraceSpan]:
        """
        Generate a single trace chain with parent-child relationships.
        
        Args:
            chain: Dependency chain configuration
            trace_start: Trace start time
            context: Incident context
            inject_error: Whether to inject errors in this trace
        
        Returns:
            List of TraceSpan objects forming a trace
        """
        trace_id = f"trace_{uuid.uuid4().hex[:16]}"
        spans = []
        parent_span_id = None
        current_time = trace_start
        
        # Determine where error originates (upstream component)
        error_origin_index = random.randint(0, len(chain) - 1) if inject_error else -1
        
        for idx, step in enumerate(chain):
            span_id = f"span_{uuid.uuid4().hex[:12]}"
            
            # Determine duration (with variance and potential degradation)
            base_duration = step["base_duration_ms"]
            
            if inject_error and idx >= error_origin_index:
                # Errors cause increased latency downstream
                duration_ms = base_duration * random.uniform(5.0, 20.0)  # 5-20x slower
                status = "error" if idx == error_origin_index else "timeout"
            else:
                # Normal operation with variance
                duration_ms = base_duration * random.uniform(0.8, 1.2)
                status = "ok"
            
            span_start = current_time
            span_end = span_start + timedelta(milliseconds=duration_ms)
            
            span = TraceSpan(
                span_id=span_id,
                parent_span_id=parent_span_id,
                trace_id=trace_id,
                component=step["component"],
                operation=step["operation"],
                start_time=span_start,
                end_time=span_end,
                duration_ms=round(duration_ms, 2),
                status=status,
                source_type=SourceType.MOCK,
                is_mock=True,
                metadata={
                    "incident_id": context.incident_id,
                    "client": context.client,
                    "position_in_chain": idx,
                    "total_chain_length": len(chain),
                    "is_error_origin": (idx == error_origin_index)
                }
            )
            
            spans.append(span)
            
            # Next span's parent is this span
            parent_span_id = span_id
            
            # Next span starts when this one ends (sequential dependency)
            current_time = span_end
        
        return spans
    
    def get_dependency_graph(self, traces: List[TraceSpan]) -> Dict[str, List[str]]:
        """
        Extract dependency graph from traces.
        
        Args:
            traces: List of trace spans
        
        Returns:
            Dict mapping component -> list of downstream components
        """
        dependencies = {}
        
        # Group spans by trace_id
        traces_by_id = {}
        for span in traces:
            if span.trace_id not in traces_by_id:
                traces_by_id[span.trace_id] = []
            traces_by_id[span.trace_id].append(span)
        
        # Extract dependencies from each trace
        for trace_id, trace_spans in traces_by_id.items():
            # Sort by start time to get ordering
            sorted_spans = sorted(trace_spans, key=lambda s: s.start_time)
            
            for i in range(len(sorted_spans) - 1):
                upstream = sorted_spans[i].component
                downstream = sorted_spans[i + 1].component
                
                if upstream not in dependencies:
                    dependencies[upstream] = []
                
                if downstream not in dependencies[upstream]:
                    dependencies[upstream].append(downstream)
        
        return dependencies
