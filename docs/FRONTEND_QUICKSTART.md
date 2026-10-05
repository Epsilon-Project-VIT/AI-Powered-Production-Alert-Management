# Frontend Quickstart Guide

**Last Updated:** October 5, 2026

## Quick Start

```bash
cd /home/akash-t-s-m/alert_management

# Activate virtual environment
source venv/bin/activate

# Run the frontend
streamlit run frontend/app.py
```

Access at: **http://localhost:8501**

---

## Test Data Loading

Before running the UI, verify data loads correctly:

```bash
# Activate venv
source venv/bin/activate

# Run data loading tests
python frontend/test_data_loading.py
```

Expected output:
```
✅ All data loading tests passed!

Stage 2: 889 alerts loaded
Stage 3: 151 candidate incident groups loaded
Stage 4: 151 RCA analyses loaded
```

---

## UI Pages

### 1. Dashboard (`/`)
- **Summary KPIs**: Total alerts, candidate incident groups, correlated/uncorrelated alerts
- **Recent Alerts**: Last 10 alerts with basic info
- **Quick Actions**: Links to Alerts, Incidents, RCA pages

### 2. Alerts (`/Alerts`)
- **Filters**: Client, Alert Type, Severity
- **Alert Table**: All 889 alerts with Stage 2 predictions
- **Alert Detail**: 
  - Alert information (description, timestamps)
  - Stage 2 ML classifications (Alert Type, Severity, Business Impact with confidence)
  - Stage 3 correlation status (candidate incident group or uncorrelated)

### 3. Candidate Incident Groups (`/Incidents`)
- **Filters**: Client, Minimum Alerts, Correlation Method
- **Incident Table**: 151 candidate groups
- **Incident Detail**:
  - Incident timeline (first/last alert, duration)
  - Correlation analysis (method, score)
  - Related alerts list
  - Link to Stage 4 RCA

### 4. Stage 4 RCA (`/RCA`)
- **Filters**: Client, Diagnosis Status, Component
- **RCA Table**: 151 analyses
- **RCA Detail**:
  - Probable failure mechanism (NOT confirmed root cause)
  - Experimental confidence (NOT calibrated probability)
  - Alternative hypotheses
  - Evidence availability (⚠ ALL MOCK telemetry)
  - Recommended actions
  - Human approval gate

---

## Data Sources

The frontend loads pre-generated canonical outputs:

**Stage 2 (ML Predictions):**
- `data/stage2_models_canonical/alert_type_predictions.csv`
- `data/stage2_models_canonical/severity_predictions.csv`
- `data/stage2_models_canonical/business_impact_predictions.csv`

**Stage 3 (Correlation):**
- `data/stage3_canonical_results/incident_groups.json`
- `data/stage3_canonical_results/results_summary.json`

**Stage 4 (RCA):**
- `data/stage4_canonical_results/rca_results.json`
- `data/stage4_canonical_results/rca_summary.csv`
- `data/stage4_canonical_results/rca_statistics.json`

**Raw Alerts:**
- `data/raw/Data_Alert_Ticket_Segregation.xlsx`

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total Alerts | 889 |
| Candidate Incident Groups | 151 |
| Grouped Alerts | 509 (57.3%) |
| Uncorrelated Alerts | 380 (42.7%) |
| RCA Analyses | 151 |
| Ambiguous RCA | 150 |
| Insufficient Evidence | 1 |
| Sufficient Evidence | 0 |
| Total Evidence Items | ~579,000 |
| MOCK Evidence | 100% |

---

## Terminology

**Use this terminology when discussing the UI:**

✅ **Correct:**
- "Candidate incident groups" (Stage 3)
- "Probable failure mechanism" (Stage 4)
- "Experimental confidence" (Stage 4)
- "MOCK telemetry"
- "Human review required"
- "Prototype" / "Demo environment"

❌ **Incorrect:**
- "Confirmed incidents"
- "Confirmed root cause"
- "Calibrated probability"
- "Real logs/metrics/traces"
- "Automatic remediation"
- "Production-ready"

---

## Troubleshooting

### Data Not Loading
```bash
# Check files exist
ls -lh data/stage2_models_canonical/
ls -lh data/stage3_canonical_results/
ls -lh data/stage4_canonical_results/

# Run data loading test
python frontend/test_data_loading.py
```

### Streamlit Not Found
```bash
# Activate venv first
source venv/bin/activate

# Or install streamlit
pip install streamlit pandas openpyxl
```

### Port Already in Use
```bash
# Use different port
streamlit run frontend/app.py --server.port 8502
```

### Caching Issues
```bash
# Clear Streamlit cache
streamlit cache clear
```

---

## Dependencies

Required Python packages (included in project venv):
- `streamlit` - Web framework
- `pandas` - Data manipulation
- `openpyxl` - Excel file reading

---

## Navigation Flow

**Example User Journey:**

1. **Dashboard** → View summary statistics
2. **Alerts Page** → Find alert "INC3529446"
3. **Alert Detail** → See Stage 2 predictions (Disk Space, Sev2-High, Medium impact)
4. **Alert Detail** → Click "Open Candidate Incident Group" (if correlated)
5. **Incident Detail** → View 6 correlated alerts, correlation method, timeline
6. **Incident Detail** → Click "Open Stage 4 RCA Analysis"
7. **RCA Detail** → View probable failure mechanism (database connection_exhaustion)
8. **RCA Detail** → See MOCK telemetry warning, experimental confidence, alternatives
9. **RCA Detail** → Review recommended actions
10. **RCA Detail** → Note human approval gate (execution disabled)

---

## Notes

- **Read-Only**: Frontend does not modify Stage 1-4 data or execute actions
- **Demo Environment**: Clearly labeled as demo/review, not production
- **No Real Telemetry**: All evidence is MOCK (simulated)
- **No Ground Truth**: Incident groupings are experimental, not validated
- **Human Oversight**: All actions require human approval (execution disabled)

---

## Support

For issues or questions about the frontend integration, see:
- `FRONTEND_INTEGRATION_COMPLETE.md` - Complete integration report
- `frontend/test_data_loading.py` - Data loading tests
- `STAGE1_TO_4_FINAL_AUDIT.md` - Stage 1-4 pipeline audit
- `FINAL_AUDIT_CORRECTIONS.md` - Latest corrections and fixes

---

**Status:** ✅ Frontend integration complete and tested  
**Environment:** Demo / Review  
**Next Steps:** User acceptance testing, feedback collection
