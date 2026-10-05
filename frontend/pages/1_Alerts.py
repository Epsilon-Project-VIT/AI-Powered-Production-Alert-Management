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
    st.page_link("app.py", label="🏠 Dashboard", icon="🏠")
    st.page_link("pages/1_Alerts.py", label="🔔 Alerts", icon="🔔")
    st.page_link("pages/2_Incidents.py", label="📊 Incidents", icon="📊")
    st.page_link("pages/3_RCA.py", label="🔍 Root Cause Analysis", icon="🔍")

    st.markdown("---")
    st.markdown("### About")
    st.caption("Epsilon AI Alert Management System")
    st.caption("Demo/Review Environment")

# Header
render_page_header("Alerts", "Search, filter and review alert classifications")

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

            html("<br>")

            # Two-column layout
            col1, col2 = st.columns([1.2, 1])

            with col1:
                html("<h3>Alert Information</h3>")

                html(f"""
                <div class="custom-card">
                    <div class="section-label">Description</div>
                    <div class="desc-text">{alert['description']}</div>
                </div>
                """)

                html(f"""
                <table class="compact-table" style="margin-top: 1rem;">
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
                """)

            with col2:
                html("<h3>Stage 2: ML Classifications</h3>")

                alert_type_conf = alert.get('alert_type_confidence', 0)
                severity_conf = alert.get('severity_confidence', 0)
                business_impact_conf = alert.get('business_impact_confidence', 0)
                
                alert_type_text = str(alert.get('predicted_alert_type', 'Unknown'))
                if len(alert_type_text) > 50:
                    alert_type_text = alert_type_text[:50] + "..."
                
                business_impact_text = str(alert.get('predicted_business_impact', 'Unknown'))
                assignment_group_text = str(alert.get('assignment_group', 'Unknown'))
                if len(assignment_group_text) > 50:
                    assignment_group_text = assignment_group_text[:50] + "..."

                html(f"""
                <div class="custom-card">
                    <table class="compact-table">
                        <tr>
                            <td class="td-label">Alert Type:</td>
                            <td class="td-value">{alert_type_text}</td>
                        </tr>
                        <tr>
                            <td class="td-label">Confidence:</td>
                            <td class="td-bold">{alert_type_conf:.1%}</td>
                        </tr>
                        <tr>
                            <td class="td-label" style="padding-top: 0.5rem;">Severity:</td>
                            <td style="padding-top: 0.5rem;">{get_priority_badge(alert['predicted_severity'])}</td>
                        </tr>
                        <tr>
                            <td class="td-label">Confidence:</td>
                            <td class="td-bold">{severity_conf:.1%}</td>
                        </tr>
                        <tr>
                            <td class="td-label" style="padding-top: 0.5rem;">Business Impact:</td>
                            <td class="td-value" style="padding-top: 0.5rem;">{business_impact_text}</td>
                        </tr>
                        <tr>
                            <td class="td-label">Confidence:</td>
                            <td class="td-bold">{business_impact_conf:.1%}</td>
                        </tr>
                        <tr>
                            <td class="td-label" style="padding-top: 0.5rem;">Priority:</td>
                            <td class="td-value" style="padding-top: 0.5rem;">{alert.get('priority', 'Unknown')}</td>
                        </tr>
                        <tr>
                            <td class="td-label">Assignment Group:</td>
                            <td class="td-value" style="font-size: 0.825rem;">{assignment_group_text}</td>
                        </tr>
                    </table>
                </div>
                """)

                render_info_box(
                    "<strong>Stage 2 ML Models:</strong><br>"
                    "• Alert Type: TF-IDF + Logistic Regression<br>"
                    "• Severity: Embedding + SVM<br>"
                    "• Business Impact: Embedding + SVM<br>"
                    "• Priority: Raw data (historical ground truth)<br>"
                    "• Assignment Group: Raw data (historical ground truth)",
                    "info"
                )

            # AI Reasoning - removed since Stage 2 is ML not LLM
            # Stage 2 uses trained Random Forest models, no reasoning text

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
