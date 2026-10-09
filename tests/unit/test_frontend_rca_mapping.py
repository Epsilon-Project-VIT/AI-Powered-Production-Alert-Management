"""
Frontend RCA mapping tests.

Tests the normalize_rca_record() function and data_loader Stage 4 methods
using synthetic fixtures.  Does NOT run backend pipelines or modify Stage 4 results.

Key invariant: the CANONICAL source for component / failure_type / confidence /
evidence_count is rca_summary.csv (stage4_canonical_results/), NOT the JSON.
"""

import math
import pytest
import sys
from pathlib import Path

# Make sure the frontend module is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "frontend"))

from data_loader import normalize_rca_record


# ---------------------------------------------------------------------------
# Fixtures – synthetic records mirroring the real stored schemas
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_json_record():
    """Schema A – current canonical JSON (final_outputs/stage4_rca_results.json)."""
    return {
        "incident_id": "INCIDENT-0001",
        "diagnosis_status": "ambiguous",
        "probable_root_cause": {
            "component": "database",
            "failure_type": "performance_degradation",
        },
        "evidence_count": 22,
        "recommended_actions_count": 2,
    }


@pytest.fixture
def rich_schema_record():
    """Schema B – LLM-generated (llm_outputs/stage4_full_889.json)."""
    return {
        "incident_id": "INC-LLM-001",
        "diagnosis_status": "AMBIGUOUS",
        "probable_root_cause": {
            "component": "Batch / job service",
            "failure_type": "batch/job execution failure",
            "description": "Historical-alert evidence supports the following probable failure mechanism.",
            "analysis_confidence": 0.73,
            "is_confirmed": False,
        },
        "alternative_hypotheses": [],
        "supporting_evidence_ids": ["hist_INC001", "hist_INC002"],
        "evidence": [
            {
                "evidence_id": "hist_INC001",
                "source_type": "historical_alert",
                "source": "Excel alert description",
                "source_id": "INC001",
                "is_mock": False,
                "description": "Batch job failed",
                "provenance_note": "Directly copied from historical record",
            },
            {
                "evidence_id": "hist_INC002",
                "source_type": "historical_alert",
                "source": "Excel alert description",
                "source_id": "INC002",
                "is_mock": False,
                "description": "Another batch job failed",
                "provenance_note": "Directly copied from historical record",
            },
        ],
        "recommended_actions": [
            {"action": "Investigate scheduler", "priority": 1, "rationale": "Most likely cause"},
        ],
        "missing_evidence": ["logs", "metrics", "traces"],
    }


@pytest.fixture
def csv_row_as_dict():
    """Schema C – CSV row passed as dict (flat canonical mock-pipeline layout)."""
    return {
        "incident_id": "INCIDENT-0001",
        "diagnosis_status": "ambiguous",
        "root_cause_component": "database",
        "root_cause_failure_type": "connection_exhaustion",
        "root_cause_confidence": 0.9400000000000001,
        "evidence_count": 2959,
        "mock_evidence_count": 2959,
        "alternative_hypotheses_count": 3,
        "recommended_actions_count": 2,
        "human_review_required": "True",
        "telemetry_is_mock": "True",
        "reasoning_provider": "mock",
    }


@pytest.fixture
def csv_row_mulesoft():
    """CSV row for a mulesoft incident."""
    return {
        "incident_id": "INCIDENT-0025",
        "diagnosis_status": "ambiguous",
        "root_cause_component": "mulesoft",
        "root_cause_failure_type": "service_error",
        "root_cause_confidence": 0.904,
        "evidence_count": 69,
        "mock_evidence_count": 69,
        "alternative_hypotheses_count": 3,
        "recommended_actions_count": 2,
        "human_review_required": "True",
        "telemetry_is_mock": "True",
        "reasoning_provider": "mock",
    }


@pytest.fixture
def csv_row_elb():
    """CSV row for the ELB incident."""
    return {
        "incident_id": "INCIDENT-0121",
        "diagnosis_status": "ambiguous",
        "root_cause_component": "elb",
        "root_cause_failure_type": "service_error",
        "root_cause_confidence": 0.9400000000000001,
        "evidence_count": 19,
        "mock_evidence_count": 19,
        "alternative_hypotheses_count": 3,
        "recommended_actions_count": 2,
        "human_review_required": "True",
        "telemetry_is_mock": "True",
        "reasoning_provider": "mock",
    }


@pytest.fixture
def csv_row_insufficient():
    """CSV row for the insufficient_evidence incident."""
    return {
        "incident_id": "INCIDENT-0096",
        "diagnosis_status": "insufficient_evidence",
        "root_cause_component": "extract / report delivery delay",
        "root_cause_failure_type": "service_error",
        "root_cause_confidence": 0.0,
        "evidence_count": 0,
        "mock_evidence_count": 0,
        "alternative_hypotheses_count": 1,
        "recommended_actions_count": 2,
        "human_review_required": "True",
        "telemetry_is_mock": "True",
        "reasoning_provider": "mock",
    }


@pytest.fixture
def no_root_cause_record():
    """Record with no root cause info at all."""
    return {
        "incident_id": "INCIDENT-EMPTY",
        "diagnosis_status": "insufficient_evidence",
    }


# ---------------------------------------------------------------------------
# Tests – normalize_rca_record() on JSON schemas
# ---------------------------------------------------------------------------

class TestMinimalJSONRecord:
    """Tests for Schema A (current canonical minimal JSON)."""

    def test_component_preserved(self, minimal_json_record):
        norm = normalize_rca_record(minimal_json_record)
        assert norm["probable_root_cause"]["component"] == "database"

    def test_failure_type_preserved(self, minimal_json_record):
        norm = normalize_rca_record(minimal_json_record)
        assert norm["probable_root_cause"]["failure_type"] == "performance_degradation"

    def test_confidence_is_none_when_absent(self, minimal_json_record):
        """Minimal JSON has no confidence field → must be None, not 0.0."""
        norm = normalize_rca_record(minimal_json_record)
        assert norm["probable_root_cause"]["confidence"] is None

    def test_description_is_none_when_absent(self, minimal_json_record):
        norm = normalize_rca_record(minimal_json_record)
        assert norm["probable_root_cause"]["description"] is None

    def test_evidence_count_from_stored_field(self, minimal_json_record):
        norm = normalize_rca_record(minimal_json_record)
        assert norm["evidence_count"] == 22

    def test_evidence_list_is_empty(self, minimal_json_record):
        norm = normalize_rca_record(minimal_json_record)
        assert norm["evidence"] == []

    def test_diagnosis_status_lowercased(self, minimal_json_record):
        norm = normalize_rca_record(minimal_json_record)
        assert norm["diagnosis_status"] == "ambiguous"


class TestRichJSONRecord:
    """Tests for Schema B (LLM-generated rich JSON)."""

    def test_component_preserved(self, rich_schema_record):
        norm = normalize_rca_record(rich_schema_record)
        assert norm["probable_root_cause"]["component"] == "Batch / job service"

    def test_failure_type_preserved(self, rich_schema_record):
        norm = normalize_rca_record(rich_schema_record)
        assert norm["probable_root_cause"]["failure_type"] == "batch/job execution failure"

    def test_confidence_from_analysis_confidence_field(self, rich_schema_record):
        norm = normalize_rca_record(rich_schema_record)
        assert norm["probable_root_cause"]["confidence"] == pytest.approx(0.73)

    def test_description_preserved(self, rich_schema_record):
        norm = normalize_rca_record(rich_schema_record)
        assert "probable failure mechanism" in norm["probable_root_cause"]["description"]

    def test_evidence_list_preserved(self, rich_schema_record):
        norm = normalize_rca_record(rich_schema_record)
        assert len(norm["evidence"]) == 2

    def test_evidence_count_from_list_length(self, rich_schema_record):
        norm = normalize_rca_record(rich_schema_record)
        assert norm["evidence_count"] == 2

    def test_diagnosis_status_lowercased(self, rich_schema_record):
        """AMBIGUOUS → ambiguous."""
        norm = normalize_rca_record(rich_schema_record)
        assert norm["diagnosis_status"] == "ambiguous"

    def test_historical_alert_evidence_not_fabricated(self, rich_schema_record):
        norm = normalize_rca_record(rich_schema_record)
        for ev in norm["evidence"]:
            assert ev["source_type"] == "historical_alert"
            assert ev["is_mock"] is False


class TestCSVRowFormat:
    """Tests for Schema C – CSV rows passed as dicts (flat canonical layout)."""

    def test_component_from_root_cause_component(self, csv_row_as_dict):
        norm = normalize_rca_record(csv_row_as_dict)
        assert norm["probable_root_cause"]["component"] == "database"

    def test_failure_type_is_connection_exhaustion(self, csv_row_as_dict):
        """The canonical mock-pipeline output uses connection_exhaustion – must be preserved."""
        norm = normalize_rca_record(csv_row_as_dict)
        assert norm["probable_root_cause"]["failure_type"] == "connection_exhaustion"

    def test_confidence_from_root_cause_confidence(self, csv_row_as_dict):
        """CSV stores actual confidence (0.94) – must NOT be discarded."""
        norm = normalize_rca_record(csv_row_as_dict)
        assert norm["probable_root_cause"]["confidence"] == pytest.approx(0.94, rel=1e-3)

    def test_evidence_count_from_csv(self, csv_row_as_dict):
        """CSV evidence_count (2959) is correct canonical value, not 22 from JSON."""
        norm = normalize_rca_record(csv_row_as_dict)
        assert norm["evidence_count"] == 2959

    def test_diagnosis_status_lowercased(self, csv_row_as_dict):
        norm = normalize_rca_record(csv_row_as_dict)
        assert norm["diagnosis_status"] == "ambiguous"

    def test_mulesoft_component_preserved(self, csv_row_mulesoft):
        norm = normalize_rca_record(csv_row_mulesoft)
        assert norm["probable_root_cause"]["component"] == "mulesoft"
        assert norm["probable_root_cause"]["failure_type"] == "service_error"

    def test_elb_component_preserved(self, csv_row_elb):
        norm = normalize_rca_record(csv_row_elb)
        assert norm["probable_root_cause"]["component"] == "elb"

    def test_extract_report_component_preserved(self, csv_row_insufficient):
        norm = normalize_rca_record(csv_row_insufficient)
        assert norm["probable_root_cause"]["component"] == "extract / report delivery delay"

    def test_zero_confidence_preserved_for_insufficient_evidence(self, csv_row_insufficient):
        """0.0 is a legitimate stored value for insufficient_evidence – must NOT become None."""
        norm = normalize_rca_record(csv_row_insufficient)
        conf = norm["probable_root_cause"]["confidence"]
        assert conf is not None, "Explicit 0.0 confidence must not be treated as absent"
        assert conf == pytest.approx(0.0)

    def test_insufficient_evidence_zero_evidence_count(self, csv_row_insufficient):
        norm = normalize_rca_record(csv_row_insufficient)
        assert norm["evidence_count"] == 0


class TestNoFabricatedDefaults:
    """Explicit tests asserting no fabricated/generic values are injected."""

    def test_confidence_none_not_zero_for_absent_field(self, minimal_json_record):
        """Absent confidence → None, not 0.0."""
        norm = normalize_rca_record(minimal_json_record)
        conf = norm["probable_root_cause"]["confidence"]
        assert conf is None, f"Expected None for missing confidence, got {conf!r}"

    def test_description_none_not_string_for_absent_field(self, minimal_json_record):
        """Absent description → None, not 'No description available'."""
        norm = normalize_rca_record(minimal_json_record)
        desc = norm["probable_root_cause"]["description"]
        assert desc is None, f"Expected None for missing description, got {desc!r}"

    def test_evidence_not_fabricated(self, minimal_json_record):
        """Evidence list must be [] when no evidence objects exist."""
        norm = normalize_rca_record(minimal_json_record)
        assert norm["evidence"] == []

    def test_connection_exhaustion_preserved_from_csv(self, csv_row_as_dict):
        """connection_exhaustion IS the actual canonical value from the mock pipeline."""
        norm = normalize_rca_record(csv_row_as_dict)
        assert norm["probable_root_cause"]["failure_type"] == "connection_exhaustion"

    def test_mulesoft_not_replaced_by_database(self, csv_row_mulesoft):
        norm = normalize_rca_record(csv_row_mulesoft)
        assert norm["probable_root_cause"]["component"] == "mulesoft"
        assert norm["probable_root_cause"]["component"] != "database"

    def test_elb_not_replaced_by_application(self, csv_row_elb):
        norm = normalize_rca_record(csv_row_elb)
        assert norm["probable_root_cause"]["component"] == "elb"
        assert norm["probable_root_cause"]["component"] != "application"


class TestCanonical151RecordCSV:
    """
    Integration-style tests verifying the canonical 151-record CSV dataset.
    Skipped gracefully if files are not present.
    """

    @pytest.fixture(autouse=True)
    def check_data_files(self):
        project_root = Path(__file__).parent.parent.parent
        csv_path = project_root / "data" / "stage4_canonical_results" / "rca_summary.csv"
        if not csv_path.exists():
            pytest.skip("Canonical Stage 4 CSV not found – skipping integration tests")

    def _load_csv(self):
        import csv as csv_mod
        project_root = Path(__file__).parent.parent.parent
        path = project_root / "data" / "stage4_canonical_results" / "rca_summary.csv"
        return list(csv_mod.DictReader(open(path)))

    def test_csv_has_151_rows(self):
        rows = self._load_csv()
        assert len(rows) == 151, f"Expected 151 rows, got {len(rows)}"

    def test_incident_0001_in_csv(self):
        rows = self._load_csv()
        ids = [r["incident_id"] for r in rows]
        assert "INCIDENT-0001" in ids

    def test_incident_0001_component_is_database(self):
        rows = self._load_csv()
        r = next(r for r in rows if r["incident_id"] == "INCIDENT-0001")
        assert r["root_cause_component"] == "database"

    def test_incident_0001_failure_type_is_connection_exhaustion(self):
        """
        The canonical CSV shows connection_exhaustion for INCIDENT-0001.
        This IS the actual canonical value from the mock pipeline run.
        """
        rows = self._load_csv()
        r = next(r for r in rows if r["incident_id"] == "INCIDENT-0001")
        assert r["root_cause_failure_type"] == "connection_exhaustion"

    def test_incident_0001_confidence_is_0_94(self):
        rows = self._load_csv()
        r = next(r for r in rows if r["incident_id"] == "INCIDENT-0001")
        assert float(r["root_cause_confidence"]) == pytest.approx(0.94, rel=1e-3)

    def test_incident_0001_evidence_count_is_2959(self):
        rows = self._load_csv()
        r = next(r for r in rows if r["incident_id"] == "INCIDENT-0001")
        assert int(r["evidence_count"]) == 2959

    def test_mulesoft_incidents_exist(self):
        """4 mulesoft incidents must appear in CSV."""
        rows = self._load_csv()
        mulesoft = [r for r in rows if r["root_cause_component"] == "mulesoft"]
        assert len(mulesoft) == 4

    def test_elb_incident_exists(self):
        rows = self._load_csv()
        elb = [r for r in rows if r["root_cause_component"] == "elb"]
        assert len(elb) == 1
        assert elb[0]["incident_id"] == "INCIDENT-0121"

    def test_extract_report_incident_exists(self):
        rows = self._load_csv()
        er = [r for r in rows if r["root_cause_component"] == "extract / report delivery delay"]
        assert len(er) == 1
        assert er[0]["incident_id"] == "INCIDENT-0096"

    def test_insufficient_evidence_is_incident_0096(self):
        rows = self._load_csv()
        insuf = [r for r in rows if r["diagnosis_status"] == "insufficient_evidence"]
        assert len(insuf) == 1
        assert insuf[0]["incident_id"] == "INCIDENT-0096"

    def test_connection_exhaustion_is_dominant_failure_type(self):
        """
        144 of 151 incidents have connection_exhaustion per the canonical mock-pipeline run.
        """
        rows = self._load_csv()
        conn_ex = sum(1 for r in rows if r["root_cause_failure_type"] == "connection_exhaustion")
        assert conn_ex == 144

    def test_status_counts_match_statistics(self):
        import json
        project_root = Path(__file__).parent.parent.parent
        stats = json.load(open(project_root / "data" / "stage4_canonical_results" / "rca_statistics.json"))
        rows = self._load_csv()
        from collections import Counter
        status_counts = Counter(r["diagnosis_status"] for r in rows)
        assert status_counts.get("ambiguous", 0) == stats["diagnosis_status"]["ambiguous"]
        assert status_counts.get("insufficient_evidence", 0) == stats["diagnosis_status"]["insufficient_evidence"]


