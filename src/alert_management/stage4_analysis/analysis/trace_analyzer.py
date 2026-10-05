"""
Trace Analyzer - Analyze distributed traces.
"""

from typing import List, Dict, Set, Tuple
from datetime import datetime, timedelta

from alert_management.stage4_analysis.schemas import TraceSpan, Evidence, SourceType


class TraceAnalyzer:
    """Analyze distributed traces to identify dependency issues."""
    
    def analyze(
        self,
        traces: List[TraceSpan],
        diagnostic_start: datetime,
        diagnostic_end: datetime,
        incident_start: datetime,
        incident_end: datetime
    ) -> List[Evidence]:
        """
        Analyze traces and generate evidence.
        
        Args:
            traces: Trace spans (already filtered to diagnostic window)
            diagnostic_start: Start of diagnostic window
            diagnostic_end: End of diagnostic window
            incident_start: Incident start time
            incident_end: Incident end time
            
        Returns:
            List of evidence from traces
        """
        evidence_list = []
        
        if not traces:
            return evidence_list
        
        # Analyze all traces in diagnostic window
        # Focus on incident timeframe for error analysis
        # If incident_start == incident_end (single timestamp), expand window
        incident_window_end = incident_end
        if incident_window_end == incident_start:
            incident_window_end = incident_start + timedelta(minutes=10)
        
        incident_traces = [
            t for t in traces
            if incident_start <= t.start_time <= incident_window_end
        ]
        
        if not incident_traces:
            return evidence_list
        
        # Build dependency graph
        dependencies = self._build_dependency_graph(incident_traces)
        
        # Analyze errors
        error_spans = [t for t in incident_traces if t.status == "error"]
        
        if error_spans:
            # Component error analysis
            component_errors: Dict[str, int] = {}
            for span in error_spans:
                comp = span.component
                component_errors[comp] = component_errors.get(comp, 0) + 1
            
            for component, count in component_errors.items():
                evidence_list.append(Evidence(
                    source="traces",
                    source_type=traces[0].source_type,
                    source_id=f"trace_error_{component}_{count}",
                    is_mock=traces[0].is_mock,
                    timestamp=incident_start,
                    description=f"{count} error spans in {component} component",
                    weight=0.7,
                    metadata={
                        "component": component,
                        "error_count": count
                    }
                ))
            
            # Analyze error propagation
            for span in error_spans:
                if span.parent_span_id:
                    # Find parent
                    parent = next(
                        (t for t in incident_traces if t.span_id == span.parent_span_id),
                        None
                    )
                    if parent and parent.status != "error":
                        # Downstream error
                        evidence_list.append(Evidence(
                            source="traces",
                            source_type=span.source_type,
                            source_id=f"trace_propagation_{span.span_id}",
                            is_mock=span.is_mock,
                            timestamp=span.start_time,
                            description=(
                                f"Error in {span.component} following call from "
                                f"{parent.component}"
                            ),
                            weight=0.6,
                            metadata={
                                "downstream_component": span.component,
                                "upstream_component": parent.component
                            }
                        ))
        
        # Dependency chain evidence
        if dependencies:
            dep_chain = " → ".join(dependencies)
            evidence_list.append(Evidence(
                source="traces",
                source_type=traces[0].source_type,
                source_id="trace_dependency_chain",
                is_mock=traces[0].is_mock,
                timestamp=incident_start,
                description=f"Dependency chain observed: {dep_chain}",
                weight=0.5,
                metadata={"dependency_chain": dependencies}
            ))
        
        return evidence_list
    
    def _build_dependency_graph(self, traces: List[TraceSpan]) -> List[str]:
        """
        Build dependency chain from traces.
        
        Args:
            traces: Trace spans
            
        Returns:
            Ordered list of components in dependency chain
        """
        # Build parent-child relationships
        children: Dict[str, List[str]] = {}
        components: Dict[str, str] = {}
        
        for trace in traces:
            components[trace.span_id] = trace.component
            if trace.parent_span_id:
                if trace.parent_span_id not in children:
                    children[trace.parent_span_id] = []
                children[trace.parent_span_id].append(trace.span_id)
        
        # Find root spans (no parent)
        roots = [t.span_id for t in traces if not t.parent_span_id]
        
        if not roots:
            return []
        
        # Build chain from first root
        chain = []
        visited = set()
        
        def traverse(span_id: str):
            if span_id in visited:
                return
            visited.add(span_id)
            
            comp = components.get(span_id)
            if comp and comp not in chain:
                chain.append(comp)
            
            # Visit children
            for child_id in children.get(span_id, []):
                traverse(child_id)
        
        traverse(roots[0])
        
        return chain
