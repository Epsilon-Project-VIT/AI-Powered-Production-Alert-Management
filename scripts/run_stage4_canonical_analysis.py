"""
Run Stage 4 RCA Analysis on 151 Canonical Incident Groups.

Analyzes all incident groups from Stage 3 using Stage 2 canonical predictions
(Alert Type, Severity, Business Impact).

Outputs:
- JSON file with all RCA results
- CSV summary with key metrics
- Statistics and evaluation report
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_management.stage3_correlation.schemas import IncidentGroup
from alert_management.stage2_classification.schemas import EnrichedAlert, ClassificationResult
from alert_management.stage4_analysis.pipeline import Stage4Pipeline
from alert_management.stage4_analysis.schemas import RCAResult, DiagnosisStatus
from alert_management.stage4_analysis.telemetry.mock_log_provider import MockLogProvider
from alert_management.stage4_analysis.telemetry.mock_metric_provider import MockMetricProvider
from alert_management.stage4_analysis.telemetry.mock_trace_provider import MockTraceProvider
from alert_management.stage4_analysis.reasoning.mock_reasoning_provider import MockReasoningProvider


def load_stage3_incidents(path: Path) -> List[Dict[str, Any]]:
    """Load Stage 3 incident groups from JSON."""
    print(f"📂 Loading Stage 3 incident groups from: {path}")
    with open(path, 'r') as f:
        incidents = json.load(f)
    print(f"✅ Loaded {len(incidents)} incident groups")
    return incidents


def load_stage2_predictions(base_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load Stage 2 canonical predictions by alert_id."""
    print(f"📂 Loading Stage 2 canonical predictions from: {base_path}")
    
    predictions = {}
    
    for filename, key in [
        ("alert_type_predictions.csv", "alert_type"),
        ("severity_predictions.csv", "severity"),
        ("business_impact_predictions.csv", "business_impact"),
    ]:
        csv_path = base_path / filename
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            print(f"   ✅ Loaded {len(df)} {key} predictions")
            for _, row in df.iterrows():
                alert_id = str(row["alert_id"])
                if alert_id not in predictions:
                    predictions[alert_id] = {}
                predictions[alert_id][key] = {
                    "label": row["predicted_label"],
                    "confidence": row["confidence"]
                }
    
    print(f"✅ Total alerts with predictions: {len(predictions)}")
    return predictions



def load_raw_alerts(excel_path: Path) -> pd.DataFrame:
    """Load raw alerts from Excel."""
    print(f"📂 Loading raw alerts from: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name='Sheet1')
    print(f"✅ Loaded {len(df)} raw alerts")
    return df


def create_enriched_alerts(
    raw_df: pd.DataFrame,
    stage2_predictions: Dict[str, Dict[str, Any]]
) -> Dict[str, EnrichedAlert]:
    """Create enriched alerts with Stage 2 canonical predictions."""
    print(f"🔧 Creating enriched alerts with Stage 2 predictions...")
    
    enriched_alerts = {}
    
    for idx, row in raw_df.iterrows():
        alert_id = row['Number']
        
        # Get Stage 2 predictions for this alert (by alert_id)
        predictions = stage2_predictions.get(alert_id, {})

        
        # Create classification results
        alert_type = None
        severity = None
        business_impact = None
        
        if 'alert_type' in predictions:
            alert_type = ClassificationResult(
                label=predictions['alert_type']['label'],
                confidence=predictions['alert_type']['confidence']
            )
        
        if 'severity' in predictions:
            severity = ClassificationResult(
                label=predictions['severity']['label'],
                confidence=predictions['severity']['confidence']
            )
        
        if 'business_impact' in predictions:
            business_impact = ClassificationResult(
                label=predictions['business_impact']['label'],
                confidence=predictions['business_impact']['confidence']
            )
        
        # Create enriched alert
        enriched_alert = EnrichedAlert(
            alert_id=alert_id,
            created_at=pd.to_datetime(row['Created']),
            client=row['Impacted client'],
            raw_description=row['Short description'],
            normalized_description=str(row.get('normalized_description', row['Short description'])).lower(),
            metadata={
                'priority': row.get('Priority', 'UNKNOWN'),
                'assignment_group': row.get('Assignment group', 'UNKNOWN'),
                'state': row.get('Active', 'UNKNOWN')
            },
            alert_type=alert_type,
            severity=severity,
            business_impact=business_impact,
            priority=ClassificationResult(label=row.get('Priority', 'UNKNOWN'), confidence=0.5),
            routing=ClassificationResult(label=row.get('Assignment group', 'UNKNOWN'), confidence=0.5)
        )
        
        enriched_alerts[alert_id] = enriched_alert
    
    print(f"✅ Created {len(enriched_alerts)} enriched alerts")
    return enriched_alerts


def convert_to_incident_group(incident_dict: Dict[str, Any]) -> IncidentGroup:
    """Convert incident dict to IncidentGroup schema."""
    return IncidentGroup(
        incident_id=incident_dict['incident_id'],
        alert_ids=incident_dict['alert_ids'],
        primary_alert_id=incident_dict['alert_ids'][0],
        client=incident_dict['client'],
        incident_start=datetime.fromisoformat(incident_dict['incident_start']),
        incident_end=datetime.fromisoformat(incident_dict['incident_end']) if incident_dict.get('incident_end') else datetime.fromisoformat(incident_dict['incident_start']),
        alert_count=incident_dict['alert_count'],
        normalized_signature=incident_dict.get('normalized_signature', ''),
        correlation_method=incident_dict.get('correlation_method', 'unknown'),
        avg_correlation_score=incident_dict.get('avg_correlation_score', 0.0)
    )


def analyze_all_incidents(
    incidents: List[Dict[str, Any]],
    enriched_alerts: Dict[str, EnrichedAlert],
    pipeline: Stage4Pipeline
) -> List[RCAResult]:
    """Run Stage 4 analysis on all incidents."""
    print(f"\n{'=' * 80}")
    print(f"RUNNING STAGE 4 ANALYSIS ON {len(incidents)} INCIDENT GROUPS")
    print(f"{'=' * 80}\n")
    
    results = []
    
    for i, incident_dict in enumerate(incidents, 1):
        incident_id = incident_dict['incident_id']
        
        if i % 10 == 0:
            print(f"Progress: {i}/{len(incidents)} incidents analyzed...")
        
        try:
            # Convert to IncidentGroup
            incident_group = convert_to_incident_group(incident_dict)
            
            # Get enriched alerts for this incident
            incident_alerts = []
            for alert_id in incident_group.alert_ids:
                if alert_id in enriched_alerts:
                    incident_alerts.append(enriched_alerts[alert_id])
            
            if not incident_alerts:
                print(f"⚠️  Warning: No enriched alerts found for {incident_id}")
                continue
            
            # Run Stage 4 analysis
            rca_result, support_msg, stakeholder_msg = pipeline.analyze_incident(
                incident_group,
                incident_alerts
            )
            
            results.append(rca_result)
            
        except Exception as e:
            print(f"❌ Error analyzing {incident_id}: {e}")
            continue
    
    print(f"\n✅ Analyzed {len(results)} incident groups successfully")
    return results


def compute_statistics(results: List[RCAResult]) -> Dict[str, Any]:
    """Compute statistics for RCA results."""
    print(f"\n📊 Computing statistics...")
    
    stats = {
        'total_incidents': len(results),
        'diagnosis_status': {
            'sufficient_evidence': 0,
            'insufficient_evidence': 0,
            'ambiguous': 0
        },
        'evidence_stats': {
            'total_evidence_items': 0,
            'avg_evidence_per_incident': 0.0,
            'mock_evidence_count': 0,
            'real_evidence_count': 0,
            'model_prediction_count': 0
        },
        'root_cause_stats': {
            'incidents_with_root_cause': 0,
            'incidents_without_root_cause': 0,
            'avg_confidence': 0.0,
            'components': {},
            'failure_types': {}
        },
        'action_stats': {
            'total_actions': 0,
            'avg_actions_per_incident': 0.0,
            'requires_human_approval': 0,
            'action_types': {
                'diagnostic': 0,
                'remediation': 0,
                'escalation': 0
            }
        },
        'alternative_hypotheses_stats': {
            'incidents_with_alternatives': 0,
            'avg_alternatives_per_incident': 0.0
        }
    }
    
    total_evidence = 0
    total_confidence = 0.0
    incidents_with_root_cause = 0
    total_actions = 0
    total_alternatives = 0
    
    for result in results:
        # Diagnosis status
        stats['diagnosis_status'][result.diagnosis_status.value] += 1
        
        # Evidence
        evidence_count = len(result.evidence)
        total_evidence += evidence_count
        
        for evidence in result.evidence:
            if evidence.is_mock:
                stats['evidence_stats']['mock_evidence_count'] += 1
            else:
                stats['evidence_stats']['real_evidence_count'] += 1
            
            if evidence.source_type.value == 'model_prediction':
                stats['evidence_stats']['model_prediction_count'] += 1
        
        # Root cause
        if result.probable_root_cause:
            incidents_with_root_cause += 1
            stats['root_cause_stats']['incidents_with_root_cause'] += 1
            total_confidence += result.probable_root_cause.confidence
            
            # Track components and failure types
            component = result.probable_root_cause.component
            failure_type = result.probable_root_cause.failure_type
            
            stats['root_cause_stats']['components'][component] = \
                stats['root_cause_stats']['components'].get(component, 0) + 1
            stats['root_cause_stats']['failure_types'][failure_type] = \
                stats['root_cause_stats']['failure_types'].get(failure_type, 0) + 1
        else:
            stats['root_cause_stats']['incidents_without_root_cause'] += 1
        
        # Actions
        action_count = len(result.recommended_actions)
        total_actions += action_count
        
        for action in result.recommended_actions:
            stats['action_stats']['action_types'][action.action_type.value] += 1
            if action.requires_human_approval:
                stats['action_stats']['requires_human_approval'] += 1
        
        # Alternatives
        alt_count = len(result.alternative_hypotheses)
        total_alternatives += alt_count
        if alt_count > 0:
            stats['alternative_hypotheses_stats']['incidents_with_alternatives'] += 1
    
    # Compute averages
    if len(results) > 0:
        stats['evidence_stats']['total_evidence_items'] = total_evidence
        stats['evidence_stats']['avg_evidence_per_incident'] = total_evidence / len(results)
        stats['action_stats']['total_actions'] = total_actions
        stats['action_stats']['avg_actions_per_incident'] = total_actions / len(results)
        stats['alternative_hypotheses_stats']['avg_alternatives_per_incident'] = total_alternatives / len(results)
    
    if incidents_with_root_cause > 0:
        stats['root_cause_stats']['avg_confidence'] = total_confidence / incidents_with_root_cause
    
    return stats


def save_results(
    results: List[RCAResult],
    stats: Dict[str, Any],
    output_dir: Path
):
    """Save RCA results to JSON and CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Saving results to: {output_dir}")
    
    # Save full JSON results
    json_path = output_dir / "rca_results.json"
    with open(json_path, 'w') as f:
        json_data = [result.model_dump(mode='json') for result in results]
        json.dump(json_data, f, indent=2, default=str)
    print(f"   ✅ Saved JSON: {json_path}")
    
    # Save CSV summary
    csv_path = output_dir / "rca_summary.csv"
    csv_data = []
    
    for result in results:
        row = {
            'incident_id': result.incident_id,
            'diagnosis_status': result.diagnosis_status.value,
            'root_cause_component': result.probable_root_cause.component if result.probable_root_cause else 'NONE',
            'root_cause_failure_type': result.probable_root_cause.failure_type if result.probable_root_cause else 'NONE',
            'root_cause_confidence': result.probable_root_cause.confidence if result.probable_root_cause else 0.0,
            'evidence_count': len(result.evidence),
            'mock_evidence_count': sum(1 for e in result.evidence if e.is_mock),
            'alternative_hypotheses_count': len(result.alternative_hypotheses),
            'recommended_actions_count': len(result.recommended_actions),
            'human_review_required': result.human_review_required,
            'telemetry_is_mock': result.telemetry_is_mock,
            'reasoning_provider': result.reasoning_provider
        }
        csv_data.append(row)
    
    df = pd.DataFrame(csv_data)
    df.to_csv(csv_path, index=False)
    print(f"   ✅ Saved CSV: {csv_path}")
    
    # Save statistics
    stats_path = output_dir / "rca_statistics.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    print(f"   ✅ Saved statistics: {stats_path}")


def print_report(stats: Dict[str, Any]):
    """Print comprehensive report."""
    print(f"\n{'=' * 80}")
    print("STAGE 4 RCA ANALYSIS - FINAL REPORT")
    print(f"{'=' * 80}\n")
    
    # Overall statistics
    print(f"📊 OVERALL STATISTICS")
    print(f"   Total Incidents Analyzed: {stats['total_incidents']}")
    print()
    
    # Diagnosis status
    print(f"🎯 DIAGNOSIS STATUS")
    print(f"   Sufficient Evidence: {stats['diagnosis_status']['sufficient_evidence']} ({stats['diagnosis_status']['sufficient_evidence']/stats['total_incidents']*100:.1f}%)")
    print(f"   Insufficient Evidence: {stats['diagnosis_status']['insufficient_evidence']} ({stats['diagnosis_status']['insufficient_evidence']/stats['total_incidents']*100:.1f}%)")
    print(f"   Ambiguous: {stats['diagnosis_status']['ambiguous']} ({stats['diagnosis_status']['ambiguous']/stats['total_incidents']*100:.1f}%)")
    print()
    
    # Evidence statistics
    print(f"🔍 EVIDENCE STATISTICS")
    print(f"   Total Evidence Items: {stats['evidence_stats']['total_evidence_items']}")
    print(f"   Avg Evidence per Incident: {stats['evidence_stats']['avg_evidence_per_incident']:.2f}")
    print(f"   Mock Evidence: {stats['evidence_stats']['mock_evidence_count']} ({stats['evidence_stats']['mock_evidence_count']/stats['evidence_stats']['total_evidence_items']*100:.1f}%)")
    print(f"   Real Evidence: {stats['evidence_stats']['real_evidence_count']} ({stats['evidence_stats']['real_evidence_count']/stats['evidence_stats']['total_evidence_items']*100:.1f}%)")
    print(f"   Model Predictions: {stats['evidence_stats']['model_prediction_count']}")
    print()
    
    # Root cause statistics
    print(f"🎯 ROOT CAUSE STATISTICS")
    print(f"   Incidents with Root Cause: {stats['root_cause_stats']['incidents_with_root_cause']} ({stats['root_cause_stats']['incidents_with_root_cause']/stats['total_incidents']*100:.1f}%)")
    print(f"   Incidents without Root Cause: {stats['root_cause_stats']['incidents_without_root_cause']}")
    print(f"   Avg Confidence (when available): {stats['root_cause_stats']['avg_confidence']:.2%}")
    print()
    
    # Top components
    if stats['root_cause_stats']['components']:
        print(f"   Top Components:")
        sorted_components = sorted(
            stats['root_cause_stats']['components'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        for component, count in sorted_components[:10]:
            print(f"      - {component}: {count}")
        print()
    
    # Top failure types
    if stats['root_cause_stats']['failure_types']:
        print(f"   Top Failure Types:")
        sorted_failures = sorted(
            stats['root_cause_stats']['failure_types'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        for failure_type, count in sorted_failures[:10]:
            print(f"      - {failure_type}: {count}")
        print()
    
    # Action statistics
    print(f"💡 RECOMMENDED ACTIONS")
    print(f"   Total Actions: {stats['action_stats']['total_actions']}")
    print(f"   Avg Actions per Incident: {stats['action_stats']['avg_actions_per_incident']:.2f}")
    print(f"   Require Human Approval: {stats['action_stats']['requires_human_approval']}")
    print(f"   By Type:")
    print(f"      - Diagnostic: {stats['action_stats']['action_types']['diagnostic']}")
    print(f"      - Remediation: {stats['action_stats']['action_types']['remediation']}")
    print(f"      - Escalation: {stats['action_stats']['action_types']['escalation']}")
    print()
    
    # Alternative hypotheses
    print(f"🔄 ALTERNATIVE HYPOTHESES")
    print(f"   Incidents with Alternatives: {stats['alternative_hypotheses_stats']['incidents_with_alternatives']} ({stats['alternative_hypotheses_stats']['incidents_with_alternatives']/stats['total_incidents']*100:.1f}%)")
    print(f"   Avg Alternatives per Incident: {stats['alternative_hypotheses_stats']['avg_alternatives_per_incident']:.2f}")
    print()
    
    print(f"{'=' * 80}")
    print("✅ STAGE 4 ANALYSIS COMPLETE")
    print(f"{'=' * 80}\n")


def main():
    """Main execution."""
    print(f"{'=' * 80}")
    print("STAGE 4 RCA ANALYSIS - 151 CANONICAL INCIDENT GROUPS")
    print(f"{'=' * 80}\n")
    
    # Paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    
    stage3_incidents_path = data_dir / "stage3_canonical_results" / "incident_groups.json"
    stage2_predictions_dir = data_dir / "stage2_models_canonical"
    raw_excel_path = data_dir / "raw" / "Data_Alert_Ticket_Segregation.xlsx"
    output_dir = data_dir / "stage4_canonical_results"
    
    # Load data
    incidents = load_stage3_incidents(stage3_incidents_path)
    stage2_predictions = load_stage2_predictions(stage2_predictions_dir)
    raw_df = load_raw_alerts(raw_excel_path)
    enriched_alerts = create_enriched_alerts(raw_df, stage2_predictions)
    
    # Initialize Stage 4 pipeline
    print(f"\n🔧 Initializing Stage 4 Pipeline...")
    pipeline = Stage4Pipeline(
        log_provider=MockLogProvider(),
        metric_provider=MockMetricProvider(),
        trace_provider=MockTraceProvider(),
        reasoning_provider=MockReasoningProvider()
    )
    print(f"✅ Pipeline initialized (using MOCK telemetry and reasoning)")
    
    # Run analysis
    results = analyze_all_incidents(incidents, enriched_alerts, pipeline)
    
    # Compute statistics
    stats = compute_statistics(results)
    
    # Save results
    save_results(results, stats, output_dir)
    
    # Print report
    print_report(stats)
    
    print(f"\n📂 Results saved to: {output_dir}")
    print(f"   - rca_results.json (full RCA results)")
    print(f"   - rca_summary.csv (summary table)")
    print(f"   - rca_statistics.json (statistics)")
    print()


if __name__ == "__main__":
    main()
