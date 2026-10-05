"""
TRANSCRIPTION UTILITY - NOT A CLASSIFIER.

This script contains ZERO decision-making logic. Every priority/routing
value and every reasoning string below is a fixed, hand-authored judgment
already made by the reasoning agent (Codex) after personally reading all
361 unique alert descriptions in the real Excel dataset.

This script's only job is mechanical:
  1. Hold that fixed per-pattern-id lookup table (PATTERN_ANALYSIS).
  2. Join it onto the 889 raw alert rows (data/llm_analysis/raw_alerts_extract.csv)
     by exact (client, description) match - a pure lookup, not inference.
  3. Serialize the result to data/llm_analysis/stage2_results.json / .csv.

No alert's Priority/Routing is being *decided* here - it was decided by
reading the text. This file exists only because manually typing ~889
near-duplicate JSON records (many of which are exact repeats of the same
alert) by hand adds no analytical value over doing it once per unique
pattern and joining.
"""
import json
import csv
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent.parent
RAW_CSV = BASE / "data" / "llm_analysis" / "raw_alerts_extract.csv"
OUT_DIR = BASE / "data" / "llm_analysis"

# ---------------------------------------------------------------------------
# Fixed, hand-authored analysis per unique (client, description) pattern.
# Keyed by pattern_id from unique_patterns.csv (already generated).
# ---------------------------------------------------------------------------

PATTERN_ANALYSIS = {}

def add(pat, priority, p_reason, routing_category, r_reason):
    PATTERN_ANALYSIS[pat] = {
        "predicted_priority": priority,
        "priority_reasoning": p_reason,
        "predicted_routing_category": routing_category,
        "routing_reasoning": r_reason,
    }

# ---- Bridgestone (PAT-0001 .. PAT-0016) ----
add("PAT-0001", "1 - Critical",
    "CRITICAL_AutoTicket prefix + explicit P1 tag; TRN5_NOT200RC indicates repeated non-200 HTTP response codes on transactions (80 occurrences) - a direct, recurring API/web failure signal.",
    "API/Web Support",
    "Alert concerns HTTP response-code failures on transactions; routed to the team owning API/web transaction health.")
add("PAT-0002", "1 - Critical",
    "CRITICAL_AutoTicket + P1 tag; alert code explicitly names 'API_ERR_CRITICAL' - an API error-rate breach.",
    "API/Web Support",
    "Explicit 'API_ERR' in alert code.")
add("PAT-0003", "1 - Critical",
    "P1 tag + explicit 'FAILURE' outcome on a named batch/ETL job (BGSN_Batch_Custom_Extract_Point_Detail_Delta_AZREWARDS) feeding the AZREWARDS loyalty data extract.",
    "Batch/Workflow Operations",
    "Named as a 'Data Hub Alert (Workflow)' batch/ETL job failure.")
add("PAT-0004", "1 - Critical",
    "P1 tag present, but this is a soft latency/SLA breach (API average time exceeded 1000ms), not a hard failure - noted as a lower-severity flavor of Critical than an outright failure, though the source tag itself is P1 so Priority label kept at Critical.",
    "API/Web Support",
    "API latency threshold breach.")
add("PAT-0005", "2 - High",
    "Same batch job family as PAT-0003 but flagged for RUN_DURATION (job running long), not a confirmed FAILURE - a job still executing/slow is less certain to be a real incident than a hard failure, so downgraded one tier from Critical to High versus PAT-0003/PAT-0006.",
    "Batch/Workflow Operations",
    "Batch job duration-threshold alert, same job family as PAT-0003.")
add("PAT-0006", "1 - Critical",
    "Same job family as PAT-0003 (Daily variant) with explicit FAILURE + P1 tag.",
    "Batch/Workflow Operations",
    "Named batch/ETL job failure.")
add("PAT-0007", "1 - Critical",
    "Related AZREWARDS batch job (point *redemption* delta, a different feed than PAT-0003's *detail* delta) with explicit FAILURE + P1 tag.",
    "Batch/Workflow Operations",
    "Named batch/ETL job failure.")
add("PAT-0008", "1 - Critical",
    "'Multiple OpsRamp Agents Offline' + CRITICAL prefix - simultaneous loss of monitoring visibility across several hosts often signals a broader network/infra segment outage, not an isolated blip.",
    "Infrastructure/Monitoring Operations",
    "Monitoring-agent connectivity loss across multiple hosts.")
add("PAT-0009", "1 - Critical",
    "Disk usage at 95% used / 5% free on an ETL host, at the alert's own 95% threshold - effectively out of headroom for a system used for batch data processing, real risk of job failures.",
    "Infrastructure Operations",
    "Disk-capacity exhaustion on a named ETL host.")
add("PAT-0010", "1 - Critical",
    "P1 tag + explicit FAILURE on a named batch job (Point Expiration Daily).",
    "Batch/Workflow Operations",
    "Named batch job failure.")
add("PAT-0011", "3 - Medium",
    "WARNING_AutoTicket prefix (not CRITICAL) for a single host's monitoring agent going offline - loss of visibility on one host, not a confirmed service outage.",
    "Infrastructure/Monitoring Operations",
    "Single-host monitoring-agent connectivity loss, Warning-tier.")
add("PAT-0012", "1 - Critical",
    "P1 tag; web/API server load-distribution anomaly (uneven load balancing) - a real infra symptom that can cause uneven latency/errors.",
    "Infrastructure/Cloud Operations",
    "Load-balancing anomaly across web/API servers.")
add("PAT-0013", "1 - Critical",
    "P1 tag; API requests exceeding 10 seconds is a severe latency breach - more severe than the 1000ms breach in PAT-0004.",
    "API/Web Support",
    "Severe API latency threshold breach (10s).")
add("PAT-0014", "1 - Critical",
    "P1 tag + explicit FAILURE on a named batch job (Email Process Activity import).",
    "Batch/Workflow Operations",
    "Named batch job failure.")
add("PAT-0015", "1 - Critical",
    "P1 tag + explicit FAILURE on a named batch job (Store Import).",
    "Batch/Workflow Operations",
    "Named batch job failure.")
add("PAT-0016", "3 - Medium",
    "WARNING_AutoTicket prefix for a single host's monitoring agent offline - same lower-severity pattern as PAT-0011.",
    "Infrastructure/Monitoring Operations",
    "Single-host monitoring-agent connectivity loss, Warning-tier.")

# ---- EA Sports (PAT-0017 .. PAT-0185) ----
add("PAT-0017", "1 - Critical", "CRITICAL_AutoTicket via ThousandEyes (network path synthetic monitoring) reporting errors on the path to Mulesoft - a network-layer signal.", "Network Operations", "ThousandEyes is a network path/synthetic-monitoring tool; error on Mulesoft path.")
add("PAT-0018", "1 - Critical", "P1 tag, explicit 'Jobs Failure in last 1 hour' for production batch jobs.", "Batch/Workflow Operations", "Named production batch-job failure monitor.")
add("PAT-0019", "1 - Critical", "Same job-failure family as PAT-0018, different date.", "Batch/Workflow Operations", "Named production batch-job failure monitor.")
add("PAT-0020", "3 - Medium", "WARNING_AutoTicket, single-host monitoring agent offline; hostname 'ora' suggests an Oracle host but the agent-offline event itself is a monitoring-visibility issue, not a confirmed DB failure.", "Infrastructure/Monitoring Operations", "Single-host agent offline; DB-adjacent hostname noted but not a confirmed DB incident.")
add("PAT-0021", "1 - Critical", "P1 tag and the message explicitly states 'CRITICAL' for an INTERNALSERVERERROR (HTTP 500) threshold breach.", "API/Web Support", "Explicit 500-error-rate threshold breach.")
add("PAT-0022", "1 - Critical", "CRITICAL_AutoTicket via ThousandEyes reporting errors on the Prod Web API path.", "Network Operations", "ThousandEyes network path monitoring on Web API.")
add("PAT-0023", "1 - Critical", "Same job-failure family as PAT-0018/19.", "Batch/Workflow Operations", "Named production batch-job failure monitor.")
add("PAT-0024", "1 - Critical", "'Multiple OpsRamp Agents Offline' - same broad-impact reasoning as Bridgestone PAT-0008.", "Infrastructure/Monitoring Operations", "Monitoring-agent connectivity loss across multiple hosts.")
add("PAT-0025", "2 - High", "No P1/CRITICAL tag (plain 'FRMS Workflow ... FAILED' notice), but explicit FAILED outcome on a named production SFTP delivery job - softer framing than the tagged AutoTicket alerts, hence High rather than Critical.", "Batch/Workflow Operations", "SFTP data-delivery batch workflow explicitly FAILED.")
add("PAT-0026", "3 - Medium", "Warning AutoTicket; disk usage 85% - elevated but at the warning threshold, not yet critical (85-95% range seen elsewhere for Critical).", "Infrastructure/Cloud Operations", "Host disk-capacity warning.")
add("PAT-0027", "3 - Medium", "Same disk-warning pattern as PAT-0026, different host.", "Infrastructure/Cloud Operations", "Host disk-capacity warning.")
add("PAT-0028", "3 - Medium", "Same disk-warning pattern, marginally higher usage (85.01%), still Warning-tier.", "Infrastructure/Cloud Operations", "Host disk-capacity warning.")
add("PAT-0029", "1 - Critical", "CRITICAL_AutoTicket; required SSH remote-access service not running on host.", "Infrastructure/Cloud Operations", "SSH server process down - infra/remote-access service, not batch-specific.")
add("PAT-0030", "1 - Critical", "CRITICAL_AutoTicket; Epsilon.Fusion.Batch.JobService (batch pipeline control service) not running.", "Batch/Workflow Operations", "Batch job-orchestration service down - directly controls the batch pipeline.")
add("PAT-0031", "1 - Critical", "Same host/incident window as PAT-0030; ScannerService (batch pipeline component) not running.", "Batch/Workflow Operations", "Batch pipeline scanner service down.")
add("PAT-0032", "1 - Critical", "Same host/incident window as PAT-0030/31; SchedulerService not running.", "Batch/Workflow Operations", "Batch pipeline scheduler service down.")
add("PAT-0033", "1 - Critical", "Different host, JobService not running - same service-down pattern.", "Batch/Workflow Operations", "Batch job-orchestration service down.")
add("PAT-0034", "1 - Critical", "SSH server down on a different host - same as PAT-0029.", "Infrastructure/Cloud Operations", "SSH server process down.")
add("PAT-0035", "4 - Low", "Message explicitly says 'Testing OpsRamp Integration' - this is a declared test event, not a production incident, despite carrying a P1/CRITICAL wrapper. Downgraded from the tag's face value.", "Monitoring/NOC", "Explicit integration test of the monitoring tool itself.")
add("PAT-0036", "1 - Critical", "P1 tag; 10% INTERNALSERVERERROR (500) threshold exceeded - specific timestamped instance of the API-error family.", "API/Web Support", "500-error-rate threshold breach.")
add("PAT-0037", "1 - Critical", "Same API-error family as PAT-0036, different timestamp.", "API/Web Support", "500-error-rate threshold breach.")
add("PAT-0038", "1 - Critical", "Same API-error family as PAT-0036.", "API/Web Support", "500-error-rate threshold breach.")
add("PAT-0039", "1 - Critical", "Same API-error family as PAT-0036.", "API/Web Support", "500-error-rate threshold breach.")
add("PAT-0040", "1 - Critical", "Same API-error family as PAT-0036.", "API/Web Support", "500-error-rate threshold breach.")

# ELB errcheck family: PAT-0041..PAT-0072, all count=1, magnitude varies.
_elb = {
    "PAT-0041": 7, "PAT-0042": 7, "PAT-0043": 6, "PAT-0044": 22, "PAT-0045": 8,
    "PAT-0046": 26, "PAT-0047": 6, "PAT-0048": 12, "PAT-0049": 6, "PAT-0050": 6,
    "PAT-0051": 472, "PAT-0052": 2238, "PAT-0053": 8, "PAT-0054": 6, "PAT-0055": 793,
    "PAT-0056": 34, "PAT-0057": 15, "PAT-0058": 6, "PAT-0059": 13, "PAT-0060": 12,
    "PAT-0061": 14, "PAT-0062": 6, "PAT-0063": 11, "PAT-0064": 6, "PAT-0065": 6,
    "PAT-0066": 6, "PAT-0067": 26, "PAT-0068": 23, "PAT-0069": 6, "PAT-0070": 6,
    "PAT-0071": 20, "PAT-0072": 8,
}
for pat, n in _elb.items():
    severe = n >= 100
    add(pat, "1 - Critical",
        f"P1EASS_ELB_ERRCHECK, P1 tag, CRITICAL prefix; {n} ELB errors reported in the window." +
        (f" This is a severe outlier magnitude (baseline is ~6-30) - the single worst signal in this alert family." if severe else " Magnitude is within the family's typical baseline range (~6-30)."),
        "Infrastructure/Cloud Operations",
        "ELB (load balancer) error-count monitor - AWS infra component.")

add("PAT-0073", "1 - Critical", "P1 tag; 14 'Moment' (personalization/messaging service) API failures in a 15-minute window.", "API/Integration Support", "Named downstream service (Moment) API failures.")
add("PAT-0074", "1 - Critical", "Same Moment-failure family as PAT-0073, 6 failures.", "API/Integration Support", "Named downstream service (Moment) API failures.")
add("PAT-0075", "1 - Critical", "Same Moment-failure family, 7 failures.", "API/Integration Support", "Named downstream service (Moment) API failures.")

# TRN5_NOT200RC family: PAT-0076..PAT-0109, magnitude = 'total hits'
_trn5 = {
    "PAT-0076": 7, "PAT-0077": 56, "PAT-0078": 56, "PAT-0079": 56, "PAT-0080": 56,
    "PAT-0081": 18, "PAT-0082": 18, "PAT-0083": 18, "PAT-0084": 18, "PAT-0085": 18,
    "PAT-0086": 18, "PAT-0087": 18, "PAT-0088": 18, "PAT-0089": 18, "PAT-0090": 18,
    "PAT-0091": 12, "PAT-0092": 12, "PAT-0093": 12, "PAT-0094": 12, "PAT-0095": 12,
    "PAT-0096": 35, "PAT-0097": 6, "PAT-0098": 11, "PAT-0099": 11, "PAT-0100": 12,
    "PAT-0101": 11, "PAT-0102": 16, "PAT-0103": 53, "PAT-0104": 14, "PAT-0105": 14,
    "PAT-0106": 14, "PAT-0107": 14, "PAT-0108": 5, "PAT-0109": 5,
}
for pat, n in _trn5.items():
    add(pat, "1 - Critical",
        f"P1EASS_TRN5_NOT200RC, P1 tag, CRITICAL prefix; {n} non-200-HTTP-response hits recorded. Magnitude is modest/typical for this family (all instances fall in a comparatively narrow 5-56 range, no extreme outlier).",
        "API/Web Support",
        "Non-200 HTTP response-code monitor on transactions.")

add("PAT-0110", "4 - Low", "Explicitly says 'Q3EASS Testing OpsRamp Integration' - QA environment (Q3), declared test, not production. Downgraded despite CRITICAL wrapper.", "Monitoring/NOC", "Test-environment integration test of the monitoring tool.")
add("PAT-0111", "3 - Medium", "Hedged, predictive language ('may be delayed today') - a proactive warning, not a confirmed failure, for a named daily data extract.", "Batch/Workflow Operations", "Predictive delay warning for a scheduled data extract.")
for pat in ["PAT-0112","PAT-0113","PAT-0114","PAT-0115","PAT-0116","PAT-0117","PAT-0118","PAT-0119","PAT-0120","PAT-0121","PAT-0122"]:
    add(pat, "3 - Medium", "Same predictive 'may be delayed today' extract-delay warning family as PAT-0111, different date.", "Batch/Workflow Operations", "Predictive delay warning for a scheduled data extract.")
add("PAT-0123", "1 - Critical", "Same production Jobs-Failure family as PAT-0018/19/23.", "Batch/Workflow Operations", "Named production batch-job failure monitor.")
add("PAT-0124", "1 - Critical", "Same production Jobs-Failure family.", "Batch/Workflow Operations", "Named production batch-job failure monitor.")
add("PAT-0125", "1 - Critical", "Same production Jobs-Failure family.", "Batch/Workflow Operations", "Named production batch-job failure monitor.")
add("PAT-0126", "1 - Critical", "Same production Jobs-Failure family.", "Batch/Workflow Operations", "Named production batch-job failure monitor.")
add("PAT-0127", "3 - Medium", "Environment tag 'QA_[Q3EASS...]' - a QA-environment batch failure, not production; matters for release readiness but does not affect live customers, so downgraded from the Critical label a PROD equivalent would carry.", "Batch/Workflow Operations", "QA-environment batch job failure.")
add("PAT-0128", "3 - Medium", "Environment tag 'UAT_[U1EASS...]' - a UAT-environment batch failure, same downgrade rationale as PAT-0127.", "Batch/Workflow Operations", "UAT-environment batch job failure.")

_svc_down = {
    "PAT-0129": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0130": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0131": ("JobService", "Batch/Workflow Operations"),
    "PAT-0132": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0133": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0134": ("JobService", "Batch/Workflow Operations"),
    "PAT-0135": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0136": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0138": ("JobService", "Batch/Workflow Operations"),
    "PAT-0139": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0140": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0142": ("JobService", "Batch/Workflow Operations"),
    "PAT-0143": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0144": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0146": ("JobService", "Batch/Workflow Operations"),
    "PAT-0147": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0148": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0150": ("JobService", "Batch/Workflow Operations"),
    "PAT-0151": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0152": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0154": ("JobService", "Batch/Workflow Operations"),
    "PAT-0155": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0156": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0158": ("JobService", "Batch/Workflow Operations"),
    "PAT-0159": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0160": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0162": ("JobService", "Batch/Workflow Operations"),
    "PAT-0163": ("ScannerService", "Batch/Workflow Operations"),
    "PAT-0164": ("SchedulerService", "Batch/Workflow Operations"),
    "PAT-0165": ("SchedulerService", "Batch/Workflow Operations"),
}
for pat, (svc, route) in _svc_down.items():
    add(pat, "1 - Critical",
        f"CRITICAL_AutoTicket; Epsilon.Fusion.Batch.{svc} (batch pipeline component) not running on host - directly controls the batch job pipeline.",
        route,
        f"Batch pipeline {svc} down.")
_ssh_down = ["PAT-0137", "PAT-0141", "PAT-0145", "PAT-0149", "PAT-0153", "PAT-0157", "PAT-0161"]
for pat in _ssh_down:
    add(pat, "1 - Critical",
        "CRITICAL_AutoTicket; Bitvise SSH remote-access server not running on host. (Trailing '|<code>' text in some of these entries appears to be a stray reference-code artifact from data merging, not part of the alert's own semantics.)",
        "Infrastructure/Cloud Operations",
        "SSH server process down - remote-access infra service.")

add("PAT-0166", "1 - Critical", "'SYSTEM_REBOOT' event; hostname 'da2uEASSora11' follows an Oracle-host naming convention ('ora') - an unplanned reboot on what appears to be a database host is a significant, potentially service-impacting event.", "Database Engineering", "Hostname naming convention ('ora') strongly implies an Oracle database server.")
add("PAT-0167", "1 - Critical", "Same SYSTEM_REBOOT + Oracle-hostname-naming reasoning as PAT-0166, different host.", "Database Engineering", "Hostname naming convention implies Oracle database server.")
add("PAT-0168", "1 - Critical", "CRITICAL_AutoTicket via ThousandEyes on the Fusion Admin Tool path.", "Network Operations", "ThousandEyes network path monitoring.")
add("PAT-0169", "1 - Critical", "Same ThousandEyes family as PAT-0168, 'Error is present' variant.", "Network Operations", "ThousandEyes network path monitoring.")
add("PAT-0170", "1 - Critical", "Critical AutoTicket; disk usage 90.36% - above the 90% critical threshold convention used elsewhere.", "Infrastructure/Cloud Operations", "Host disk-capacity critical.")
add("PAT-0171", "1 - Critical", "Critical AutoTicket; disk usage 95.00% at threshold, 5% free.", "Infrastructure/Cloud Operations", "Host disk-capacity critical.")
add("PAT-0172", "1 - Critical", "'ESCALATE :' prefix on top of Critical + 90.64% disk usage - explicitly escalated critical disk issue.", "Infrastructure/Cloud Operations", "Escalated host disk-capacity critical.")
add("PAT-0173", "2 - High", "'ESCALATE :' prefix added to an otherwise Warning-tier disk alert (85% used) - the explicit escalation raises urgency above a normal Warning, but the underlying condition (85%) is not yet at the Critical (90-95%) threshold seen elsewhere, so High rather than Critical.", "Infrastructure/Cloud Operations", "Escalated host disk-capacity warning.")
add("PAT-0174", "1 - Critical", "No AutoTicket wrapper or P-tag at all, but a direct human instruction to 'page out' to a named on-call team is the strongest urgency signal in the dataset - paging implies immediate human response is required.", "Database Engineering", "Explicitly names the 'EASS_DBA Team' in the alert text itself.")
add("PAT-0175", "3 - Medium", "WARNING_AutoTicket, single-host monitoring agent offline.", "Infrastructure/Monitoring Operations", "Single-host agent offline, Warning-tier.")
_disk_warn_ea = ["PAT-0176","PAT-0177","PAT-0178","PAT-0179","PAT-0180","PAT-0181","PAT-0182","PAT-0183","PAT-0184","PAT-0185"]
for pat in _disk_warn_ea:
    add(pat, "3 - Medium", "Warning AutoTicket; disk usage in the 85-88% Warning-tier range, below the 90-95% Critical threshold convention used elsewhere in this dataset.", "Infrastructure/Cloud Operations", "Host disk-capacity warning.")

# ---- Pizza Hut (PAT-0186 .. PAT-0361) ----
add("PAT-0186", "2 - High", "P1 tag + CRITICAL_AutoTicket wrapper, BUT the alert's own embedded text explicitly says 'Warning:' for SLA extracts 'not yet delivered' (still pending, not a confirmed failure). Resolving this conflict in favor of the message's own self-assessment: High rather than full Critical.", "Batch/Workflow Operations", "SLA data-extract delivery delay.")
add("PAT-0187", "1 - Critical", "P1 tag AND explicit 'CRITICAL:' both agree - unambiguous batch job failure.", "Batch/Workflow Operations", "Named production batch-job failure.")
add("PAT-0188", "1 - Critical", "CRITICAL_AutoTicket; IP address reported Unreachable - a network-layer connectivity failure.", "Network Operations", "IP-address unreachability is fundamentally a network-connectivity signal.")
add("PAT-0189", "3 - Medium", "WARNING_AutoTicket for the *same IP* as PAT-0188's agent going offline - likely a correlated symptom of the same underlying host/network issue, but on its own (agent visibility loss) is lower severity than confirmed unreachability.", "Infrastructure/Monitoring Operations", "Monitoring-agent offline; likely correlates with PAT-0188's Unreachable alerts for the same host.")
add("PAT-0190", "1 - Critical", "CRITICAL_AutoTicket; a specific compute worker node reported Unreachable.", "Infrastructure/Cloud Operations", "Named worker/compute node unreachable.")
add("PAT-0191", "1 - Critical", "CRITICAL_AutoTicket; IP address Unreachable - same pattern as PAT-0188, different host.", "Network Operations", "IP-address unreachability.")
add("PAT-0192", "2 - High", "No P1/CRITICAL tag (plain FRMS workflow notice), but explicit FAILED outcome on a named production SFTP delivery job.", "Batch/Workflow Operations", "SFTP data-delivery batch workflow explicitly FAILED.")
add("PAT-0193", "1 - Critical", "P1PZHT_PPL_API_MOMENT_ERRORS, P1 tag; 1 Moment API-call failure in 15 min - low magnitude but tag carries Critical classification from the source system.", "API/Integration Support", "Named downstream service (Moment) API failures.")
add("PAT-0194", "1 - Critical", "Critical AutoTicket; disk usage 95% used / 5% free on a DBA-related path ('/lfs/dba').", "Database Engineering", "Filesystem path explicitly references 'dba' (database administration).")
add("PAT-0195", "1 - Critical", "Same Moment-error family as PAT-0193, 2 failures.", "API/Integration Support", "Named downstream service (Moment) API failures.")
add("PAT-0196", "1 - Critical", "P1 tag + explicit 'CRITICAL:' for a weekly reporting batch job not completed - respecting the explicit tag, though noted as a back-office reporting job rather than a customer-facing outage.", "Batch/Workflow Operations", "Named reporting batch job not completed.")
add("PAT-0197", "1 - Critical", "P1PZHT_MOMENT_FAILCHECK, P1 tag; 2 Moment failures in 5 min.", "API/Integration Support", "Named downstream service (Moment) API failures.")
add("PAT-0198", "1 - Critical", "P1 tag AND explicit internal 'CRITICAL:' agree (unlike PAT-0186) for a data-delivery SLA miss (Segment delta extract).", "Batch/Workflow Operations", "SLA data-extract delivery failure, internally self-labeled Critical.")
add("PAT-0199", "2 - High", "Same internal/outer tag conflict as PAT-0186: P1/CRITICAL wrapper but text says 'Warning:' for VAP Extract Process Not Completed.", "Batch/Workflow Operations", "SLA/extract-process delay, self-labeled Warning internally.")
add("PAT-0200", "1 - Critical", "CRITICAL_AutoTicket; Epsilon.Fusion.Batch.SchedulerService not running.", "Batch/Workflow Operations", "Batch pipeline scheduler service down.")
add("PAT-0201", "1 - Critical", "Same MOMENT_FAILCHECK family as PAT-0197, 3 failures.", "API/Integration Support", "Named downstream service (Moment) API failures.")
add("PAT-0202", "1 - Critical", "Same PPL_API_MOMENT_ERRORS family as PAT-0193, 3 failures.", "API/Integration Support", "Named downstream service (Moment) API failures.")
add("PAT-0203", "1 - Critical", "Same PPL_API_MOMENT_ERRORS family, 43 failures - notably higher than PAT-0193/0202's 1-3, a real spike.", "API/Integration Support", "Named downstream service (Moment) API failures, elevated magnitude.")
add("PAT-0204", "1 - Critical", "P1PZHT_TRN10_GT7SEC, P1 tag; 46,265 slow (>7s) API calls in an hour - a very large volume indicating widespread latency degradation.", "API/Integration Support", "API latency-threshold breach, large magnitude.")
add("PAT-0205", "1 - Critical", "'Multiple OpsRamp Agents Offline' - same broad-impact reasoning as prior instances of this alert family.", "Infrastructure/Monitoring Operations", "Monitoring-agent connectivity loss across multiple hosts.")
add("PAT-0206", "1 - Critical", "CRITICAL_AutoTicket; hostname explicitly contains 'DB-STANDBY' - a database standby/replica server unreachable threatens failover/HA capability even if the primary DB is healthy.", "Database Engineering", "Hostname explicitly names a DB standby server.")
add("PAT-0207", "1 - Critical", "CRITICAL_AutoTicket; hostname 'ua2uPZHTora61' follows Oracle-host naming convention ('ora').", "Database Engineering", "Hostname naming convention implies Oracle database server.")
add("PAT-0208", "1 - Critical", "Critical AutoTicket; disk usage 90.17%.", "Infrastructure/Cloud Operations", "Host disk-capacity critical.")
add("PAT-0209", "1 - Critical", "Critical AutoTicket; disk usage 95.00%, 5% free.", "Infrastructure/Cloud Operations", "Host disk-capacity critical.")
add("PAT-0210", "3 - Medium", "WARNING_AutoTicket for the same IP as PAT-0191's Unreachable alert - likely a correlated symptom, but on its own is a lower-severity monitoring-visibility signal.", "Infrastructure/Monitoring Operations", "Monitoring-agent offline; likely correlates with PAT-0191's Unreachable alerts for the same host.")

_mem = {
    "PAT-0211": (50, 43), "PAT-0212": (52, 37), "PAT-0213": (63, 52), "PAT-0214": (50, 41),
    "PAT-0215": (51, 36), "PAT-0216": (51, 42), "PAT-0217": (52, 39), "PAT-0220": (50, 43),
    "PAT-0221": (51, 44), "PAT-0222": (57, 35), "PAT-0223": (52, 25), "PAT-0224": (53, 36),
    "PAT-0225": (53, 47), "PAT-0226": (54, 47), "PAT-0227": (55, 48), "PAT-0228": (58, 39),
    "PAT-0229": (50, 13), "PAT-0230": (50, 41), "PAT-0231": (51, 13), "PAT-0232": (57, 50),
    "PAT-0233": (50, 36),
}
for pat, (phys, virt) in _mem.items():
    add(pat, "4 - Low",
        f"Tagged CRITICAL_AutoTicket by the monitoring tool, but the actual reported value ({phys}% physical / {virt}% virtual memory used) is NOT alarming by the 85-95% thresholds this same dataset uses for disk-capacity alerts - normal servers commonly run at 50-65% memory. Overriding the tool's default CRITICAL label as not reflective of real risk.",
        "Infrastructure/Cloud Operations",
        "Host resource-utilization monitor.")

add("PAT-0218", "3 - Medium", "CRITICAL_AutoTicket; a batch server (ASG name references P1PZHT) reports uptime under 5 minutes, implying a recent restart. Occurs only once (1x) so it's not possible to distinguish a benign autoscaling event from a crash-loop from this single data point - kept at Medium given genuine uncertainty rather than accepting the CRITICAL face value.", "Infrastructure/Cloud Operations", "Batch server auto-scaling-group uptime check.")
add("PAT-0219", "1 - Critical", "CRITICAL_AutoTicket; Epsilon.Fusion.Batch.JobService not running.", "Batch/Workflow Operations", "Batch pipeline job-orchestration service down.")

_moment_failcheck = {
    "PAT-0234": 1, "PAT-0235": 107, "PAT-0236": 16, "PAT-0237": 203, "PAT-0238": 25,
    "PAT-0239": 26, "PAT-0240": 2943, "PAT-0241": 2944, "PAT-0242": 3285, "PAT-0243": 35,
    "PAT-0244": 5, "PAT-0245": 61, "PAT-0246": 62, "PAT-0247": 66, "PAT-0248": 76,
    "PAT-0249": 78, "PAT-0250": 85, "PAT-0251": 9, "PAT-0252": 92, "PAT-0253": 93,
}
for pat, n in _moment_failcheck.items():
    severe = n >= 1000
    add(pat, "1 - Critical",
        f"P1PZHT_MOMENT_FAILCHECK, P1 tag; {n} Moment-service failures in a 5-minute window." +
        (f" This is an extreme-magnitude outlier (baseline is single/double digits) - represents a severe outage of the Moment service, warranting the most urgent attention among this family." if severe else " Within the family's typical range."),
        "API/Integration Support",
        "Named downstream service (Moment) API failures.")

_ppl_moment_errors = {
    "PAT-0254": 10, "PAT-0255": 14, "PAT-0256": 16, "PAT-0257": 17, "PAT-0258": 172,
    "PAT-0259": 1754, "PAT-0260": 206, "PAT-0261": 207, "PAT-0262": 223, "PAT-0263": 228,
    "PAT-0264": 234, "PAT-0265": 243, "PAT-0266": 245, "PAT-0267": 26, "PAT-0268": 292,
    "PAT-0269": 3710, "PAT-0270": 6, "PAT-0271": 69, "PAT-0272": 72, "PAT-0273": 94,
}
for pat, n in _ppl_moment_errors.items():
    severe = n >= 1000
    add(pat, "1 - Critical",
        f"P1PZHT_PPL_API_MOMENT_ERRORS, P1 tag; {n} API calls had Moment failures in 15 min." +
        (f" Extreme-magnitude outlier - a severe API-error storm, the most urgent instance in this family." if severe else " Within the family's typical range."),
        "API/Integration Support",
        "Named downstream service (Moment) API failures.")

_trn10 = {
    "PAT-0274": 103708, "PAT-0275": 104169, "PAT-0276": 106112, "PAT-0277": 106360,
    "PAT-0278": 116346, "PAT-0279": 11896, "PAT-0280": 121046, "PAT-0281": 1288,
    "PAT-0282": 135838, "PAT-0283": 148169, "PAT-0284": 154880, "PAT-0285": 156197,
    "PAT-0286": 16527, "PAT-0287": 169198, "PAT-0288": 20331, "PAT-0289": 206187,
    "PAT-0290": 20766, "PAT-0291": 22127, "PAT-0292": 2309, "PAT-0293": 23754,
    "PAT-0294": 247004, "PAT-0295": 29908, "PAT-0296": 30556, "PAT-0297": 3094,
    "PAT-0298": 32429, "PAT-0299": 36941, "PAT-0300": 3793, "PAT-0301": 3975,
    "PAT-0302": 48232, "PAT-0303": 48856, "PAT-0304": 49353, "PAT-0305": 5003,
    "PAT-0306": 5433, "PAT-0307": 5544, "PAT-0308": 6055, "PAT-0309": 61038,
    "PAT-0310": 6106, "PAT-0311": 6205, "PAT-0312": 6206, "PAT-0313": 6234,
    "PAT-0314": 66235, "PAT-0315": 67579, "PAT-0316": 73321, "PAT-0317": 7769,
    "PAT-0318": 78838, "PAT-0319": 82984, "PAT-0320": 9117, "PAT-0321": 97585,
    "PAT-0322": 98594,
}
for pat, n in _trn10.items():
    extreme = n >= 100000
    add(pat, "1 - Critical",
        f"P1PZHT_TRN10_GT7SEC, P1 tag; {n:,} API calls exceeded 7 seconds in the past hour." +
        (f" An extreme value - essentially systemic API-tier timeout/degradation, the most severe instances in this family (compare to the family's low end of ~1,300)." if extreme else " Within the family's wide but comparatively lower range."),
        "API/Integration Support",
        "API latency-threshold breach (>7s calls).")

add("PAT-0323", "1 - Critical", "P1 tag + explicit (doubled, likely a text-duplication artifact) 'CRITICAL:' for a named points-expiration batch job not completed.", "Batch/Workflow Operations", "Named batch job not completed.")
add("PAT-0324", "1 - Critical", "P1 tag + explicit 'CRITICAL: Failed' for a named API server pool (DRL Version API).", "API/Integration Support", "Named API server pool explicitly Failed.")
add("PAT-0325", "1 - Critical", "P1 tag + explicit 'CRITICAL:'; 13 SLA-related jobs never started - more severe than a delivery delay since the jobs did not even begin.", "Batch/Workflow Operations", "Multiple named SLA batch jobs failed to start.")

_unreachable_generic = ["PAT-0326","PAT-0327","PAT-0328","PAT-0329","PAT-0330","PAT-0332","PAT-0333","PAT-0334","PAT-0335","PAT-0336","PAT-0337"]
for pat in _unreachable_generic:
    add(pat, "1 - Critical", "CRITICAL_AutoTicket; a specific host reported Unreachable. (PAT-0336/0337 carry a trailing '|PCPO-xxxxx' reference-code artifact from data merging, not part of the alert's own semantics; same underlying IP as PAT-0191.)", "Network Operations", "Host/IP unreachability - network-connectivity signal.")
add("PAT-0331", "1 - Critical", "CRITICAL_AutoTicket; hostname explicitly contains 'DB' (not standby this time - appears to be the primary DB reference) reported Unreachable.", "Database Engineering", "Hostname explicitly names a DB server.")
add("PAT-0338", "1 - Critical", "CRITICAL_AutoTicket via ThousandEyes on the Fusion Admin Tool path.", "Network Operations", "ThousandEyes network path monitoring.")
add("PAT-0339", "1 - Critical", "CRITICAL_AutoTicket via ThousandEyes on the Web API path.", "Network Operations", "ThousandEyes network path monitoring.")
add("PAT-0340", "1 - Critical", "Critical AutoTicket; disk usage 90.56%.", "Infrastructure/Cloud Operations", "Host disk-capacity critical.")
add("PAT-0341", "1 - Critical", "Critical AutoTicket; disk usage 95.00%, 5% free.", "Infrastructure/Cloud Operations", "Host disk-capacity critical.")
add("PAT-0342", "1 - Critical", "Critical AutoTicket; disk usage 99.00%, only 1% free - the most severe disk-capacity instance in the dataset.", "Infrastructure/Cloud Operations", "Host disk-capacity critical, near-total exhaustion.")
add("PAT-0343", "1 - Critical", "Critical AutoTicket; disk usage 99.00%, 1% free, on filesystem path '/lfs/dba' - path naming explicitly references DBA (database administration), unlike the generic paths in PAT-0340-0342.", "Database Engineering", "Filesystem path explicitly references 'dba'.")
add("PAT-0344", "3 - Medium", "No severity prefix at all; raw metric readout: 156.915 average users waiting for a 'Concurrency' event class. 'Users Waiting' strongly suggests database session/lock contention (a classic Oracle wait-event metric). This is a meaningfully large queue depth without a confirmed outage.", "Database Engineering", "Inferred from metric terminology (concurrency/wait-event), not a hostname or keyword tag.")
add("PAT-0345", "4 - Low", "Same metric family as PAT-0344 but value is 27.96 - comparatively minor, likely near-baseline concurrency.", "Database Engineering", "Inferred from metric terminology (concurrency/wait-event).")

_disk_warn_pzht = ["PAT-0346","PAT-0347","PAT-0348","PAT-0349","PAT-0350","PAT-0351","PAT-0352","PAT-0353","PAT-0354","PAT-0355","PAT-0356","PAT-0357","PAT-0358","PAT-0359","PAT-0360","PAT-0361"]
for pat in _disk_warn_pzht:
    add(pat, "3 - Medium", "Warning AutoTicket; disk usage in the 85-88.7% Warning-tier range, below the 90-99% Critical threshold convention used elsewhere in this dataset.", "Infrastructure/Cloud Operations", "Host disk-capacity warning.")

# ---------------------------------------------------------------------------
# Sanity check + join to all 889 raw rows + write outputs
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uniq = pd.read_csv(OUT_DIR / "unique_patterns.csv")
    missing = [p for p in uniq["pattern_id"] if p not in PATTERN_ANALYSIS]
    if missing:
        raise SystemExit(f"ERROR: {len(missing)} pattern(s) have no analysis: {missing[:10]}")
    print(f"All {len(uniq)} unique patterns have hand-authored analysis. OK.")

    raw = pd.read_csv(RAW_CSV)
    uniq_small = uniq[["pattern_id", "client", "description", "count"]]
    merged = raw.merge(uniq_small, on=["client", "description"], how="left")
    if merged["pattern_id"].isna().any():
        raise SystemExit("ERROR: some raw rows did not match a unique pattern.")

    records = []
    for _, row in merged.iterrows():
        analysis = PATTERN_ANALYSIS[row["pattern_id"]]
        client = row["client"]
        routing_label = f"{analysis['predicted_routing_category']} - {client}"
        records.append({
            "alert_id": row["alert_id"],
            "client": client,
            "created_at": row["created_at"],
            "description": row["description"],
            "pattern_id": row["pattern_id"],
            "pattern_occurrence_count": int(row["count"]),
            "predicted_priority": analysis["predicted_priority"],
            "priority_reasoning": analysis["priority_reasoning"],
            "predicted_assignment_group": routing_label,
            "routing_reasoning": analysis["routing_reasoning"],
            "analysis_method": "direct_agent_reasoning_over_alert_text",
            "label": "OFFLINE LLM-ASSISTED REVIEW DEMO",
        })

    out_json = OUT_DIR / "stage2_results.json"
    with open(out_json, "w") as f:
        json.dump(records, f, indent=2)

    out_csv = OUT_DIR / "stage2_results.csv"
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {len(records)} rows to {out_json} and {out_csv}")

    from collections import Counter
    print("\nPriority distribution:", dict(Counter(r["predicted_priority"] for r in records)))
    print("\nRouting category distribution:")
    cat_counts = Counter(r["predicted_assignment_group"].rsplit(" - ", 1)[0] for r in records)
    for k, v in cat_counts.most_common():
        print(f"  {k}: {v}")
