"""
Synthetic telemetry subpackage for Stage 4 scenario-driven benchmark evaluation.
"""

from alert_management.stage4_analysis.telemetry.synthetic.manifest import ScenarioEvaluationManifest
from alert_management.stage4_analysis.telemetry.synthetic.scenarios import ScenarioSpec, get_scenario_catalog
from alert_management.stage4_analysis.telemetry.synthetic.generator import SyntheticTelemetryGenerator, ScenarioRun
from alert_management.stage4_analysis.telemetry.synthetic.provider_adapter import (
    ScenarioLogProvider,
    ScenarioMetricProvider,
    ScenarioTraceProvider,
)
from alert_management.stage4_analysis.telemetry.synthetic.evaluator import (
    ScenarioEvaluator,
    ScenarioEvaluationResult,
)

__all__ = [
    "ScenarioEvaluationManifest",
    "ScenarioSpec",
    "get_scenario_catalog",
    "SyntheticTelemetryGenerator",
    "ScenarioRun",
    "ScenarioLogProvider",
    "ScenarioMetricProvider",
    "ScenarioTraceProvider",
    "ScenarioEvaluator",
    "ScenarioEvaluationResult",
]
