"""
RCA Page - Enterprise root cause analysis interface
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data_loader import get_loader
from styles import get_custom_css
from components import (
    render_page_header, render_custom_card, render_footer,
    format_timestamp, get_status_badge, render_approval_gate,
    render_info_box, render_metric_card, html, format_incident_id
)

st.set_page_config(
    page_title="Root Cause Analysis",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(get_custom_css(), unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    st.markdown("## Navigation")
    st.page_link("app.py", label="🏠 Dashboard", icon="🏠")
    st.page_link("pages/1_Alerts.py", label="🔔 Alerts", icon="🔔")
    st.page_link("pages/2_Incidents.py", label="📊 Incidents", icon="📊")
    st.page_link("pages/3_RCA.py", label="🔍 Root Cause Analysis", icon="🔍")

    st.markdown("---")
    st.markdown("### About")
    st.caption("Epsilon AI Alert Management System")
    st.caption("Demo/Review Environment")

# Header
render_page_header("Stage 4: Root Cause Analysis", "Probable failure mechanisms for candidate incident groups")

# Load data
loader = get_loader()
rca_summary_df = loader.load_stage4_summary()
stage4_stats = loader.load_stage4_statistics()

# Summary stats
col1, col2, col3, col4 = st.columns(4)

with col1:
    render_metric_card("RCA Analyses", len(rca_summary_df))

with col2:
    ambiguous = stage4_stats['diagnosis_status'].get('ambiguous', 0)
    render_metric_card("Ambiguous", ambiguous)

with col3:
    insufficient = stage4_stats['diagnosis_status'].get('insufficient_evidence', 0)
    render_metric_card("Insufficient Evidence", insufficient)

with col4:
    confirmed = stage4_stats['diagnosis_status'].get('sufficient_evidence', 0)
    render_metric_card("Sufficient Evidence", confirmed)

html("<br>")

render_info_box(
    "<strong>MOCK Telemetry Warning:</strong> All evidence is MOCK (simulated). "
    "Real production logs, metrics, and traces are not available in the dataset. "
    "Probable failure mechanisms are experimental, not confirmed root causes.",
    "warning"
)

# Filters
st.sidebar.markdown("### Filters")
selected_client = st.sidebar.selectbox("Client", ["All"] + sorted(rca_summary_df['client'].dropna().unique().tolist()))
selected_status = st.sidebar.selectbox("Diagnosis Status", ["All"] + sorted(rca_summary_df['diagnosis_status'].dropna().unique().tolist()))
selected_component = st.sidebar.selectbox("Component", ["All"] + sorted(rca_summary_df['component'].dropna().unique().tolist()[:20]))

# Apply filters
filtered_df = rca_summary_df.copy()

if selected_client != "All":
    filtered_df = filtered_df[filtered_df['client'] == selected_client]

if selected_status != "All":
    filtered_df = filtered_df[filtered_df['diagnosis_status'] == selected_status]

if selected_component != "All":
    filtered_df = filtered_df[filtered_df['component'] == selected_component]

html(f"<p class='filter-count'>Showing {len(filtered_df):,} of {len(rca_summary_df):,} RCA analyses</p>")

if len(filtered_df) > 0:
    # Display using Streamlit dataframe
    display_df = filtered_df.head(50)[['incident_id', 'client', 'alert_count', 'diagnosis_status', 'component', 'failure_type']].copy()
    display_df.columns = ['Incident ID', 'Client', 'Alerts', 'Status', 'Component', 'Failure Type']

    display_df['Incident ID'] = display_df['Incident ID'].apply(format_incident_id)
    display_df['Component'] = display_df['Component'].apply(lambda x: str(x)[:30] + "..." if len(str(x)) > 30 else str(x))
    display_df['Failure Type'] = display_df['Failure Type'].apply(lambda x: str(x)[:30] + "..." if len(str(x)) > 30 else str(x))

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)

    if len(filtered_df) > 50:
        st.caption(f"Showing first 50 of {len(filtered_df)} RCA analyses. Use filters to refine results.")

    html("<br>")

    # RCA Detail
    html("<h2>RCA Detail</h2>")

    # Check if RCA is pre-selected (use positional index)
    rca_list = filtered_df['incident_id'].tolist()
    default_pos = 0
    if 'selected_rca_id' in st.session_state:
        target = st.session_state['selected_rca_id']
        if target in rca_list:
            default_pos = rca_list.index(target)
        del st.session_state['selected_rca_id']

    selected_incident_id = st.selectbox(
        "Select Incident",
        options=rca_list,
        format_func=format_incident_id,
        index=default_pos,
        key='rca_select',
        label_visibility="collapsed"
    )

    if selected_incident_id:
        rca = loader.get_rca(selected_incident_id)

        if rca:
            # Top metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Incident ID</div>
                    <div class="detail-id">{format_incident_id(rca['incident_id'])}</div>
                </div>
                """)

            with col2:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Client</div>
                    <div class="detail-text">{rca['client']}</div>
                </div>
                """)

            with col3:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Alert Count</div>
                    <div class="detail-number">{rca['alert_count']}</div>
                </div>
                """)

            with col4:
                status = rca['diagnosis_status']
                status_badge = get_status_badge(status)
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Diagnosis Status</div>
                    <div style="margin-top: 0.5rem;">{status_badge}</div>
                </div>
                """)

            html("<br>")

            # Incident Window
            if 'analysis_timestamp' in rca:
                # Calculate window from incident data
                incident_data = loader.get_incident(selected_incident_id)
                if incident_data:
                    first = format_timestamp(incident_data.get('incident_start', ''))
                    last = format_timestamp(incident_data.get('incident_end', ''))
                    
                    from datetime import datetime
                    try:
                        first_dt = datetime.fromisoformat(incident_data['incident_start'].replace('Z', '+00:00'))
                        last_dt = datetime.fromisoformat(incident_data['incident_end'].replace('Z', '+00:00'))
                        duration = (last_dt - first_dt).total_seconds() / 3600
                    except:
                        duration = 0

                    html(f"""
                    <div class="custom-card">
                        <div class="card-header">Incident Window</div>
                        <table class="compact-table">
                            <tr>
                                <td class="td-label" style="width: 150px;">First Alert:</td>
                                <td class="td-value">{first}</td>
                            </tr>
                            <tr>
                                <td class="td-label">Last Alert:</td>
                                <td class="td-value">{last}</td>
                            </tr>
                            <tr>
                                <td class="td-label">Duration:</td>
                                <td class="td-value">{duration:.2f} hours</td>
                            </tr>
                        </table>
                    </div>
                    """)

                    html("<br>")

            # RCA Scope warning
            render_info_box(
                "<strong>Evidence Source:</strong> All telemetry is MOCK (simulated). "
                "Analysis uses alert patterns and mock telemetry providers. "
                "This is experimental analysis, not production-grade RCA.",
                "warning"
            )

            html("<br>")

            # Probable Root Cause
            html("<h3>Probable Failure Mechanism</h3>")

            if rca.get('probable_root_cause'):
                root_cause = rca['probable_root_cause']
                component = root_cause.get('component', 'Unknown')
                failure_type = root_cause.get('failure_type', 'Unknown')
                confidence = root_cause.get('confidence', 0)
                description = root_cause.get('description', 'No description available')

                col1, col2 = st.columns([1, 1])

                with col1:
                    html(f"""
                    <div class="custom-card">
                        <table class="compact-table">
                            <tr>
                                <td class="td-label" style="width: 140px;">Component:</td>
                                <td class="td-bold" style="font-size: 1.125rem;">{component}</td>
                            </tr>
                            <tr>
                                <td class="td-label">Failure Type:</td>
                                <td class="td-danger">{failure_type}</td>
                            </tr>
                            <tr>
                                <td class="td-label">Experimental Confidence:</td>
                                <td>
                                    <div class="confidence-bar-wrap">
                                        <div class="confidence-bar-track">
                                            <div class="confidence-bar-fill" style="width: {confidence*100}%;"></div>
                                        </div>
                                        <span class="confidence-bar-value">{confidence:.1%}</span>
                                    </div>
                                    <div class="confidence-bar-note">
                                        Experimental score (NOT calibrated probability)
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </div>
                    """)
                    
                    render_info_box(
                        "<strong>Terminology:</strong> This is a <em>probable failure mechanism</em>, "
                        "NOT a confirmed root cause. Based on MOCK telemetry.",
                        "warning"
                    )

                with col2:
                    html(f"""
                    <div class="custom-card">
                        <div class="card-header">Description</div>
                        <div class="reasoning-text">{description}</div>
                    </div>
                    """)

                # Supporting Evidence
                if 'supporting_evidence_ids' in root_cause and root_cause['supporting_evidence_ids']:
                    evidence_ids = root_cause['supporting_evidence_ids']

                    with st.expander(f"Supporting Evidence ({len(evidence_ids)} items - ALL MOCK)"):
                        evidence_list = "<br>".join(
                            [f"&bull; <code class='evidence-code'>{eid}</code>" for eid in evidence_ids[:10]]
                        )
                        st.markdown(evidence_list, unsafe_allow_html=True)
                        if len(evidence_ids) > 10:
                            st.caption(f"... and {len(evidence_ids) - 10} more (all MOCK telemetry)")
            else:
                html("""
                <div class="warning-box">
                    <strong>No probable failure mechanism identified</strong><br>
                    <span style="font-size: 0.875rem;">Insufficient evidence available for failure mechanism determination</span>
                </div>
                """)

            html("<br>")

            # Alternative Hypotheses
            if rca.get('alternative_hypotheses'):
                html("<h3>Alternative Hypotheses</h3>")

                for i, alt in enumerate(rca['alternative_hypotheses'][:3], 1):
                    with st.expander(f"Alternative {i}: {alt.get('component', 'Unknown')} - {alt.get('failure_type', 'Unknown')}"):
                        alt_conf = alt.get('confidence', 0)
                        reason = alt.get('reason_for_lower_rank', 'N/A')

                        html(f"""
                        <table class="compact-table">
                            <tr>
                                <td class="td-label" style="width: 150px;">Experimental Confidence:</td>
                                <td class="td-bold">{alt_conf:.1%}</td>
                            </tr>
                            <tr>
                                <td class="td-label" style="vertical-align: top;">Lower Rank Reason:</td>
                                <td class="td-value">{reason}</td>
                            </tr>
                        </table>
                        """)

                html("<br>")

            # Evidence Availability
            html("<h3>Evidence Availability</h3>")
            
            # Count evidence by type
            evidence_count = len(rca.get('evidence', []))
            mock_count = sum(1 for e in rca.get('evidence', []) if e.get('is_mock', False))

            col1, col2, col3 = st.columns(3)

            with col1:
                html(f"""
                <div class="custom-card">
                    <div class="evidence-unavailable">⚠ MOCK Telemetry</div>
                    <div class="evidence-detail">{evidence_count} total items</div>
                    <div class="evidence-detail">{mock_count} are MOCK</div>
                </div>
                """)

            with col2:
                html("""
                <div class="custom-card">
                    <div class="evidence-unavailable">✗ Real Logs Unavailable</div>
                    <div class="evidence-detail">Not in dataset</div>
                </div>
                """)

            with col3:
                html("""
                <div class="custom-card">
                    <div class="evidence-unavailable">✗ Real Metrics/Traces Unavailable</div>
                    <div class="evidence-detail">Not in dataset</div>
                </div>
                """)

            html("<br>")

            # Recommended Actions
            if rca.get('recommended_actions'):
                html("<h3>Recommended Actions</h3>")

                priority_colors = {1: "#dc2626", 2: "#f59e0b", 3: "#3b82f6", 4: "#64748b", 5: "#64748b"}

                for i, action in enumerate(rca['recommended_actions'][:5], 1):
                    action_text = action.get('action', 'Unknown')
                    priority = action.get('priority', 3)
                    rationale = action.get('rationale', 'N/A')
                    priority_color = priority_colors.get(priority, "#64748b")

                    html(f"""
                    <div class="action-card">
                        <div class="action-card-header">
                            <div class="action-card-title">Action {i}</div>
                            <div class="priority-pill" style="background: {priority_color};">
                                Priority {priority}
                            </div>
                        </div>
                        <div class="action-card-body">{action_text}</div>
                        <div class="action-card-rationale">
                            <strong>Rationale:</strong> {rationale}
                        </div>
                    </div>
                    """)

                html("<br>")

            # Human Approval Gate
            html("<h3>Approval Gate</h3>")
            render_approval_gate()

else:
    html("<div class='custom-card' style='text-align: center; padding: 3rem;'>"
         "<span class='filter-count'>No RCA analyses match the current filters</span></div>")

render_footer()
