"""
Alerts Page - Enterprise alert management interface
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
    format_timestamp, get_priority_badge, render_info_box, html, format_incident_id
)

st.set_page_config(
    page_title="Alerts",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(get_custom_css(), unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    st.markdown("## Navigation")
    st.page_link("app.py", label="Dashboard", icon="🏠")
    st.page_link("pages/1_Alerts.py", label="Alerts", icon="🔔")
    st.page_link("pages/2_Incidents.py", label="Incidents", icon="📊")
    st.page_link("pages/3_RCA.py", label="Root Cause Analysis", icon="🔍")

    st.markdown("---")
    st.markdown("### About")
    st.caption("Epsilon AI Alert Management System")
    st.caption("Demo/Review Environment")

# Header
render_page_header("Agent 1: Alert Classification & Prioritization", "Automated ingestion from observability platforms, ML classification, severity scoring, and priority routing")

# Load data
loader = get_loader()
df = loader.load_stage2()

# Filters in sidebar
st.sidebar.markdown("### Filters")

search_id = st.sidebar.text_input("Search Alert ID", placeholder="INC3528890")
selected_client = st.sidebar.selectbox("Client", ["All"] + sorted(df['client'].dropna().unique().tolist()))
selected_alert_type = st.sidebar.selectbox("Alert Type", ["All"] + sorted(df['predicted_alert_type'].dropna().unique().tolist()[:20]))
selected_severity = st.sidebar.selectbox("Severity", ["All"] + sorted(df['predicted_severity'].dropna().unique().tolist()))

# Apply filters
filtered_df = df.copy()

if search_id:
    filtered_df = filtered_df[filtered_df['alert_id'].str.contains(search_id, case=False, na=False)]

if selected_client != "All":
    filtered_df = filtered_df[filtered_df['client'] == selected_client]

if selected_alert_type != "All":
    filtered_df = filtered_df[filtered_df['predicted_alert_type'] == selected_alert_type]

if selected_severity != "All":
    filtered_df = filtered_df[filtered_df['predicted_severity'] == selected_severity]

# Display count
html(f"<p class='filter-count'>Showing {len(filtered_df):,} of {len(df):,} alerts</p>")

if len(filtered_df) > 0:
    # Display using Streamlit dataframe with custom formatting
    display_df = filtered_df.head(50)[['alert_id', 'client', 'created_at', 'predicted_alert_type', 'predicted_severity', 'predicted_business_impact']].copy()
    display_df.columns = ['Alert ID', 'Client', 'Created', 'Alert Type', 'Severity', 'Business Impact']

    # Format timestamp
    display_df['Created'] = display_df['Created'].apply(lambda x: format_timestamp(x))

    # Truncate long fields
    display_df['Alert Type'] = display_df['Alert Type'].apply(lambda x: str(x)[:40] + "..." if len(str(x)) > 40 else str(x))

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "Alert ID": st.column_config.TextColumn("Alert ID", width="medium"),
            "Severity": st.column_config.TextColumn("Severity", width="medium"),
        }
    )

    if len(filtered_df) > 50:
        st.caption(f"Showing first 50 of {len(filtered_df)} alerts. Use filters to refine results.")

    html("<br>")

    # Alert detail view
    html("<h2>Alert Detail</h2>")

    selected_alert_id = st.selectbox(
        "Select Alert",
        options=filtered_df['alert_id'].tolist(),
        index=0,
        key='alert_select',
        label_visibility="collapsed"
    )

    if selected_alert_id:
        alert = loader.get_alert(selected_alert_id)

        if alert:
            # Top metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Alert ID</div>
                    <div class="detail-id">{alert['alert_id']}</div>
                </div>
                """)

            with col2:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Client</div>
                    <div class="detail-text">{alert['client']}</div>
                </div>
                """)

            with col3:
                severity_badge = get_priority_badge(alert['predicted_severity'])
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Severity (Predicted)</div>
                    <div style="margin-top: 0.5rem;">{severity_badge}</div>
                </div>
                """)

            with col4:
                created = format_timestamp(alert.get('created_at', ''))
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Timestamp</div>
                    <div class="detail-small">{created}</div>
                </div>
                """)

            # Two-column layout
            col1, col2 = st.columns([1, 1])

            with col1:
                html("<h3>Alert Information</h3>")

                html(f"""
                <div class="custom-card" style="min-height: 290px;">
                    <div class="section-label">Description</div>
                    <div class="desc-text scroll-box-y" style="max-height: 85px; overflow-y: auto; margin-bottom: 1rem; line-height: 1.5; padding-right: 4px;">{alert['description']}</div>
                    <table class="compact-table" style="table-layout: fixed; width: 100%; margin-top: 0.5rem;">
                        <colgroup>
                            <col style="width: 120px;">
                            <col style="width: calc(100% - 120px);">
                        </colgroup>
                        <tr>
                            <td class="td-label">Created At:</td>
                            <td class="td-value">{created}</td>
                        </tr>
                        <tr>
                            <td class="td-label">Client:</td>
                            <td class="td-value">{alert['client']}</td>
                        </tr>
                        <tr>
                            <td class="td-label">Alert ID:</td>
                            <td class="td-accent">{alert['alert_id']}</td>
                        </tr>
                    </table>
                </div>
                """)

            with col2:
                html("<h3>Stage 2: ML Classifications</h3>")

                alert_type_conf = alert.get('alert_type_confidence', 0)
                severity_conf = alert.get('severity_confidence', 0)
                business_impact_conf = alert.get('business_impact_confidence', 0)
                priority_conf = alert.get('priority_confidence', 0)
                assignment_group_conf = alert.get('assignment_group_confidence', 0)
                
                alert_type_text = str(alert.get('predicted_alert_type', 'Unknown'))
                business_impact_text = str(alert.get('predicted_business_impact', 'Unknown'))
                priority_text = str(alert.get('predicted_priority', 'Unknown'))
                assignment_group_text = str(alert.get('predicted_assignment_group', 'Unknown'))
                
                # Historical labels for comparison
                historical_priority = str(alert.get('priority_true_label', 'N/A'))
                historical_assignment_group = str(alert.get('assignment_group_true_label', 'N/A'))

                html(f"""
                <div class="custom-card" style="min-height: 290px;">
                    <table class="compact-table" style="table-layout: fixed; width: 100%;">
                        <colgroup>
                            <col style="width: 140px;">
                            <col style="width: calc(100% - 140px);">
                        </colgroup>
                        <tr>
                            <td class="td-label">Alert Type:</td>
                            <td>
                                <div class="scroll-cell" title="{alert_type_text} ({alert_type_conf:.1%})">
                                    <span class="td-value">{alert_type_text}</span>
                                    <span style="color: #38bdf8; font-weight: 600; font-size: 0.8rem; margin-left: 0.5rem;">({alert_type_conf:.1%})</span>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td class="td-label">Severity:</td>
                            <td>
                                <div>
                                    {get_priority_badge(alert['predicted_severity'])}
                                    <span style="color: #38bdf8; font-weight: 600; font-size: 0.8rem; margin-left: 0.5rem;">({severity_conf:.1%})</span>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td class="td-label">Business Impact:</td>
                            <td>
                                <div class="scroll-cell" title="{business_impact_text} ({business_impact_conf:.1%})">
                                    <span class="td-value">{business_impact_text}</span>
                                    <span style="color: #38bdf8; font-weight: 600; font-size: 0.8rem; margin-left: 0.5rem;">({business_impact_conf:.1%})</span>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td class="td-label">Priority:</td>
                            <td>
                                <div class="scroll-cell" title="{priority_text} ({priority_conf:.1%})">
                                    <span class="td-value">{priority_text}</span>
                                    <span style="color: #38bdf8; font-weight: 600; font-size: 0.8rem; margin-left: 0.5rem;">({priority_conf:.1%})</span>
                                </div>
                                <div class="scroll-cell" style="font-size: 0.75rem; color: #94a3b8; margin-top: 0.2rem;" title="Historical: {historical_priority}">
                                    Historical: <span style="color: #cbd5e1;">{historical_priority}</span>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td class="td-label">Assignment Group:</td>
                            <td>
                                <div class="scroll-cell" title="{assignment_group_text} ({assignment_group_conf:.1%})">
                                    <span class="td-value" style="font-size: 0.85rem;">{assignment_group_text}</span>
                                    <span style="color: #38bdf8; font-weight: 600; font-size: 0.8rem; margin-left: 0.35rem;">({assignment_group_conf:.1%})</span>
                                </div>
                                <div class="scroll-cell" style="font-size: 0.75rem; color: #94a3b8; margin-top: 0.2rem;" title="Historical: {historical_assignment_group}">
                                    Historical: <span style="color: #cbd5e1;">{historical_assignment_group}</span>
                                </div>
                            </td>
                        </tr>
                    </table>
                </div>
                """)

            # Correlation
            html("<br><h3>Stage 3: Incident Correlation</h3>")
            incident_id = loader.get_incident_for_alert(alert['alert_id'])

            if incident_id:
                incident = loader.get_incident(incident_id)
                if incident:
                    html(f"""
                    <div class="success-box">
                        <strong>Correlated to Candidate Incident Group:</strong> {format_incident_id(incident_id)}<br>
                        <span style="font-size: 0.875rem;">
                            This alert is part of a candidate incident group with {incident['alert_count']} correlated alerts
                            (Method: {incident.get('correlation_method', 'N/A')})
                        </span>
                    </div>
                    """)

                    if st.button("Open Candidate Incident Group", use_container_width=True):
                        st.session_state['selected_incident_id'] = incident_id
                        st.switch_page("pages/2_Incidents.py")
            else:
                html("""
                <div class="custom-card">
                    <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 0.25rem;">
                        Uncorrelated Alert
                    </div>
                    <div style="color: var(--text-secondary); font-size: 0.875rem;">
                        This alert is standalone and has not been correlated into a candidate incident group.
                    </div>
                </div>
                """)

else:
    html("<div class='custom-card' style='text-align: center; padding: 3rem;'>"
         "<span class='filter-count'>No alerts match the current filters</span></div>")

render_footer()
