"""
Data loader utilities for Alert Management Frontend.

Loads data from Stage 1-4 canonical outputs without re-running pipelines.
Uses the final trained models and analysis results.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
import streamlit as st


class DataLoader:
    """Loads and caches Stage 1-4 canonical analysis results."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Resolve relative to project root (one level above frontend/)
            project_root = Path(__file__).resolve().parent.parent
            self.data_dir = project_root / "data"
        else:
            self.data_dir = Path(data_dir)
        
        # Paths to canonical outputs
        self.raw_alerts_path = self.data_dir / "raw" / "Data_Alert_Ticket_Segregation.xlsx"
        self.stage2_dir = self.data_dir / "stage2_models_canonical"
        self.stage3_dir = self.data_dir / "stage3_canonical_results"
        self.stage4_dir = self.data_dir / "stage4_canonical_results"
        
        # Caches
        self._raw_alerts_df = None
        self._stage2_alert_type_df = None
        self._stage2_severity_df = None
        self._stage2_business_impact_df = None
        self._stage2_combined_df = None
        self._stage3_incidents = None
        self._stage4_rca_results = None
        self._stage4_summary_df = None
        self._alert_to_incident = None
    
    @st.cache_data
    def load_raw_alerts(_self) -> pd.DataFrame:
        """Load raw alerts from Excel."""
        if _self._raw_alerts_df is None:
            _self._raw_alerts_df = pd.read_excel(_self.raw_alerts_path, sheet_name='Sheet1')
        return _self._raw_alerts_df
    
    @st.cache_data
    def load_stage2(_self) -> pd.DataFrame:
        """Load Stage 2 canonical classification results (all fields combined)."""
        if _self._stage2_combined_df is None:
            # Load predictions
            alert_type_df = pd.read_csv(_self.stage2_dir / "alert_type_predictions.csv")
            severity_df = pd.read_csv(_self.stage2_dir / "severity_predictions.csv")
            business_impact_df = pd.read_csv(_self.stage2_dir / "business_impact_predictions.csv")
            
            # Load raw alerts for basic info
            raw_df = _self.load_raw_alerts()
            
            # Combine all predictions (using index as join key since predictions are in same order as raw data)
            combined = pd.DataFrame({
                'alert_id': raw_df['Number'],
                'client': raw_df['Impacted client'],
                'created_at': pd.to_datetime(raw_df['Created']),
                'description': raw_df['Short description'],
                'priority': raw_df['Priority'],
                'assignment_group': raw_df['Assignment group'],
                
                # Stage 2 canonical predictions
                'predicted_alert_type': alert_type_df['predicted_label'],
                'alert_type_confidence': alert_type_df['confidence'],
                'alert_type_true_label': alert_type_df['true_label'],
                
                'predicted_severity': severity_df['predicted_label'],
                'severity_confidence': severity_df['confidence'],
                'severity_true_label': severity_df['true_label'],
                
                'predicted_business_impact': business_impact_df['predicted_label'],
                'business_impact_confidence': business_impact_df['confidence'],
                'business_impact_true_label': business_impact_df['true_label'],
            })
            
            _self._stage2_combined_df = combined
        return _self._stage2_combined_df
    
    @st.cache_data
    def load_stage3_incidents(_self) -> List[Dict[str, Any]]:
        """Load Stage 3 candidate incident groups."""
        if _self._stage3_incidents is None:
            path = _self.stage3_dir / "incident_groups.json"
            with open(path, 'r') as f:
                _self._stage3_incidents = json.load(f)
        return _self._stage3_incidents
    
    @st.cache_data
    def load_stage3_summary(_self) -> Dict[str, Any]:
        """Load Stage 3 summary statistics."""
        path = _self.stage3_dir / "results_summary.json"
        with open(path, 'r') as f:
            return json.load(f)
    
    @st.cache_data
    def load_stage4_rca(_self) -> List[Dict[str, Any]]:
        """Load Stage 4 RCA results."""
        if _self._stage4_rca_results is None:
            path = _self.stage4_dir / "rca_results.json"
            with open(path, 'r') as f:
                _self._stage4_rca_results = json.load(f)
        return _self._stage4_rca_results
    
    @st.cache_data
    def load_stage4_summary(_self) -> pd.DataFrame:
        """Load Stage 4 RCA summary CSV."""
        if _self._stage4_summary_df is None:
            path = _self.stage4_dir / "rca_summary.csv"
            _self._stage4_summary_df = pd.read_csv(path)
        return _self._stage4_summary_df
    
    @st.cache_data
    def load_stage4_statistics(_self) -> Dict[str, Any]:
        """Load Stage 4 statistics."""
        path = _self.stage4_dir / "rca_statistics.json"
        with open(path, 'r') as f:
            return json.load(f)
    
    def build_alert_to_incident_map(self) -> Dict[str, str]:
        """Build mapping from alert_id to incident_id."""
        if self._alert_to_incident is None:
            self._alert_to_incident = {}
            incidents = self.load_stage3_incidents()
            
            for incident in incidents:
                incident_id = incident['incident_id']
                for alert_id in incident.get('alert_ids', []):
                    self._alert_to_incident[alert_id] = incident_id
        
        return self._alert_to_incident
    
    def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Get alert classification data from Stage 2."""
        df = self.load_stage2()
        alert_rows = df[df['alert_id'] == alert_id]
        
        if alert_rows.empty:
            return None
        
        return alert_rows.iloc[0].to_dict()
    
    def get_incident_for_alert(self, alert_id: str) -> Optional[str]:
        """Get incident_id for given alert_id."""
        mapping = self.build_alert_to_incident_map()
        return mapping.get(alert_id)
    
    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get candidate incident details from Stage 3."""
        incidents = self.load_stage3_incidents()
        
        for incident in incidents:
            if incident['incident_id'] == incident_id:
                return incident
        
        return None
    
    def get_rca(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get RCA analysis for incident from Stage 4."""
        rca_results = self.load_stage4_rca()
        
        for rca in rca_results:
            if rca['incident_id'] == incident_id:
                return rca
        
        return None
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get dashboard summary statistics."""
        stage2_df = self.load_stage2()
        stage3_summary = self.load_stage3_summary()
        stage4_stats = self.load_stage4_statistics()
        
        # Stage 3 statistics are directly in the statistics key
        stats = stage3_summary['statistics']
        
        return {
            'total_alerts': len(stage2_df),
            'candidate_incident_groups': stats['total_incidents'],
            'grouped_alerts': stats['grouped_alerts'],
            'uncorrelated_alerts': stats['uncorrelated_alerts'],
            'grouping_rate': stats['grouping_rate'],
            'rca_analyses': stage4_stats['total_incidents'],
            'sufficient_evidence': stage4_stats['diagnosis_status']['sufficient_evidence'],
            'insufficient_evidence': stage4_stats['diagnosis_status']['insufficient_evidence'],
            'ambiguous': stage4_stats['diagnosis_status']['ambiguous'],
            'avg_evidence_per_incident': stage4_stats['evidence_stats']['avg_evidence_per_incident'],
            'mock_evidence_percentage': (stage4_stats['evidence_stats']['mock_evidence_count'] / 
                                        stage4_stats['evidence_stats']['total_evidence_items'] * 100 
                                        if stage4_stats['evidence_stats']['total_evidence_items'] > 0 else 100),
        }


# Global singleton
_loader = None

def get_loader() -> DataLoader:
    """Get or create the global data loader."""
    global _loader
    if _loader is None:
        _loader = DataLoader()
    return _loader
