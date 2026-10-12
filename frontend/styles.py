"""
Custom CSS styles for enterprise dashboard.
Uses CSS custom properties derived from Streamlit's theme variables
so that all colours adapt automatically to dark and light mode.
"""


def get_custom_css():
    """Return custom CSS for enterprise-grade styling (dark + light mode)."""
    return """
    <style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ===== CSS Custom Properties ===== */
    :root {
        --card-bg: var(--secondary-background-color, #1e2839);
        --card-border: rgba(128, 128, 128, 0.2);
        --card-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
        --divider: rgba(128, 128, 128, 0.15);
        --accent: var(--primary-color, #3b82f6);
        --danger: #ef4444;
        --success: #10b981;
        --warning: #f59e0b;
        --radius-sm: 6px;
        --radius-md: 10px;
        --radius-lg: 14px;
    }

    /* ===== Global ===== */
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    header    { visibility: hidden; }

    .stApp { overflow-x: hidden; }

    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 4rem;
        max-width: 1400px;
    }

    [data-testid="stSidebar"] {
        border-right: 1px solid var(--card-border);
    }

    /* ===== Typography ===== */
    h1 { color: var(--text-color); font-weight: 700; font-size: 2rem;
         letter-spacing: -0.5px; margin-bottom: 0.5rem; }
    h2 { color: var(--text-color); font-weight: 600; font-size: 1.5rem;
         margin-top: 2rem; margin-bottom: 1rem; }
    h3 { color: var(--text-color); font-weight: 600; font-size: 1.125rem;
         margin-bottom: 0.75rem; }
    p  { color: var(--text-color); }

    .page-subtitle   { color: var(--text-color); opacity: 0.6;
                        font-size: 1.125rem; margin-bottom: 2rem; }
    .section-subtitle { color: var(--text-color); opacity: 0.6;
                        margin-bottom: 1.5rem; }
    .filter-count     { color: var(--text-color); opacity: 0.6;
                        margin-bottom: 1rem; }

    /* ===== Metric Cards ===== */
    .metric-card {
        background: var(--card-bg);
        border-radius: var(--radius-lg);
        padding: 1.5rem;
        box-shadow: var(--card-shadow);
        border: 1px solid var(--card-border);
        height: 100%;
        transition: transform 0.2s, box-shadow 0.2s;
        overflow: hidden;
        word-wrap: break-word;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
    }
    .metric-label {
        font-size: 0.8rem; color: var(--text-color); opacity: 0.55;
        font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.5px; margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 2.25rem; font-weight: 700;
        color: var(--text-color); line-height: 1;
    }
    .metric-delta {
        font-size: 0.875rem; color: var(--success);
        font-weight: 600; margin-top: 0.5rem;
    }

    /* Detail values inside metric cards */
    .detail-id {
        font-family: 'Courier New', monospace;
        font-size: 1.25rem; font-weight: 600;
        color: var(--accent); margin-top: 0.5rem;
        word-break: break-all;
    }
    .detail-text {
        font-size: 1.25rem; font-weight: 600;
        color: var(--text-color); margin-top: 0.5rem;
    }
    .detail-number {
        font-size: 2rem; font-weight: 700;
        color: var(--text-color); margin-top: 0.5rem;
    }
    .detail-secondary {
        font-size: 1.5rem; font-weight: 600;
        color: var(--text-color); opacity: 0.8; margin-top: 0.5rem;
    }
    .detail-small {
        font-size: 1rem; font-weight: 500;
        color: var(--text-color); opacity: 0.8; margin-top: 0.5rem;
    }

    /* ===== Badges ===== */
    .badge {
        display: inline-block; padding: 0.25rem 0.75rem;
        border-radius: var(--radius-sm); font-size: 0.75rem;
        font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
    }
    .badge-critical    { background: rgba(239, 68, 68, 0.15);  color: #f87171; }
    .badge-high        { background: rgba(249, 115, 22, 0.15); color: #fb923c; }
    .badge-medium      { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
    .badge-low         { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .badge-ambiguous   { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
    .badge-insufficient{ background: rgba(239, 68, 68, 0.15);  color: #f87171; }
    .badge-open        { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
    .badge-default     { background: rgba(128, 128, 128, 0.15);
                         color: var(--text-color); opacity: 0.7; }

    /* ===== Custom Card ===== */
    .custom-card {
        background: var(--card-bg);
        border-radius: var(--radius-lg);
        padding: 1.5rem;
        box-shadow: var(--card-shadow);
        border: 1px solid var(--card-border);
        margin-bottom: 1rem;
        overflow: hidden;
        word-wrap: break-word;
    }
    .card-header {
        font-weight: 600; font-size: 1rem;
        color: var(--text-color);
        margin-bottom: 1rem; padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--divider);
    }
    .card-body {
        color: var(--text-color); opacity: 0.8; line-height: 1.6;
    }

    /* ===== Compact Table ===== */
    .compact-table {
        width: 100%; font-size: 0.875rem; border-collapse: collapse;
    }
    .compact-table td {
        padding: 0.6rem 0.75rem;
        border-bottom: 1px solid var(--divider);
        color: var(--text-color);
        overflow: hidden;
    }
    .compact-table tr:last-child td { border-bottom: none; }

    .td-label  { color: var(--text-color) !important; opacity: 0.55; font-weight: 600; }
    .td-value  { color: var(--text-color) !important; }
    .td-accent { color: var(--accent) !important; font-family: 'Courier New', monospace; }
    .td-danger { color: var(--danger) !important; font-weight: 600; }
    .td-bold   { color: var(--text-color) !important; font-weight: 600; }
    .td-highlight { color: var(--success) !important; font-weight: 600; }
    .td-muted  { color: var(--text-color) !important; opacity: 0.65; }

    /* ===== Scrollable Content Within Cards & Cells ===== */
    .scroll-cell {
        max-width: 100%;
        overflow-x: auto;
        white-space: nowrap;
        scrollbar-width: thin;
        scrollbar-color: rgba(56, 189, 248, 0.4) transparent;
        padding-bottom: 2px;
    }
    .scroll-cell::-webkit-scrollbar {
        height: 4px;
    }
    .scroll-cell::-webkit-scrollbar-track {
        background: transparent;
    }
    .scroll-cell::-webkit-scrollbar-thumb {
        background: rgba(56, 189, 248, 0.35);
        border-radius: 4px;
    }
    .scroll-cell::-webkit-scrollbar-thumb:hover {
        background: rgba(56, 189, 248, 0.7);
    }

    .scroll-box-y {
        scrollbar-width: thin;
        scrollbar-color: rgba(128, 128, 128, 0.3) transparent;
    }
    .scroll-box-y::-webkit-scrollbar {
        width: 4px;
    }
    .scroll-box-y::-webkit-scrollbar-track {
        background: transparent;
    }
    .scroll-box-y::-webkit-scrollbar-thumb {
        background: rgba(128, 128, 128, 0.3);
        border-radius: 4px;
    }
    .scroll-box-y::-webkit-scrollbar-thumb:hover {
        background: rgba(128, 128, 128, 0.6);
    }

    /* Section label (upper-case small heading inside cards) */
    .section-label {
        color: var(--text-color); opacity: 0.5;
        font-size: 0.75rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }
    .desc-text {
        color: var(--text-color); opacity: 0.85;
        line-height: 1.6; font-size: 0.9rem;
    }
    .reasoning-text {
        color: var(--text-color); opacity: 0.8;
        line-height: 1.6; font-size: 0.875rem;
    }

    /* ===== Performance Table ===== */
    .perf-table {
        width: 100%; font-size: 0.9rem; border-collapse: collapse;
    }
    .perf-table th {
        padding: 1rem; text-align: left;
        color: var(--text-color); opacity: 0.55; font-weight: 600;
        border-bottom: 2px solid var(--divider);
    }
    .perf-table th:not(:first-child) { text-align: center; }
    .perf-table td {
        padding: 1rem; color: var(--text-color);
        border-bottom: 1px solid var(--divider);
    }
    .perf-table td:not(:first-child) { text-align: center; }

    /* ===== Data Table (related-alert lists, etc.) ===== */
    .data-table {
        width: 100%; font-size: 0.875rem; border-collapse: collapse;
    }
    .data-table td {
        padding: 0.75rem; border-bottom: 1px solid var(--divider);
        color: var(--text-color);
    }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table .td-index {
        color: var(--text-color); opacity: 0.45; font-weight: 600; width: 40px;
    }
    .data-table .td-mono {
        font-family: 'Courier New', monospace; color: var(--accent);
    }

    /* ===== Info / Warning / Success Boxes ===== */
    .info-box {
        background: rgba(59, 130, 246, 0.1);
        border-left: 4px solid #3b82f6;
        padding: 1rem 1.25rem; border-radius: var(--radius-sm);
        margin: 1rem 0; color: var(--text-color);
    }
    .warning-box {
        background: rgba(245, 158, 11, 0.1);
        border-left: 4px solid #f59e0b;
        padding: 1rem 1.25rem; border-radius: var(--radius-sm);
        margin: 1rem 0; color: var(--text-color);
    }
    .success-box {
        background: rgba(16, 185, 129, 0.1);
        border-left: 4px solid #10b981;
        padding: 1rem 1.25rem; border-radius: var(--radius-sm);
        margin: 1rem 0; color: var(--text-color);
    }
    .info-box strong, .warning-box strong, .success-box strong {
        color: var(--text-color);
    }

    /* ===== Summary Banner ===== */
    .summary-banner {
        background: rgba(59, 130, 246, 0.1);
        border-left: 4px solid var(--accent);
        padding: 1rem 1.5rem; border-radius: var(--radius-md);
        margin-bottom: 2rem;
    }
    .summary-banner-title  { color: var(--accent); font-weight: 600;
                             margin-bottom: 0.5rem; }
    .summary-banner-detail { color: var(--text-color); opacity: 0.7;
                             font-size: 0.875rem; }

    /* ===== Buttons ===== */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white !important; border: none;
        border-radius: var(--radius-md);
        padding: 0.625rem 1.5rem;
        font-weight: 600; font-size: 0.875rem;
        transition: all 0.2s;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }

    /* ===== Evidence Card ===== */
    .evidence-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: var(--radius-md);
        padding: 1rem; margin-bottom: 0.75rem;
    }
    .evidence-header {
        display: flex; justify-content: space-between;
        align-items: center; margin-bottom: 0.5rem;
    }
    .evidence-source    { font-weight: 600; color: var(--text-color);
                          font-size: 0.875rem; }
    .evidence-timestamp { font-size: 0.75rem; color: var(--text-color);
                          opacity: 0.5; }
    .evidence-desc      { margin-top: 0.5rem; color: var(--text-color);
                          opacity: 0.8; font-size: 0.875rem; }

    /* ===== Approval Gate ===== */
    .approval-gate {
        background: rgba(239, 68, 68, 0.08);
        border: 2px solid rgba(239, 68, 68, 0.4);
        border-radius: var(--radius-lg);
        padding: 2rem; margin: 2rem 0;
    }
    .approval-header { font-size: 1.25rem; font-weight: 700;
                       color: #ef4444; margin-bottom: 1rem; }
    .approval-text   { color: var(--text-color); opacity: 0.8;
                       margin-bottom: 1.5rem; }
    .approval-status {
        display: grid; grid-template-columns: repeat(2, 1fr);
        gap: 1rem; margin-top: 1rem;
    }
    .status-item {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.75rem 1rem; background: var(--card-bg);
        border-radius: var(--radius-md); border: 1px solid var(--card-border);
    }
    .status-label    { font-weight: 600; color: var(--text-color);
                       font-size: 0.875rem; }
    .status-value    { font-weight: 700; font-size: 0.875rem; }
    .status-disabled { color: #ef4444; }
    .status-required { color: #10b981; }
    .approval-footer { color: var(--text-color); opacity: 0.5;
                       margin-top: 1rem; font-size: 0.875rem;
                       text-align: center; }

    /* ===== Timeline ===== */
    .timeline {
        border-left: 2px solid var(--card-border);
        padding-left: 1.5rem; margin-left: 0.5rem;
    }
    .timeline-item { margin-bottom: 1.5rem; position: relative; }
    .timeline-item::before {
        content: ''; position: absolute;
        left: -1.625rem; top: 0.25rem;
        width: 0.75rem; height: 0.75rem;
        border-radius: 50%; background: var(--accent);
        border: 2px solid var(--card-bg);
    }
    .timeline-time    { font-size: 0.75rem; color: var(--text-color);
                        opacity: 0.5; font-weight: 600; }
    .timeline-content { color: var(--text-color); margin-top: 0.25rem; }

    /* ===== Action Card ===== */
    .action-card {
        background: var(--card-bg);
        border-radius: var(--radius-lg);
        padding: 1.5rem; box-shadow: var(--card-shadow);
        border: 1px solid var(--card-border);
        margin-bottom: 1rem; overflow: hidden; word-wrap: break-word;
    }
    .action-card-header {
        display: flex; justify-content: space-between;
        align-items: start; margin-bottom: 0.75rem;
    }
    .action-card-title     { font-weight: 600; color: var(--text-color);
                             font-size: 1rem; }
    .action-card-body      { color: var(--text-color); margin-bottom: 0.75rem;
                             line-height: 1.5; }
    .action-card-rationale { color: var(--text-color); opacity: 0.7;
                             font-size: 0.875rem; line-height: 1.5; }
    .priority-pill {
        color: white; padding: 0.25rem 0.75rem;
        border-radius: var(--radius-sm);
        font-size: 0.75rem; font-weight: 600; white-space: nowrap;
    }

    /* ===== Confidence Bar ===== */
    .confidence-bar-wrap {
        display: flex; align-items: center; gap: 0.5rem;
    }
    .confidence-bar-track {
        flex: 1; background: var(--divider);
        border-radius: 999px; height: 8px; overflow: hidden;
    }
    .confidence-bar-fill {
        background: var(--accent); height: 100%;
        border-radius: 999px; transition: width 0.3s ease;
    }
    .confidence-bar-value { color: var(--text-color); font-weight: 600; }
    .confidence-bar-note  { color: var(--text-color); opacity: 0.5;
                            font-size: 0.75rem; margin-top: 0.25rem; }

    /* ===== Evidence Availability ===== */
    .evidence-available   { color: var(--success); font-weight: 600;
                            margin-bottom: 0.5rem; }
    .evidence-unavailable { color: var(--danger); font-weight: 600;
                            margin-bottom: 0.5rem; }
    .evidence-detail      { color: var(--text-color); opacity: 0.6;
                            font-size: 0.875rem; }

    /* Code/evidence chips */
    .evidence-code {
        background: var(--card-bg); padding: 0.125rem 0.5rem;
        border-radius: 4px; font-size: 0.875rem;
        border: 1px solid var(--card-border); color: var(--text-color);
    }

    .alert-group-count {
        color: var(--text-color); font-weight: 600; margin-bottom: 1rem;
    }

    /* ===== Footer (normal flow, not fixed) ===== */
    .custom-footer {
        margin-top: 4rem; padding: 1rem 0;
        border-top: 1px solid var(--divider);
        text-align: center; font-size: 0.75rem;
        color: var(--text-color); opacity: 0.5;
    }

    /* ===== Streamlit DataFrame ===== */
    [data-testid="stDataFrame"] {
        border-radius: var(--radius-md); overflow: hidden;
    }

    /* ===== Responsive ===== */
    @media (max-width: 768px) {
        .approval-status { grid-template-columns: 1fr; }
        .metric-card     { margin-bottom: 0.5rem; }
    }
    </style>
    """
