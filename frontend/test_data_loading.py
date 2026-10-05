"""
Quick test to validate data loading for the frontend.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data_loader import DataLoader

def test_data_loading():
    """Test that all data files load successfully."""
    print("Testing data loading...")
    print("=" * 60)
    
    loader = DataLoader()
    
    # Test Stage 2
    print("\n[Stage 2] Loading classification results...")
    try:
        stage2_df = loader.load_stage2()
        print(f"  ✅ Loaded {len(stage2_df)} alerts")
        print(f"  Columns: {list(stage2_df.columns)}")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    # Test Stage 3
    print("\n[Stage 3] Loading correlation data...")
    try:
        stage3_summary = loader.load_stage3_summary()
        print(f"  ✅ Loaded summary: {stage3_summary['statistics']['total_incidents']} incidents")
        
        stage3_incidents = loader.load_stage3_incidents()
        print(f"  ✅ Loaded incident list: {len(stage3_incidents)} candidate incident groups")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    # Test Stage 4
    print("\n[Stage 4] Loading RCA data...")
    try:
        stage4_rca = loader.load_stage4_rca()
        print(f"  ✅ Loaded {len(stage4_rca)} RCA analyses")
        
        stage4_summary_df = loader.load_stage4_summary()
        print(f"  ✅ Loaded RCA summary CSV: {len(stage4_summary_df)} rows")
        
        stage4_stats = loader.load_stage4_statistics()
        print(f"  ✅ Loaded RCA statistics")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    # Test alert-to-incident mapping
    print("\n[Linking] Building alert-to-incident map...")
    try:
        mapping = loader.build_alert_to_incident_map()
        print(f"  ✅ Built mapping: {len(mapping)} alerts mapped to incidents")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    # Test get_alert
    print("\n[Testing] get_alert()...")
    try:
        first_alert_id = stage2_df.iloc[0]['alert_id']
        alert = loader.get_alert(first_alert_id)
        if alert:
            print(f"  ✅ Retrieved alert: {alert['alert_id']}")
            print(f"     Alert Type: {alert.get('predicted_alert_type')}")
            print(f"     Severity: {alert.get('predicted_severity')}")
            print(f"     Business Impact: {alert.get('predicted_business_impact')}")
            print(f"     Client: {alert.get('client')}")
        else:
            print(f"  ❌ Alert not found: {first_alert_id}")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    # Test get_incident_for_alert
    print("\n[Testing] get_incident_for_alert()...")
    try:
        incident_id = loader.get_incident_for_alert(first_alert_id)
        if incident_id:
            print(f"  ✅ Alert {first_alert_id} → Incident {incident_id}")
        else:
            print(f"  ℹ️  Alert {first_alert_id} is uncorrelated")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    # Test get_incident
    print("\n[Testing] get_incident()...")
    try:
        first_incident = stage3_incidents[0]
        incident_id = first_incident['incident_id']
        incident = loader.get_incident(incident_id)
        if incident:
            print(f"  ✅ Retrieved incident: {incident['incident_id']}")
            print(f"     Client: {incident.get('client')}")
            print(f"     Alerts: {incident.get('alert_count')}")
            print(f"     Method: {incident.get('correlation_method')}")
        else:
            print(f"  ❌ Incident not found: {incident_id}")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    # Test get_rca
    print("\n[Testing] get_rca()...")
    try:
        rca = loader.get_rca(incident_id)
        if rca:
            print(f"  ✅ Retrieved RCA: {rca['incident_id']}")
            print(f"     Status: {rca.get('diagnosis_status')}")
            print(f"     Component: {rca.get('probable_root_cause', {}).get('component', 'N/A')}")
        else:
            print(f"  ❌ RCA not found: {incident_id}")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    # Test get_summary_stats
    print("\n[Testing] get_summary_stats()...")
    try:
        stats = loader.get_summary_stats()
        print(f"  ✅ Summary stats:")
        print(f"     Total Alerts: {stats['total_alerts']}")
        print(f"     Candidate Incident Groups: {stats['candidate_incident_groups']}")
        print(f"     Grouped Alerts: {stats['grouped_alerts']}")
        print(f"     Uncorrelated Alerts: {stats['uncorrelated_alerts']}")
        print(f"     RCA Analyses: {stats['rca_analyses']}")
        print(f"     Ambiguous: {stats['ambiguous']}")
        print(f"     Insufficient Evidence: {stats['insufficient_evidence']}")
        print(f"     Mock Evidence %: {stats['mock_evidence_percentage']:.1f}%")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All data loading tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_data_loading()
    sys.exit(0 if success else 1)
