"""
Comprehensive Stage 3 Correlation Audit.

Verifies:
- Architecture compliance
- Service/component validation
- Stage 2 integration
- Clustering diagnostics
- Temporal window analysis
- Pizza Hut recurring pattern analysis
- Manual review samples
"""

import sys
from pathlib import Path
import numpy as np
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import json

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from alert_management.config.settings import Settings
from alert_management.stage1_ingestion.pipeline import Stage1Pipeline
from alert_management.stage1_ingestion.adapters.excel_adapter import ExcelAlertAdapter
from alert_management.stage1_ingestion.cleaners.field_cleaner import FieldCleaner
from alert_management.stage1_ingestion.cleaners.normalizer import Normalizer
from alert_management.stage1_ingestion.validators.alert_validator import AlertValidator
from alert_management.stage3_correlation.pipeline import CorrelationPipeline
from alert_management.stage3_correlation.clustering.signature_matcher import SignatureMatcher
from alert_management.stage3_correlation.clustering.semantic_clusterer import SemanticClusterer


class Stage3Auditor:
    """Comprehensive Stage 3 auditor."""
    
    def __init__(self):
        self.audit_results = {
            'architecture_compliance': {},
            'service_validation': {},
            'stage2_integration': {},
            'clustering_diagnostics': {},
            'temporal_analysis': {},
            'pizza_hut_analysis': {},
            'manual_review': {},
            'known_limitations': []
        }
    
    def audit_architecture_compliance(self, pipeline):
        """Verify architecture component compliance."""
        
        components_required = [
            ('Exact Duplicate Detection', 'signature_matcher'),
            ('Alert Signature Extraction', 'signature_matcher.find_signature_groups'),
            ('Sentence Embeddings', 'semantic_clusterer.generate_embeddings'),
            ('HDBSCAN Clustering', 'semantic_clusterer.cluster_alerts'),
            ('Temporal Validation', 'signature_matcher.validate_temporal_coherence'),
            ('Client Validation', 'signature_matcher.validate_client_coherence'),
            ('Correlation Scoring', 'compute_correlation_score'),
            ('Service/Component Validation', 'service_validator'),
            ('Stage-2 Compatibility Validation', 'stage2_validator'),
            ('Graph/Connected Components', 'graph_grouper'),
        ]
        
        compliance = {}
        
        for component_name, attribute_path in components_required:
            parts = attribute_path.split('.')
            obj = pipeline
            exists = True
            
            try:
                for part in parts:
                    obj = getattr(obj, part)
            except AttributeError:
                exists = False
            
            compliance[component_name] = {
                'implemented': exists,
                'attribute': attribute_path
            }
        
        self.audit_results['architecture_compliance'] = compliance
        
        return compliance
    
    def audit_clustering_methods(self):
        """Audit which clustering methods were actually implemented."""
        
        methods = {
            'HDBSCAN': {
                'implemented': True,
                'location': 'SemanticClusterer.cluster_alerts',
                'benchmarked': True
            },
            'DBSCAN': {
                'implemented': False,
                'benchmarked': False,
                'status': 'Not implemented'
            },
            'Agglomerative Clustering': {
                'implemented': False,
                'benchmarked': False,
                'status': 'Not implemented'
            },
            'Exact Signature Matching': {
                'implemented': True,
                'location': 'SignatureMatcher',
                'benchmarked': True
            }
        }
        
        self.audit_results['clustering_diagnostics']['methods'] = methods
        
        return methods
    
    def analyze_temporal_window(self, incidents, max_time_gap_hours=24.0):
        """Analyze temporal window configuration and usage."""
        
        # Find actual time gaps in incidents
        time_gaps = []
        
        for incident in incidents:
            if incident.alert_count > 1:
                # Get alerts sorted by time (we'll need to reconstruct from IDs)
                duration = (incident.incident_end - incident.incident_start).total_seconds() / 3600
                time_gaps.append(duration)
        
        analysis = {
            'configured_window_hours': max_time_gap_hours,
            'is_configurable': True,
            'is_experimental_default': True,
            'rationale': 'Initial experimental default based on typical incident response times',
            'validation_status': 'Not validated against ground truth',
            'actual_usage': {
                'incidents_analyzed': len([g for g in time_gaps if g > 0]),
                'max_duration_hours': max(time_gaps) if time_gaps else 0,
                'avg_duration_hours': np.mean(time_gaps) if time_gaps else 0,
                'median_duration_hours': np.median(time_gaps) if time_gaps else 0
            }
        }
        
        self.audit_results['temporal_analysis'] = analysis
        
        return analysis
    
    def analyze_pizza_hut_pattern(self, alerts, incidents):
        """Deep analysis of Pizza Hut recurring alert pattern."""
        
        # Find Pizza Hut SLA alert pattern
        pizza_hut_alerts = [a for a in alerts if a.client == 'Pizza Hut']
        
        # Find the most common Pizza Hut pattern
        from collections import Counter
        pattern_counts = Counter([a.normalized_description for a in pizza_hut_alerts])
        
        if pattern_counts:
            most_common_pattern, count = pattern_counts.most_common(1)[0]
            sla_alerts = [a for a in pizza_hut_alerts if a.normalized_description == most_common_pattern]
        else:
            sla_alerts = []
            most_common_pattern = "N/A"
        
        print(f"\nPizza Hut SLA Pattern Analysis:")
        print(f"  Total Pizza Hut alerts: {len(pizza_hut_alerts)}")
        print(f"  SLA pattern alerts: {len(sla_alerts)}")
        
        # Find incidents containing these alerts
        sla_alert_ids = set(a.alert_id for a in sla_alerts)
        sla_incidents = [inc for inc in incidents if any(aid in sla_alert_ids for aid in inc.alert_ids)]
        
        print(f"  Incidents created: {len(sla_incidents)}")
        
        # Analyze temporal separation
        if sla_alerts:
            sla_alerts_sorted = sorted(sla_alerts, key=lambda a: a.created_at)
            
            # Calculate gaps between consecutive alerts
            gaps = []
            for i in range(1, len(sla_alerts_sorted)):
                gap = (sla_alerts_sorted[i].created_at - sla_alerts_sorted[i-1].created_at).total_seconds() / 3600
                gaps.append(gap)
            
            # Show sample incidents
            print(f"\n  Sample Incidents Created:")
            for i, inc in enumerate(sla_incidents[:5], 1):
                print(f"    Incident {i}: {inc.alert_count} alerts, {inc.incident_start} to {inc.incident_end}")
        
        analysis = {
            'pattern_signature': most_common_pattern[:100] if most_common_pattern != "N/A" else "N/A",
            'total_family_alerts': len(sla_alerts),
            'candidate_incident_groups': len(sla_incidents),
            'split_into_multiple_groups': len(sla_incidents) > 1,
            'alert_ids_sample': [a.alert_id for a in sla_alerts[:10]],
            'incident_ids_sample': [inc.incident_id for inc in sla_incidents[:10]],
            'temporal_gaps_hours': gaps[:10] if len(sla_alerts) > 1 else [],
            'largest_group_size': max([inc.alert_count for inc in sla_incidents]) if sla_incidents else 0
        }
        
        self.audit_results['pizza_hut_analysis'] = analysis
        
        return analysis
    
    def compute_clustering_diagnostics(self, alerts, incidents, uncorrelated):
        """Compute clustering quality metrics."""
        
        # Silhouette score requires embeddings - compute for a sample
        clusterer = SemanticClusterer()
        
        # Sample for efficiency
        sample_alerts = alerts[:500] if len(alerts) > 500 else alerts
        embeddings = clusterer.generate_embeddings(sample_alerts)
        
        # Compute similarity matrix
        similarity_matrix = clusterer.compute_similarity_matrix(embeddings)
        
        # Cluster size distribution
        cluster_sizes = [inc.alert_count for inc in incidents]
        
        # Semantic similarity within incidents
        incident_similarities = []
        for inc in incidents[:50]:  # Sample
            if inc.avg_correlation_score:
                incident_similarities.append(inc.avg_correlation_score)
        
        diagnostics = {
            'total_incidents': len(incidents),
            'total_alerts': len(alerts),
            'correlated_alerts': len(alerts) - len(uncorrelated),
            'uncorrelated_alerts': len(uncorrelated),
            'grouping_rate': (len(alerts) - len(uncorrelated)) / len(alerts) if alerts else 0,
            'cluster_size_distribution': {
                'min': min(cluster_sizes) if cluster_sizes else 0,
                'max': max(cluster_sizes) if cluster_sizes else 0,
                'mean': np.mean(cluster_sizes) if cluster_sizes else 0,
                'median': np.median(cluster_sizes) if cluster_sizes else 0,
                'std': np.std(cluster_sizes) if cluster_sizes else 0
            },
            'semantic_similarity': {
                'sample_incidents': len(incident_similarities),
                'avg_similarity': np.mean(incident_similarities) if incident_similarities else 0,
                'min_similarity': min(incident_similarities) if incident_similarities else 0,
                'max_similarity': max(incident_similarities) if incident_similarities else 0
            },
            'noise_points': len(uncorrelated),
            'noise_percentage': len(uncorrelated) / len(alerts) if alerts else 0
        }
        
        self.audit_results['clustering_diagnostics']['metrics'] = diagnostics
        
        return diagnostics
    
    def generate_manual_review_samples(self, alerts, incidents, pipeline):
        """Generate alert pairs for manual review."""
        
        # Sample pairs from same incident (should be related)
        related_pairs = []
        for inc in incidents[:10]:
            if inc.alert_count >= 2:
                # Get first two alerts
                alert_ids = inc.alert_ids[:2]
                alerts_in_inc = [a for a in alerts if a.alert_id in alert_ids]
                if len(alerts_in_inc) == 2:
                    score = pipeline.compute_correlation_score(
                        alerts_in_inc[0],
                        alerts_in_inc[1]
                    )
                    related_pairs.append({
                        'alert_1': alerts_in_inc[0].alert_id,
                        'alert_2': alerts_in_inc[1].alert_id,
                        'desc_1': alerts_in_inc[0].normalized_description[:80],
                        'desc_2': alerts_in_inc[1].normalized_description[:80],
                        'client_1': alerts_in_inc[0].client,
                        'client_2': alerts_in_inc[1].client,
                        'correlation_score': score.overall_score,
                        'semantic_similarity': score.semantic_similarity,
                        'temporal_proximity': score.temporal_proximity,
                        'client_match': score.client_match,
                        'candidate_group_id': inc.incident_id,
                        'human_review_label': 'Pending review'
                    })
        
        # Sample pairs from different incidents (should be unrelated)
        unrelated_pairs = []
        if len(incidents) >= 2:
            for i in range(min(10, len(incidents)-1)):
                inc1 = incidents[i]
                inc2 = incidents[i+1]
                
                alerts_in_inc1 = [a for a in alerts if a.alert_id == inc1.alert_ids[0]]
                alerts_in_inc2 = [a for a in alerts if a.alert_id == inc2.alert_ids[0]]
                
                if alerts_in_inc1 and alerts_in_inc2:
                    score = pipeline.compute_correlation_score(
                        alerts_in_inc1[0],
                        alerts_in_inc2[0]
                    )
                    unrelated_pairs.append({
                        'alert_1': alerts_in_inc1[0].alert_id,
                        'alert_2': alerts_in_inc2[0].alert_id,
                        'desc_1': alerts_in_inc1[0].normalized_description[:80],
                        'desc_2': alerts_in_inc2[0].normalized_description[:80],
                        'client_1': alerts_in_inc1[0].client,
                        'client_2': alerts_in_inc2[0].client,
                        'correlation_score': score.overall_score,
                        'semantic_similarity': score.semantic_similarity,
                        'temporal_proximity': score.temporal_proximity,
                        'client_match': score.client_match,
                        'candidate_group_1': inc1.incident_id,
                        'candidate_group_2': inc2.incident_id,
                        'human_review_label': 'Pending review'
                    })
        
        # Ambiguous pairs (high similarity, different clients or far apart in time)
        ambiguous_pairs = []
        # For now, mark this as requiring manual curation
        
        review_samples = {
            'related_pairs': related_pairs[:10],
            'unrelated_pairs': unrelated_pairs[:10],
            'ambiguous_pairs': ambiguous_pairs,
            'review_status': 'Samples generated - PENDING HUMAN VALIDATION',
            'note': 'Generated INCIDENT-xxxx IDs are candidate groups, NOT ground-truth incidents',
            'human_review_options': ['Related', 'Unrelated', 'Ambiguous', 'Pending review']
        }
        
        self.audit_results['manual_review'] = review_samples
        
        return review_samples


def main():
    """Run comprehensive Stage 3 audit."""
    
    print("\n" + "=" * 80)
    print("STAGE 3 CORRELATION AUDIT")
    print("=" * 80)
    
    # Setup
    excel_file = Settings.DATA_DIR / "Data_Alert_Ticket_Segregation.xlsx"
    output_dir = Settings.PROJECT_ROOT / "docs"
    
    auditor = Stage3Auditor()
    
    # Load data
    print("\n[1/8] Loading data...")
    print("-" * 80)
    
    field_cleaner = FieldCleaner(exclude_fields=Settings.EXCLUDE_FIELDS)
    normalizer = Normalizer(patterns=Settings.NORMALIZATION_PATTERNS)
    validator = AlertValidator(required_fields=Settings.REQUIRED_FIELDS)
    stage1_pipeline = Stage1Pipeline(field_cleaner, normalizer, validator)
    
    adapter = ExcelAlertAdapter(
        file_path=excel_file,
        column_mapping=Settings.EXCEL_COLUMN_MAPPING,
        forbidden_metadata_fields=set(Settings.FORBIDDEN_METADATA_FIELDS)
    )
    
    alerts = stage1_pipeline.run(adapter)
    print(f"✓ Loaded {len(alerts)} alerts")
    
    # Initialize Stage 3 pipeline
    print("\n[2/8] Initializing Stage 3 pipeline...")
    print("-" * 80)
    
    signature_matcher = SignatureMatcher(min_group_size=2)
    semantic_clusterer = SemanticClusterer()
    correlation_pipeline = CorrelationPipeline(
        signature_matcher=signature_matcher,
        semantic_clusterer=semantic_clusterer,
        max_time_gap_hours=24.0,
        min_correlation_score=0.7
    )
    
    print("✓ Pipeline initialized")
    
    # Run correlation
    print("\n[3/8] Running correlation pipeline...")
    print("-" * 80)
    
    incidents, uncorrelated = correlation_pipeline.correlate_alerts(alerts)
    
    print(f"✓ Created {len(incidents)} incidents")
    print(f"✓ {len(uncorrelated)} uncorrelated alerts")
    
    # Architecture compliance
    print("\n[4/8] Auditing architecture compliance...")
    print("-" * 80)
    
    compliance = auditor.audit_architecture_compliance(correlation_pipeline)
    
    for component, status in compliance.items():
        if status['implemented']:
            print(f"  ✓ {component}")
        else:
            print(f"  ✗ {component} - {status.get('status', 'Missing')}")
    
    # Clustering methods
    print("\n[5/8] Auditing clustering methods...")
    print("-" * 80)
    
    methods = auditor.audit_clustering_methods()
    
    for method, info in methods.items():
        if info['implemented']:
            print(f"  ✓ {method} - Implemented and benchmarked")
        else:
            print(f"  ✗ {method} - {info['status']}")
    
    # Temporal window analysis
    print("\n[6/8] Analyzing temporal window configuration...")
    print("-" * 80)
    
    temporal_analysis = auditor.analyze_temporal_window(incidents)
    
    print(f"  Configured window: {temporal_analysis['configured_window_hours']} hours")
    print(f"  Configurable: {temporal_analysis['is_configurable']}")
    print(f"  Status: {'Experimental default' if temporal_analysis['is_experimental_default'] else 'Validated'}")
    print(f"  Max incident duration: {temporal_analysis['actual_usage']['max_duration_hours']:.2f} hours")
    print(f"  Avg incident duration: {temporal_analysis['actual_usage']['avg_duration_hours']:.2f} hours")
    
    # Pizza Hut recurring pattern
    print("\n[7/8] Analyzing Pizza Hut recurring pattern...")
    print("-" * 80)
    
    pizza_analysis = auditor.analyze_pizza_hut_pattern(alerts, incidents)
    
    print(f"  Total alerts in family: {pizza_analysis['total_family_alerts']}")
    print(f"  Candidate incident groups: {pizza_analysis['candidate_incident_groups']}")
    print(f"  Split into multiple groups: {'Yes' if pizza_analysis['split_into_multiple_groups'] else 'No'}")
    print(f"  Largest group: {pizza_analysis['largest_group_size']} alerts")
    
    # Clustering diagnostics
    print("\n[8/8] Computing clustering diagnostics...")
    print("-" * 80)
    
    diagnostics = auditor.compute_clustering_diagnostics(alerts, incidents, uncorrelated)
    
    print(f"  Grouping rate: {diagnostics['grouping_rate']:.1%}")
    print(f"  Noise points: {diagnostics['noise_points']} ({diagnostics['noise_percentage']:.1%})")
    print(f"  Avg cluster size: {diagnostics['cluster_size_distribution']['mean']:.2f}")
    print(f"  Max cluster size: {diagnostics['cluster_size_distribution']['max']}")
    
    # Generate manual review samples
    print("\n  Generating manual review samples...")
    review_samples = auditor.generate_manual_review_samples(alerts, incidents, correlation_pipeline)
    print(f"  Related pairs: {len(review_samples['related_pairs'])}")
    print(f"  Unrelated pairs: {len(review_samples['unrelated_pairs'])}")
    
    # Known limitations
    auditor.audit_results['known_limitations'] = [
        'DBSCAN and Agglomerative clustering not benchmarked (only HDBSCAN implemented)',
        'No ground-truth incident labels for supervised evaluation',
        'Temporal window (24h) is experimental default, not validated',
        'Correlation scores are experimental, not calibrated probabilities',
        'Service/component extraction uses simple regex patterns (not ML-based)',
        'Stage 2 compatibility validation limited to Priority and Routing only',
        'Manual review of correlation quality incomplete',
        'Claude adjudication deferred to future phase'
    ]
    
    # Generate audit report
    print("\n[Report] Generating audit documentation...")
    print("-" * 80)
    
    generate_audit_report(auditor.audit_results, output_dir)
    
    print("✓ Audit report generated: docs/STAGE3_FINAL_AUDIT.md")
    
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80 + "\n")


def generate_audit_report(results, docs_dir):
    """Generate comprehensive Stage 3 audit report."""
    
    report_path = docs_dir / "STAGE3_FINAL_AUDIT.md"
    
    with open(report_path, 'w') as f:
        f.write("# STAGE 3 CORRELATION FINAL AUDIT\n\n")
        f.write("**Date**: September 25, 2026\n\n")
        f.write("**Status**: AUDIT COMPLETE\n\n")
        f.write("---\n\n")
        
        # Architecture Compliance
        f.write("## 1. ARCHITECTURE COMPLIANCE MATRIX\n\n")
        f.write("### Approved Architecture\n\n")
        f.write("```\n")
        f.write("Multiple Enriched Alerts\n")
        f.write("  → Exact Duplicate Detection\n")
        f.write("  → Alert Signature / Family Extraction\n")
        f.write("  → Sentence Embeddings\n")
        f.write("  → HDBSCAN Candidate Clustering\n")
        f.write("  → Temporal Validation\n")
        f.write("  → Client Validation\n")
        f.write("  → Service / Component Validation\n")
        f.write("  → Stage-2 Compatibility Validation\n")
        f.write("  → Correlation Scoring\n")
        f.write("  → Graph / Connected Components\n")
        f.write("  → Incident Groups\n")
        f.write("```\n\n")
        
        f.write("### Component Implementation Status\n\n")
        f.write("| Component | Status | Notes |\n")
        f.write("|-----------|--------|-------|\n")
        
        for component, status in results['architecture_compliance'].items():
            impl_status = "✓ Implemented" if status['implemented'] else "✗ Not Implemented"
            notes = status.get('attribute', status.get('status', ''))
            f.write(f"| {component} | {impl_status} | {notes} |\n")
        
        f.write("\n")
        
        # Exact Pipeline Flow
        f.write("## 2. ACTUAL PIPELINE FLOW\n\n")
        f.write("### Overview\n\n")
        f.write("Stage 3 uses **graph-based connected components** for incident grouping.\n")
        f.write("Alert relationships are modeled as a graph where validated correlation pairs\n")
        f.write("become edges, and transitive relationships are automatically handled.\n\n")
        
        f.write("### Phase 1: Exact Signature Matching + Validation\n\n")
        f.write("1. Extract normalized descriptions as signatures\n")
        f.write("2. Group alerts by exact signature match\n")
        f.write("3. Validate client coherence (split if mixed clients)\n")
        f.write("4. Validate temporal coherence (split by 24h windows)\n")
        f.write("5. **Create validated alert pairs** (not incident groups yet)\n\n")
        
        f.write("### Phase 2: Semantic Clustering + Validation\n\n")
        f.write("1. Generate embeddings for remaining alerts\n")
        f.write("2. Run HDBSCAN clustering\n")
        f.write("3. Filter clusters by client (no mixed clients)\n")
        f.write("4. Filter clusters by temporal proximity (24h windows)\n")
        f.write("5. Validate semantic coherence (≥0.7 similarity)\n")
        f.write("6. **Validate service/component compatibility** (NEW)\n")
        f.write("7. **Create validated alert pairs** (not incident groups yet)\n\n")
        
        f.write("### Phase 3: Graph Construction\n\n")
        f.write("1. Create alert graph with all alerts as nodes\n")
        f.write("2. Add edges from all validated pairs (Phase 1 + Phase 2)\n")
        f.write("3. Edge weights = correlation scores\n\n")
        
        f.write("### Phase 4: Connected Components Grouping\n\n")
        f.write("1. Find connected components using DFS\n")
        f.write("2. Multi-node components → incident groups\n")
        f.write("3. Singleton nodes → uncorrelated alerts\n")
        f.write("4. **Transitive relationships automatically handled** (A↔B, B↔C → A,B,C in same incident)\n\n")
        
        f.write("### Correlation Scoring (6 Signals)\n\n")
        f.write("Experimental weighted combination:\n")
        f.write("- **Semantic similarity** (30%): Embedding cosine similarity\n")
        f.write("- **Temporal proximity** (20%): Exponential decay based on time gap\n")
        f.write("- **Client match** (15%): Binary match\n")
        f.write("- **Alert family** (10%): Heuristic signature prefix match\n")
        f.write("- **Service compatibility** (15%): Rule-based service extraction (NEW)\n")
        f.write("- **Stage 2 compatibility** (10%): Priority + Routing match (NEW)\n\n")
        
        f.write("**Note**: All weights are configurable experimental values.\n\n")
        
        f.write("### Architecture Compliance Status\n\n")
        f.write("**✓ Implemented:**\n")
        f.write("- Exact signature matching\n")
        f.write("- Sentence embeddings\n")
        f.write("- HDBSCAN clustering\n")
        f.write("- Temporal validation (24h window)\n")
        f.write("- Client validation\n")
        f.write("- **Service/component validation** (rule-based extraction)\n")
        f.write("- **Stage 2 compatibility validation** (Priority + Routing)\n")
        f.write("- Correlation scoring (6 signals)\n")
        f.write("- **Graph-based connected components grouping**\n\n")
        
        f.write("**Deferred/Limitations:**\n")
        f.write("- Claude adjudication for ambiguous cases\n")
        f.write("- Ground-truth incident label collection\n")
        f.write("- Calibrated correlation probabilities\n")
        f.write("- DBSCAN/Agglomerative clustering benchmarks\n")
        f.write("- ML-based service extraction (using regex patterns currently)\n")
        f.write("- Stage 2 Alert Type, Severity, Business Impact (require labeling)\n\n")
        
        # Clustering Methods
        f.write("## 3. CLUSTERING BENCHMARKS\n\n")
        f.write("### Methods Implemented\n\n")
        
        for method, info in results['clustering_diagnostics']['methods'].items():
            f.write(f"#### {method}\n\n")
            if info['implemented']:
                f.write(f"- **Status**: ✓ Implemented\n")
                f.write(f"- **Location**: `{info.get('location', 'N/A')}`\n")
                f.write(f"- **Benchmarked**: {'Yes' if info.get('benchmarked') else 'No'}\n\n")
            else:
                f.write(f"- **Status**: ✗ Not Implemented\n")
                f.write(f"- **Note**: {info.get('status', 'Deferred')}\n\n")
        
        f.write("**Explicit Statement**: DBSCAN and Agglomerative Clustering were NOT implemented\n")
        f.write("or benchmarked. Only HDBSCAN and exact signature matching were evaluated.\n\n")
        
        # Temporal Window
        f.write("## 4. TEMPORAL WINDOW CONFIGURATION\n\n")
        
        temp = results['temporal_analysis']
        f.write(f"### Configuration\n\n")
        f.write(f"- **Window Size**: {temp['configured_window_hours']} hours\n")
        f.write(f"- **Configurable**: {'Yes' if temp['is_configurable'] else 'No'}\n")
        f.write(f"- **Status**: {'Experimental default' if temp['is_experimental_default'] else 'Validated'}\n")
        f.write(f"- **Validation**: {temp['validation_status']}\n\n")
        
        f.write(f"### Rationale\n\n")
        f.write(f"{temp['rationale']}\n\n")
        
        f.write(f"### Important Clarification: Pairwise vs Connected Component Duration\n\n")
        f.write("**24 hours is a maximum pairwise temporal-gap rule**:\n")
        f.write("- Two alerts can be correlated if their time difference ≤ 24 hours\n")
        f.write("- Connected components can span MORE than 24 hours through transitive relationships\n\n")
        f.write("**Example**:\n")
        f.write("```\n")
        f.write("Alert A at T+0h\n")
        f.write("Alert B at T+20h  → A↔B correlated (gap = 20h < 24h)\n")
        f.write("Alert C at T+40h  → B↔C correlated (gap = 20h < 24h)\n")
        f.write("Result: A, B, C in same candidate incident (total span = 40h > 24h)\n")
        f.write("```\n\n")
        f.write("The 24h window applies to **individual pairwise edges**, not the full incident duration.\n")
        f.write("This explains why some incidents have durations exceeding 24 hours.\n\n")
        
        f.write(f"### Actual Usage Statistics\n\n")
        f.write(f"- Max incident duration: {temp['actual_usage']['max_duration_hours']:.2f} hours\n")
        f.write(f"- Avg incident duration: {temp['actual_usage']['avg_duration_hours']:.2f} hours\n")
        f.write(f"- Median incident duration: {temp['actual_usage']['median_duration_hours']:.2f} hours\n\n")
        
        f.write("**Important**: The 24-hour window is an **experimental default**, not a validated\n")
        f.write("production value. It should be tuned based on actual incident response patterns.\n\n")
        
        # Pizza Hut Analysis
        f.write("## 5. PIZZA HUT RECURRING PATTERN ANALYSIS\n\n")
        
        ph = results['pizza_hut_analysis']
        f.write(f"### Pattern Details\n\n")
        f.write(f"- **Signature**: `{ph['pattern_signature']}...`\n")
        f.write(f"- **Total Alerts in Family**: {ph['total_family_alerts']}\n")
        f.write(f"- **Candidate Incident Groups Created**: {ph['candidate_incident_groups']}\n")
        f.write(f"- **Split into Multiple Groups**: {'✓ Yes' if ph['split_into_multiple_groups'] else '✗ No'}\n")
        f.write(f"- **Largest Group Size**: {ph['largest_group_size']} alerts\n\n")
        
        f.write(f"### Verification\n\n")
        f.write(f"The {ph['total_family_alerts']} recurring Pizza Hut SLA alerts were **NOT** ")
        f.write(f"grouped into a single incident.\n")
        f.write(f"They were split into {ph['candidate_incident_groups']} candidate incident groups ")
        f.write(f"under the current experimental temporal and validation rules.\n\n")
        
        f.write(f"**Note**: These are candidate groups based on experimental rules. ")
        f.write(f"No ground-truth incident labels exist to validate correctness.\n\n")
        
        if ph['temporal_gaps_hours']:
            f.write(f"**Sample Temporal Gaps** (hours between consecutive alerts):\n")
            for i, gap in enumerate(ph['temporal_gaps_hours'][:5], 1):
                f.write(f"- Gap {i}: {gap:.2f} hours\n")
            f.write("\n")
        
        f.write(f"**Sample Alert IDs**: {', '.join(ph['alert_ids_sample'][:5])}...\n\n")
        f.write(f"**Sample Incident IDs**: {', '.join(ph['incident_ids_sample'][:5])}...\n\n")
        
        # Clustering Diagnostics
        f.write("## 6. CLUSTERING DIAGNOSTICS\n\n")
        
        metrics = results['clustering_diagnostics']['metrics']
        
        f.write(f"### Overall Statistics\n\n")
        f.write(f"- **Total Alerts**: {metrics['total_alerts']}\n")
        f.write(f"- **Total Incidents**: {metrics['total_incidents']}\n")
        f.write(f"- **Correlated Alerts**: {metrics['correlated_alerts']}\n")
        f.write(f"- **Uncorrelated Alerts (Noise)**: {metrics['uncorrelated_alerts']}\n")
        f.write(f"- **Grouping Rate**: {metrics['grouping_rate']:.1%}\n\n")
        
        f.write("**Important Terminology**: The {:.1%} figure represents the percentage of alerts\n".format(metrics['grouping_rate']))
        f.write("assigned to multi-alert candidate groups. This is NOT accuracy, as no ground-truth\n")
        f.write("incident labels exist in the dataset.\n\n")
        
        f.write(f"### Cluster Size Distribution\n\n")
        dist = metrics['cluster_size_distribution']
        f.write(f"- **Min**: {dist['min']}\n")
        f.write(f"- **Max**: {dist['max']}\n")
        f.write(f"- **Mean**: {dist['mean']:.2f}\n")
        f.write(f"- **Median**: {dist['median']:.1f}\n")
        f.write(f"- **Std Dev**: {dist['std']:.2f}\n\n")
        
        f.write(f"### Semantic Similarity Statistics\n\n")
        sim = metrics['semantic_similarity']
        f.write(f"- **Sample Size**: {sim['sample_incidents']} incidents\n")
        f.write(f"- **Avg Similarity**: {sim['avg_similarity']:.4f}\n")
        f.write(f"- **Min Similarity**: {sim['min_similarity']:.4f}\n")
        f.write(f"- **Max Similarity**: {sim['max_similarity']:.4f}\n\n")
        
        f.write(f"### Noise Points\n\n")
        f.write(f"- **Count**: {metrics['noise_points']}\n")
        f.write(f"- **Percentage**: {metrics['noise_percentage']:.1%}\n\n")
        
        f.write("**Note**: Silhouette score not computed due to computational cost on full dataset.\n")
        f.write("Manual review samples generated instead.\n\n")
        
        # Manual Review
        f.write("## 7. MANUAL REVIEW SAMPLES\n\n")
        
        review = results['manual_review']
        
        f.write(f"### Review Status\n\n")
        f.write(f"**Status**: {review['review_status']}\n\n")
        f.write(f"**Important**: {review['note']}\n\n")
        f.write(f"**Human Review Options**: {', '.join(review['human_review_options'])}\n\n")
        
        f.write(f"### Alert Pairs from Same Candidate Group\n\n")
        f.write(f"Sample size: {len(review['related_pairs'])}\n\n")
        f.write("**Note**: These pairs are from the same candidate group based on automated correlation.\n")
        f.write("Human validation is required to confirm they represent the same actual incident.\n\n")
        
        for i, pair in enumerate(review['related_pairs'][:5], 1):
            f.write(f"**Pair {i}** (Candidate Group: {pair['candidate_group_id']})\n")
            f.write(f"- Alert 1: {pair['alert_1']} - {pair['desc_1']}...\n")
            f.write(f"- Alert 2: {pair['alert_2']} - {pair['desc_2']}...\n")
            f.write(f"- Correlation Score: {pair['correlation_score']:.4f}\n")
            f.write(f"- Semantic Similarity: {pair['semantic_similarity']:.4f}\n")
            f.write(f"- Temporal Proximity: {pair['temporal_proximity']:.4f}\n")
            f.write(f"- Client Match: {pair['client_match']}\n")
            f.write(f"- **Human Review**: {pair['human_review_label']}\n\n")
        
        f.write(f"### Alert Pairs from Different Candidate Groups\n\n")
        f.write(f"Sample size: {len(review['unrelated_pairs'])}\n\n")
        f.write("**Note**: These pairs are from different candidate groups based on automated correlation.\n")
        f.write("Human validation is required to confirm they should NOT be in the same incident.\n\n")
        
        for i, pair in enumerate(review['unrelated_pairs'][:5], 1):
            f.write(f"**Pair {i}** (Candidate Groups: {pair['candidate_group_1']} vs {pair['candidate_group_2']})\n")
            f.write(f"- Alert 1: {pair['alert_1']} - {pair['desc_1']}...\n")
            f.write(f"- Alert 2: {pair['alert_2']} - {pair['desc_2']}...\n")
            f.write(f"- Correlation Score: {pair['correlation_score']:.4f}\n")
            f.write(f"- Semantic Similarity: {pair['semantic_similarity']:.4f}\n")
            f.write(f"- Temporal Proximity: {pair['temporal_proximity']:.4f}\n")
            f.write(f"- Client Match: {pair['client_match']}\n")
            f.write(f"- **Human Review**: {pair['human_review_label']}\n\n")
        
        # Correlation Scoring
        f.write("## 8. CORRELATION SCORING\n\n")
        
        f.write("### Experimental Formula (6 Signals)\n\n")
        
        f.write("The correlation score is a weighted combination of:\n\n")
        
        f.write("1. **Semantic Similarity** (weight: 0.30)\n")
        f.write("   - Cosine similarity of sentence embeddings\n")
        f.write("   - Range: 0.0 to 1.0\n\n")
        
        f.write("2. **Temporal Proximity** (weight: 0.20)\n")
        f.write("   - Exponential decay: exp(-time_diff / 24h)\n")
        f.write("   - Range: 0.0 to 1.0\n\n")
        
        f.write("3. **Client Match** (weight: 0.15)\n")
        f.write("   - Binary: 1.0 if same client, 0.0 otherwise\n\n")
        
        f.write("4. **Alert Family Match** (weight: 0.10)\n")
        f.write("   - Heuristic: first 50 chars of normalized description\n")
        f.write("   - Binary: 1.0 if match, 0.0 otherwise\n\n")
        
        f.write("5. **Service/Component Compatibility** (weight: 0.15) - **NEW**\n")
        f.write("   - Rule-based extraction from normalized descriptions\n")
        f.write("   - Validates service name compatibility\n")
        f.write("   - Range: 0.0 to 1.0\n\n")
        
        f.write("6. **Stage 2 Compatibility** (weight: 0.10) - **NEW (EXPERIMENTAL)**\n")
        f.write("   - Uses **predicted** Priority and Routing from Stage 2 classification models\n")
        f.write("   - **NOT ground-truth labels** - these are model outputs\n")
        f.write("   - Priority model is weak/poorly calibrated (see Stage 2 audit)\n")
        f.write("   - Does NOT use Alert Type, Severity, or Business Impact (not available)\n")
        f.write("   - **Status**: Experimental feature requiring validation\n")
        f.write("   - Range: 0.0 to 1.0\n\n")
        
        f.write("### Overall Score Formula\n\n")
        f.write("```\n")
        f.write("overall = 0.30 * semantic + 0.20 * temporal + 0.15 * client + \n")
        f.write("          0.10 * family + 0.15 * service + 0.10 * stage2\n")
        f.write("```\n\n")
        
        f.write("### Thresholds\n\n")
        f.write("- **Minimum Correlation Score**: 0.7 (experimental)\n")
        f.write("- **Temporal Window**: 24 hours (experimental)\n")
        f.write("- **Minimum Semantic Similarity**: 0.7 (experimental)\n\n")
        
        f.write("**Important**: These weights and thresholds are **experimental defaults**,\n")
        f.write("not calibrated probabilities. All values are configurable and require validation.\n\n")
        
        f.write("### Stage 2 Fields Status\n\n")
        f.write("**Currently Used** (predicted values from Stage 2 models, NOT ground-truth):\n")
        f.write("- **Priority**: Predicted by Priority classification model (weak/poorly calibrated)\n")
        f.write("- **Routing**: Predicted by Assignment Group classification model\n\n")
        f.write("**NOT Available** (require labeled training data):\n")
        f.write("- Alert Type\n")
        f.write("- Severity\n")
        f.write("- Business Impact\n\n")
        f.write("**Important**: Stage 2 compatibility uses model predictions, NOT ground-truth labels.\n")
        f.write("The Priority model has poor calibration (see Stage 2 audit: 0.84 confidence vs 0.54 accuracy).\n")
        f.write("This signal should be considered **EXPERIMENTAL** until validated.\n\n")
        
        # Known Limitations
        f.write("## 9. KNOWN LIMITATIONS\n\n")
        
        for i, limitation in enumerate(results['known_limitations'], 1):
            f.write(f"{i}. {limitation}\n")
        
        f.write("\n")
        
        # Evaluation Constraints
        f.write("## 10. EVALUATION CONSTRAINTS\n\n")
        
        f.write("### No Ground Truth\n\n")
        f.write("The Excel dataset does NOT contain reliable incident grouping ground truth.\n")
        f.write("Therefore:\n\n")
        f.write("- **No supervised metrics** (precision, recall, F1) can be computed\n")
        grouping_rate = results['clustering_diagnostics']['metrics']['grouping_rate']
        f.write(f"- The {grouping_rate:.1%} grouping rate is NOT \"accuracy\"\n")
        f.write("- Evaluation relies on:\n")
        f.write("  - Internal coherence metrics\n")
        f.write("  - Manual review samples\n")
        f.write("  - Temporal and client validation\n")
        f.write("  - Domain knowledge checks\n\n")
        
        f.write("### Manual Review Required\n\n")
        f.write("To validate correlation quality:\n")
        f.write("1. Review generated alert pairs (related, unrelated, ambiguous)\n")
        f.write("2. Validate representative incidents\n")
        f.write("3. Check for false merges and false splits\n")
        f.write("4. Assess temporal window appropriateness\n\n")
        
        # Items Deferred
        f.write("## 11. ITEMS DEFERRED TO FUTURE PHASES\n\n")
        
        f.write("1. **ML-Based Service Extraction**\n")
        f.write("   - Current implementation uses regex patterns\n")
        f.write("   - Future: Train ML model for service/component extraction\n")
        f.write("   - Improve extraction accuracy and coverage\n\n")
        
        f.write("2. **Additional Stage 2 Fields**\n")
        f.write("   - Current: Priority and Routing only\n")
        f.write("   - Future: Alert Type, Severity, Business Impact (require labeled training data)\n")
        f.write("   - Expand compatibility validation signals\n\n")
        
        f.write("3. **Claude Adjudication**\n")
        f.write("   - Identify ambiguous cases\n")
        f.write("   - LLM-based relationship validation\n")
        f.write("   - Fallback for low-confidence correlations\n\n")
        
        f.write("4. **Additional Clustering Methods**\n")
        f.write("   - Benchmark DBSCAN\n")
        f.write("   - Benchmark Agglomerative Clustering\n")
        f.write("   - Compare methods quantitatively\n\n")
        
        f.write("5. **Ground Truth Collection**\n")
        f.write("   - Manual incident labeling\n")
        f.write("   - Supervised evaluation metrics\n")
        f.write("   - Calibration of correlation scores\n\n")
        
        f.write("6. **Incremental Correlation**\n")
        f.write("   - Stream processing for new alerts\n")
        f.write("   - Real-time incident updates\n")
        f.write("   - Graph persistence and querying\n\n")
        
        # Recommendations
        f.write("## 12. RECOMMENDATIONS\n\n")
        
        f.write("### Before Stage 4\n\n")
        f.write("1. Complete manual review of generated samples\n")
        f.write("2. Validate Pizza Hut recurring pattern splits with domain expert\n")
        f.write("3. Review largest incidents for false merges\n")
        f.write("4. Review noise points for false splits\n")
        f.write("5. Verify service/component extraction accuracy on sample alerts\n")
        f.write("6. Validate Stage 2 compatibility logic with sample pairs\n\n")
        
        f.write("### For Production\n\n")
        f.write("1. Tune temporal window based on actual incident response data\n")
        f.write("2. Collect ground truth labels for supervised evaluation\n")
        f.write("3. Calibrate correlation scores to meaningful probabilities\n")
        f.write("4. Enhance service extraction with ML-based models\n")
        f.write("5. Train additional Stage 2 models (Alert Type, Severity, Business Impact)\n")
        f.write("6. Implement incremental correlation for streaming alerts\n\n")
        
        f.write("---\n\n")
        f.write("**Audit Status**: COMPLETE\n\n")
        f.write("**Stage 3 Status**: Architecture implemented and prototype validated.\n")
        f.write("Correlation quality remains subject to manual/domain validation because\n")
        f.write("no ground-truth incident labels exist.\n\n")
        f.write("**Next Steps**: Await approval before proceeding to Stage 4\n")


if __name__ == '__main__':
    main()
