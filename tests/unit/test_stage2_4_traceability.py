"""
Unit tests for Stage 2 prediction alert_id reordering resilience,
exact alert-set identity matching, partial overlap classification, and confidence provenance.
"""

import sys
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "frontend"))

from data_loader import DataLoader, normalize_rca_record


class TestStage2PredictionTraceability:
    """Tests for Stage 2 keyed join by alert_id and reordering resilience."""

    def test_reordered_prediction_rows_join_by_alert_id(self):
        """Reordering rows in Stage 2 prediction CSV must NOT change joined alert predictions."""
        loader = DataLoader()
        alerts_df = loader.load_raw_alerts().rename(columns={"Number": "alert_id"})
        predictions_df = loader.load_stage2()

        assert "alert_id" in predictions_df.columns
        assert len(alerts_df) == len(predictions_df) == 889

        # Verify predictions match by alert_id
        original_joined = pd.merge(alerts_df, predictions_df, on="alert_id", how="left")

        # Shuffle predictions dataframe
        shuffled_predictions = predictions_df.sample(frac=1.0, random_state=42).reset_index(drop=True)
        shuffled_joined = pd.merge(alerts_df, shuffled_predictions, on="alert_id", how="left")

        # Joined result must be 100% identical regardless of row order
        pd.testing.assert_frame_equal(original_joined, shuffled_joined)

    def test_all_889_alerts_accounted_for_in_stage2(self):
        """All 889 alerts must have corresponding Stage 2 predictions."""
        loader = DataLoader()
        alerts_df = loader.load_raw_alerts()
        predictions_df = loader.load_stage2()

        raw_alert_ids = set(alerts_df["Number"])
        pred_ids = set(predictions_df["alert_id"])

        assert raw_alert_ids == pred_ids
        assert len(raw_alert_ids) == 889


class TestStage4IdentityMatchingAndProvenance:
    """Tests for Stage 4 exact alert-set matching, partial overlap handling, and confidence provenance."""

    def test_151_incidents_classification_counts(self):
        """Verify the exact count of exact matches (119), partial matches (21), and basic canonical (11)."""
        loader = DataLoader()
        incidents = loader.load_stage3_incidents()
        assert len(incidents) == 151

        exact_cnt = 0
        partial_cnt = 0
        basic_cnt = 0

        for inc in incidents:
            rca = loader.get_rca(inc["incident_id"])
            assert rca is not None
            method = rca.get("match_method")
            if method == "exact_set_match":
                exact_cnt += 1
            elif method == "partial_overlap":
                partial_cnt += 1
            elif method == "basic_canonical":
                basic_cnt += 1

        assert exact_cnt == 119, f"Expected 119 exact set matches, got {exact_cnt}"
        assert partial_cnt == 21, f"Expected 21 partial overlap matches, got {partial_cnt}"
        assert basic_cnt == 11, f"Expected 11 basic canonical records, got {basic_cnt}"

    def test_identical_alert_sets_match_successfully_as_exact(self):
        """Identical alert sets must be classified as match_method='exact_set_match' with is_partial_match=False."""
        loader = DataLoader()
        incidents = loader.load_stage3_incidents()

        exact_incidents = [inc for inc in incidents if loader.get_rca(inc["incident_id"]).get("match_method") == "exact_set_match"]
        assert len(exact_incidents) == 119

        for inc in exact_incidents:
            rca = loader.get_rca(inc["incident_id"])
            assert rca["match_method"] == "exact_set_match"
            assert rca["is_partial_match"] is False
            assert rca["source_type"] == "llm_exact"
            assert rca["confidence_provenance"] == "model_reported_llm"

    def test_partial_overlap_alert_sets_not_treated_as_exact(self):
        """Partial overlap alert sets must NOT be treated as exact matches (is_partial_match=True)."""
        loader = DataLoader()
        incidents = loader.load_stage3_incidents()

        partial_incidents = [inc for inc in incidents if loader.get_rca(inc["incident_id"]).get("match_method") == "partial_overlap"]
        assert len(partial_incidents) == 21

        for inc in partial_incidents:
            rca = loader.get_rca(inc["incident_id"])
            assert rca["match_method"] == "partial_overlap"
            assert rca["is_partial_match"] is True
            assert rca["source_type"] == "llm_partial"
            assert rca["overlap_info"] is not None
            assert rca["overlap_info"]["matched_llm_incident_id"] is not None
            assert rca["overlap_info"]["shared_alert_count"] > 0

    def test_multiple_rich_records_sharing_alerts_deterministic_selection(self):
        """When multiple LLM records share alerts, candidate selection is deterministic by overlap ratio."""
        loader = DataLoader()
        rca = loader.get_rca("INCIDENT-0022")
        assert rca["match_method"] == "partial_overlap"
        assert rca["is_partial_match"] is True
        assert len(rca["overlap_info"]["all_candidate_llm_matches"]) >= 2

    def test_preservation_of_legitimate_basic_canonical_records(self):
        """The 11 basic canonical records preserve component, failure_type, confidence, and have description=None."""
        loader = DataLoader()
        incidents = loader.load_stage3_incidents()

        basic_incidents = [inc for inc in incidents if loader.get_rca(inc["incident_id"]).get("match_method") == "basic_canonical"]
        assert len(basic_incidents) == 11

        for inc in basic_incidents:
            rca = loader.get_rca(inc["incident_id"])
            assert rca["match_method"] == "basic_canonical"
            assert rca["confidence_provenance"] == "mock_pipeline_baseline"
            prc = rca["probable_root_cause"]
            assert prc.get("component") is not None
            assert prc.get("failure_type") is not None
            assert prc.get("description") is None
            assert rca.get("recommended_actions") == []

    def test_unavailable_confidence_remains_unavailable(self):
        """If confidence is missing/NaN, it remains None with provenance='none'."""
        raw_record = {
            "incident_id": "INCIDENT-NO-CONF",
            "diagnosis_status": "ambiguous",
        }
        norm = normalize_rca_record(raw_record)
        assert norm["probable_root_cause"]["confidence"] is None

    def test_human_approval_remains_mandatory(self):
        """All normalised RCA records enforce human_review_required=True and execution_status='NOT EXECUTED'."""
        loader = DataLoader()
        incidents = loader.load_stage3_incidents()

        for inc in incidents:
            rca = loader.get_rca(inc["incident_id"])
            assert rca.get("human_review_required") is True
            assert rca.get("execution_status") == "NOT EXECUTED"
