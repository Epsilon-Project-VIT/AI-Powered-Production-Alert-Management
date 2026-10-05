"""
Reusable UI components for enterprise dashboard.
All HTML uses CSS classes defined in styles.py – no hardcoded colours.
"""

import streamlit as st
from datetime import datetime
from textwrap import dedent


def html(markup: str):
    """Render HTML via st.markdown, stripping leading whitespace so that
    indented f-strings are not treated as Markdown code blocks."""
    st.markdown(dedent(markup), unsafe_allow_html=True)


def render_metric_card(label, value, delta=None):
    """Render a metric card."""
    delta_html = ""
    if delta:
        delta_html = f'<div class="metric-delta">{delta}</div>'

    html(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value:,}</div>
        {delta_html}
    </div>
    """)


def render_badge(text, badge_type="default"):
    """Render a status badge (returns HTML string)."""
    badge_class = f"badge badge-{badge_type.lower()}"
    return f'<span class="{badge_class}">{text}</span>'


def get_priority_badge(priority):
    """Get styled priority badge."""
    priority_str = str(priority).lower()
    if '1' in priority_str or 'critical' in priority_str:
        return render_badge('CRITICAL', 'critical')
    elif '2' in priority_str or 'high' in priority_str:
        return render_badge('HIGH', 'high')
    elif '3' in priority_str or 'medium' in priority_str:
        return render_badge('MEDIUM', 'medium')
    elif '4' in priority_str or 'low' in priority_str:
        return render_badge('LOW', 'low')
    else:
        return render_badge(priority, 'default')


def get_status_badge(status):
    """Get styled status badge."""
    status_str = str(status).lower()
    if 'ambiguous' in status_str:
        return render_badge('AMBIGUOUS', 'ambiguous')
    elif 'insufficient' in status_str:
        return render_badge('INSUFFICIENT', 'insufficient')
    elif 'open' in status_str:
        return render_badge('OPEN', 'open')
    else:
        return render_badge(status, 'default')


def render_custom_card(title, content, card_type="default"):
    """Render a custom card."""
    html(f"""
    <div class="custom-card">
        <div class="card-header">{title}</div>
        <div class="card-body">{content}</div>
    </div>
    """)


def render_info_box(message, box_type="info"):
    """Render an info/warning/success box."""
    html(f"""
    <div class="{box_type}-box">
        {message}
    </div>
    """)


def render_evidence_card(source, timestamp, description, provenance):
    """Render an evidence card."""
    provenance_badge = render_badge(provenance, 'open')
    time_str = timestamp if isinstance(timestamp, str) else timestamp.strftime("%Y-%m-%d %H:%M")

    html(f"""
    <div class="evidence-card">
        <div class="evidence-header">
            <span class="evidence-source">{source}</span>
            {provenance_badge}
        </div>
        <div class="evidence-timestamp">{time_str}</div>
        <div class="evidence-desc">{description}</div>
    </div>
    """)


def render_timeline_item(time, content):
    """Render a timeline item (returns HTML string)."""
    time_str = time if isinstance(time, str) else time.strftime("%H:%M:%S")
    return f"""
    <div class="timeline-item">
        <div class="timeline-time">{time_str}</div>
        <div class="timeline-content">{content}</div>
    </div>
    """


def render_approval_gate():
    """Render the human approval gate."""
    html("""
    <div class="approval-gate">
        <div class="approval-header">HUMAN APPROVAL REQUIRED</div>
        <p class="approval-text">
            All remediation actions require explicit human review and policy approval before execution.
        </p>
        <div class="approval-status">
            <div class="status-item">
                <span class="status-label">Automatic Execution</span>
                <span class="status-value status-disabled">DISABLED</span>
            </div>
            <div class="status-item">
                <span class="status-label">Human Review</span>
                <span class="status-value status-required">REQUIRED</span>
            </div>
            <div class="status-item">
                <span class="status-label">Policy Approval</span>
                <span class="status-value status-required">REQUIRED</span>
            </div>
            <div class="status-item">
                <span class="status-label">Execution Status</span>
                <span class="status-value status-disabled">NOT EXECUTED</span>
            </div>
        </div>
        <p class="approval-footer">
            Demo / Review Interface — No production actions are executed
        </p>
    </div>
    """)


def render_page_header(title, subtitle=None):
    """Render page header."""
    st.markdown(f"<h1>{title}</h1>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(
            f"<p class='page-subtitle'>{subtitle}</p>",
            unsafe_allow_html=True,
        )


def render_section_header(title):
    """Render section header."""
    st.markdown(f"<h2>{title}</h2>", unsafe_allow_html=True)


def render_subsection_header(title):
    """Render subsection header."""
    st.markdown(f"<h3>{title}</h3>", unsafe_allow_html=True)


def format_incident_id(raw_id: str) -> str:
    """Convert raw incident ID to clean display format.

    Examples:
        'INC-LLM-038' → 'Incident-38'
        'INC-LLM-005' → 'Incident-5'
    """
    raw = str(raw_id)
    if raw.upper().startswith("INC-LLM-"):
        num = raw[8:].lstrip("0") or "0"
        return f"Incident-{num}"
    return raw


def format_timestamp(ts):
    """Format timestamp for display."""
    if not ts or str(ts) == 'nan':
        return "Unknown"

    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.strftime("%d %b %Y %H:%M")
        except Exception:
            return ts[:19] if len(ts) > 19 else ts
    else:
        try:
            return ts.strftime("%d %b %Y %H:%M")
        except Exception:
            return str(ts)


def render_footer():
    """Render footer (normal-flow, not fixed)."""
    html("""
    <div class="custom-footer">
        <strong>LLM-assisted review</strong> &bull; Demo / Review Environment &bull;
        Data from pre-generated Stage 2-4 outputs
    </div>
    """)
