"""
Incident Context Builder - Transform Stage 3 IncidentGroup into Stage 4 IncidentContext.

Responsibilities:
- Resolve alert IDs to full EnrichedAlert records
- Build diagnostic time window
- Aggregate alert metadata
- Extract services/components
- Preserve Stage 2 prediction provenance
- Handle missing alerts explicitly
"""

from typing import List, Dict, Set, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from alert_management.stage3_correlation.schemas import IncidentGroup
from alert_management.stage2_classification.schemas import EnrichedAlert
from alert_management.stage4_analysis.schemas import IncidentContext, SourceType


class ContextBuilderConfig(BaseModel):
    """Configuration for context builder."""
    
    pre_window_minutes: int = Field(
        default=30,
        ge=0,
        description="Minutes before incident start for diagnostic window"
    )
    
    post_window_minutes: int = Field(
        default=30,
        ge=0,
        description="Minutes after incident end for diagnostic window"
    )
    
    require_all_alerts: bool = Field(
        default=False,
        description="If True, fail if any alert ID cannot be resolved"
    )


class IncidentContextBuilder:
    """
    Build IncidentContext from IncidentGroup + EnrichedAlerts.
    """
    
    def __init__(self, config: Optional[ContextBuilderConfig] = None):
        """
        Initialize context builder.
        
        Args:
            config: Optional configuration, uses defaults if not provided
        """
        self.config = config or ContextBuilderConfig()
    
    def build_context(
        self,
        incident_group: IncidentGroup,
        enriched_alerts: List[EnrichedAlert]
    ) -> IncidentContext:
        """
        Build IncidentContext from IncidentGroup and corresponding alerts.
        
        Args:
            incident_group: Stage 3 incident group
            enriched_alerts: All available enriched alerts
            
        Returns:
            IncidentContext ready for Stage 4 analysis
            
        Raises:
            ValueError: If critical data is missing or inconsistent
        """
        # Build alert lookup
        alert_lookup = {alert.alert_id: alert for alert in enriched_alerts}
        
        # Resolve alert IDs
        resolved_alerts = []
        missing_ids = []
        
        for alert_id in incident_group.alert_ids:
            alert = alert_lookup.get(alert_id)
            if alert:
                resolved_alerts.append(alert)
            else:
                missing_ids.append(alert_id)
        
        # Handle missing alerts
        if missing_ids:
            if self.config.require_all_alerts:
                raise ValueError(
                    f"Cannot resolve alert IDs: {missing_ids}. "
                    f"Required {len(incident_group.alert_ids)} alerts, "
                    f"found {len(resolved_alerts)}."
                )
        
        if not resolved_alerts:
            raise ValueError(
                f"No alerts resolved for incident {incident_group.incident_id}. "
                f"All {len(incident_group.alert_ids)} alert IDs are missing."
            )
        
        # Verify client consistency
        clients = {alert.client for alert in resolved_alerts}
        if len(clients) > 1:
            raise ValueError(
                f"Incident {incident_group.incident_id} has inconsistent clients: {clients}"
            )
        
        # Select primary alert
        primary_alert = self._select_primary_alert(
            incident_group.primary_alert_id,
            resolved_alerts
        )
        
        # Extract timestamps
        incident_start = min(alert.created_at for alert in resolved_alerts)
        incident_end = max(alert.created_at for alert in resolved_alerts)
        
        # Build diagnostic window
        diagnostic_start = incident_start - timedelta(
            minutes=self.config.pre_window_minutes
        )
        diagnostic_end = incident_end + timedelta(
            minutes=self.config.post_window_minutes
        )
        
        # Extract services/components
        services = self._extract_services(resolved_alerts)
        
        # Collect normalized descriptions
        normalized_descriptions = self._collect_normalized_descriptions(resolved_alerts)
        
        # Collect Stage 2 predictions with provenance
        stage2_predictions = self._collect_stage2_predictions(resolved_alerts)
        
        # Build IncidentContext
        context = IncidentContext(
            incident_id=incident_group.incident_id,
            alert_ids=[alert.alert_id for alert in resolved_alerts],
            client=list(clients)[0],
            incident_start=incident_start,
            incident_end=incident_end,
            primary_alert_id=primary_alert.alert_id,
            alert_count=len(resolved_alerts),
            services=services,
            components=services,  # Use same list for components
            normalized_descriptions=normalized_descriptions,
            diagnostic_start=diagnostic_start,
            diagnostic_end=diagnostic_end,
            stage2_predictions=stage2_predictions
        )
        
        return context
    
    def _select_primary_alert(
        self,
        suggested_primary_id: str,
        alerts: List[EnrichedAlert]
    ) -> EnrichedAlert:
        """
        Select primary alert deterministically.
        
        Prefers the suggested primary ID from Stage 3.
        Falls back to earliest alert.
        
        Args:
            suggested_primary_id: Primary alert ID from Stage 3
            alerts: Resolved alerts
            
        Returns:
            Primary alert
        """
        # Try to use suggested primary
        for alert in alerts:
            if alert.alert_id == suggested_primary_id:
                return alert
        
        # Fallback: earliest alert
        return min(alerts, key=lambda a: a.created_at)
    
    def _collect_normalized_descriptions(self, alerts: List[EnrichedAlert]) -> List[str]:
        """
        Collect normalized descriptions from all alerts.
        
        Preserves order, includes duplicates for complete context.
        
        Args:
            alerts: Resolved alerts
            
        Returns:
            List of normalized descriptions
        """
        descriptions = []
        
        for alert in sorted(alerts, key=lambda a: a.created_at):
            descriptions.append(alert.normalized_description)
        
        return descriptions
    
    def _extract_services(self, alerts: List[EnrichedAlert]) -> List[str]:
        """
        Extract services/components from alerts.
        
        Uses metadata fields and alert descriptions.
        
        Args:
            alerts: Resolved alerts
            
        Returns:
            List of unique services
        """
        services: Set[str] = set()
        
        for alert in alerts:
            # Check metadata for service fields
            if alert.metadata:
                if "service" in alert.metadata:
                    services.add(str(alert.metadata["service"]))
                if "component" in alert.metadata:
                    services.add(str(alert.metadata["component"]))
                if "Service" in alert.metadata:
                    services.add(str(alert.metadata["Service"]))
                if "Component" in alert.metadata:
                    services.add(str(alert.metadata["Component"]))
            
            # Extract from alert type
            if alert.alert_type and alert.alert_type.label != "UNKNOWN":
                services.add(alert.alert_type.label.lower())
            
            # Extract from description (heuristic patterns)
            desc_lower = alert.normalized_description.lower()
            
            # Common service patterns
            if "database" in desc_lower or "db" in desc_lower:
                services.add("database")
            if "application" in desc_lower or "app" in desc_lower:
                services.add("application")
            if "elb" in desc_lower or "load balancer" in desc_lower:
                services.add("elb")
            if "mulesoft" in desc_lower or "esb" in desc_lower:
                services.add("mulesoft")
            if "network" in desc_lower:
                services.add("network")
            if "api" in desc_lower:
                services.add("api")
        
        # Return sorted for determinism
        return sorted(list(services))
    
    def _collect_stage2_predictions(
        self,
        alerts: List[EnrichedAlert]
    ) -> Dict[str, Dict[str, any]]:
        """
        Collect Stage 2 predictions with provenance.
        
        Stage 2 predictions are model outputs, not telemetry.
        They should be distinguished with source_type="model_prediction".
        
        Args:
            alerts: Resolved alerts
            
        Returns:
            Dictionary of Stage 2 predictions with provenance
        """
        # Use primary alert for predictions
        primary_alert = min(alerts, key=lambda a: a.created_at)
        
        predictions = {
            "priority": {
                "label": primary_alert.priority.label,
                "confidence": primary_alert.priority.confidence,
                "source_type": SourceType.MODEL_PREDICTION,
                "is_mock": False,
            },
            "routing": {
                "label": primary_alert.routing.label,
                "confidence": primary_alert.routing.confidence,
                "source_type": SourceType.MODEL_PREDICTION,
                "is_mock": False,
            },
            "alert_type": {
                "label": primary_alert.alert_type.label,
                "confidence": primary_alert.alert_type.confidence,
                "source_type": SourceType.MODEL_PREDICTION,
                "is_mock": False,
            },
            "severity": {
                "label": primary_alert.severity.label,
                "confidence": primary_alert.severity.confidence,
                "source_type": SourceType.MODEL_PREDICTION,
                "is_mock": False,
            },
            "business_impact": {
                "label": primary_alert.business_impact.label,
                "confidence": primary_alert.business_impact.confidence,
                "source_type": SourceType.MODEL_PREDICTION,
                "is_mock": False,
            },
        }
        
        return predictions
