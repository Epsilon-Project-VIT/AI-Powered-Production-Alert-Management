"""
Stage 3 Correlation Pipeline.

Orchestrates alert correlation and incident grouping using:
- Exact/signature candidate generation
- Semantic similarity
- Temporal validation
- Client validation
- Service/component validation
- Stage 2 compatibility validation (Alert Type, Severity, Business Impact, Priority, Routing)
- Graph-based connected components grouping

IMPORTANT: Stage 2 compatibility now uses finalized canonical models for:
- Alert Type (F1=0.60, 16 classes in test set from 20-class taxonomy)
- Severity (F1=0.88, 4 classes)
- Business Impact (F1=0.94, 3 classes)
- Priority (existing model)
- Assignment Group (existing model)
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime
import numpy as np

from ..stage1_ingestion.schemas import StandardizedAlert
from ..stage2_classification.schemas import EnrichedAlert
from .schemas import IncidentGroup, CorrelationScore
from .clustering.signature_matcher import SignatureMatcher
from .clustering.semantic_clusterer import SemanticClusterer
from .validation.service_validator import ServiceComponentExtractor, ServiceValidator
from .validation.stage2_validator import Stage2CompatibilityValidator
from .grouping.graph_grouper import AlertGraph, GraphGrouper


class CorrelationPipeline:
    """
    Stage 3 pipeline that correlates alerts into incident groups.
    
    Process:
    1. Exact signature matching
    2. Temporal validation
    3. Client validation
    4. Semantic clustering (HDBSCAN) for non-exact matches
    5. Final correlation scoring and incident creation
    """
    
    def __init__(
        self,
        signature_matcher: SignatureMatcher = None,
        semantic_clusterer: SemanticClusterer = None,
        service_validator: ServiceValidator = None,
        stage2_validator: Stage2CompatibilityValidator = None,
        graph_grouper: GraphGrouper = None,
        max_time_gap_hours: float = 24.0,
        min_correlation_score: float = 0.7,
        correlation_weights: Dict[str, float] = None
    ):
        """
        Initialize correlation pipeline.
        
        Args:
            signature_matcher: Signature matching component
            semantic_clusterer: Semantic clustering component
            service_validator: Service/component validation component
            stage2_validator: Stage 2 compatibility validation component
            graph_grouper: Graph-based grouping component
            max_time_gap_hours: Maximum time gap for temporal validation (experimental)
            min_correlation_score: Minimum score to correlate alerts (experimental)
            correlation_weights: Weights for correlation scoring (experimental)
        """
        self.signature_matcher = signature_matcher or SignatureMatcher(min_group_size=2)
        self.semantic_clusterer = semantic_clusterer or SemanticClusterer()
        self.service_validator = service_validator or ServiceValidator()
        self.stage2_validator = stage2_validator or Stage2CompatibilityValidator()
        self.graph_grouper = graph_grouper or GraphGrouper()
        self.max_time_gap_hours = max_time_gap_hours
        self.min_correlation_score = min_correlation_score
        
        # Experimental correlation weights (configurable)
        self.correlation_weights = correlation_weights or {
            'semantic': 0.30,
            'temporal': 0.20,
            'client': 0.15,
            'family': 0.10,
            'service': 0.15,
            'stage2': 0.10
        }
        
        # Validate weights sum to 1.0
        weight_sum = sum(self.correlation_weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            raise ValueError(f"Correlation weights must sum to 1.0, got {weight_sum}")
        
        self._incident_counter = 0
    
    def _generate_incident_id(self) -> str:
        """Generate unique incident ID."""
        self._incident_counter += 1
        return f"INCIDENT-{self._incident_counter:04d}"
    
    def _create_incident_group(
        self,
        alerts: List[StandardizedAlert],
        correlation_method: str,
        avg_score: float = None
    ) -> IncidentGroup:
        """
        Create an IncidentGroup from a list of correlated alerts.
        
        Args:
            alerts: List of correlated alerts
            correlation_method: Method used to correlate
            avg_score: Average correlation score
        
        Returns:
            IncidentGroup object
        """
        # Sort by time
        sorted_alerts = sorted(alerts, key=lambda a: a.created_at)
        
        incident = IncidentGroup(
            incident_id=self._generate_incident_id(),
            alert_ids=[a.alert_id for a in sorted_alerts],
            primary_alert_id=sorted_alerts[0].alert_id,
            client=sorted_alerts[0].client,
            incident_start=sorted_alerts[0].created_at,
            incident_end=sorted_alerts[-1].created_at if len(sorted_alerts) > 1 else None,
            alert_count=len(sorted_alerts),
            normalized_signature=sorted_alerts[0].normalized_description,
            correlation_method=correlation_method,
            avg_correlation_score=avg_score
        )
        
        return incident
    
    def correlate_alerts(
        self,
        alerts: List[StandardizedAlert],
        use_graph_grouping: bool = True
    ) -> Tuple[List[IncidentGroup], List[StandardizedAlert]]:
        """
        Correlate alerts into incident groups using graph-based connected components.
        
        Process:
        1. Phase 1: Exact signature matching + validation → validated pairs
        2. Phase 2: Semantic clustering + validation → validated pairs
        3. Build alert graph from all validated pairs
        4. Find connected components → incident groups
        
        Args:
            alerts: List of standardized alerts
            use_graph_grouping: Whether to use graph-based grouping (True) or legacy direct grouping (False)
        
        Returns:
            Tuple of (incident_groups, uncorrelated_alerts)
        """
        print(f"\n[Stage 3] Correlating {len(alerts)} alerts...")
        print("-" * 70)
        
        if use_graph_grouping:
            return self._correlate_with_graph(alerts)
        else:
            return self._correlate_legacy(alerts)
    
    def _correlate_with_graph(
        self,
        alerts: List[StandardizedAlert]
    ) -> Tuple[List[IncidentGroup], List[StandardizedAlert]]:
        """
        Correlate alerts using graph-based connected components.
        
        Args:
            alerts: List of standardized alerts
        
        Returns:
            Tuple of (incident_groups, uncorrelated_alerts)
        """
        validated_pairs = []
        
        # Phase 1: Exact signature matching
        print("[Phase 1] Exact signature matching...")
        signature_groups = self.signature_matcher.find_signature_groups(alerts)
        print(f"  Found {len(signature_groups)} unique signatures with repeats")
        
        phase1_pairs = 0
        for signature, sig_alerts in signature_groups.items():
            # Apply temporal and client validation
            temporal_subgroups = self.signature_matcher.validate_temporal_coherence(
                {signature: sig_alerts},
                self.max_time_gap_hours
            )[signature]
            
            for subgroup in temporal_subgroups:
                # Validate client coherence
                if self.signature_matcher.validate_client_coherence(subgroup):
                    # All pairs in this subgroup are validated
                    for i in range(len(subgroup)):
                        for j in range(i + 1, len(subgroup)):
                            validated_pairs.append((subgroup[i], subgroup[j], 1.0))
                            phase1_pairs += 1
        
        print(f"  Validated {phase1_pairs} alert pairs from exact matches")
        
        # Phase 2: Semantic clustering for remaining alerts
        processed_alert_ids = set()
        for alert1, alert2, _ in validated_pairs:
            processed_alert_ids.add(alert1.alert_id)
            processed_alert_ids.add(alert2.alert_id)
        
        remaining_alerts = [a for a in alerts if a.alert_id not in processed_alert_ids]
        
        phase2_pairs = 0
        if len(remaining_alerts) >= self.semantic_clusterer.min_cluster_size:
            print(f"\n[Phase 2] Semantic clustering for {len(remaining_alerts)} remaining alerts...")
            
            cluster_labels, embeddings = self.semantic_clusterer.cluster_alerts(remaining_alerts)
            cluster_groups = self.semantic_clusterer.get_cluster_groups(remaining_alerts, cluster_labels)
            
            print(f"  Found {len(cluster_groups)} semantic clusters")
            
            for cluster_id, cluster_alerts in cluster_groups.items():
                # Filter by client
                client_filtered = self.semantic_clusterer.filter_by_client(
                    {cluster_id: cluster_alerts}
                )[cluster_id]
                
                for client, client_alerts in client_filtered.items():
                    # Filter by temporal proximity
                    temporal_subgroups = self.semantic_clusterer.filter_by_time_proximity(
                        client_alerts,
                        self.max_time_gap_hours
                    )
                    
                    for subgroup in temporal_subgroups:
                        if len(subgroup) >= 2:
                            # Validate semantic coherence
                            subgroup_indices = [remaining_alerts.index(a) for a in subgroup]
                            is_coherent, avg_sim = self.semantic_clusterer.validate_cluster_coherence(
                                subgroup,
                                embeddings,
                                subgroup_indices
                            )
                            
                            if is_coherent and avg_sim >= self.min_correlation_score:
                                # Validate service compatibility for all pairs
                                for i in range(len(subgroup)):
                                    for j in range(i + 1, len(subgroup)):
                                        service_compatible, service_score, _ = self.service_validator.validate_compatibility(
                                            subgroup[i], subgroup[j]
                                        )
                                        
                                        # Only add edge if service compatible
                                        if service_compatible:
                                            validated_pairs.append((subgroup[i], subgroup[j], avg_sim))
                                            phase2_pairs += 1
            
            print(f"  Validated {phase2_pairs} alert pairs from semantic clustering")
        
        # Phase 3: Build graph and find connected components
        print(f"\n[Phase 3] Building alert graph...")
        graph = self.graph_grouper.build_graph(alerts, validated_pairs)
        
        graph_stats = graph.get_statistics()
        print(f"  Graph: {graph_stats['total_nodes']} nodes, {graph_stats['total_edges']} edges")
        print(f"  Singleton nodes: {graph_stats['singleton_nodes']}")
        
        print(f"\n[Phase 4] Finding connected components...")
        incident_components, singleton_alert_ids = self.graph_grouper.group_incidents(graph)
        
        print(f"  Found {len(incident_components)} connected components")
        print(f"  Singleton alerts: {len(singleton_alert_ids)}")
        
        # Create IncidentGroup objects from components
        incident_groups = []
        for component in incident_components:
            component_alerts = [graph.alert_lookup[aid] for aid in component]
            
            # Compute average correlation score
            coherence = self.graph_grouper.compute_group_coherence(graph, component)
            
            # Determine correlation method
            # If all pairs have perfect score (1.0), it's exact match
            if coherence['min_correlation'] == 1.0:
                method = 'exact_signature_match'
            else:
                method = 'graph_connected_component'
            
            incident = self._create_incident_group(
                component_alerts,
                correlation_method=method,
                avg_score=coherence['avg_correlation']
            )
            incident_groups.append(incident)
        
        # Uncorrelated alerts
        uncorrelated = [graph.alert_lookup[aid] for aid in singleton_alert_ids]
        
        print(f"\n[Stage 3] Correlation complete:")
        print(f"  Total incidents: {len(incident_groups)}")
        print(f"  Correlated alerts: {sum(inc.alert_count for inc in incident_groups)}")
        print(f"  Uncorrelated alerts: {len(uncorrelated)}")
        print(f"  Graph density: {graph_stats['avg_degree']:.2f} avg edges per node")
        print("-" * 70)
        
        return incident_groups, uncorrelated
    
    def _correlate_legacy(
        self,
        alerts: List[StandardizedAlert]
    ) -> Tuple[List[IncidentGroup], List[StandardizedAlert]]:
        """
        Legacy correlation method using direct grouping (preserved for comparison).
        
        Args:
            alerts: List of standardized alerts
        
        Returns:
            Tuple of (incident_groups, uncorrelated_alerts)
        """
        incident_groups = []
        processed_alert_ids = set()
        
        # Phase 1: Exact signature matching
        print("[Phase 1] Exact signature matching (legacy)...")
        signature_groups = self.signature_matcher.find_signature_groups(alerts)
        
        print(f"  Found {len(signature_groups)} unique signatures with repeats")
        
        for signature, sig_alerts in signature_groups.items():
            if not self.signature_matcher.validate_client_coherence(sig_alerts):
                by_client = {}
                for alert in sig_alerts:
                    if alert.client not in by_client:
                        by_client[alert.client] = []
                    by_client[alert.client].append(alert)
                
                for client, client_alerts in by_client.items():
                    temporal_subgroups = self.signature_matcher.validate_temporal_coherence(
                        {signature: client_alerts},
                        self.max_time_gap_hours
                    )[signature]
                    
                    for subgroup in temporal_subgroups:
                        incident = self._create_incident_group(
                            subgroup,
                            correlation_method='exact_signature_match',
                            avg_score=1.0
                        )
                        incident_groups.append(incident)
                        processed_alert_ids.update(a.alert_id for a in subgroup)
            else:
                temporal_subgroups = self.signature_matcher.validate_temporal_coherence(
                    {signature: sig_alerts},
                    self.max_time_gap_hours
                )[signature]
                
                for subgroup in temporal_subgroups:
                    incident = self._create_incident_group(
                        subgroup,
                        correlation_method='exact_signature_match',
                        avg_score=1.0
                    )
                    incident_groups.append(incident)
                    processed_alert_ids.update(a.alert_id for a in subgroup)
        
        print(f"  Created {len(incident_groups)} incidents from exact matches")
        
        remaining_alerts = [a for a in alerts if a.alert_id not in processed_alert_ids]
        
        if len(remaining_alerts) >= self.semantic_clusterer.min_cluster_size:
            print(f"\n[Phase 2] Semantic clustering for {len(remaining_alerts)} remaining alerts (legacy)...")
            
            cluster_labels, embeddings = self.semantic_clusterer.cluster_alerts(remaining_alerts)
            cluster_groups = self.semantic_clusterer.get_cluster_groups(remaining_alerts, cluster_labels)
            
            print(f"  Found {len(cluster_groups)} semantic clusters")
            
            for cluster_id, cluster_alerts in cluster_groups.items():
                client_filtered = self.semantic_clusterer.filter_by_client(
                    {cluster_id: cluster_alerts}
                )[cluster_id]
                
                for client, client_alerts in client_filtered.items():
                    temporal_subgroups = self.semantic_clusterer.filter_by_time_proximity(
                        client_alerts,
                        self.max_time_gap_hours
                    )
                    
                    for subgroup in temporal_subgroups:
                        if len(subgroup) >= 2:
                            subgroup_indices = [remaining_alerts.index(a) for a in subgroup]
                            _, avg_sim = self.semantic_clusterer.validate_cluster_coherence(
                                subgroup,
                                embeddings,
                                subgroup_indices
                            )
                            
                            if avg_sim >= self.min_correlation_score:
                                incident = self._create_incident_group(
                                    subgroup,
                                    correlation_method='semantic_clustering',
                                    avg_score=float(avg_sim)
                                )
                                incident_groups.append(incident)
                                processed_alert_ids.update(a.alert_id for a in subgroup)
        
        uncorrelated = [a for a in alerts if a.alert_id not in processed_alert_ids]
        
        print(f"\n[Stage 3] Correlation complete (legacy):")
        print(f"  Total incidents: {len(incident_groups)}")
        print(f"  Correlated alerts: {len(processed_alert_ids)}")
        print(f"  Uncorrelated alerts: {len(uncorrelated)}")
        print("-" * 70)
        
        return incident_groups, uncorrelated
    
    def compute_correlation_score(
        self,
        alert1: StandardizedAlert,
        alert2: StandardizedAlert,
        embeddings: np.ndarray = None,
        idx1: int = None,
        idx2: int = None,
        enriched1: EnrichedAlert = None,
        enriched2: EnrichedAlert = None
    ) -> CorrelationScore:
        """
        Compute detailed correlation score between two alerts.
        
        Uses multiple signals with configurable experimental weights:
        - Semantic similarity (embedding cosine similarity)
        - Temporal proximity (exponential decay)
        - Client match (binary)
        - Alert family/signature match (heuristic)
        - Service/component compatibility (rule-based extraction)
        - Stage 2 compatibility (when enriched alerts available)
        
        IMPORTANT: This is an EXPERIMENTAL correlation score, NOT a calibrated probability.
        All weights and thresholds are configurable defaults requiring validation.
        
        Args:
            alert1: First alert
            alert2: Second alert
            embeddings: Precomputed embeddings (optional)
            idx1: Index of alert1 in embeddings (optional)
            idx2: Index of alert2 in embeddings (optional)
            enriched1: EnrichedAlert for alert1 (optional)
            enriched2: EnrichedAlert for alert2 (optional)
        
        Returns:
            CorrelationScore object
        """
        # 1. Semantic similarity
        if embeddings is not None and idx1 is not None and idx2 is not None:
            emb1 = embeddings[idx1] / np.linalg.norm(embeddings[idx1])
            emb2 = embeddings[idx2] / np.linalg.norm(embeddings[idx2])
            semantic_sim = float(np.dot(emb1, emb2))
        else:
            # Compute on-the-fly
            emb = self.semantic_clusterer.generate_embeddings([alert1, alert2])
            similarity_matrix = self.semantic_clusterer.compute_similarity_matrix(emb)
            semantic_sim = float(similarity_matrix[0, 1])
        
        # Clip to valid range due to floating point precision
        semantic_sim = min(1.0, max(0.0, semantic_sim))
        
        # 2. Temporal proximity (exponential decay)
        time_diff_hours = abs((alert2.created_at - alert1.created_at).total_seconds()) / 3600
        temporal_proximity = np.exp(-time_diff_hours / self.max_time_gap_hours)
        
        # 3. Client match
        client_match = alert1.client == alert2.client
        
        # 4. Alert family match (simple heuristic: first 50 chars of normalized description)
        alert_family_match = alert1.normalized_description[:50] == alert2.normalized_description[:50]
        
        # 5. Service/component compatibility
        service_compatible, service_score, service_reason = self.service_validator.validate_compatibility(
            alert1, alert2
        )
        
        # 6. Stage 2 compatibility (if enriched alerts available)
        stage2_compatible = True
        stage2_score = 0.5  # Neutral default
        
        if enriched1 is not None and enriched2 is not None:
            if self.stage2_validator.can_use_for_correlation(enriched1) and \
               self.stage2_validator.can_use_for_correlation(enriched2):
                stage2_compatible, stage2_score, stage2_reason = self.stage2_validator.validate_compatibility(
                    enriched1, enriched2,
                    use_priority=True,
                    use_routing=True,
                    use_alert_type=True,  # ✅ NOW ENABLED (canonical model available)
                    use_severity=True,  # ✅ NOW ENABLED (canonical model available)
                    use_business_impact=True  # ✅ NOW ENABLED (canonical model available)
                )
        
        # Overall score (weighted combination - EXPERIMENTAL)
        weights = self.correlation_weights
        
        overall = (
            weights['semantic'] * semantic_sim +
            weights['temporal'] * temporal_proximity +
            weights['client'] * (1.0 if client_match else 0.0) +
            weights['family'] * (1.0 if alert_family_match else 0.0) +
            weights['service'] * service_score +
            weights['stage2'] * stage2_score
        )
        
        return CorrelationScore(
            semantic_similarity=semantic_sim,
            temporal_proximity=float(temporal_proximity),
            client_match=client_match,
            alert_family_match=alert_family_match,
            service_compatibility=service_score,
            stage2_compatibility=stage2_score,
            overall_score=overall
        )
    
    def get_incident_statistics(
        self,
        incident_groups: List[IncidentGroup]
    ) -> Dict[str, any]:
        """
        Get statistics about incident grouping.
        
        Args:
            incident_groups: List of incident groups
        
        Returns:
            Dict with incident statistics
        """
        if not incident_groups:
            return {
                'total_incidents': 0,
                'total_alerts_in_incidents': 0,
                'avg_alerts_per_incident': 0,
                'max_alerts_in_incident': 0,
                'incidents_by_method': {},
                'incidents_by_client': {}
            }
        
        total_alerts = sum(inc.alert_count for inc in incident_groups)
        
        by_method = {}
        for inc in incident_groups:
            by_method[inc.correlation_method] = by_method.get(inc.correlation_method, 0) + 1
        
        by_client = {}
        for inc in incident_groups:
            by_client[inc.client] = by_client.get(inc.client, 0) + 1
        
        return {
            'total_incidents': len(incident_groups),
            'total_alerts_in_incidents': total_alerts,
            'avg_alerts_per_incident': total_alerts / len(incident_groups),
            'max_alerts_in_incident': max(inc.alert_count for inc in incident_groups),
            'incidents_by_method': by_method,
            'incidents_by_client': by_client
        }
    
    def get_correlation_configuration(self) -> Dict[str, any]:
        """
        Get current correlation configuration.
        
        Returns:
            Dict with configuration parameters
        """
        return {
            'temporal_window_hours': self.max_time_gap_hours,
            'temporal_window_status': 'Experimental default - not validated',
            'min_correlation_score': self.min_correlation_score,
            'correlation_score_status': 'Experimental threshold - not calibrated probability',
            'correlation_weights': self.correlation_weights.copy(),
            'weights_status': 'Experimental weights - configurable',
            'weight_formula': (
                f"{self.correlation_weights['semantic']:.2f} * semantic + "
                f"{self.correlation_weights['temporal']:.2f} * temporal + "
                f"{self.correlation_weights['client']:.2f} * client + "
                f"{self.correlation_weights['family']:.2f} * family + "
                f"{self.correlation_weights['service']:.2f} * service + "
                f"{self.correlation_weights['stage2']:.2f} * stage2"
            ),
            'stage2_fields_available': self.stage2_validator.get_available_fields_status(),
            'clustering_method': 'HDBSCAN',
            'grouping_method': 'Graph-based connected components'
        }
