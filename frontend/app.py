"""
Epsilon AI Production Alert Management
Enterprise-grade incident management dashboard
"""

import streamlit as st
import pandas as pd
from data_loader import get_loader
from styles import get_custom_css
from components import (
    render_metric_card, render_page_header, render_info_box,
    render_footer, format_timestamp, get_priority_badge, html
)

st.set_page_config(
    page_title="Epsilon AI Alert Management",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS
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


def main():
    # Header
    render_page_header(
        "Epsilon AI Production Alert Management",
        "AI-powered alert classification, incident correlation and root-cause analysis"
    )

    # Load data
    loader = get_loader()
    stats = loader.get_summary_stats()
    stage2_df = loader.load_stage2()

    # Section: Production Operations Overview
    html("<h2>Production Operations Overview</h2>")
    html("<p class='section-subtitle'>Monitor alert volume, correlation and AI-assisted incident analysis</p>")

    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_metric_card("Total Alerts", stats['total_alerts'])

    with col2:
        render_metric_card("Candidate Incident Groups", stats['candidate_incident_groups'])

    with col3:
        render_metric_card("Correlated Alerts", stats['grouped_alerts'])

    with col4:
        render_metric_card("Uncorrelated Alerts", stats['uncorrelated_alerts'])

    html("<br>")

    # Recent Alerts
    html("<h2>Recent Alerts</h2>")

    # Get recent alerts (first 10)
    recent_alerts = stage2_df.head(10)

    # Display recent alerts using Streamlit dataframe
    display_df = recent_alerts[['alert_id', 'client', 'created_at', 'priority', 'assignment_group']].copy()
    display_df.columns = ['Alert ID', 'Client', 'Created', 'Priority', 'Assignment Group']

    # Format timestamp
    display_df['Created'] = display_df['Created'].apply(lambda x: format_timestamp(x))

    # Truncate routing
    display_df['Assignment Group'] = display_df['Assignment Group'].apply(lambda x: str(x)[:50] + "..." if len(str(x)) > 50 else str(x))

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400
    )

    # Quick actions
    html("<br><br>")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("View All Alerts", use_container_width=True):
            st.switch_page("pages/1_Alerts.py")

    with col2:
        if st.button("View Incidents", use_container_width=True):
            st.switch_page("pages/2_Incidents.py")

    with col3:
        if st.button("View RCA Analyses", use_container_width=True):
            st.switch_page("pages/3_RCA.py")

    # Footer
    render_footer()


if __name__ == "__main__":
    main()
