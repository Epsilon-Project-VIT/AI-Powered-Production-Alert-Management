"""
Stage 2 compatibility validation for alert correlation.

Uses Stage 2 enriched alert classifications (when available) to
validate compatibility between alerts.
"""

from typing import Tuple, Optional, Dict

from ...stage2_classification.schemas import EnrichedAlert
from ...stage1_ingestion.schemas import StandardizedAlert


class Stage2CompatibilityValidator:
    """
    Validates compatibility using Stage 2 classifications.
    
    Now uses finalized Stage 2 canonical models for:
    - Alert Type (20-class taxonomy)
    - Severity (4 classes)
    - Business Impact (3 classes)
    - Priority (existing model)
    - Assignment Group/Routing (existing model)
    """
    
    def __init__(
        self,
        alert_type_weight: float = 0.30,
        severity_weight: float = 0.25,
        business_impact_weight: float = 0.20,
        priority_weight: float = 0.15,
        routing_weight: float = 0.10
    ):
        """
        Initialize Stage 2 compatibility validator.
        
        Args:
            alert_type_weight: Weight for alert type compatibility
            severity_weight: Weight for severity compatibility
            business_impact_weight: Weight for business impact compatibility
            priority_weight: Weight for priority compatibility
            routing_weight: Weight for routing compatibility
        """
        # Fields now available from Stage 2 canonical models
        self.available_fields = {
            'priority': True,  # Trained model exists
            'routing': True,   # Trained model exists (assignment group)
            'alert_type': True,  # ✅ NOW AVAILABLE - canonical model trained
            'severity': True,  # ✅ NOW AVAILABLE - canonical model trained
            'business_impact': True  # ✅ NOW AVAILABLE - canonical model trained
        }
        
        # Configurable experimental weights
        self.weights = {
            'alert_type': alert_type_weight,
            'severity': severity_weight,
            'business_impact': business_impact_weight,
            'priority': priority_weight,
            'routing': routing_weight
        }
        
        # Validate weights sum to 1.0
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            raise ValueError(f"Stage 2 weights must sum to 1.0, got {weight_sum}")
    
    def validate_compatibility(
        self,
        alert1: EnrichedAlert,
        alert2: EnrichedAlert,
        use_priority: bool = True,
        use_routing: bool = True,
        use_alert_type: bool = True,  # ✅ NOW ENABLED by default
        use_severity: bool = True,  # ✅ NOW ENABLED by default
        use_business_impact: bool = True,  # ✅ NOW ENABLED by default
        min_confidence: float = 0.0  # Minimum confidence to use a field
    ) -> Tuple[bool, float, str]:
        """
        Validate if two enriched alerts are compatible based on Stage 2 classifications.
        
        IMPORTANT: This uses Stage 2 ML model predictions, which have varying accuracy:
        - Alert Type: F1=0.60 (moderate, zero-shot issues for rare classes)
        - Severity: F1=0.88 (strong)
        - Business Impact: F1=0.94 (excellent)
        - Priority: existing model
        - Routing: existing model
        
        Args:
            alert1: First EnrichedAlert
            alert2: Second EnrichedAlert
            use_priority: Whether to compare priority
            use_routing: Whether to compare routing/assignment group
            use_alert_type: Whether to compare alert type
            use_severity: Whether to compare severity
            use_business_impact: Whether to compare business impact
            min_confidence: Minimum confidence threshold to use a field (0-1)
        
        Returns:
            Tuple of (is_compatible, compatibility_score, reason)
        """
        compatibility_scores = []
        reasons = []
        
        # Alert Type comparison (NOW AVAILABLE - 16 classes in test set from 20-class taxonomy)
        if use_alert_type and self.available_fields['alert_type']:
            if alert1.alert_type.confidence >= min_confidence and alert2.alert_type.confidence >= min_confidence:
                # Skip UNKNOWN labels
                if alert1.alert_type.label != 'UNKNOWN' and alert2.alert_type.label != 'UNKNOWN':
                    if alert1.alert_type.label == alert2.alert_type.label:
                        # Same alert type - strong compatibility signal
                        # Weight by minimum confidence (if one prediction is uncertain, reduce score)
                        min_conf = min(alert1.alert_type.confidence, alert2.alert_type.confidence)
                        score = 1.0 * min_conf
                        compatibility_scores.append(score)
                        reasons.append(f"Same alert type: {alert1.alert_type.label}")
                    else:
                        # Different alert types - likely incompatible
                        # But not zero (allow for model errors)
                        compatibility_scores.append(0.2)
                        reasons.append(f"Different alert types: {alert1.alert_type.label} vs {alert2.alert_type.label}")
        
        # Severity comparison (NOW AVAILABLE - 4 classes)
        if use_severity and self.available_fields['severity']:
            if alert1.severity.confidence >= min_confidence and alert2.severity.confidence >= min_confidence:
                sev1 = alert1.severity.label
                sev2 = alert2.severity.label
                
                # Skip UNKNOWN labels
                if sev1 != 'UNKNOWN' and sev2 != 'UNKNOWN':
                    if sev1 == sev2:
                        # Same severity - compatible
                        min_conf = min(alert1.severity.confidence, alert2.severity.confidence)
                        compatibility_scores.append(1.0 * min_conf)
                        reasons.append(f"Same severity: {sev1}")
                    else:
                        # Adjacent severities are somewhat compatible
                        # e.g., Sev1-Critical and Sev2-High might correlate
                        severity_order = ['Sev4 - Low', 'Sev3 - Medium', 'Sev2 - High', 'Sev1 - Critical']
                        
                        if sev1 in severity_order and sev2 in severity_order:
                            idx1 = severity_order.index(sev1)
                            idx2 = severity_order.index(sev2)
                            distance = abs(idx1 - idx2)
                            
                            if distance == 1:
                                # Adjacent severities (e.g., Sev1 and Sev2)
                                compatibility_scores.append(0.6)
                                reasons.append(f"Adjacent severities: {sev1} vs {sev2}")
                            else:
                                # Far apart severities
                                compatibility_scores.append(0.3)
                                reasons.append(f"Different severities: {sev1} vs {sev2}")
                        else:
                            # Unknown severity or not in order
                            compatibility_scores.append(0.5)
        
        # Business Impact comparison (NOW AVAILABLE - 3 classes)
        if use_business_impact and self.available_fields['business_impact']:
            if alert1.business_impact.confidence >= min_confidence and alert2.business_impact.confidence >= min_confidence:
                impact1 = alert1.business_impact.label
                impact2 = alert2.business_impact.label
                
                # Skip UNKNOWN labels
                if impact1 != 'UNKNOWN' and impact2 != 'UNKNOWN':
                    if impact1 == impact2:
                        # Same business impact - compatible
                        min_conf = min(alert1.business_impact.confidence, alert2.business_impact.confidence)
                        compatibility_scores.append(1.0 * min_conf)
                        reasons.append(f"Same business impact: {impact1}")
                    else:
                        # Adjacent impacts are somewhat compatible
                        impact_order = ['Low', 'Medium', 'High']
                        
                        if impact1 in impact_order and impact2 in impact_order:
                            idx1 = impact_order.index(impact1)
                            idx2 = impact_order.index(impact2)
                            distance = abs(idx1 - idx2)
                            
                            if distance == 1:
                                # Adjacent impacts
                                compatibility_scores.append(0.6)
                                reasons.append(f"Adjacent business impacts: {impact1} vs {impact2}")
                            else:
                                # Far apart
                                compatibility_scores.append(0.3)
                                reasons.append(f"Different business impacts: {impact1} vs {impact2}")
                        else:
                            compatibility_scores.append(0.5)
        
        # Priority comparison (EXISTING - available)
        if use_priority and self.available_fields['priority']:
            if alert1.priority.confidence >= min_confidence and alert2.priority.confidence >= min_confidence:
                if alert1.priority.label == alert2.priority.label:
                    compatibility_scores.append(1.0)
                    reasons.append(f"Same priority: {alert1.priority.label}")
                else:
                    # Different priorities - not necessarily incompatible, but reduces score
                    compatibility_scores.append(0.5)
                    reasons.append(f"Different priorities: {alert1.priority.label} vs {alert2.priority.label}")
        
        # Routing/Assignment group comparison (EXISTING - available)
        if use_routing and self.available_fields['routing']:
            if alert1.routing.confidence >= min_confidence and alert2.routing.confidence >= min_confidence:
                if alert1.routing.label == alert2.routing.label:
                    compatibility_scores.append(1.0)
                    reasons.append(f"Same routing group")
                else:
                    # Different routing groups - likely incompatible
                    compatibility_scores.append(0.2)
                    reasons.append(f"Different routing groups")
        
        # Calculate overall compatibility (WEIGHTED by field importance)
        if not compatibility_scores:
            # No Stage 2 comparisons available
            return True, 0.5, "No Stage 2 fields available for comparison"
        
        # Weighted average based on which fields were used
        total_weight = 0.0
        weighted_sum = 0.0
        
        field_usage = []
        idx = 0
        
        if use_alert_type and self.available_fields['alert_type'] and \
           alert1.alert_type.confidence >= min_confidence and alert2.alert_type.confidence >= min_confidence and \
           alert1.alert_type.label != 'UNKNOWN' and alert2.alert_type.label != 'UNKNOWN':
            weighted_sum += self.weights['alert_type'] * compatibility_scores[idx]
            total_weight += self.weights['alert_type']
            field_usage.append('alert_type')
            idx += 1
        
        if use_severity and self.available_fields['severity'] and \
           alert1.severity.confidence >= min_confidence and alert2.severity.confidence >= min_confidence and \
           alert1.severity.label != 'UNKNOWN' and alert2.severity.label != 'UNKNOWN':
            weighted_sum += self.weights['severity'] * compatibility_scores[idx]
            total_weight += self.weights['severity']
            field_usage.append('severity')
            idx += 1
        
        if use_business_impact and self.available_fields['business_impact'] and \
           alert1.business_impact.confidence >= min_confidence and alert2.business_impact.confidence >= min_confidence and \
           alert1.business_impact.label != 'UNKNOWN' and alert2.business_impact.label != 'UNKNOWN':
            weighted_sum += self.weights['business_impact'] * compatibility_scores[idx]
            total_weight += self.weights['business_impact']
            field_usage.append('business_impact')
            idx += 1
        
        if use_priority and self.available_fields['priority'] and \
           alert1.priority.confidence >= min_confidence and alert2.priority.confidence >= min_confidence:
            weighted_sum += self.weights['priority'] * compatibility_scores[idx]
            total_weight += self.weights['priority']
            field_usage.append('priority')
            idx += 1
        
        if use_routing and self.available_fields['routing'] and \
           alert1.routing.confidence >= min_confidence and alert2.routing.confidence >= min_confidence:
            weighted_sum += self.weights['routing'] * compatibility_scores[idx]
            total_weight += self.weights['routing']
            field_usage.append('routing')
            idx += 1
        
        # Normalize by actual weights used
        if total_weight > 0:
            avg_score = weighted_sum / total_weight
        else:
            avg_score = sum(compatibility_scores) / len(compatibility_scores)
        
        # Compatibility threshold: average score >= 0.5
        is_compatible = avg_score >= 0.5
        
        reason = "; ".join(reasons) if reasons else "Stage 2 comparison"
        reason += f" (fields: {', '.join(field_usage)})"
        
        return is_compatible, avg_score, reason
    
    def get_available_fields_status(self) -> dict:
        """
        Get status of which Stage 2 fields are available.
        
        Returns:
            Dict mapping field names to availability status
        """
        return {
            **self.available_fields,
            'model_performance': {
                'alert_type': 'F1=0.60 (moderate, zero-shot issues)',
                'severity': 'F1=0.88 (strong)',
                'business_impact': 'F1=0.94 (excellent)',
                'priority': 'existing model',
                'routing': 'existing model'
            }
        }
    
    def get_weights(self) -> Dict[str, float]:
        """
        Get current Stage 2 compatibility weights.
        
        Returns:
            Dict of field weights
        """
        return self.weights.copy()
    
    def can_use_for_correlation(self, alert: EnrichedAlert, min_confidence: float = 0.0) -> bool:
        """
        Check if alert has usable Stage 2 classifications.
        
        Args:
            alert: EnrichedAlert
            min_confidence: Minimum confidence threshold
        
        Returns:
            True if alert has Stage 2 data available
        """
        # Check if any field has valid predictions above confidence threshold
        has_alert_type = (
            self.available_fields['alert_type'] and
            alert.alert_type.confidence >= min_confidence
        )
        
        has_severity = (
            self.available_fields['severity'] and
            alert.severity.confidence >= min_confidence
        )
        
        has_business_impact = (
            self.available_fields['business_impact'] and
            alert.business_impact.confidence >= min_confidence
        )
        
        has_priority = (
            self.available_fields['priority'] and
            alert.priority.confidence >= min_confidence
        )
        
        has_routing = (
            self.available_fields['routing'] and
            alert.routing.confidence >= min_confidence
        )
        
        return has_alert_type or has_severity or has_business_impact or has_priority or has_routing
