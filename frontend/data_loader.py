"""
Data loader utilities for Alert Management Frontend.

Loads data from Stage 1-4 canonical outputs without re-running pipelines.
Uses the final trained models and analysis results.
"""

import json
import math
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
import streamlit as st


# ---------------------------------------------------------------------------
# Schema normalization for JSON-format Stage-4 RCA records
# ---------------------------------------------------------------------------

def normalize_rca_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a canonical in-memory RCA record regardless of which historical
    Stage-4 schema version the stored JSON uses.
    """
    rec = dict(raw)  # shallow copy

    # 1. Normalise diagnosis_status to lower-case
    if "diagnosis_status" in rec:
        rec["diagnosis_status"] = str(rec["diagnosis_status"]).lower()

    # 2. Build a normalised probable_root_cause dict
    prc: Dict[str, Any] = {}

    if "probable_root_cause" in rec and isinstance(rec["probable_root_cause"], dict):
        src = rec["probable_root_cause"]
        prc["component"] = src.get("component", None)
        prc["failure_type"] = src.get("failure_type") or src.get("type", None)

        if "analysis_confidence" in src:
            prc["confidence"] = src["analysis_confidence"]
        elif "confidence" in src:
            prc["confidence"] = src["confidence"]
        else:
            prc["confidence"] = None

        prc["description"] = src.get("description", None)

        if "supporting_evidence_ids" in src:
            prc["supporting_evidence_ids"] = src["supporting_evidence_ids"]

    elif any(k in rec for k in ("root_cause_component", "probable_root_cause_component")):
        prc["component"] = (
            rec.get("root_cause_component")
            or rec.get("probable_root_cause_component")
            or None
        )
        prc["failure_type"] = (
            rec.get("root_cause_failure_type")
            or rec.get("probable_failure_type")
            or None
        )
        raw_conf = rec.get("root_cause_confidence")
        if raw_conf is None:
            raw_conf = rec.get("analysis_confidence_score")
        
        if raw_conf is None:
            prc["confidence"] = None
        else:
            try:
                prc["confidence"] = float(raw_conf)
                if math.isnan(prc["confidence"]):
                    prc["confidence"] = None
            except (TypeError, ValueError):
                prc["confidence"] = None
                
        prc["description"] = rec.get("description", None)
    else:
        prc["component"] = None
        prc["failure_type"] = None
        prc["confidence"] = None
        prc["description"] = None

    rec["probable_root_cause"] = prc

    # 3. Evidence list
    if "evidence" not in rec or not isinstance(rec.get("evidence"), list):
        rec["evidence"] = []

    if "evidence_count" in rec:
        try:
            rec["evidence_count"] = int(rec["evidence_count"])
        except (TypeError, ValueError):
            rec["evidence_count"] = len(rec["evidence"])
    else:
        rec["evidence_count"] = len(rec["evidence"])

    # 4. Recommended actions & alternative hypotheses
    if "recommended_actions" not in rec or not isinstance(rec.get("recommended_actions"), list):
        rec["recommended_actions"] = []
    if "alternative_hypotheses" not in rec or not isinstance(rec.get("alternative_hypotheses"), list):
        rec["alternative_hypotheses"] = []

    return rec


class DataLoader:
    """Loads and caches Stage 1-4 canonical analysis results."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            project_root = Path(__file__).resolve().parent.parent
            self.data_dir = project_root / "data"
        else:
            self.data_dir = Path(data_dir)
        
        self.raw_alerts_path = self.data_dir / "raw" / "Data_Alert_Ticket_Segregation.xlsx"
        self.stage2_dir = self.data_dir / "stage2_models_canonical"
        self.stage3_dir = self.data_dir / "stage3_canonical_results"
        self.stage4_dir = self.data_dir / "stage4_canonical_results"
        
        self._raw_alerts_df = None
        self._stage2_combined_df = None
        self._stage3_incidents = None
        self._stage4_rich_mapping = None
        self._stage4_summary_df = None
        self._alert_to_incident = None
    
    @st.cache_data
    def load_raw_alerts(_self) -> pd.DataFrame:
        if _self._raw_alerts_df is None:
            _self._raw_alerts_df = pd.read_excel(_self.raw_alerts_path, sheet_name='Sheet1')
        return _self._raw_alerts_df
    
    @st.cache_data
    def load_stage2(_self) -> pd.DataFrame:
        if _self._stage2_combined_df is None:
            canonical_path = _self.data_dir / "final_outputs" / "stage2_canonical_labels.json"
            with open(canonical_path, 'r') as f:
                canonical_data = json.load(f)
            
            alert_type_df = pd.read_csv(_self.stage2_dir / "alert_type_predictions.csv")
            severity_df = pd.read_csv(_self.stage2_dir / "severity_predictions.csv")
            business_impact_df = pd.read_csv(_self.stage2_dir / "business_impact_predictions.csv")
            raw_df = _self.load_raw_alerts()
            
            alerts_list = []
            for i, alert in enumerate(canonical_data['alerts']):
                alerts_list.append({
                    'alert_id': alert['alert_id'],
                    'client': alert['client'],
                    'created_at': pd.to_datetime(alert['created_at']),
                    'description': raw_df.iloc[i]['Short description'],
                    'predicted_alert_type': alert_type_df.iloc[i]['predicted_label'],
                    'alert_type_confidence': alert_type_df.iloc[i]['confidence'],
                    'alert_type_true_label': alert_type_df.iloc[i]['true_label'],
                    'alert_type_canonical_label': alert['alert_type'],
                    'predicted_severity': severity_df.iloc[i]['predicted_label'],
                    'severity_confidence': severity_df.iloc[i]['confidence'],
                    'severity_true_label': severity_df.iloc[i]['true_label'],
                    'severity_canonical_label': alert['severity'],
                    'predicted_business_impact': business_impact_df.iloc[i]['predicted_label'],
                    'business_impact_confidence': business_impact_df.iloc[i]['confidence'],
                    'business_impact_true_label': business_impact_df.iloc[i]['true_label'],
                    'business_impact_canonical_label': alert['business_impact'],
                    'predicted_priority': alert['priority'],
                    'priority_confidence': alert.get('priority_confidence', 0.0),
                    'priority_true_label': raw_df.iloc[i]['Priority'],
                    'predicted_assignment_group': alert['routing'],
                    'assignment_group_confidence': alert.get('routing_confidence', 0.0),
                    'assignment_group_true_label': raw_df.iloc[i]['Assignment group'],
                })
            
            _self._stage2_combined_df = pd.DataFrame(alerts_list)
        return _self._stage2_combined_df
    
    @st.cache_data
    def load_stage3_incidents(_self) -> List[Dict[str, Any]]:
        if _self._stage3_incidents is None:
            path = _self.stage3_dir / "incident_groups.json"
            with open(path, 'r') as f:
                data = json.load(f)
            if isinstance(data, list):
                _self._stage3_incidents = data
            elif isinstance(data, dict):
                _self._stage3_incidents = data.get('incidents', data.get('incident_groups', []))
        return _self._stage3_incidents
    
    @st.cache_data
    def load_stage3_summary(_self) -> Dict[str, Any]:
        path = _self.stage3_dir / "results_summary.json"
        with open(path, 'r') as f:
            return json.load(f)

    def _get_stage4_rich_mapping(self) -> Dict[str, Dict[str, Any]]:
        """
        Builds a map of incident_id -> rich RCA record.
        The user requires 151 incident groups (from stage3) but wants the rich
        components/failure_types from the LLM outputs (e.g. "Batch / job service",
        confidence scores, rich descriptions).

        Since IDs don't match directly (INCIDENT-0001 vs INC-LLM-XXX), we map
        them by alert_id overlap. Unmapped records fall back to the basic
        151-record json outputs.
        """
        if self._stage4_rich_mapping is not None:
            return self._stage4_rich_mapping

        self._stage4_rich_mapping = {}

        # 1. Load canonical basic 151 records (minimal schema)
        basic_rca = {}
        basic_path = self.data_dir / "final_outputs" / "stage4_rca_results.json"
        if basic_path.exists():
            with open(basic_path) as f:
                d = json.load(f)
                recs = d.get('analyses', []) if isinstance(d, dict) else d
                for r in recs:
                    basic_rca[r['incident_id']] = normalize_rca_record(r)

        # 2. Load the rich LLM records (152 records)
        llm_rca = []
        llm_path = self.data_dir / "llm_outputs" / "stage4_full_889.json"
        if llm_path.exists():
            with open(llm_path) as f:
                d = json.load(f)
                llm_rca = d.get('incidents', [])

        # 3. Map via Stage 3 incident alert IDs
        stage3_incidents = self.load_stage3_incidents()
        
        for inc in stage3_incidents:
            inc_id = inc['incident_id']
            a_set = set(inc.get('alert_ids', []))
            
            matched_llm = None
            for rich in llm_rca:
                r_set = set(rich.get('alert_ids', []))
                if a_set.intersection(r_set):
                    matched_llm = rich
                    break
            
            if matched_llm:
                # Merge: use the incident_id from stage3, but all rich data from llm
                merged = dict(matched_llm)
                merged['incident_id'] = inc_id
                self._stage4_rich_mapping[inc_id] = normalize_rca_record(merged)
            else:
                # Fallback to basic record
                self._stage4_rich_mapping[inc_id] = basic_rca.get(inc_id, normalize_rca_record({'incident_id': inc_id}))

        return self._stage4_rich_mapping

    @st.cache_data
    def load_stage4_summary(_self) -> pd.DataFrame:
        """
        Load Stage 4 RCA summary DataFrame for the UI table.
        Uses the rich mapping to get the correct component/failure_type.
        """
        if _self._stage4_summary_df is None:
            incidents = _self.load_stage3_incidents()
            rich_map = _self._get_stage4_rich_mapping()
            
            rows = []
            for inc in incidents:
                inc_id = inc['incident_id']
                rca = rich_map.get(inc_id, {})
                prc = rca.get('probable_root_cause', {})
                
                rows.append({
                    'incident_id': inc_id,
                    'client': inc.get('client', ''),
                    'alert_count': inc.get('alert_count', 0),
                    'diagnosis_status': rca.get('diagnosis_status', 'ambiguous'),
                    'component': prc.get('component'),
                    'failure_type': prc.get('failure_type'),
                    'confidence': prc.get('confidence'),
                    'evidence_count': rca.get('evidence_count', 0)
                })
                
            _self._stage4_summary_df = pd.DataFrame(rows)

        return _self._stage4_summary_df
    
    @st.cache_data
    def load_stage4_statistics(_self) -> Dict[str, Any]:
        """Load Stage 4 statistics."""
        path = _self.stage4_dir / "rca_statistics.json"
        with open(path, 'r') as f:
            return json.load(f)
    
    def build_alert_to_incident_map(self) -> Dict[str, str]:
        if self._alert_to_incident is None:
            self._alert_to_incident = {}
            incidents = self.load_stage3_incidents()
            for incident in incidents:
                incident_id = incident['incident_id']
                for alert_id in incident.get('alert_ids', []):
                    self._alert_to_incident[alert_id] = incident_id
        return self._alert_to_incident
    
    def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        df = self.load_stage2()
        alert_rows = df[df['alert_id'] == alert_id]
        if alert_rows.empty:
            return None
        return alert_rows.iloc[0].to_dict()
    
    def get_incident_for_alert(self, alert_id: str) -> Optional[str]:
        mapping = self.build_alert_to_incident_map()
        return mapping.get(alert_id)
    
    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        incidents = self.load_stage3_incidents()
        for incident in incidents:
            if incident['incident_id'] == incident_id:
                return incident
        return None
    
    def get_rca(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the fully mapped RCA analysis for an incident.
        """
        rich_map = self._get_stage4_rich_mapping()
        rca_data = rich_map.get(incident_id)
        
        if not rca_data:
            return None
            
        # Enrich with Stage 3 incident metadata
        incident = self.get_incident(incident_id)
        if incident:
            rca_data['client'] = incident.get('client', '')
            rca_data['alert_count'] = incident.get('alert_count', 0)
            rca_data['alert_ids'] = incident.get('alert_ids', [])
            
        return rca_data
    
    def get_summary_stats(self) -> Dict[str, Any]:
        stage2_df = self.load_stage2()
        stage3_summary = self.load_stage3_summary()
        stage4_stats = self.load_stage4_statistics()
        
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


_loader = None

def get_loader() -> DataLoader:
    global _loader
    if _loader is None:
        _loader = DataLoader()
    return _loader
