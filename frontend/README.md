# LLM Review Frontend

A simple Streamlit-based review interface for offline LLM reasoning outputs (Stage 2-4).

## Overview

This frontend reads **pre-generated CSV/JSON files** from `data/llm_outputs/` and provides an interactive interface to:

- Browse 889 alerts with LLM classifications
- View correlation analysis (146 candidate incident groups)
- Explore RCA analyses with evidence and recommendations
- Review human approval requirements

**IMPORTANT:** This interface does NOT:
- Re-run ML/LLM pipelines
- Call external APIs (Gemini, NVIDIA, OpenAI)
- Generate new predictions
- Execute remediation actions

## Data Files

The frontend reads from:
```
data/llm_outputs/
├── stage2_llm_results.csv          # Alert classifications
├── stage3_full_889.json            # Full correlation data
├── stage3_incident_groups.csv      # Incident summary
├── stage4_full_889.json            # Full RCA data
└── stage4_incident_summary.csv     # RCA summary
```

## Running the Dashboard

### 1. Activate virtual environment
```bash
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

### 2. Start Streamlit
```bash
streamlit run frontend/app.py
```

### 3. Access the dashboard
The browser should open automatically to:
```
http://localhost:8501
```

## Navigation Flow

```
Dashboard
    ↓
[View All Alerts]
    ↓
Select Alert → View Classification & Reasoning
    ↓
[Open Correlated Incident]
    ↓
View Incident Group → Correlation Analysis
    ↓
[Open RCA Analysis]
    ↓
View Root Cause → Evidence → Recommendations
    ↓
Human Approval Gate (Demo Only)
```

## Features

### Dashboard Page
- KPI cards (Total Alerts, Incidents, Grouped/Uncorrelated)
- Performance comparison: Existing ML vs Offline LLM Reasoning
- Quick navigation buttons

### Alerts Page
- Search by Alert ID
- Filter by Client, Priority, Assignment Group
- View LLM classification with reasoning
- Navigate to correlated incident

### Incidents Page
- Browse 146 candidate incident groups
- Filter by client, alert count, correlation method
- View correlation reasoning
- See semantic similarity scores
- Navigate to RCA analysis

### RCA Page
- View probable root cause
- Explore alternative hypotheses
- Review evidence (with provenance warnings)
- See recommendations with approval requirements
- Human approval gate (demo interface)

## Important Notes

### Performance Metrics
- **Existing ML**: Priority 53.73%, Routing 80.60%
- **Offline LLM Reasoning**: Priority 73.13%, Routing 83.58%

These are labeled as "Offline LLM Reasoning" not "Gemini" or "NVIDIA" accuracy.

### Evidence Limitations
Stage 4 RCA is constrained to historical alert text. The interface clearly shows:
- ❌ Logs: Missing (or limited to historical alerts)
- ❌ Metrics: Missing
- ❌ Traces: Missing

### Ground Truth
- No verified incident ground truth exists in the dataset
- Correlation groups are **hypotheses**, not confirmed incidents
- RCA analyses are **ambiguous** or have **insufficient evidence**

### Human Approval
All remediation recommendations require human/policy approval:
- Execution Status: **NOT EXECUTED**
- Approval: **HUMAN / POLICY APPROVAL REQUIRED**

Approval buttons are disabled in this review interface.

## Architecture

```
frontend/
├── app.py                  # Main dashboard
├── data_loader.py          # Data loading utilities
├── pages/
│   ├── 1_Alerts.py        # Alert list & detail
│   ├── 2_Incidents.py     # Incident groups
│   └── 3_RCA.py           # RCA analysis
└── README.md              # This file
```

## Data Linking

The frontend creates these relationships:
- Alert ID → Incident ID (via Stage 3 alert_ids)
- Incident ID → RCA (via incident_id matching)
- Alert → Classification (via alert_id matching)

Missing data is handled gracefully with warnings.

## Troubleshooting

### "No module named streamlit"
```bash
pip install streamlit
```

### "File not found" errors
Ensure data files exist:
```bash
ls data/llm_outputs/
```

Should show 5 files (2 JSON, 3 CSV).

### Performance issues
The dashboard caches data using `@st.cache_data` for fast loading.
Clear cache: Click "Clear cache" in Streamlit menu (hamburger icon).

## Dependencies

- streamlit>=1.28.0
- pandas>=2.0.0
- Python 3.8+

Already included in project's venv.

## License

Part of the Alert Management System project.
