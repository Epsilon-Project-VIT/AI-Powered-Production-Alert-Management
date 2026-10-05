"""
Semantic clustering using embeddings and HDBSCAN.

Groups alerts by semantic similarity when exact matches don't exist.
"""

from typing import List, Dict, Tuple, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import hdbscan

from ...stage1_ingestion.schemas import StandardizedAlert
from ...stage2_classification.schemas import EnrichedAlert


class SemanticClusterer:
    """
    Clusters alerts using embeddings and HDBSCAN.
    
    This is the second pass of Stage 3 correlation - for alerts that
    don't have exact signature matches, we use semantic similarity
    to find related alerts.
    """
    
    def __init__(
        self,
        embedding_model: str = 'all-MiniLM-L6-v2',
        min_cluster_size: int = 2,
        min_samples: int = 1,
        metric: str = 'euclidean'
    ):
        """
        Initialize semantic clusterer.
        
        Args:
            embedding_model: Sentence transformer model name
            min_cluster_size: Minimum alerts for HDBSCAN cluster
            min_samples: Minimum samples for HDBSCAN core points
            metric: Distance metric for HDBSCAN
        """
        self.embedding_model_name = embedding_model
        self.embedding_model = SentenceTransformer(embedding_model)
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.metric = metric
        
        self._embeddings_cache = {}
    
    def generate_embeddings(
        self,
        alerts: List[StandardizedAlert],
        use_cache: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for alert descriptions.
        
        Args:
            alerts: List of standardized alerts
            use_cache: Whether to use cached embeddings
        
        Returns:
            Array of embeddings (n_alerts, embedding_dim)
        """
        texts = [alert.normalized_description for alert in alerts]
        alert_ids = [alert.alert_id for alert in alerts]
        
        # Check cache
        if use_cache:
            uncached_indices = []
            embeddings = []
            
            for i, alert_id in enumerate(alert_ids):
                if alert_id in self._embeddings_cache:
                    embeddings.append(self._embeddings_cache[alert_id])
                else:
                    uncached_indices.append(i)
            
            # Generate embeddings for uncached alerts
            if uncached_indices:
                uncached_texts = [texts[i] for i in uncached_indices]
                uncached_embeddings = self.embedding_model.encode(
                    uncached_texts,
                    show_progress_bar=False,
                    convert_to_numpy=True
                )
                
                # Cache them
                for i, idx in enumerate(uncached_indices):
                    self._embeddings_cache[alert_ids[idx]] = uncached_embeddings[i]
                    embeddings.insert(idx, uncached_embeddings[i])
            
            return np.array(embeddings)
        else:
            # Generate all embeddings
            embeddings = self.embedding_model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            return embeddings
    
    def compute_similarity_matrix(
        self,
        embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute pairwise cosine similarity matrix.
        
        Args:
            embeddings: Array of embeddings (n_alerts, embedding_dim)
        
        Returns:
            Similarity matrix (n_alerts, n_alerts)
        """
        # Normalize embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized_embeddings = embeddings / norms
        
        # Compute cosine similarity
        similarity_matrix = np.dot(normalized_embeddings, normalized_embeddings.T)
        
        return similarity_matrix
    
    def cluster_alerts(
        self,
        alerts: List[StandardizedAlert]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Cluster alerts using HDBSCAN.
        
        Args:
            alerts: List of standardized alerts
        
        Returns:
            Tuple of (cluster_labels, embeddings)
            - cluster_labels: Array of cluster assignments (-1 = noise)
            - embeddings: Array of alert embeddings
        """
        if len(alerts) < self.min_cluster_size:
            # Not enough alerts to cluster
            return np.array([-1] * len(alerts)), np.array([])
        
        # Generate embeddings
        embeddings = self.generate_embeddings(alerts)
        
        # Cluster with HDBSCAN
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric=self.metric,
            cluster_selection_method='eom'
        )
        
        cluster_labels = clusterer.fit_predict(embeddings)
        
        return cluster_labels, embeddings
    
    def get_cluster_groups(
        self,
        alerts: List[StandardizedAlert],
        cluster_labels: np.ndarray
    ) -> Dict[int, List[StandardizedAlert]]:
        """
        Group alerts by cluster label.
        
        Args:
            alerts: List of standardized alerts
            cluster_labels: Cluster assignments from HDBSCAN
        
        Returns:
            Dict mapping cluster ID to list of alerts
        """
        cluster_groups = {}
        
        for alert, label in zip(alerts, cluster_labels):
            if label == -1:
                # Noise point - skip or handle separately
                continue
            
            if label not in cluster_groups:
                cluster_groups[label] = []
            
            cluster_groups[label].append(alert)
        
        return cluster_groups
    
    def validate_cluster_coherence(
        self,
        cluster_alerts: List[StandardizedAlert],
        embeddings: np.ndarray,
        cluster_indices: List[int],
        min_avg_similarity: float = 0.7
    ) -> Tuple[bool, float]:
        """
        Validate that a cluster is semantically coherent.
        
        Args:
            cluster_alerts: Alerts in the cluster
            embeddings: All alert embeddings
            cluster_indices: Indices of cluster alerts in embeddings array
            min_avg_similarity: Minimum average similarity threshold
        
        Returns:
            Tuple of (is_coherent, avg_similarity)
        """
        if len(cluster_alerts) < 2:
            return True, 1.0
        
        # Get cluster embeddings
        cluster_embeddings = embeddings[cluster_indices]
        
        # Compute pairwise similarities
        similarity_matrix = self.compute_similarity_matrix(cluster_embeddings)
        
        # Calculate average pairwise similarity (excluding diagonal)
        n = len(cluster_embeddings)
        avg_similarity = (np.sum(similarity_matrix) - n) / (n * (n - 1))
        
        is_coherent = avg_similarity >= min_avg_similarity
        
        return is_coherent, avg_similarity
    
    def filter_by_client(
        self,
        cluster_groups: Dict[int, List[StandardizedAlert]]
    ) -> Dict[int, Dict[str, List[StandardizedAlert]]]:
        """
        Split clusters by client.
        
        Clusters should not mix alerts from different clients.
        
        Args:
            cluster_groups: Dict of cluster ID to alerts
        
        Returns:
            Dict of cluster ID to dict of client to alerts
        """
        filtered_groups = {}
        
        for cluster_id, alerts in cluster_groups.items():
            # Group by client
            client_groups = {}
            for alert in alerts:
                if alert.client not in client_groups:
                    client_groups[alert.client] = []
                client_groups[alert.client].append(alert)
            
            filtered_groups[cluster_id] = client_groups
        
        return filtered_groups
    
    def filter_by_time_proximity(
        self,
        alerts: List[StandardizedAlert],
        max_time_gap_hours: float = 24.0
    ) -> List[List[StandardizedAlert]]:
        """
        Split alert group into temporal windows.
        
        Args:
            alerts: List of alerts (assumed same client, same cluster)
            max_time_gap_hours: Maximum time gap to consider related
        
        Returns:
            List of temporal sub-groups
        """
        if len(alerts) <= 1:
            return [alerts]
        
        # Sort by time
        sorted_alerts = sorted(alerts, key=lambda a: a.created_at)
        
        # Split into temporal windows
        subgroups = []
        current_group = [sorted_alerts[0]]
        
        for i in range(1, len(sorted_alerts)):
            time_diff = (sorted_alerts[i].created_at - current_group[-1].created_at).total_seconds() / 3600
            
            if time_diff <= max_time_gap_hours:
                current_group.append(sorted_alerts[i])
            else:
                subgroups.append(current_group)
                current_group = [sorted_alerts[i]]
        
        subgroups.append(current_group)
        
        return subgroups
