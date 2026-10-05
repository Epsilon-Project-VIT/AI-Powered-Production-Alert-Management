"""
Exact signature matching for alert correlation.

Groups alerts with identical normalized descriptions.
"""

from typing import List, Dict, Set
from collections import defaultdict
from datetime import datetime

from ...stage1_ingestion.schemas import StandardizedAlert


class SignatureMatcher:
    """
    Groups alerts by exact normalized description match.
    
    This is the first pass of Stage 3 correlation - alerts with
    identical normalized descriptions are candidates for the same
    incident family, but temporal validation is still required.
    """
    
    def __init__(self, min_group_size: int = 1):
        """
        Initialize signature matcher.
        
        Args:
            min_group_size: Minimum alerts required to form a group
        """
        self.min_group_size = min_group_size
    
    def find_signature_groups(
        self,
        alerts: List[StandardizedAlert]
    ) -> Dict[str, List[StandardizedAlert]]:
        """
        Group alerts by exact normalized description signature.
        
        Args:
            alerts: List of standardized alerts
        
        Returns:
            Dict mapping signature to list of matching alerts
        """
        signature_groups = defaultdict(list)
        
        for alert in alerts:
            signature = alert.normalized_description
            signature_groups[signature].append(alert)
        
        # Filter by minimum group size
        filtered_groups = {
            sig: alerts_list
            for sig, alerts_list in signature_groups.items()
            if len(alerts_list) >= self.min_group_size
        }
        
        return filtered_groups
    
    def get_signature_statistics(
        self,
        alerts: List[StandardizedAlert]
    ) -> Dict[str, any]:
        """
        Get statistics about signature matching.
        
        Args:
            alerts: List of standardized alerts
        
        Returns:
            Dict with signature match statistics
        """
        signature_groups = self.find_signature_groups(alerts)
        
        total_alerts = len(alerts)
        unique_signatures = len(set(a.normalized_description for a in alerts))
        repeated_signatures = len(signature_groups)
        alerts_in_repeated_groups = sum(len(group) for group in signature_groups.values())
        
        # Find largest groups
        largest_groups = sorted(
            signature_groups.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]
        
        return {
            'total_alerts': total_alerts,
            'unique_signatures': unique_signatures,
            'repeated_signatures': repeated_signatures,
            'alerts_in_repeated_groups': alerts_in_repeated_groups,
            'repeat_percentage': alerts_in_repeated_groups / total_alerts if total_alerts > 0 else 0,
            'largest_groups': [
                {
                    'signature': sig[:100] + '...' if len(sig) > 100 else sig,
                    'count': len(group),
                    'clients': list(set(a.client for a in group))
                }
                for sig, group in largest_groups
            ]
        }
    
    def validate_temporal_coherence(
        self,
        signature_groups: Dict[str, List[StandardizedAlert]],
        max_time_gap_hours: float = 24.0
    ) -> Dict[str, List[List[StandardizedAlert]]]:
        """
        Split signature groups into temporal windows.
        
        Alerts with the same signature but separated by large time gaps
        likely represent different incident occurrences.
        
        Args:
            signature_groups: Dict of signature to alert lists
            max_time_gap_hours: Maximum time gap to consider alerts related
        
        Returns:
            Dict mapping signature to list of temporal sub-groups
        """
        temporal_groups = {}
        
        for signature, alerts_list in signature_groups.items():
            # Sort by time
            sorted_alerts = sorted(alerts_list, key=lambda a: a.created_at)
            
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
            temporal_groups[signature] = subgroups
        
        return temporal_groups
    
    def validate_client_coherence(
        self,
        alerts_group: List[StandardizedAlert]
    ) -> bool:
        """
        Check if all alerts in a group belong to the same client.
        
        Args:
            alerts_group: List of alerts to validate
        
        Returns:
            True if all alerts are from same client
        """
        if not alerts_group:
            return True
        
        clients = set(a.client for a in alerts_group)
        return len(clients) == 1
