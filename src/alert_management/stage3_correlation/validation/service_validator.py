"""
Service/Component extraction and validation for alert correlation.

Extracts service/component identifiers from alert descriptions and
validates compatibility between alerts.
"""

import re
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass

from ...stage1_ingestion.schemas import StandardizedAlert


@dataclass
class ServiceComponent:
    """Represents an extracted service/component."""
    
    name: str
    category: str  # 'service', 'component', 'api', 'batch', 'database', 'unknown'
    confidence: float  # 0.0 to 1.0


class ServiceComponentExtractor:
    """
    Extracts service/component identifiers from alert descriptions.
    
    Uses rule-based patterns to identify meaningful service names
    while avoiding dynamic values.
    """
    
    def __init__(self):
        """Initialize service extractor with pattern rules."""
        
        # Known service/component patterns (case-insensitive)
        self.service_patterns = [
            # Specific service identifiers
            (re.compile(r'\b(pzht|pizza\s*hut)\b', re.IGNORECASE), 'service', 1.0),
            (re.compile(r'\b(bgsn|bridgestone)\b', re.IGNORECASE), 'service', 1.0),
            (re.compile(r'\b(eass|ea\s*sports)\b', re.IGNORECASE), 'service', 1.0),
            
            # Watcher/monitoring services
            (re.compile(r'\b(\w+)_watcher_alert\b', re.IGNORECASE), 'service', 0.9),
            (re.compile(r'\b(\w+)_watcher\b', re.IGNORECASE), 'service', 0.9),
            
            # API patterns
            (re.compile(r'\b(\w+)_api\b', re.IGNORECASE), 'api', 0.8),
            (re.compile(r'\bapi[\s_](\w+)\b', re.IGNORECASE), 'api', 0.8),
            
            # Batch/workflow patterns
            (re.compile(r'\b(\w+)_batch\b', re.IGNORECASE), 'batch', 0.8),
            (re.compile(r'\bbatch[\s_](\w+)\b', re.IGNORECASE), 'batch', 0.8),
            (re.compile(r'\b(\w+)_workflow\b', re.IGNORECASE), 'batch', 0.8),
            
            # Database patterns
            (re.compile(r'\b(\w+)[\s_]database\b', re.IGNORECASE), 'database', 0.8),
            (re.compile(r'\bdb[\s_](\w+)\b', re.IGNORECASE), 'database', 0.7),
            
            # ELB/load balancer
            (re.compile(r'\belb\b', re.IGNORECASE), 'component', 0.9),
            
            # Job/task patterns
            (re.compile(r'\b(\w+)_job\b', re.IGNORECASE), 'batch', 0.7),
            (re.compile(r'\bjob[\s_](\w+)\b', re.IGNORECASE), 'batch', 0.7),
        ]
        
        # Patterns to exclude (dynamic values, not service names)
        self.exclude_patterns = [
            re.compile(r'^\d+$'),  # Pure numbers
            re.compile(r'^<\w+>$'),  # Normalized tokens like <id>, <timestamp>
            re.compile(r'^[a-f0-9-]{8,}$', re.IGNORECASE),  # UUIDs/hex IDs
        ]
    
    def extract(self, alert: StandardizedAlert) -> List[ServiceComponent]:
        """
        Extract service/component identifiers from alert.
        
        Args:
            alert: StandardizedAlert with normalized description
        
        Returns:
            List of ServiceComponent objects
        """
        components = []
        text = alert.normalized_description
        
        for pattern, category, confidence in self.service_patterns:
            matches = pattern.finditer(text)
            
            for match in matches:
                # Extract the captured group (service name)
                if match.groups():
                    name = match.group(1).lower().strip()
                else:
                    name = match.group(0).lower().strip()
                
                # Filter out excluded patterns
                if any(exclude.match(name) for exclude in self.exclude_patterns):
                    continue
                
                # Filter out very short names (likely false positives)
                if len(name) < 2:
                    continue
                
                component = ServiceComponent(
                    name=name,
                    category=category,
                    confidence=confidence
                )
                
                # Avoid duplicates
                if not any(c.name == name and c.category == category for c in components):
                    components.append(component)
        
        # If no components found, mark as unknown
        if not components:
            components.append(ServiceComponent(
                name='unknown',
                category='unknown',
                confidence=0.0
            ))
        
        return components
    
    def get_primary_service(self, components: List[ServiceComponent]) -> ServiceComponent:
        """
        Get the primary (highest confidence) service component.
        
        Args:
            components: List of extracted components
        
        Returns:
            Primary ServiceComponent
        """
        if not components:
            return ServiceComponent(name='unknown', category='unknown', confidence=0.0)
        
        return max(components, key=lambda c: c.confidence)


class ServiceValidator:
    """
    Validates service/component compatibility between alerts.
    
    Determines if two alerts are compatible based on their
    service/component identifiers.
    """
    
    def __init__(self, extractor: ServiceComponentExtractor = None):
        """
        Initialize service validator.
        
        Args:
            extractor: ServiceComponentExtractor instance
        """
        self.extractor = extractor or ServiceComponentExtractor()
    
    def validate_compatibility(
        self,
        alert1: StandardizedAlert,
        alert2: StandardizedAlert
    ) -> Tuple[bool, float, str]:
        """
        Validate if two alerts are service-compatible.
        
        Args:
            alert1: First alert
            alert2: Second alert
        
        Returns:
            Tuple of (is_compatible, compatibility_score, reason)
            - is_compatible: True if alerts are compatible
            - compatibility_score: 0.0 to 1.0
            - reason: Explanation
        """
        components1 = self.extractor.extract(alert1)
        components2 = self.extractor.extract(alert2)
        
        # Get service names
        services1 = {c.name for c in components1}
        services2 = {c.name for c in components2}
        
        # Check for overlap
        common_services = services1 & services2
        
        if common_services:
            if 'unknown' in common_services and len(common_services) == 1:
                # Both have unknown service - compatible but low confidence
                return True, 0.5, "Both services unknown"
            else:
                # Have common identified services
                primary1 = self.extractor.get_primary_service(components1)
                primary2 = self.extractor.get_primary_service(components2)
                
                if primary1.name == primary2.name:
                    avg_conf = (primary1.confidence + primary2.confidence) / 2
                    return True, avg_conf, f"Same primary service: {primary1.name}"
                else:
                    return True, 0.7, f"Shared services: {', '.join(common_services)}"
        
        # No common services
        # Check if one is unknown (compatible but uncertain)
        if 'unknown' in services1 or 'unknown' in services2:
            return True, 0.3, "One service unknown - uncertain compatibility"
        
        # Different known services - generally incompatible
        primary1 = self.extractor.get_primary_service(components1)
        primary2 = self.extractor.get_primary_service(components2)
        
        return False, 0.0, f"Different services: {primary1.name} vs {primary2.name}"
    
    def get_service_summary(self, alert: StandardizedAlert) -> str:
        """
        Get human-readable service summary for an alert.
        
        Args:
            alert: StandardizedAlert
        
        Returns:
            Service summary string
        """
        components = self.extractor.extract(alert)
        
        if not components or (len(components) == 1 and components[0].name == 'unknown'):
            return "unknown"
        
        # List service names
        service_names = [c.name for c in components if c.name != 'unknown']
        
        if not service_names:
            return "unknown"
        
        return ", ".join(sorted(set(service_names)))
