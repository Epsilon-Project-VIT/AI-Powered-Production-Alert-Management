"""
Graph-based incident grouping using connected components.

Represents alert relationships as a graph and uses connected components
to form incident groups, properly handling transitive relationships.
"""

from typing import List, Dict, Set, Tuple
from collections import defaultdict

from ...stage1_ingestion.schemas import StandardizedAlert
from ..schemas import CorrelationScore


class AlertGraph:
    """
    Graph representation of alert relationships.
    
    Nodes: Alerts (identified by alert_id)
    Edges: Validated correlations between alerts
    """
    
    def __init__(self):
        """Initialize empty alert graph."""
        self.nodes: Set[str] = set()  # Alert IDs
        self.edges: Dict[str, Set[str]] = defaultdict(set)  # Adjacency list
        self.edge_scores: Dict[Tuple[str, str], float] = {}  # Edge weights
        self.alert_lookup: Dict[str, StandardizedAlert] = {}  # Alert ID -> Alert
    
    def add_node(self, alert: StandardizedAlert) -> None:
        """
        Add an alert node to the graph.
        
        Args:
            alert: StandardizedAlert to add
        """
        self.nodes.add(alert.alert_id)
        self.alert_lookup[alert.alert_id] = alert
    
    def add_edge(
        self,
        alert_id1: str,
        alert_id2: str,
        correlation_score: float
    ) -> None:
        """
        Add an edge between two alerts.
        
        Args:
            alert_id1: First alert ID
            alert_id2: Second alert ID
            correlation_score: Correlation score (0-1)
        """
        if alert_id1 not in self.nodes or alert_id2 not in self.nodes:
            raise ValueError("Both alerts must be added as nodes before creating edge")
        
        # Add bidirectional edge
        self.edges[alert_id1].add(alert_id2)
        self.edges[alert_id2].add(alert_id1)
        
        # Store score (normalized order for lookup)
        edge_key = tuple(sorted([alert_id1, alert_id2]))
        self.edge_scores[edge_key] = correlation_score
    
    def has_edge(self, alert_id1: str, alert_id2: str) -> bool:
        """
        Check if edge exists between two alerts.
        
        Args:
            alert_id1: First alert ID
            alert_id2: Second alert ID
        
        Returns:
            True if edge exists
        """
        return alert_id2 in self.edges.get(alert_id1, set())
    
    def get_edge_score(self, alert_id1: str, alert_id2: str) -> float:
        """
        Get correlation score for an edge.
        
        Args:
            alert_id1: First alert ID
            alert_id2: Second alert ID
        
        Returns:
            Correlation score, or 0.0 if no edge
        """
        edge_key = tuple(sorted([alert_id1, alert_id2]))
        return self.edge_scores.get(edge_key, 0.0)
    
    def get_neighbors(self, alert_id: str) -> Set[str]:
        """
        Get all neighbors of an alert.
        
        Args:
            alert_id: Alert ID
        
        Returns:
            Set of neighbor alert IDs
        """
        return self.edges.get(alert_id, set())
    
    def get_connected_components(self) -> List[Set[str]]:
        """
        Find connected components using DFS.
        
        Returns:
            List of connected components (each is a set of alert IDs)
        """
        visited = set()
        components = []
        
        def dfs(node: str, component: Set[str]) -> None:
            """Depth-first search to find connected component."""
            visited.add(node)
            component.add(node)
            
            for neighbor in self.get_neighbors(node):
                if neighbor not in visited:
                    dfs(neighbor, component)
        
        # Find all connected components
        for node in self.nodes:
            if node not in visited:
                component = set()
                dfs(node, component)
                components.append(component)
        
        return components
    
    def get_singleton_nodes(self) -> Set[str]:
        """
        Get nodes with no edges (singleton alerts).
        
        Returns:
            Set of alert IDs with no connections
        """
        singletons = set()
        
        for node in self.nodes:
            if not self.edges.get(node):
                singletons.add(node)
        
        return singletons
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get graph statistics.
        
        Returns:
            Dict with graph statistics
        """
        return {
            'total_nodes': len(self.nodes),
            'total_edges': sum(len(neighbors) for neighbors in self.edges.values()) // 2,
            'singleton_nodes': len(self.get_singleton_nodes()),
            'connected_components': len(self.get_connected_components()),
            'avg_degree': sum(len(neighbors) for neighbors in self.edges.values()) / len(self.nodes) if self.nodes else 0
        }


class GraphGrouper:
    """
    Groups alerts into incidents using graph-based connected components.
    
    This is the final incident grouping mechanism that replaces direct grouping.
    """
    
    def __init__(self):
        """Initialize graph grouper."""
        pass
    
    def build_graph(
        self,
        alerts: List[StandardizedAlert],
        validated_pairs: List[Tuple[StandardizedAlert, StandardizedAlert, float]]
    ) -> AlertGraph:
        """
        Build alert graph from validated correlation pairs.
        
        Args:
            alerts: List of all alerts
            validated_pairs: List of (alert1, alert2, score) tuples that passed validation
        
        Returns:
            AlertGraph with nodes and edges
        """
        graph = AlertGraph()
        
        # Add all alerts as nodes
        for alert in alerts:
            graph.add_node(alert)
        
        # Add validated relationships as edges
        for alert1, alert2, score in validated_pairs:
            graph.add_edge(alert1.alert_id, alert2.alert_id, score)
        
        return graph
    
    def group_incidents(
        self,
        graph: AlertGraph
    ) -> Tuple[List[Set[str]], Set[str]]:
        """
        Group alerts into incidents using connected components.
        
        Args:
            graph: AlertGraph with validated relationships
        
        Returns:
            Tuple of (incident_groups, singleton_alerts)
            - incident_groups: List of connected components (sets of alert IDs)
            - singleton_alerts: Set of alert IDs with no connections
        """
        # Get connected components
        components = graph.get_connected_components()
        
        # Separate multi-alert incidents from singletons
        incident_groups = []
        singleton_alerts = set()
        
        for component in components:
            if len(component) > 1:
                incident_groups.append(component)
            else:
                singleton_alerts.update(component)
        
        return incident_groups, singleton_alerts
    
    def compute_group_coherence(
        self,
        graph: AlertGraph,
        component: Set[str]
    ) -> Dict[str, any]:
        """
        Compute coherence metrics for a connected component.
        
        Args:
            graph: AlertGraph
            component: Set of alert IDs in the component
        
        Returns:
            Dict with coherence metrics
        """
        if len(component) < 2:
            return {
                'size': len(component),
                'avg_correlation': 1.0,
                'min_correlation': 1.0,
                'max_correlation': 1.0,
                'density': 1.0
            }
        
        # Get all pairwise correlations within component
        alert_ids = list(component)
        correlations = []
        
        for i in range(len(alert_ids)):
            for j in range(i + 1, len(alert_ids)):
                if graph.has_edge(alert_ids[i], alert_ids[j]):
                    score = graph.get_edge_score(alert_ids[i], alert_ids[j])
                    correlations.append(score)
        
        # Calculate metrics
        avg_correlation = sum(correlations) / len(correlations) if correlations else 0.0
        min_correlation = min(correlations) if correlations else 0.0
        max_correlation = max(correlations) if correlations else 0.0
        
        # Density: actual edges / possible edges
        n = len(component)
        possible_edges = n * (n - 1) / 2
        actual_edges = len(correlations)
        density = actual_edges / possible_edges if possible_edges > 0 else 0.0
        
        return {
            'size': n,
            'avg_correlation': avg_correlation,
            'min_correlation': min_correlation,
            'max_correlation': max_correlation,
            'density': density,
            'actual_edges': actual_edges,
            'possible_edges': int(possible_edges)
        }
    
    def explain_transitive_relationships(
        self,
        graph: AlertGraph,
        component: Set[str]
    ) -> List[str]:
        """
        Explain transitive relationships in a component.
        
        Identifies cases where A↔B and B↔C exist, causing A and C to be
        in the same incident even without a direct A↔C edge.
        
        Args:
            graph: AlertGraph
            component: Set of alert IDs
        
        Returns:
            List of explanation strings
        """
        if len(component) < 3:
            return []
        
        explanations = []
        alert_ids = list(component)
        
        # Find transitive relationships
        for i in range(len(alert_ids)):
            for j in range(i + 1, len(alert_ids)):
                alert_a = alert_ids[i]
                alert_c = alert_ids[j]
                
                # Check if A and C are NOT directly connected
                if not graph.has_edge(alert_a, alert_c):
                    # Find common neighbors (bridges)
                    neighbors_a = graph.get_neighbors(alert_a)
                    neighbors_c = graph.get_neighbors(alert_c)
                    bridges = neighbors_a & neighbors_c & component
                    
                    if bridges:
                        for bridge in bridges:
                            explanations.append(
                                f"{alert_a} ↔ {bridge} ↔ {alert_c} "
                                f"(transitive via {bridge})"
                            )
        
        return explanations[:10]  # Limit to 10 examples
