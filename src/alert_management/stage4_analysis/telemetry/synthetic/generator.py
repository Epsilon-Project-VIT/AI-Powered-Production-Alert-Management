"""
Synthetic Telemetry Generator.

Generates coherent multi-modal telemetry (logs, metrics, traces, topology)
with shared clocks, fault windows, and trace-context correlation.

Ground-Truth Isolation Invariant:
All runtime telemetry records (LogRecord, MetricRecord, TraceSpan) carry
explicit `source_type=MOCK` and `is_mock=True` provenance. Ground-truth fault
labels are stored ONLY in the isolated ScenarioEvaluationManifest object.
"""

import hashlib
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from alert_management.stage4_analysis.schemas import (
    IncidentContext,
    LogRecord,
    MetricRecord,
    TraceSpan,
    SourceType,
    DiagnosisStatus,
)
from alert_management.stage4_analysis.telemetry.synthetic.manifest import ScenarioEvaluationManifest
from alert_management.stage4_analysis.telemetry.synthetic.scenarios import ScenarioSpec


def _stable_hash_int(key: str, modulus: int = 90000, offset: int = 10000) -> int:
    """Generate a deterministic integer from sha256, independent of process Python hash seed."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulus + offset


class ScenarioRun(BaseModel if False else object):
    """Container for a generated synthetic scenario run."""
    def __init__(
        self,
        spec: ScenarioSpec,
        context: IncidentContext,
        logs: List[LogRecord],
        metrics: List[MetricRecord],
        traces: List[TraceSpan],
        topology: Dict[str, List[str]],
        manifest: ScenarioEvaluationManifest
    ):
        self.spec = spec
        self.context = context
        self.logs = logs
        self.metrics = metrics
        self.traces = traces
        self.topology = topology
        self.manifest = manifest


class SyntheticTelemetryGenerator:
    """
    Generator for multi-modal scenario-driven synthetic telemetry.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed

    def generate_scenario_run(
        self,
        spec: ScenarioSpec,
        base_time: Optional[datetime] = None,
        seed_override: Optional[int] = None
    ) -> ScenarioRun:
        """
        Generate a complete ScenarioRun given a ScenarioSpec.
        """
        run_seed = seed_override if seed_override is not None else (self.seed + _stable_hash_int(spec.scenario_id, 100000, 0))
        rng = random.Random(run_seed)

        if base_time is None:
            base_time = datetime(2026, 10, 10, 14, 0, 0)

        incident_start = base_time
        incident_end = base_time + timedelta(minutes=spec.fault_duration_minutes)
        diagnostic_start = base_time - timedelta(minutes=30)
        diagnostic_end = base_time + timedelta(minutes=30)

        # 1. Build IncidentContext with opaque synthetic IDs (stable across processes, no fault/scenario leakage)
        synth_id = _stable_hash_int(spec.scenario_id, 90000, 10000)
        context = IncidentContext(
            incident_id=f"INC-SYNTH-{synth_id}",
            client=spec.client,
            alert_ids=[f"ALT-SYNTH-{synth_id}-01", f"ALT-SYNTH-{synth_id}-02"],
            primary_alert_id=f"ALT-SYNTH-{synth_id}-01",
            incident_start=incident_start,
            incident_end=incident_end,
            alert_count=2,
            services=["elb", "application", "database", "mulesoft", "message_queue", "extract_service", "worker_service"],
            components=["elb", "application", "database", "mulesoft", "message_queue", "extract_service", "worker_service"],
            normalized_descriptions=[
                f"Service degradation symptom reported for {spec.client}",
                "Elevated latency and error rate detected across service endpoints"
            ],
            diagnostic_start=diagnostic_start,
            diagnostic_end=diagnostic_end
        )

        # 2. Build Service Topology Graph
        topology = {
            "elb": ["application"],
            "application": ["mulesoft", "database", "message_queue", "extract_service"],
            "mulesoft": ["database"],
            "message_queue": ["worker_service"],
            "worker_service": ["database"],
        }

        # 3. Generate Coherent Telemetry
        logs: List[LogRecord] = []
        metrics: List[MetricRecord] = []
        traces: List[TraceSpan] = []

        if spec.include_traces:
            traces = self._generate_traces(spec, context, diagnostic_start, diagnostic_end, rng)

        if spec.include_logs:
            logs = self._generate_logs(spec, context, diagnostic_start, diagnostic_end, traces, rng)

        if spec.include_metrics:
            metrics = self._generate_metrics(spec, context, diagnostic_start, diagnostic_end, rng)

        # 4. Build Evaluation-Only Manifest (ISOLATED from runtime telemetry)
        manifest = ScenarioEvaluationManifest(
            scenario_id=spec.scenario_id,
            scenario_type=spec.scenario_type,
            variant=spec.variant,
            expected_root_cause_component=spec.primary_component,
            expected_failure_type=spec.failure_type,
            expected_diagnosis_mode=spec.expected_diagnosis_mode,
            expected_supporting_signals=[spec.primary_component, spec.failure_type],
            fault_onset=incident_start,
            fault_recovery=incident_end,
            is_evaluation_only=True
        )

        return ScenarioRun(
            spec=spec,
            context=context,
            logs=logs,
            metrics=metrics,
            traces=traces,
            topology=topology,
            manifest=manifest
        )

    def _generate_traces(
        self,
        spec: ScenarioSpec,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        rng: random.Random
    ) -> List[TraceSpan]:
        traces: List[TraceSpan] = []
        duration_sec = (end_time - start_time).total_seconds()
        num_traces = 15  # Bounded count per scenario

        for i in range(num_traces):
            offset = rng.uniform(0, duration_sec)
            t_start = start_time + timedelta(seconds=offset)

            is_in_fault = (context.incident_start <= t_start <= (context.incident_end or context.incident_start))
            trace_id = f"synth_trace_{rng.randint(100000, 999999)}"

            # Chain: elb -> application -> primary_component
            root_span_id = f"synth_span_root_{rng.randint(1000, 9999)}"
            app_span_id = f"synth_span_app_{rng.randint(1000, 9999)}"
            comp_span_id = f"synth_span_comp_{rng.randint(1000, 9999)}"

            is_error = is_in_fault and (spec.variant != "insufficient" or rng.random() < 0.3)

            comp_duration = rng.uniform(500, 3000) if is_error else rng.uniform(20, 80)
            app_duration = comp_duration + rng.uniform(20, 100)
            root_duration = app_duration + rng.uniform(10, 50)

            if spec.primary_component == "elb":
                root_status = "error" if is_error else "ok"
                app_status = "error" if (is_error and spec.variant == "ambiguous") else "ok"
                comp_status = "ok"
            else:
                comp_status = "error" if is_error else "ok"
                app_status = "error" if is_error else "ok"
                root_status = "error" if is_error else "ok"

            # Root span (elb)
            traces.append(TraceSpan(
                span_id=root_span_id,
                parent_span_id=None,
                trace_id=trace_id,
                component="elb",
                operation="http_route",
                start_time=t_start,
                end_time=t_start + timedelta(milliseconds=root_duration),
                duration_ms=round(root_duration, 2),
                status=root_status,
                source_type=SourceType.MOCK,
                is_mock=True
            ))

            # App span
            traces.append(TraceSpan(
                span_id=app_span_id,
                parent_span_id=root_span_id,
                trace_id=trace_id,
                component="application",
                operation="handle_request",
                start_time=t_start + timedelta(milliseconds=5),
                end_time=t_start + timedelta(milliseconds=app_duration),
                duration_ms=round(app_duration, 2),
                status=app_status,
                source_type=SourceType.MOCK,
                is_mock=True
            ))

            # Primary component span
            domain_ops = {
                "database": "db_query_execute",
                "application": "handle_http_request",
                "elb": "http_route",
                "message_queue": "consume_queue_message",
                "worker_service": "process_worker_task",
                "mulesoft": "esb_flow_execute",
                "extract_service": "generate_extract_report",
            }
            comp_op = domain_ops.get(spec.primary_component, "service_operation_execute")

            traces.append(TraceSpan(
                span_id=comp_span_id,
                parent_span_id=app_span_id,
                trace_id=trace_id,
                component=spec.primary_component,
                operation=comp_op,
                start_time=t_start + timedelta(milliseconds=10),
                end_time=t_start + timedelta(milliseconds=comp_duration),
                duration_ms=round(comp_duration, 2),
                status=comp_status,
                source_type=SourceType.MOCK,
                is_mock=True
            ))

        return sorted(traces, key=lambda s: s.start_time)

    def _generate_logs(
        self,
        spec: ScenarioSpec,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        traces: List[TraceSpan],
        rng: random.Random
    ) -> List[LogRecord]:
        logs: List[LogRecord] = []
        duration_sec = (end_time - start_time).total_seconds()
        log_count = 35 if spec.log_volume == "dense" else (10 if spec.log_volume == "sparse" else 20)

        # Fault error messages per scenario type
        messages = {
            "db_pool_exhaustion": [
                "Connection pool exhausted: 0/100 available connections",
                "Timeout acquiring database connection after 5000ms",
                "DBPoolSaturation: Active connections reached hard limit 100/100"
            ],
            "api_lb_failure": [
                "503 Service Unavailable: no healthy upstream targets in target group",
                "Load balancer target health check failed for application backend",
                "HTTP 502 Bad Gateway: upstream load balancer target error"
            ],
            "batch_job_failure": [
                "Fatal: Batch process terminated with unhandled exception",
                "BatchJobError: Task runner failed with exit code 137 (OutOfMemory)",
                "Execution failed in batch processing pipeline"
            ],
            "sla_delivery_delay": [
                "SLA Warning: Extract delivery window exceeded threshold (3600s)",
                "Report delivery pipeline stalled: SLA breach imminent",
                "Delay threshold exceeded for client scheduled export"
            ],
            "queue_backlog": [
                "Queue capacity warning: 50,000 unconsumed messages in queue",
                "Worker starvation: Consumer lag exceeded 120,000ms",
                "Queue overflow warning: message processing worker backlog"
            ],
            "cpu_memory_pressure": [
                "Resource Exhaustion: CPU utilization sustained at 99.4%",
                "OutOfMemoryError: Java heap space capacity exceeded 95%",
                "Long GC pause detected: 3400ms duration"
            ],
            "network_degradation": [
                "SocketTimeoutException: Read timed out after 10000ms",
                "Network degradation: High packet loss (18.5%) across inter-service link",
                "TCP retransmit spike detected on interface eth0"
            ],
            "ambiguous_evidence": [
                "WARN: Intermittent latency increase in database query execution",
                "WARN: Moderate CPU utilization increase on application host",
                "WARN: Transient network socket timeout"
            ]
        }

        comp_messages = messages.get(spec.scenario_type, ["Service component error encountered"])

        for i in range(log_count):
            offset = rng.uniform(0, duration_sec)
            l_time = start_time + timedelta(seconds=offset)

            is_in_fault = (context.incident_start <= l_time <= (context.incident_end or context.incident_start))

            # Select trace_id for correlation if error during fault
            linked_trace = traces[i % len(traces)] if traces else None
            trace_id = linked_trace.trace_id if linked_trace else None
            span_id = linked_trace.span_id if linked_trace else None

            if is_in_fault:
                level = "ERROR"
                component = spec.primary_component
                msg = rng.choice(comp_messages)
            else:
                level = rng.choice(["INFO", "DEBUG"])
                component = rng.choice(["application", "database", "elb"])
                msg = f"{component} service operating within normal parameters"

            # Ambiguous variant: inject competing noise logs from competing component
            if spec.variant == "ambiguous" and is_in_fault and rng.random() < 0.4 and spec.competing_component:
                component = spec.competing_component
                msg = f"Competing error signal in {component}: secondary component warning"

            logs.append(LogRecord(
                log_id=f"synth_log_{rng.randint(100000, 999999)}",
                timestamp=l_time,
                component=component,
                level=level,
                message=msg,
                source_type=SourceType.MOCK,
                is_mock=True,
                metadata={
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "client": context.client,
                }
            ))

        return sorted(logs, key=lambda l: l.timestamp)

    def _generate_metrics(
        self,
        spec: ScenarioSpec,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        rng: random.Random
    ) -> List[MetricRecord]:
        metrics: List[MetricRecord] = []
        duration_sec = (end_time - start_time).total_seconds()
        sample_interval = 60  # 1 minute points
        num_samples = int(duration_sec / sample_interval)

        metric_names = {
            "db_pool_exhaustion": ("db_connection_pool_utilization", "percent", 55.0, 99.0),
            "api_lb_failure": ("elb_healthy_targets", "count", 10.0, 0.0),
            "batch_job_failure": ("batch_processing_status", "status", 1.0, 0.0),
            "sla_delivery_delay": ("extract_processing_time_sec", "seconds", 120.0, 3600.0),
            "queue_backlog": ("queue_depth_count", "messages", 50.0, 50000.0),
            "cpu_memory_pressure": ("app_cpu_utilization", "percent", 35.0, 99.0),
            "network_degradation": ("network_packet_loss_pct", "percent", 0.1, 18.5),
            "ambiguous_evidence": ("app_response_time", "milliseconds", 150.0, 800.0),
        }

        m_name, unit, baseline, fault_val = metric_names.get(
            spec.scenario_type, ("component_health_score", "score", 100.0, 20.0)
        )

        for i in range(num_samples):
            m_time = start_time + timedelta(seconds=i * sample_interval)
            is_in_fault = (context.incident_start <= m_time <= (context.incident_end or context.incident_start))

            if is_in_fault:
                val = fault_val + rng.gauss(0, abs(fault_val * 0.05) + 0.1)
                is_anom = True
            else:
                val = baseline + rng.gauss(0, abs(baseline * 0.05) + 0.1)
                is_anom = False

            if unit == "percent":
                val = max(0.0, min(100.0, val))

            metrics.append(MetricRecord(
                metric_id=f"synth_metric_{rng.randint(100000, 999999)}",
                timestamp=m_time,
                metric_name=m_name,
                component=spec.primary_component,
                value=round(val, 2),
                unit=unit,
                source_type=SourceType.MOCK,
                is_mock=True,
                metadata={"is_anomalous": is_anom}
            ))

            # Ambiguous variant: inject competing metric series for competing component across window
            if spec.variant == "ambiguous" and spec.competing_component:
                comp_metric_name = "app_response_time" if spec.competing_component == "application" else "service_health_score"
                comp_unit = "milliseconds" if comp_metric_name == "app_response_time" else "score"
                comp_baseline = 150.0 if comp_unit == "milliseconds" else 100.0
                comp_fault = 850.0 if comp_unit == "milliseconds" else 15.0
                
                c_val = (comp_fault if is_in_fault else comp_baseline) + rng.gauss(0, 5.0)
                metrics.append(MetricRecord(
                    metric_id=f"synth_metric_comp_{rng.randint(100000, 999999)}",
                    timestamp=m_time,
                    metric_name=comp_metric_name,
                    component=spec.competing_component,
                    value=round(max(0.0, c_val), 2),
                    unit=comp_unit,
                    source_type=SourceType.MOCK,
                    is_mock=True,
                    metadata={"is_anomalous": is_in_fault}
                ))

        return sorted(metrics, key=lambda m: m.timestamp)


