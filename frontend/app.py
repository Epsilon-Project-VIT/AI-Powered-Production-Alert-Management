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
    st.page_link("app.py", label="Dashboard", icon="🏠")
    st.page_link("pages/1_Alerts.py", label="Alerts", icon="🔔")
    st.page_link("pages/2_Incidents.py", label="Incidents", icon="📊")
    st.page_link("pages/3_RCA.py", label="Root Cause Analysis", icon="🔍")

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

    # Section: Multi-Agent AI Framework Workflow
    html("<h2>Multi-Agent AI Framework</h2>")
    html("<p class='section-subtitle'>Automated production alert analysis and incident response workflow</p>")

    ma_col1, ma_col2, ma_col3 = st.columns(3)

    with ma_col1:
        html("""
        <div class="custom-card" style="border-top: 3px solid #3b82f6; height: 100%;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">🤖</span>
                <div style="font-weight: 700; font-size: 1.05rem; color: #93c5fd;">Agent 1: Classification & Prioritization</div>
            </div>
            <ul style="color: #cbd5e1; font-size: 0.85rem; padding-left: 1.2rem; line-height: 1.6; margin-bottom: 0;">
                <li><strong>Observability Ingestion:</strong> Monitors alerts from APM, cloud & synthetic probes.</li>
                <li><strong>Taxonomy Classification:</strong> Identifies alert type across API, DB, App, Infra, Network.</li>
                <li><strong>Impact & Priority:</strong> Determines severity, business impact, and P1–P4 priority routing.</li>
                <li><strong>Noise Reduction:</strong> Correlates duplicate & cascading alerts (<strong>83.0% noise reduction</strong>).</li>
            </ul>
        </div>
        """)

    with ma_col2:
        html("""
        <div class="custom-card" style="border-top: 3px solid #10b981; height: 100%;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">🤖</span>
                <div style="font-weight: 700; font-size: 1.05rem; color: #6ee7b7;">Agent 2: Incident Analysis & Recommendation</div>
            </div>
            <ul style="color: #cbd5e1; font-size: 0.85rem; padding-left: 1.2rem; line-height: 1.6; margin-bottom: 0;">
                <li><strong>Telemetry Corroboration:</strong> Reviews logs, metrics, traces & historical patterns.</li>
                <li><strong>Root Cause Analysis:</strong> Identifies probable failure mechanisms with confidence.</li>
                <li><strong>Runbook Recommendations:</strong> Generates prioritized diagnostic & remediation actions.</li>
                <li><strong>Incident Communications:</strong> Drafts dual-audience updates for SREs & stakeholders.</li>
            </ul>
        </div>
        """)

    with ma_col3:
        html("""
        <div class="custom-card" style="border-top: 3px solid #f59e0b; height: 100%;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">👨‍💻</span>
                <div style="font-weight: 700; font-size: 1.05rem; color: #fcd34d;">Human Agent: SRE Governance</div>
            </div>
            <ul style="color: #cbd5e1; font-size: 0.85rem; padding-left: 1.2rem; line-height: 1.6; margin-bottom: 0;">
                <li><strong>Policy Approval Gate:</strong> Human review required for all impactful remediation actions.</li>
                <li><strong>Complex Incident Execution:</strong> SRE executes approved scripts & runbooks safely.</li>
                <li><strong>Reliability Focus:</strong> Engineers focus on P1 critical incidents & preventative fixes.</li>
                <li><strong>Continuous Feedback:</strong> Human validation feeds back into model accuracy improvements.</li>
            </ul>
        </div>
        """)

    html("<br>")

    # Section: Business Impact
    html("<h2>Business Impact & Outcomes</h2>")
    bi_col1, bi_col2, bi_col3, bi_col4 = st.columns(4)

    with bi_col1:
        html("""
        <div class="metric-card" style="border-left: 3px solid #3b82f6;">
            <div class="metric-label">Operational Efficiency</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #93c5fd; margin: 0.35rem 0;">83.0%</div>
            <div style="font-size: 0.8rem; color: #94a3b8;">Alert noise reduction (889 → 151 incident groups)</div>
        </div>
        """)

    with bi_col2:
        html("""
        <div class="metric-card" style="border-left: 3px solid #10b981;">
            <div class="metric-label">Service Reliability</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #6ee7b7; margin: 0.35rem 0;">Faster MTTR</div>
            <div style="font-size: 0.8rem; color: #94a3b8;">Automated root-cause hypotheses & log/metric traces</div>
        </div>
        """)

    with bi_col3:
        html("""
        <div class="metric-card" style="border-left: 3px solid #f59e0b;">
            <div class="metric-label">Cost Optimization</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #fcd34d; margin: 0.35rem 0;">Zero Triage Toil</div>
            <div style="font-size: 0.8rem; color: #94a3b8;">Automated classification, priority routing & deduplication</div>
        </div>
        """)

    with bi_col4:
        html("""
        <div class="metric-card" style="border-left: 3px solid #ec4899;">
            <div class="metric-label">Customer Experience</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #f472b6; margin: 0.35rem 0;">SLA Protection</div>
            <div style="font-size: 0.8rem; color: #94a3b8;">Drafted communications & proactive stakeholder updates</div>
        </div>
        """)

    html("<br>")

    # Recent Alerts
    html("<h2>Recent Alerts</h2>")

    # Get recent alerts (first 10)
    recent_alerts = stage2_df.head(10)

    # Display recent alerts using Streamlit dataframe
    display_df = recent_alerts[['alert_id', 'client', 'created_at', 'predicted_priority', 'predicted_assignment_group']].copy()
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
