"""
RCA Candidate Generator - Generate RCA hypotheses from evidence.
"""

from typing import List, Set
from collections import Counter

from alert_management.stage4_analysis.schemas import (
    Evidence,
    ProbableRootCause,
    IncidentContext
)


class RCACandidateGenerator:
    """Generate RCA candidates from evidence."""
    
    def generate_candidates(
        self,
        context: IncidentContext,
        evidence: List[Evidence]
    ) -> List[ProbableRootCause]:
        """
        Generate RCA candidates from evidence.
        
        Uses deterministic rules based on evidence signals.
        
        Args:
            context: Incident context
            evidence: Collected evidence
            
        Returns:
            List of RCA candidates
        """
        candidates = []
        
        # Extract components mentioned in evidence
        component_counts: Counter = Counter()
        failure_types: Set[str] = set()
        
        for ev in evidence:
            if ev.metadata and "component" in ev.metadata:
                component_counts[ev.metadata["component"]] += ev.weight
            
            # Extract failure types from descriptions & metric metadata
            desc_lower = ev.description.lower()
            metric_name = (ev.metadata.get("metric_name") if ev.metadata else "") or ""
            
            if "connection" in desc_lower or "pool" in desc_lower or "db_connection_pool" in metric_name:
                failure_types.add("connection_pool_exhaustion")
            if "batch" in desc_lower or "job" in desc_lower or "batch_processing" in metric_name:
                failure_types.add("batch_execution_failure")
            if "sla" in desc_lower or "delivery" in desc_lower or "delay" in desc_lower or "extract_processing" in metric_name:
                failure_types.add("delivery_delay")
            if "queue" in desc_lower or "backlog" in desc_lower or "queue_depth" in metric_name:
                failure_types.add("queue_backlog")
            if "cpu" in desc_lower or "memory" in desc_lower or "resource" in desc_lower or "gc pause" in desc_lower or "cpu_utilization" in metric_name:
                failure_types.add("resource_exhaustion")
            if "network" in desc_lower or "packet" in desc_lower or "socket" in desc_lower or "packet_loss" in metric_name:
                failure_types.add("network_degradation")
            if "timeout" in desc_lower:
                failure_types.add("timeout")
            if "error" in desc_lower or "503" in desc_lower or "504" in desc_lower or "healthy_targets" in metric_name:
                failure_types.add("service_error")
            if "degradation" in desc_lower or "latency" in desc_lower or "app_response_time" in metric_name:
                failure_types.add("performance_degradation")

        # Metric to failure_type domain mapping helper
        metric_ft_map = {
            "db_connection_pool_utilization": "connection_pool_exhaustion",
            "batch_processing_status": "batch_execution_failure",
            "extract_processing_time_sec": "delivery_delay",
            "queue_depth_count": "queue_backlog",
            "app_cpu_utilization": "resource_exhaustion",
            "network_packet_loss_pct": "network_degradation",
            "elb_healthy_targets": "service_error",
            "app_response_time": "performance_degradation",
        }

        # Generate candidates for top components
        for component, weight_sum in component_counts.most_common(3):
            # If specific failure types exist for this component, filter out generic 'service_error'
            specific_fts = [ft for ft in failure_types if ft not in ("service_error", "performance_degradation")]
            active_fts = specific_fts if specific_fts else list(failure_types)

            for failure_type in active_fts:
                # Gather supporting evidence for this specific component + failure_type
                matching_ev_ids = []
                ft_terms = failure_type.split("_")
                for ev in evidence:
                    ev_comp = (ev.metadata.get("component") if ev.metadata else None) or ""
                    comp_match = (ev_comp == component) or (component.lower() in ev.description.lower())
                    if comp_match:
                        ev_desc = ev.description.lower()
                        ev_mname = (ev.metadata.get("metric_name") if ev.metadata else "") or ""
                        
                        # If this metric belongs to a different failure type, do not match it to other failure types
                        mapped_ft = metric_ft_map.get(ev_mname)
                        if mapped_ft and mapped_ft != failure_type:
                            continue

                        if mapped_ft == failure_type or any(term in ev_desc for term in ft_terms if len(term) > 2):
                            matching_ev_ids.append(ev.source_id)
                
                # Fallback to general component evidence if no specific failure type match
                if not matching_ev_ids:
                    matching_ev_ids = [
                        ev.source_id for ev in evidence
                        if ((ev.metadata and ev.metadata.get("component") == component) or (component.lower() in ev.description.lower()))
                        and not (metric_ft_map.get((ev.metadata.get("metric_name") if ev.metadata else "") or "") and metric_ft_map.get((ev.metadata.get("metric_name") if ev.metadata else "") or "") != failure_type)
                    ]

                candidate = ProbableRootCause(
                    component=component,
                    failure_type=failure_type,
                    description=f"{component} {failure_type.replace('_', ' ')}",
                    confidence=0.5,  # Will be updated by ranker
                    supporting_evidence_ids=matching_ev_ids[:8]
                )
                candidates.append(candidate)



        
        # Fallback: generate from services if no component evidence
        if not candidates and context.services:
            for service in context.services[:2]:
                candidate = ProbableRootCause(
                    component=service,
                    failure_type="service_error",
                    description=f"{service} service error",
                    confidence=0.3,
                    supporting_evidence_ids=[ev.source_id for ev in evidence[:3]]
                )
                candidates.append(candidate)
        
        return candidates
