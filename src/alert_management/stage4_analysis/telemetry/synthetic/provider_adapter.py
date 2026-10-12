"""
Scenario Telemetry Provider Adapters.

Connects a generated ScenarioRun to the abstract LogProvider, MetricProvider,
and TraceProvider interfaces consumed by Stage4Pipeline.
"""

from typing import List, Optional
from datetime import datetime

from alert_management.stage4_analysis.schemas import (
    LogRecord,
    MetricRecord,
    TraceSpan,
    IncidentContext,
)
from alert_management.stage4_analysis.telemetry.interfaces import (
    LogProvider,
    MetricProvider,
    TraceProvider,
)
from alert_management.stage4_analysis.telemetry.synthetic.generator import ScenarioRun


class ScenarioLogProvider(LogProvider):
    """LogProvider implementation backed by a ScenarioRun."""

    def __init__(self, scenario_run: ScenarioRun):
        self.scenario_run = scenario_run

    def get_logs(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None,
        levels: List[str] = None
    ) -> List[LogRecord]:
        logs = [
            l for l in self.scenario_run.logs
            if start_time <= l.timestamp <= end_time
        ]

        if components:
            matched = [l for l in logs if l.component in components]
            if matched:
                logs = matched

        if levels:
            logs = [l for l in logs if l.level in levels]

        return logs


class ScenarioMetricProvider(MetricProvider):
    """MetricProvider implementation backed by a ScenarioRun."""

    def __init__(self, scenario_run: ScenarioRun):
        self.scenario_run = scenario_run

    def get_metrics(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None,
        metric_names: List[str] = None
    ) -> List[MetricRecord]:
        metrics = [
            m for m in self.scenario_run.metrics
            if start_time <= m.timestamp <= end_time
        ]

        if components:
            matched = [m for m in metrics if m.component in components]
            if matched:
                metrics = matched

        if metric_names:
            metrics = [m for m in metrics if m.metric_name in metric_names]

        return metrics


class ScenarioTraceProvider(TraceProvider):
    """TraceProvider implementation backed by a ScenarioRun."""

    def __init__(self, scenario_run: ScenarioRun):
        self.scenario_run = scenario_run

    def get_traces(
        self,
        context: IncidentContext,
        start_time: datetime,
        end_time: datetime,
        components: List[str] = None
    ) -> List[TraceSpan]:
        traces = [
            t for t in self.scenario_run.traces
            if start_time <= t.start_time <= end_time
        ]

        if components:
            matched = [t for t in traces if t.component in components]
            if matched:
                traces = matched

        return traces
