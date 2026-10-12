"""
Data loader utilities for Alert Management Frontend.

Loads data from Stage 1-4 canonical outputs without re-running pipelines.

Data-join contract
------------------
Stage 2: All three prediction CSVs include an `alert_id` column.
         Predictions are always joined to alerts by `alert_id`, never by
         row position. Row-position joins are explicitly forbidden here.

Stage 4: Per-incident RCA records are evaluated against `stage4_full_889.json`
         using strict incident-level identity validation:

         1. Exact Group Match (match_method="exact_set_match", 119 incidents):
            Stage 3 candidate incident's alert set is 100% equal to an LLM
            rich RCA record's alert set. Presented as exact incident RCA.

         2. Partial Overlap Match (match_method="partial_overlap", 21 incidents):
            Stage 3 incident's alert set shares alerts with LLM RCA records, but
            alert sets are not identical. Flagged as partial/related match with
            overlap metadata. Not presented as exact incident-specific RCA.

         3. Basic Canonical Record (match_method="basic_canonical", 11 incidents):
            Alert IDs absent from LLM JSON. Loaded from basic canonical CSV
            (`rca_summary.csv`). Component, failure_type, confidence, and
            evidence count are preserved. Confidence is flagged as unverified
            `mock_pipeline_baseline`. Description is None, actions are [].

         Synthetic fallback templates and approximate taxonomy matching for
         incident-specific RCA are explicitly prohibited.

Evidence pools
--------------
Historical alert text (source_type="historical_alert", is_mock=False) is
real data from the source workbook.

Mock telemetry (metrics/logs/traces) was simulated by the pipeline.
The two pools are kept separate and never mixed in counts or labels.
"""

import json
import math
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
import streamlit as st


# ---------------------------------------------------------------------------
# Schema normalization — canonical Stage-4 RCA record
# ---------------------------------------------------------------------------

def normalize_rca_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a canonical in-memory RCA record from any of the historical
    Stage-4 schema variants, preserving every available source value.

    Normalised output always contains:
      incident_id, diagnosis_status,
      probable_root_cause: {component, failure_type, confidence, description},
      evidence (list), evidence_count,
      recommended_actions (list), alternative_hypotheses (list),
      human_review_required, telemetry_is_mock,
      match_method ("exact_set_match" | "partial_overlap" | "basic_canonical" | "unresolved"),
      source_type ("llm_exact" | "llm_partial" | "basic_canonical" | "unresolved"),
      confidence_provenance ("model_reported_llm" | "mock_pipeline_baseline" | "none"),
      is_partial_match (bool), overlap_info (dict | None),
      evidence_pool: {"historical_alert": N, "mock_telemetry": N}

    Fields that are genuinely absent are set to None / [] — they are never
    substituted with silent defaults or synthetic templates.
    """
    rec = dict(raw)  # shallow copy

    # 1. diagnosis_status → lower-case
    if "diagnosis_status" in rec:
        rec["diagnosis_status"] = str(rec["diagnosis_status"]).lower()

    # 2. probable_root_cause — handle all known schema variants
    prc: Dict[str, Any] = {}

    if "probable_root_cause" in rec and isinstance(rec["probable_root_cause"], dict):
        # Rich LLM schema (stage4_full_889.json)
        src = rec["probable_root_cause"]
        prc["component"]    = src.get("component", None)
        prc["failure_type"] = src.get("failure_type") or src.get("type", None)

        if "analysis_confidence" in src:
            raw_conf = src["analysis_confidence"]
        elif "confidence" in src:
            raw_conf = src["confidence"]
        else:
            raw_conf = None

        if raw_conf is None:
            prc["confidence"] = None
        else:
            try:
                cv = float(raw_conf)
                prc["confidence"] = None if math.isnan(cv) else cv
            except (TypeError, ValueError):
                prc["confidence"] = None

        prc["description"]             = src.get("description", None)
        prc["supporting_evidence_ids"] = src.get("supporting_evidence_ids", [])
        prc["is_tentative"]            = bool(src.get("is_tentative", False)) or (str(rec.get("diagnosis_status", "")).lower() == "insufficient_evidence")

    elif any(k in rec for k in ("root_cause_component", "probable_root_cause_component")):
        # Flat CSV / basic JSON schema
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
        # Explicit None check — 0.0 is a valid confidence value
        raw_conf = rec.get("root_cause_confidence")
        if raw_conf is None:
            raw_conf = rec.get("analysis_confidence_score")

        if raw_conf is None:
            prc["confidence"] = None
        else:
            try:
                cv = float(raw_conf)
                prc["confidence"] = None if math.isnan(cv) else cv
            except (TypeError, ValueError):
                prc["confidence"] = None

        prc["description"]             = rec.get("description", None)
        prc["supporting_evidence_ids"] = []
    else:
        # No recognisable root-cause fields
        prc["component"]               = None
        prc["failure_type"]            = None
        prc["confidence"]              = None
        prc["description"]             = None
        prc["supporting_evidence_ids"] = []

    rec["probable_root_cause"] = prc

    # 3. Evidence list — classify by pool
    raw_ev = rec.get("evidence", [])
    if not isinstance(raw_ev, list):
        raw_ev = []
    rec["evidence"] = raw_ev

    hist_count  = sum(1 for e in raw_ev if e.get("source_type") == "historical_alert")
    mock_count  = sum(1 for e in raw_ev if e.get("is_mock", False))
    rec["evidence_pool"] = {
        "historical_alert": hist_count,
        "mock_telemetry":   mock_count,
    }

    if "evidence_count" in rec:
        try:
            rec["evidence_count"] = int(rec["evidence_count"])
        except (TypeError, ValueError):
            rec["evidence_count"] = len(raw_ev)
    else:
        rec["evidence_count"] = len(raw_ev)

    # 4. Recommended actions & alternative hypotheses
    if not isinstance(rec.get("recommended_actions"), list):
        rec["recommended_actions"] = []
    if not isinstance(rec.get("alternative_hypotheses"), list):
        rec["alternative_hypotheses"] = []

    # 5. Safety / provenance flags
    rec.setdefault("human_review_required", True)
    rec.setdefault("telemetry_is_mock", True)
    rec.setdefault("execution_status", "NOT EXECUTED")

    # 6. Identity match method & confidence provenance
    rec.setdefault("match_method", rec.get("match_method", "exact_set_match"))
    rec.setdefault("source_type", rec.get("source_type", "llm_exact"))
    rec.setdefault("confidence_provenance", rec.get("confidence_provenance", "model_reported_llm"))
    rec.setdefault("is_partial_match", rec.get("is_partial_match", False))
    rec.setdefault("overlap_info", rec.get("overlap_info", None))

    return rec


# ---------------------------------------------------------------------------
# DataLoader
# ---------------------------------------------------------------------------

class DataLoader:
    """Loads and caches Stage 1-4 canonical analysis results."""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)

        self.raw_alerts_path = self.data_dir / "labels" / "sheet_Alerts.xlsx"
        self.stage2_dir = self.data_dir / "stage2_models_canonical"
        self.stage3_dir = self.data_dir / "final_outputs"
        self.stage4_dir = self.data_dir / "stage4_canonical_results"

        # Cache fields
        self._raw_alerts_df: Optional[pd.DataFrame] = None
        self._stage2_combined: Optional[pd.DataFrame] = None
        self._stage3_incidents: Optional[List[Dict[str, Any]]] = None
        self._stage4_rich_map: Optional[Dict[str, Dict[str, Any]]] = None
        self._stage4_summary_df: Optional[pd.DataFrame] = None
        self._alert_to_incident: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------------
    # Stage 1 — raw source alerts
    # ------------------------------------------------------------------

    @st.cache_data
    def load_raw_alerts(_self) -> pd.DataFrame:
        if _self._raw_alerts_df is None:
            if _self.raw_alerts_path.exists():
                _self._raw_alerts_df = pd.read_excel(
                    _self.raw_alerts_path, sheet_name="Sheet1"
                )
            else:
                csv_path = _self.data_dir / "labels" / "sheet_Alerts.csv"
                _self._raw_alerts_df = pd.read_csv(csv_path)
        return _self._raw_alerts_df

    # ------------------------------------------------------------------
    # Stage 2 — predictions joined by alert_id (never by row position)
    # ------------------------------------------------------------------

    @st.cache_data
    def load_stage2(_self) -> pd.DataFrame:
        """
        Load Stage 2 classification predictions.

        All three prediction CSVs contain an `alert_id` column.
        This method joins every prediction table to the canonical alert list
        by `alert_id`. It raises ValueError if any alert_id is missing or
        duplicated in a prediction file, ensuring data integrity.
        """
        if _self._stage2_combined is not None:
            return _self._stage2_combined

        canonical_path = _self.data_dir / "final_outputs" / "stage2_canonical_labels.json"
        with open(canonical_path) as f:
            canonical_data = json.load(f)

        # Build canonical alert lookup (keyed by alert_id)
        alerts_by_id: Dict[str, Dict] = {a["alert_id"]: a for a in canonical_data["alerts"]}
        ordered_ids  = [a["alert_id"] for a in canonical_data["alerts"]]

        if len(ordered_ids) != len(alerts_by_id):
            raise ValueError(
                f"Duplicate alert IDs in canonical labels: "
                f"{len(ordered_ids)} rows, {len(alerts_by_id)} unique IDs"
            )

        # Load prediction CSVs — must have alert_id column
        at_df = pd.read_csv(_self.stage2_dir / "alert_type_predictions.csv")
        sv_df = pd.read_csv(_self.stage2_dir / "severity_predictions.csv")
        bi_df = pd.read_csv(_self.stage2_dir / "business_impact_predictions.csv")

        for name, df in [("alert_type", at_df), ("severity", sv_df), ("business_impact", bi_df)]:
            if "alert_id" not in df.columns:
                raise ValueError(
                    f"{name}_predictions.csv is missing the 'alert_id' column."
                )
            dup = df[df.duplicated("alert_id")]
            if not dup.empty:
                raise ValueError(
                    f"{name}_predictions.csv has duplicate alert_ids: {dup['alert_id'].tolist()}"
                )
            missing = set(ordered_ids) - set(df["alert_id"])
            extra   = set(df["alert_id"]) - set(ordered_ids)
            if missing:
                raise ValueError(f"{name}: missing alert_ids {sorted(missing)[:10]}")
            if extra:
                raise ValueError(f"{name}: unexpected alert_ids {sorted(extra)[:10]}")

        # Index by alert_id for keyed join
        at_by_id = at_df.set_index("alert_id")
        sv_by_id = sv_df.set_index("alert_id")
        bi_by_id = bi_df.set_index("alert_id")

        raw_df = _self.load_raw_alerts()
        raw_by_id = raw_df.set_index("Number") if "Number" in raw_df.columns else None

        rows = []
        for aid in ordered_ids:
            at_row = at_by_id.loc[aid]
            sv_row = sv_by_id.loc[aid]
            bi_row = bi_by_id.loc[aid]
            c_info = alerts_by_id[aid]
            raw_row = raw_by_id.loc[aid] if raw_by_id is not None and aid in raw_by_id.index else {}

            desc = raw_row.get("Short description") if hasattr(raw_row, "get") else None
            if pd.isna(desc) or not desc:
                desc = raw_row.get("Description") if hasattr(raw_row, "get") else None
            if pd.isna(desc) or not desc:
                desc = c_info.get("description", "")

            hist_pri = raw_row.get("Priority") if hasattr(raw_row, "get") else None
            if pd.isna(hist_pri) or not hist_pri:
                hist_pri = c_info.get("priority_true_label")

            hist_group = raw_row.get("Assignment group") if hasattr(raw_row, "get") else None
            if pd.isna(hist_group) or not hist_group:
                hist_group = c_info.get("assignment_group_true_label")

            hist_at = at_row.get("true_label") or (raw_row.get("Alert Type") if hasattr(raw_row, "get") else None) or c_info.get("alert_type_true_label")
            hist_sv = sv_row.get("true_label") or (raw_row.get("Severity") if hasattr(raw_row, "get") else None) or c_info.get("severity_true_label")
            hist_bi = bi_row.get("true_label") or (raw_row.get("Business Impact") if hasattr(raw_row, "get") else None) or c_info.get("business_impact_true_label")

            pred_at = at_row.get("predicted_label") or at_row.get("predicted_alert_type") or c_info.get("alert_type")
            pred_sv = sv_row.get("predicted_label") or sv_row.get("predicted_severity") or c_info.get("severity")
            pred_bi = bi_row.get("predicted_label") or bi_row.get("predicted_business_impact") or c_info.get("business_impact")
            pred_pri = c_info.get("priority") or bi_row.get("predicted_priority")
            pred_group = c_info.get("routing") or bi_row.get("predicted_assignment_group")

            rows.append({
                "alert_id":                       aid,
                "client":                         c_info.get("client", ""),
                "created_at":                     c_info.get("created_at", ""),
                "description":                    str(desc) if desc and not pd.isna(desc) else "",

                # Stage 2 model predictions
                "predicted_alert_type":           pred_at,
                "alert_type_confidence":          float(at_row.get("confidence", 0.0)),

                "predicted_severity":             pred_sv,
                "severity_confidence":            float(sv_row.get("confidence", 0.0)),

                "predicted_business_impact":      pred_bi,
                "business_impact_confidence":     float(bi_row.get("confidence", 0.0)),

                "predicted_priority":             pred_pri,
                "priority_confidence":            float(c_info.get("priority_confidence", 0.0)),

                "predicted_assignment_group":     pred_group,
                "assignment_group_confidence":    float(c_info.get("routing_confidence", 0.0)),

                # Historical true labels for comparison
                "alert_type_true_label":          hist_at if not pd.isna(hist_at) else None,
                "severity_true_label":            hist_sv if not pd.isna(hist_sv) else None,
                "business_impact_true_label":     hist_bi if not pd.isna(hist_bi) else None,
                "priority_true_label":            hist_pri if not pd.isna(hist_pri) else None,
                "assignment_group_true_label":    hist_group if not pd.isna(hist_group) else None,
            })

        _self._stage2_combined = pd.DataFrame(rows)
        return _self._stage2_combined

    # ------------------------------------------------------------------
    # Stage 3 — candidate incident groups
    # ------------------------------------------------------------------

    @st.cache_data
    def load_stage3_incidents(_self) -> List[Dict[str, Any]]:
        if _self._stage3_incidents is not None:
            return _self._stage3_incidents

        path = _self.stage3_dir / "stage3_candidate_incidents.json"
        with open(path) as f:
            data = json.load(f)
            _self._stage3_incidents = data.get("incidents", [])
        return _self._stage3_incidents

    @st.cache_data
    def load_stage3_summary(_self) -> Dict[str, Any]:
        path = _self.data_dir / "stage3_canonical_results" / "results_summary.json"
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Stage 4 — RCA results mapping & Identity Validation
    # ------------------------------------------------------------------

    def _get_stage4_rich_mapping(self) -> Dict[str, Dict[str, Any]]:
        """
        Return a dict of {incident_id: normalised RCA record} for all 151
        Stage 3 incidents using strict incident-level identity validation.

        Matching Tiers & Data Provenance:
          1. Exact Group Match (`match_method="exact_set_match"`, `source_type="llm_exact"`):
             Stage 3 candidate incident's alert set is 100% equal to an LLM
             rich RCA record's alert set in `stage4_full_889.json` (119 incidents).

          2. Partial Overlap Match (`match_method="partial_overlap"`, `source_type="llm_partial"`):
             Stage 3 incident's alert set shares alerts with LLM RCA records, but
             alert sets are not identical (21 incidents). Flagged as partial match
             with overlap metadata. Not presented as exact incident RCA.

          3. Basic Canonical Record (`match_method="basic_canonical"`, `source_type="basic_canonical"`):
             The 11 incidents whose alert IDs do not appear in `stage4_full_889.json`
             match against `rca_summary.csv`. Values genuinely present (component,
             failure_type, confidence, evidence_count, diagnosis_status) are preserved.
             Confidence is flagged as `confidence_provenance="mock_pipeline_baseline"`.
             Description is None and recommended_actions is [].

          4. Unresolved (`match_method="unresolved"`, `source_type="unresolved"`):
             Fallback for incidents with no data in any source (0 incidents).
        """
        if self._stage4_rich_map is not None:
            return self._stage4_rich_map

        self._stage4_rich_map = {}

        # --- Load LLM rich JSON ---
        llm_rca: List[Dict] = []
        llm_path = self.data_dir / "llm_outputs" / "stage4_full_889.json"
        if llm_path.exists():
            with open(llm_path) as f:
                llm_rca = json.load(f).get("incidents", [])

        # Index LLM records by exact frozenset of alert_ids, and build list for partial overlap checking
        llm_by_exact_set: Dict[frozenset, Dict] = {}
        llm_set_list: List[tuple[frozenset, Dict]] = []
        for llm_inc in llm_rca:
            f_set = frozenset(llm_inc.get("alert_ids", []))
            if f_set:
                llm_by_exact_set[f_set] = llm_inc
                llm_set_list.append((f_set, llm_inc))

        # --- Load basic canonical CSV (rca_summary.csv) ---
        csv_by_id: Dict[str, Dict] = {}
        csv_path = self.stage4_dir / "rca_summary.csv"
        if csv_path.exists():
            import csv as csv_module
            with open(csv_path) as f:
                reader = csv_module.DictReader(f)
                for row in reader:
                    csv_by_id[row["incident_id"]] = row

        # --- Map every Stage 3 incident ---
        stage3_incidents = self.load_stage3_incidents()

        for inc in stage3_incidents:
            inc_id = inc["incident_id"]
            s3_set = frozenset(inc.get("alert_ids", []))

            # Tier 1: Exact group match (100% alert-set equality)
            if s3_set in llm_by_exact_set:
                matched_llm = llm_by_exact_set[s3_set]
                merged = dict(matched_llm)
                merged["incident_id"] = inc_id
                merged["match_method"] = "exact_set_match"
                merged["source_type"] = "llm_exact"
                merged["confidence_provenance"] = "model_reported_llm"
                merged["is_partial_match"] = False
                merged["overlap_info"] = None
                self._stage4_rich_map[inc_id] = normalize_rca_record(merged)
                continue

            # Tier 2: Partial / Overlapping match (shares alerts, but set equality fails)
            overlapping_matches = []
            for l_set, l_inc in llm_set_list:
                shared = s3_set & l_set
                if shared:
                    overlap_ratio = len(shared) / max(len(s3_set), len(l_set))
                    overlapping_matches.append((overlap_ratio, len(shared), l_inc))

            if overlapping_matches:
                # Deterministic sorting by highest overlap ratio, then shared count, then LLM incident_id
                overlapping_matches.sort(key=lambda x: (x[0], x[1], x[2].get("incident_id", "")), reverse=True)
                best_ratio, best_shared_cnt, best_llm = overlapping_matches[0]

                merged = dict(best_llm)
                merged["incident_id"] = inc_id
                merged["match_method"] = "partial_overlap"
                merged["source_type"] = "llm_partial"
                merged["confidence_provenance"] = "model_reported_llm"
                merged["is_partial_match"] = True
                merged["overlap_info"] = {
                    "matched_llm_incident_id": best_llm.get("incident_id"),
                    "shared_alert_count": best_shared_cnt,
                    "incident_alert_count": len(s3_set),
                    "llm_alert_count": len(frozenset(best_llm.get("alert_ids", []))),
                    "overlap_ratio": best_ratio,
                    "all_candidate_llm_matches": [m[2].get("incident_id") for m in overlapping_matches],
                }
                self._stage4_rich_map[inc_id] = normalize_rca_record(merged)
                continue

            # Tier 3: Basic canonical record from rca_summary.csv
            basic_row = csv_by_id.get(inc_id)
            if basic_row:
                rec = {
                    "incident_id": inc_id,
                    "diagnosis_status": basic_row.get("diagnosis_status", "ambiguous"),
                    "match_method": "basic_canonical",
                    "source_type": "basic_canonical",
                    "confidence_provenance": "mock_pipeline_baseline",
                    "is_partial_match": False,
                    "overlap_info": None,
                    "root_cause_component": basic_row.get("root_cause_component"),
                    "root_cause_failure_type": basic_row.get("root_cause_failure_type"),
                    "root_cause_confidence": basic_row.get("root_cause_confidence"),
                    "evidence_count": basic_row.get("evidence_count", 0),
                    "description": None,
                    "evidence": [],
                    "recommended_actions": [],
                    "alternative_hypotheses": [],
                }
                self._stage4_rich_map[inc_id] = normalize_rca_record(rec)
                continue

            # Tier 4: Unresolved
            no_match = {
                "incident_id": inc_id,
                "diagnosis_status": "ambiguous",
                "match_method": "unresolved",
                "source_type": "unresolved",
                "confidence_provenance": "none",
                "is_partial_match": False,
                "overlap_info": None,
                "probable_root_cause": {
                    "component": None,
                    "failure_type": None,
                    "analysis_confidence": None,
                    "description": None,
                },
                "evidence_count": 0,
                "evidence": [],
                "recommended_actions": [],
                "alternative_hypotheses": [],
            }
            self._stage4_rich_map[inc_id] = normalize_rca_record(no_match)

        return self._stage4_rich_map

    @st.cache_data
    def load_stage4_summary(_self) -> pd.DataFrame:
        """Return Stage 4 summary DataFrame for the UI table (151 rows)."""
        if _self._stage4_summary_df is not None:
            return _self._stage4_summary_df

        incidents = _self.load_stage3_incidents()
        rich_map  = _self._get_stage4_rich_mapping()

        rows = []
        for inc in incidents:
            inc_id = inc["incident_id"]
            rca    = rich_map.get(inc_id, {})
            prc    = rca.get("probable_root_cause", {})

            rows.append({
                "incident_id":           inc_id,
                "client":                inc.get("client", ""),
                "alert_count":           inc.get("alert_count", 0),
                "diagnosis_status":      rca.get("diagnosis_status", "ambiguous"),
                "component":             prc.get("component"),
                "failure_type":          prc.get("failure_type"),
                "confidence":            prc.get("confidence"),
                "confidence_provenance": rca.get("confidence_provenance", "none"),
                "evidence_count":        rca.get("evidence_count", 0),
                "match_method":          rca.get("match_method", "unresolved"),
                "source_type":           rca.get("source_type", "unresolved"),
                "is_partial_match":      rca.get("is_partial_match", False),
            })

        _self._stage4_summary_df = pd.DataFrame(rows)
        return _self._stage4_summary_df

    @st.cache_data
    def load_stage4_statistics(_self) -> Dict[str, Any]:
        """Load Stage 4 statistics from rca_statistics.json."""
        path = _self.stage4_dir / "rca_statistics.json"
        with open(path) as f:
            return json.load(f)

    def get_heuristic_suggestions(self, component: Optional[str], failure_type: Optional[str]) -> List[Dict[str, Any]]:
        """
        Return taxonomy-derived heuristic suggestions for a component/failure_type.
        These are explicitly labelled as taxonomy suggestions, NOT incident-specific RCA results,
        and carry no confidence scores.
        """
        if not component:
            return []
        suggestions = []
        comp_lower = str(component).lower()
        if "db" in comp_lower or "database" in comp_lower:
            suggestions.append({
                "suggestion": "Inspect database connection pool metrics and active queries",
                "category": "Taxonomy Heuristic",
                "source": "heuristic_taxonomy",
                "is_heuristic": True,
            })
            suggestions.append({
                "suggestion": "Check for unindexed queries causing lock contention",
                "category": "Taxonomy Heuristic",
                "source": "heuristic_taxonomy",
                "is_heuristic": True,
            })
        elif "app" in comp_lower or "application" in comp_lower:
            suggestions.append({
                "suggestion": "Review application thread pool utilization and GC pauses",
                "category": "Taxonomy Heuristic",
                "source": "heuristic_taxonomy",
                "is_heuristic": True,
            })
        return suggestions

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def build_alert_to_incident_map(self) -> Dict[str, str]:
        if self._alert_to_incident is None:
            self._alert_to_incident = {}
            for incident in self.load_stage3_incidents():
                iid = incident["incident_id"]
                for aid in incident.get("alert_ids", []):
                    self._alert_to_incident[aid] = iid
        return self._alert_to_incident

    def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        df   = self.load_stage2()
        rows = df[df["alert_id"] == alert_id]
        return rows.iloc[0].to_dict() if not rows.empty else None

    def get_incident_for_alert(self, alert_id: str) -> Optional[str]:
        return self.build_alert_to_incident_map().get(alert_id)

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        for inc in self.load_stage3_incidents():
            if inc["incident_id"] == incident_id:
                return inc
        return None

    def get_rca(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the fully normalised RCA record for an incident, enriched
        with Stage 3 metadata (client, alert_count, alert_ids).
        """
        rich_map = self._get_stage4_rich_mapping()
        rca_data = rich_map.get(incident_id)
        if not rca_data:
            return None

        incident = self.get_incident(incident_id)
        if incident:
            rca_data = dict(rca_data)   # avoid mutating cached copy
            rca_data["client"]      = incident.get("client", "")
            rca_data["alert_count"] = incident.get("alert_count", 0)
            rca_data["alert_ids"]   = incident.get("alert_ids", [])

        if rca_data.get("match_method") != "basic_canonical" and not rca_data.get("support_communication") and not rca_data.get("operations_summary"):
            queue_res = self._get_stage4_queue_result(incident_id)
            if queue_res:
                rca_data["support_communication"] = queue_res.get("support_communication")
                rca_data["stakeholder_communication"] = queue_res.get("stakeholder_communication")
                if not rca_data.get("recommended_actions"):
                    rca_data["recommended_actions"] = queue_res.get("recommended_actions", [])

        return rca_data

    def _get_stage4_queue_result(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Return the completed Stage 4 task result from SQLite queue if available."""
        if not hasattr(self, "_stage4_queue_results_cache") or self._stage4_queue_results_cache is None:
            self._stage4_queue_results_cache = {}
            db_path = self.data_dir / "stage4_task_queue.db"
            if db_path.exists():
                try:
                    import sqlite3
                    with sqlite3.connect(db_path) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT incident_id, result_json FROM stage4_tasks WHERE status = 'completed';")
                        for r in cur.fetchall():
                            if r[1]:
                                self._stage4_queue_results_cache[r[0]] = json.loads(r[1])
                except Exception:
                    pass
        return self._stage4_queue_results_cache.get(incident_id)

    def get_stage4_telemetry(self, incident_id: str) -> List[Dict[str, Any]]:
        """
        Return the Stage 4 synthetic telemetry evidence (mock logs, metrics, traces)
        generated for this incident from the Stage 4 pipeline task queue.
        """
        if not hasattr(self, "_stage4_telemetry_cache") or self._stage4_telemetry_cache is None:
            self._stage4_telemetry_cache = {}
            db_path = self.data_dir / "stage4_task_queue.db"
            if db_path.exists():
                try:
                    import sqlite3
                    with sqlite3.connect(db_path) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT incident_id, evidence_json FROM stage4_tasks WHERE status = 'completed';")
                        for r in cur.fetchall():
                            if r[1]:
                                self._stage4_telemetry_cache[r[0]] = json.loads(r[1])
                except Exception:
                    pass
        return self._stage4_telemetry_cache.get(incident_id, [])

    def get_summary_stats(self) -> Dict[str, Any]:
        """Summary statistics across Stage 1-4 pipelines."""
        raw_df      = self.load_raw_alerts()
        incidents   = self.load_stage3_incidents()
        rich_map    = self._get_stage4_rich_mapping()
        stage4_stats = self.load_stage4_statistics()

        grouped_alerts = sum(inc.get("alert_count", 0) for inc in incidents)
        total_alerts   = len(raw_df)

        return {
            "total_alerts":             total_alerts,
            "candidate_incident_groups": len(incidents),
            "grouped_alerts":           grouped_alerts,
            "uncorrelated_alerts":      total_alerts - grouped_alerts,
            "rca_analyses_count":       len(rich_map),
            "ambiguous_count":          stage4_stats["diagnosis_status"].get("ambiguous", 0),
            "insufficient_count":       stage4_stats["diagnosis_status"].get("insufficient_evidence", 0),
            "sufficient_count":          stage4_stats["diagnosis_status"].get("sufficient_evidence", 0),
        }


def get_loader() -> DataLoader:
    return DataLoader()
