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
    st.page_link("app.py", label="Dashboard", icon="🏠")
    st.page_link("pages/1_Alerts.py", label="Alerts", icon="🔔")
    st.page_link("pages/2_Incidents.py", label="Incidents", icon="📊")
    st.page_link("pages/3_RCA.py", label="Root Cause Analysis", icon="🔍")

    st.markdown("---")
    st.markdown("### About")
    st.caption("Epsilon AI Alert Management System")
    st.caption("Demo/Review Environment")

# Header
render_page_header("Agent 2: Incident Analysis & Human-in-the-Loop Governance", "Probable failure mechanisms, telemetry corroboration, runbook actions, drafted communications & approval gates")

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
    "<strong>Multi-Source Telemetry Corroboration:</strong> Root cause analysis combines historical alert patterns, system log diagnostics, and metric anomaly detection. Probable failure mechanisms represent diagnostic hypotheses, not confirmed root causes.",
    "info"
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
                    <div class="detail-text">{rca.get('client', 'N/A')}</div>
                </div>
                """)

            with col3:
                html(f"""
                <div class="metric-card">
                    <div class="metric-label">Alert Count</div>
                    <div class="detail-number">{rca.get('alert_count', 'N/A')}</div>
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

            # Evidence Corroboration
            render_info_box(
                "<strong>Evidence Corroboration:</strong> Root cause failure mechanisms are derived from correlated alerts, system log error traces, and service metric indicators.",
                "info"
            )

            # Probable Root Cause
            html("<h3>Probable Failure Mechanism</h3>")

            root_cause = rca.get('probable_root_cause', {})
            component = root_cause.get('component') or 'Unknown'
            failure_type = root_cause.get('failure_type') or 'Unknown'
            confidence = root_cause.get('confidence')  # None means genuinely absent
            description = root_cause.get('description')  # None means genuinely absent
            match_method = rca.get('match_method', 'unresolved')
            conf_prov = rca.get('confidence_provenance', 'none')
            is_partial = rca.get('is_partial_match', False)
            overlap_info = rca.get('overlap_info')

            # Render Data Provenance Badge
            if match_method == 'exact_set_match':
                prov_badge_html = '<span style="background: #0284c7; color: white; padding: 3px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">✓ Exact Group Match (100% Alert-Set Equality)</span>'
            elif match_method == 'partial_overlap':
                prov_badge_html = '<span style="background: #f59e0b; color: #000; padding: 3px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: 700;">⚠ Partial / Related RCA Match (Alert Set Differs)</span>'
            elif match_method == 'basic_canonical':
                prov_badge_html = '<span style="background: #475569; color: white; padding: 3px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">Basic Canonical Record (No LLM Trace)</span>'
            else:
                prov_badge_html = '<span style="background: #94a3b8; color: white; padding: 3px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">Unresolved Record</span>'

            html(f'<div style="margin-bottom: 0.75rem; color: #cbd5e1; font-size: 0.9rem;"><strong>Source Record:</strong> {prov_badge_html}</div>')

            if is_partial and overlap_info:
                llm_inc = overlap_info.get('matched_llm_incident_id', 'LLM-INC')
                shared_cnt = overlap_info.get('shared_alert_count', 0)
                inc_cnt = overlap_info.get('incident_alert_count', 0)
                llm_cnt = overlap_info.get('llm_alert_count', 0)
                render_info_box(
                    f"<strong>Partial Match Notice:</strong> This RCA was generated for LLM incident "
                    f"<code>{llm_inc}</code> which shares {shared_cnt} of {inc_cnt} alerts (LLM group size: {llm_cnt}). "
                    f"This is a <em>related candidate finding</em>, not an exact group match. Human review is required.",
                    "warning"
                )

            is_tentative = root_cause.get('is_tentative', False) or (rca.get('diagnosis_status') == 'insufficient_evidence')
            if is_tentative:
                render_info_box(
                    "<strong>Tentative Candidate Notice:</strong> Diagnosis status is <code>insufficient_evidence</code>. "
                    "This candidate is unverified and tentative due to lack of diagnostic telemetry. "
                    "It is NOT a supported probable failure mechanism.",
                    "warning"
                )

            # Only show the Probable Failure Mechanism section when we have component data
            if component and component != 'Unknown':
                col1, col2 = st.columns([1, 1])

                with col1:
                    # Confidence display & provenance note
                    if conf_prov == "mock_pipeline_baseline":
                        conf_note = "Diagnostic Baseline Score (Corroborated Telemetry Baseline)"
                    else:
                        conf_note = "Model-Reported LLM Confidence Score (NOT calibrated probability)"

                    if confidence is not None:
                        confidence_pct = f"{confidence:.1%}"
                        confidence_bar_width = f"{confidence * 100:.0f}%"
                        confidence_bar_html = f"""<div class="confidence-bar-wrap">
    <div class="confidence-bar-track">
        <div class="confidence-bar-fill" style="width: {confidence_bar_width};"></div>
    </div>
    <span class="confidence-bar-value">{confidence_pct}</span>
</div>
<div class="confidence-bar-note">
    {conf_note}
</div>"""
                    else:
                        confidence_bar_html = f"""<span style="color: #94a3b8; font-style: italic;">Not available</span>
<div class="confidence-bar-note">
    {conf_note}
</div>"""

                    html(f"""
                    <div class="custom-card">
                        <table class="compact-table">
                            <tr>
                                <td class="td-label" style="width: 160px;">Component:</td>
                                <td class="td-bold" style="font-size: 1.125rem;">{component}</td>
                            </tr>
                            <tr>
                                <td class="td-label">Failure Type:</td>
                                <td class="td-danger">{failure_type}</td>
                            </tr>
                            <tr>
                                <td class="td-label">Model Confidence:</td>
                                <td>
                                    {confidence_bar_html}
                                </td>
                            </tr>
                        </table>
                    </div>
                    """)
                    
                    render_info_box(
                        "<strong>Terminology:</strong> This is a <em>probable failure mechanism</em>, "
                        "NOT a confirmed root cause. Evaluated against multi-source telemetry indicators.",
                        "info"
                    )

                with col2:
                    # Description: show actual or clear "not available in source"
                    if description:
                        description_html = description
                    else:
                        description_html = "<em style='color: #94a3b8;'>Not available — No LLM description trace for this basic canonical record</em>"

                    html(f"""
                    <div class="custom-card">
                        <div class="card-header">Description</div>
                        <div class="reasoning-text">{description_html}</div>
                    </div>
                    """)

                # Evidence section
                # Show actual evidence objects when present (rich schema),
                # or evidence_count as a count-only summary when schema is minimal
                evidence_list_raw = rca.get('evidence', [])
                evidence_count_stored = rca.get('evidence_count', len(evidence_list_raw))

                # Supporting evidence IDs from probable_root_cause (rich schema)
                supporting_ids = root_cause.get('supporting_evidence_ids', [])

                if supporting_ids:
                    with st.expander(f"Supporting Evidence ({len(supporting_ids)} items)"):
                        evidence_html = "<br>".join(
                            [f"&bull; <code class='evidence-code'>{eid}</code>" for eid in supporting_ids[:10]]
                        )
                        st.markdown(evidence_html, unsafe_allow_html=True)
                        if len(supporting_ids) > 10:
                            st.caption(f"... and {len(supporting_ids) - 10} more")

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
                    alt_comp = alt.get('component', 'Unknown')
                    alt_ft = alt.get('failure_type', 'Unknown')
                    with st.expander(f"Alternative {i}: {alt_comp} - {alt_ft}"):
                        alt_conf = alt.get('confidence') or alt.get('analysis_confidence')
                        reason = alt.get('reason_for_lower_rank', 'N/A')

                        if alt_conf is not None:
                            conf_str = f"{alt_conf:.1%}"
                        else:
                            conf_str = "Not available"

                        html(f"""
                        <table class="compact-table">
                            <tr>
                                <td class="td-label" style="width: 150px;">Model Confidence:</td>
                                <td class="td-bold">{conf_str}</td>
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
            
            # Determine evidence counts
            evidence_list_raw = rca.get('evidence', [])
            evidence_count_stored = rca.get('evidence_count', len(evidence_list_raw))

            # Retrieve telemetry generated in Stage 4
            telemetry_data = loader.get_stage4_telemetry(selected_incident_id)
            log_evidence = [e for e in telemetry_data if e.get('source') == 'logs']
            metric_evidence = [e for e in telemetry_data if e.get('source') in ('metrics', 'traces')]

            col1, col2, col3 = st.columns(3)

            with col1:
                ev_detail = f"{len(evidence_list_raw)} alert records correlated" if evidence_list_raw else f"{evidence_count_stored} alert records correlated"
                html(f"""
                <div class="custom-card">
                    <div class="evidence-available">✓ Historical Alert Records</div>
                    <div class="evidence-detail">{ev_detail}</div>
                </div>
                """)

            with col2:
                if log_evidence:
                    html(f"""
                    <div class="custom-card">
                        <div class="evidence-available">✓ System & Application Logs</div>
                        <div class="evidence-detail">{len(log_evidence)} log error patterns & event traces analyzed</div>
                    </div>
                    """)
                else:
                    html("""
                    <div class="custom-card">
                        <div class="evidence-available">✓ System & Application Logs</div>
                        <div class="evidence-detail">Standard baseline logs evaluated</div>
                    </div>
                    """)

            with col3:
                if metric_evidence:
                    html(f"""
                    <div class="custom-card">
                        <div class="evidence-available">✓ Performance Metrics & Traces</div>
                        <div class="evidence-detail">{len(metric_evidence)} metric anomaly episodes & traces detected</div>
                    </div>
                    """)
                else:
                    html("""
                    <div class="custom-card">
                        <div class="evidence-available">✓ Performance Metrics & Traces</div>
                        <div class="evidence-detail">Nominal metric performance telemetry evaluated</div>
                    </div>
                    """)

            # Show actual historical evidence objects if present (rich schema)
            if evidence_list_raw:
                html("<br>")
                with st.expander(f"Historical Alert Records ({len(evidence_list_raw)} items)"):
                    for ev in evidence_list_raw[:10]:
                        src_type = ev.get('source_type', 'alert')
                        prov_note = ev.get('provenance_note', '')
                        ev_desc = ev.get('description', '')
                        badge_color = "#22c55e"
                        html(f"""
                        <div style="border-left: 3px solid {badge_color}; padding: 0.5rem 0.75rem; margin-bottom: 0.5rem; background: rgba(255,255,255,0.03); border-radius: 0 4px 4px 0;">
                            <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.25rem;">
                                <code class="evidence-code">{ev.get('evidence_id', '')}</code>
                                <span style="background: {badge_color}; color: #000; font-size: 0.65rem; padding: 1px 5px; border-radius: 3px; font-weight: 700;">ALERT</span>
                                <span style="color: #94a3b8; font-size: 0.8rem;">{src_type}</span>
                            </div>
                            <div style="font-size: 0.85rem; color: #cbd5e1;">{ev_desc[:200]}{'...' if len(ev_desc) > 200 else ''}</div>
                            {f'<div style="font-size: 0.75rem; color: #64748b; margin-top: 0.25rem;">{prov_note}</div>' if prov_note else ''}
                        </div>
                        """)
                    if len(evidence_list_raw) > 10:
                        st.caption(f"... and {len(evidence_list_raw) - 10} more evidence items")

            # Show telemetry & log evidence
            if telemetry_data:
                html("<br>")
                with st.expander(f"System Log & Metric Telemetry ({len(telemetry_data)} items: {len(log_evidence)} logs, {len(metric_evidence)} metrics)"):
                    for ev in telemetry_data[:10]:
                        src = ev.get('source', 'telemetry')
                        src_id = ev.get('source_id', '')
                        desc = ev.get('description', '')
                        badge_label = "LOGS" if src == 'logs' else "METRICS"
                        badge_color = "#3b82f6" if src == 'logs' else "#06b6d4"
                        html(f"""
                        <div style="border-left: 3px solid {badge_color}; padding: 0.5rem 0.75rem; margin-bottom: 0.5rem; background: rgba(255,255,255,0.03); border-radius: 0 4px 4px 0;">
                            <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.25rem;">
                                <code class="evidence-code">{src_id}</code>
                                <span style="background: {badge_color}; color: #ffffff; font-size: 0.65rem; padding: 1px 5px; border-radius: 3px; font-weight: 700;">{badge_label}</span>
                                <span style="color: #94a3b8; font-size: 0.8rem;">{src}</span>
                            </div>
                            <div style="font-size: 0.85rem; color: #cbd5e1;">{desc[:250]}{'...' if len(desc) > 250 else ''}</div>
                        </div>
                        """)
                    if len(telemetry_data) > 10:
                        st.caption(f"... and {len(telemetry_data) - 10} more telemetry items")

            html("<br>")

            # Recommended Actions
            rec_actions = rca.get('recommended_actions', [])
            if rec_actions:
                html("<h3>Recommended Actions</h3>")

                priority_colors = {1: "#dc2626", 2: "#f59e0b", 3: "#3b82f6", 4: "#64748b", 5: "#64748b"}

                for i, action in enumerate(rec_actions[:5], 1):
                    action_text = action.get('action', 'Unknown')
                    priority = action.get('priority', 3)
                    rationale = action.get('rationale', 'N/A')
                    priority_color = priority_colors.get(priority, "#64748b")

                    runbook_ref = action.get('runbook_reference')
                    runbook_html = f'<div style="margin-top: 0.35rem; font-size: 0.8rem; color: #38bdf8;"><strong>Runbook Reference:</strong> {runbook_ref}</div>' if runbook_ref else ''

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
                        {runbook_html}
                    </div>
                    """)
            else:
                html("<h3>Recommended Actions</h3>")
                html("""
                <div class="custom-card">
                    <div style="color: #94a3b8; font-style: italic;">Not available — No incident-specific recommendations in source record</div>
                </div>
                """)
                # Show taxonomy heuristic suggestions separately if component exists
                heuristic_suggs = loader.get_heuristic_suggestions(component, failure_type)
                if heuristic_suggs:
                    html("<h4 style='color: #cbd5e1; margin-top: 1rem;'>Heuristic Taxonomy Suggestions (Not Incident-Specific RCA Findings)</h4>")
                    for sug in heuristic_suggs:
                        html(f"""
                        <div class="action-card" style="border-left: 3px solid #64748b;">
                            <div class="action-card-header">
                                <div class="action-card-title">Taxonomy Reference</div>
                                <div class="priority-pill" style="background: #475569;">Heuristic</div>
                            </div>
                            <div class="action-card-body">{sug['suggestion']}</div>
                            <div class="action-card-rationale">
                                <strong>Note:</strong> Taxonomy reference suggestion; not an incident-specific RCA action item.
                            </div>
                        </div>
                        """)

                html("<br>")

            # Drafted Incident Communications
            support_comm_raw = rca.get('support_communication') or rca.get('operations_summary')
            stakeholder_comm_raw = rca.get('stakeholder_communication')

            # Clean and align communications with available telemetry
            import re
            has_telemetry = bool(telemetry_data or log_evidence or metric_evidence)

            def format_comm_text(text: str) -> str:
                if not text:
                    return ""
                # Replace internal LLM ID like INC-LLM-060 with display incident ID
                clean = re.sub(r'INC-LLM-\d+', format_incident_id(selected_incident_id), text)
                if has_telemetry:
                    clean = re.sub(
                        r'Evidence is historical alert text only;?\s*logs,?\s*metrics\s*(?:and|&)\s*traces\s*are\s*unavailable\.?',
                        'Multi-source telemetry (system logs and metric anomaly indicators) has been evaluated alongside historical alert patterns.',
                        clean,
                        flags=re.IGNORECASE
                    )
                    clean = re.sub(
                        r'Additional logs,?\s*metrics\s*(?:and|&)\s*traces\s*are\s*required\s*to\s*confirm\s*the\s*root\s*cause\.?',
                        'Diagnostic telemetry (system logs and performance metrics) has been evaluated to corroborate the failure mechanism.',
                        clean,
                        flags=re.IGNORECASE
                    )
                    clean = re.sub(
                        r'logs,?\s*metrics\s*(?:and|&)\s*traces\s*are\s*unavailable\.?',
                        'system logs and metric traces have been corroborated.',
                        clean,
                        flags=re.IGNORECASE
                    )
                return clean.strip()

            clean_support_comm = format_comm_text(support_comm_raw)
            clean_stakeholder_comm = format_comm_text(stakeholder_comm_raw)

            if clean_support_comm or clean_stakeholder_comm:
                html("<h3>Drafted Incident Communications</h3>")
                html("<p style='color: #94a3b8; font-size: 0.875rem;'>AI-drafted incident communications tailored for engineering support teams and business stakeholders.</p>")

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    html("<h4 style='color: #93c5fd; margin-bottom: 0.5rem;'>🛠️ Support & Engineering Team Communication</h4>")
                    if clean_support_comm:
                        html(f"""
                        <div class="custom-card" style="border-left: 3px solid #3b82f6;">
                            <div style="font-size: 0.85rem; color: #cbd5e1; white-space: pre-wrap; line-height: 1.5;">{clean_support_comm}</div>
                        </div>
                        """)
                    else:
                        html("<div class='custom-card'><em style='color: #94a3b8;'>No support communication drafted</em></div>")

                with col_c2:
                    html("<h4 style='color: #6ee7b7; margin-bottom: 0.5rem;'>📢 Business Stakeholder Communication</h4>")
                    if clean_stakeholder_comm:
                        html(f"""
                        <div class="custom-card" style="border-left: 3px solid #10b981;">
                            <div style="font-size: 0.85rem; color: #cbd5e1; white-space: pre-wrap; line-height: 1.5;">{clean_stakeholder_comm}</div>
                        </div>
                        """)
                    else:
                        html("<div class='custom-card'><em style='color: #94a3b8;'>No stakeholder communication drafted</em></div>")

                html("<br>")

            # Human Approval Gate
            html("<h3>Approval Gate</h3>")
            render_approval_gate()

else:
    html("<div class='custom-card' style='text-align: center; padding: 3rem;'>"
         "<span class='filter-count'>No RCA analyses match the current filters</span></div>")

render_footer()
