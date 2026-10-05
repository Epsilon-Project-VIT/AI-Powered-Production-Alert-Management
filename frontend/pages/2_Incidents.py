"""
Incidents Page - Enterprise incident correlation interface
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
    format_timestamp, render_info_box, render_timeline_item,
    get_priority_badge, html, format_incident_id
)

st.set_page_config(
    page_title="Incidents",
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
render_page_header("Candidate Incident Groups", "Browse and analyze correlated alert groups")

# Load data
loader = get_loader()
incidents_list = loader.load_stage3_incidents()
stage3_summary = loader.load_stage3_summary()

# Convert to DataFrame for filtering
incidents_df = pd.DataFrame([
    {
        'incident_id': inc['incident_id'],
        'client': inc['client'],
        'alert_count': inc['alert_count'],
        'first_seen': inc['incident_start'],
        'last_seen': inc['incident_end'],
        'correlation_method': inc['correlation_method'],
        'correlation_score': inc.get('avg_correlation_score', 0),
    }
    for inc in incidents_list
])

# Summary stats
html(f"""
<div class="summary-banner">
    <div class="summary-banner-title">
        {len(incidents_df)} candidate incident groups identified from {stage3_summary['statistics']['total_alerts']} alerts
    </div>
    <div class="summary-banner-detail">
        Grouping rate: {stage3_summary['statistics']['grouping_rate']:.1f}% &bull;
        Candidate correlation (experimental grouping, not ground-truth incidents)
    </div>
</div>
""")

# Filters
st.sidebar.markdown("### Filters")
selected_client = st.sidebar.selectbox("Client", ["All"] + sorted(incidents_df['client'].dropna().unique().tolist()))
min_alerts = st.sidebar.slider("Minimum Alerts", 2, int(incidents_df['alert_count'].max()), 2)
selected_method = st.sidebar.selectbox("Correlation Method", ["All"] + sorted(incidents_df['correlation_method'].dropna().unique().tolist()))

# Apply filters
filtered_df = incidents_df.copy()

if selected_client != "All":
    filtered_df = filtered_df[filtered_df['client'] == selected_client]

filtered_df = filtered_df[filtered_df['alert_count'] >= min_alerts]

if selected_method != "All":
    filtered_df = filtered_df[filtered_df['correlation_method'] == selected_method]

html(f"<p class='filter-count'>Showing {len(filtered_df):,} of {len(incidents_df):,} incidents</p>")

if len(filtered_df) > 0:
    # Display using Streamlit dataframe
    display_df = filtered_df.head(50)[['incident_id', 'client', 'alert_count', 'first_seen', 'correlation_method']].copy()
    display_df.columns = ['Incident ID', 'Client', 'Alerts', 'First Seen', 'Method']

    display_df['Incident ID'] = display_df['Incident ID'].apply(format_incident_id)
    display_df['First Seen'] = display_df['First Seen'].apply(lambda x: format_timestamp(x))
    display_df['Method'] = display_df['Method'].apply(lambda x: str(x)[:40] + "..." if len(str(x)) > 40 else str(x))

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)

    if len(filtered_df) > 50:
        st.caption(f"Showing first 50 of {len(filtered_df)} incidents. Use filters to refine results.")

    html("<br>")

    # Incident detail
    html("<h2>Candidate Incident Group Detail</h2>")

    # Check if incident is pre-selected (use positional index)
    incident_list = filtered_df['incident_id'].tolist()
    default_pos = 0
    if 'selected_incident_id' in st.session_state:
        target = st.session_state['selected_incident_id']
        if target in incident_list:
            default_pos = incident_list.index(target)
        del st.session_state['selected_incident_id']

    selected_incident_id = st.selectbox(
        "Select Incident",
        options=incident_list,
        format_func=format_incident_id,
        index=default_pos,
        key='incident_select',
        label_visibility="collapsed"
    )

    if selected_incident_id:
        incident = loader.get_incident(selected_incident_id)

        if incident:
            # Top metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Incident ID</div>
                    <div class="detail-id">{format_incident_id(incident['incident_id'])}</div>
                </div>
                """)

            with col2:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Client</div>
                    <div class="detail-text">{incident['client']}</div>
                </div>
                """)

            with col3:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Alert Count</div>
                    <div class="detail-number">{incident['alert_count']}</div>
                </div>
                """)

            with col4:
                # Calculate duration from first/last seen
                from datetime import datetime
                try:
                    first = datetime.fromisoformat(incident['incident_start'].replace('Z', '+00:00'))
                    last = datetime.fromisoformat(incident['incident_end'].replace('Z', '+00:00'))
                    duration = (last - first).total_seconds() / 3600
                except:
                    duration = 0
                    
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Duration</div>
                    <div class="detail-secondary">{duration:.2f}h</div>
                </div>
                """)

            html("<br>")

            # Incident Timeline
            html("<h3>Incident Timeline</h3>")

            first_seen = format_timestamp(incident.get('incident_start', ''))
            last_seen = format_timestamp(incident.get('incident_end', ''))

            # Calculate duration
            from datetime import datetime
            try:
                first = datetime.fromisoformat(incident['incident_start'].replace('Z', '+00:00'))
                last = datetime.fromisoformat(incident['incident_end'].replace('Z', '+00:00'))
                duration = (last - first).total_seconds() / 3600
            except:
                duration = 0

            html(f"""
            <div class="custom-card">
                <table class="compact-table">
                    <tr>
                        <td class="td-label" style="width: 150px;">First Alert:</td>
                        <td class="td-value">{first_seen}</td>
                    </tr>
                    <tr>
                        <td class="td-label">Last Alert:</td>
                        <td class="td-value">{last_seen}</td>
                    </tr>
                    <tr>
                        <td class="td-label">Duration:</td>
                        <td class="td-value">{duration:.2f} hours</td>
                    </tr>
                </table>
            </div>
            """)

            html("<br>")

            # Correlation Analysis
            html("<h3>Correlation Analysis</h3>")

            col1, col2 = st.columns(2)

            with col1:
                method = incident.get('correlation_method', 'Unknown')
                corr_score = incident.get('avg_correlation_score', 0)

                html(f"""
                <div class="custom-card">
                    <div class="card-header">Correlation Signals</div>
                    <table class="compact-table">
                        <tr>
                            <td class="td-label">Method:</td>
                            <td class="td-value">{method}</td>
                        </tr>
                        <tr>
                            <td class="td-label">Correlation Score:</td>
                            <td class="td-value">{corr_score:.3f}</td>
                        </tr>
                    </table>
                </div>
                """)
                
                render_info_box(
                    "<strong>Experimental Grouping</strong><br>Stage 3 correlates alerts using semantic similarity, temporal proximity, and Stage 2 predictions. These are candidate groups, not ground-truth incidents.",
                    "warning"
                )

            with col2:
                html(f"""
                <div class="custom-card">
                    <div class="card-header">Group Information</div>
                    <table class="compact-table">
                        <tr>
                            <td class="td-label">Total Alerts:</td>
                            <td class="td-bold" style="font-size: 1.5rem;">{incident['alert_count']}</td>
                        </tr>
                        <tr>
                            <td class="td-label">Client:</td>
                            <td class="td-value">{incident['client']}</td>
                        </tr>
                    </table>
                </div>
                """)

            html("<br>")

            # Related Alerts
            html("<h3>Related Alerts</h3>")

            alert_ids = incident.get('alert_ids', [])

            alert_rows = "".join(
                f'<tr><td class="td-index">{i}</td><td class="td-mono">{aid}</td></tr>'
                for i, aid in enumerate(alert_ids[:10], 1)
            )

            html(f"""
            <div class="custom-card">
                <div class="alert-group-count">{len(alert_ids)} alerts in this incident group</div>
                <table class="data-table">
                    <tbody>{alert_rows}</tbody>
                </table>
            </div>
            """)

            if len(alert_ids) > 10:
                st.caption(f"Showing first 10 of {len(alert_ids)} alerts")

            html("<br>")

            # RCA navigation
            rca = loader.get_rca(selected_incident_id)

            if rca:
                html("""
                <div class="success-box">
                    <strong>Stage 4 RCA Available</strong><br>
                    <span style="font-size: 0.875rem;">Root Cause Analysis has been performed for this candidate incident group</span>
                </div>
                """)

                if st.button("Open Stage 4 RCA Analysis", use_container_width=True):
                    st.session_state['selected_rca_id'] = selected_incident_id
                    st.switch_page("pages/3_RCA.py")
            else:
                st.warning("No Stage 4 RCA analysis found for this candidate incident group")

else:
    html("<div class='custom-card' style='text-align: center; padding: 3rem;'>"
         "<span class='filter-count'>No incidents match the current filters</span></div>")

render_footer()
