#!/usr/bin/env python3
"""
Comprehensive frontend smoke test.

Tests:
1. Load 889 alerts
2. Open an alert
3. Navigate alert → candidate incident group
4. Show all member alerts
5. Open corresponding RCA
6. Verify Stage 2/3/4 fields are consistent
7. Check for incorrect claims
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data_loader import DataLoader


def smoke_test():
    """Run comprehensive smoke test."""
    print("\n" + "=" * 80)
    print("FRONTEND SMOKE TEST")
    print("=" * 80)
    
    loader = DataLoader()
    
    # Test 1: Load 889 alerts
    print("\n[Test 1] Loading all alerts...")
    stage2_df = loader.load_stage2()
    assert len(stage2_df) == 889, f"Expected 889 alerts, got {len(stage2_df)}"
    print(f"✅ Loaded {len(stage2_df)} alerts")
    
    # Test 2: Open an alert (first one that's in an incident group)
    print("\n[Test 2] Opening an alert that's in a candidate incident group...")
    
    # Find an alert that's mapped to an incident
    mapping = loader.build_alert_to_incident_map()
    alert_id = list(mapping.keys())[0]  # Get first mapped alert
    incident_id = mapping[alert_id]
    
    alert = loader.get_alert(alert_id)
    assert alert is not None, f"Failed to load alert {alert_id}"
    print(f"✅ Opened alert: {alert['alert_id']}")
    print(f"   Client: {alert['client']}")
    print(f"   Description: {alert['description'][:60]}...")
    
    # Verify Stage 2 predictions are present (not true_labels)
    print("\n[Test 2.1] Verifying Stage 2 predictions (not true labels)...")
    assert 'predicted_alert_type' in alert, "Missing predicted_alert_type"
    assert 'predicted_severity' in alert, "Missing predicted_severity"
    assert 'predicted_business_impact' in alert, "Missing predicted_business_impact"
    assert 'alert_type_confidence' in alert, "Missing alert_type_confidence"
    print(f"✅ Stage 2 fields present:")
    print(f"   Alert Type: {alert['predicted_alert_type']} (conf: {alert['alert_type_confidence']:.2%})")
    print(f"   Severity: {alert['predicted_severity']} (conf: {alert['severity_confidence']:.2%})")
    print(f"   Business Impact: {alert['predicted_business_impact']} (conf: {alert['business_impact_confidence']:.2%})")
    print(f"   Priority: {alert['priority']} (from raw data)")
    print(f"   Assignment Group: {str(alert['assignment_group'])[:50]}... (from raw data)")
    
    # Test 3: Navigate to candidate incident group
    print("\n[Test 3] Navigating to candidate incident group...")
    incident = loader.get_incident(incident_id)
    assert incident is not None, f"Failed to load incident {incident_id}"
    print(f"✅ Navigated to incident: {incident['incident_id']}")
    print(f"   Client: {incident['client']}")
    print(f"   Alert Count: {incident['alert_count']}")
    print(f"   Correlation Method: {incident['correlation_method']}")
    
    # Test 4: Show all member alerts
    print("\n[Test 4] Showing all member alerts...")
    member_alerts = incident.get('alert_ids', [])
    assert len(member_alerts) > 0, "No member alerts found"
    print(f"✅ Found {len(member_alerts)} member alerts:")
    for i, aid in enumerate(member_alerts[:5], 1):
        print(f"   {i}. {aid}")
    if len(member_alerts) > 5:
        print(f"   ... and {len(member_alerts) - 5} more")
    
    # Test 5: Open corresponding RCA
    print("\n[Test 5] Opening corresponding Stage 4 RCA...")
    rca = loader.get_rca(incident_id)
    assert rca is not None, f"Failed to load RCA for incident {incident_id}"
    print(f"✅ Opened RCA: {rca['incident_id']}")
    print(f"   Diagnosis Status: {rca['diagnosis_status']}")
    
    if rca.get('probable_root_cause'):
        prc = rca['probable_root_cause']
        print(f"   Component: {prc.get('component', 'N/A')}")
        print(f"   Failure Type: {prc.get('failure_type', 'N/A')}")
        print(f"   Confidence: {prc.get('confidence', 0):.2%}")
    
    # Test 6: Verify Stage 2/3/4 fields are consistent
    print("\n[Test 6] Verifying Stage 2/3/4 field consistency...")
    
    # Check that alert_id from Stage 2 is in incident's alert_ids
    assert alert['alert_id'] in incident['alert_ids'], \
        f"Alert {alert['alert_id']} not in incident's alert list"
    print(f"✅ Alert {alert['alert_id']} is in incident {incident['incident_id']}")
    
    # Check that incident_id matches RCA incident_id
    assert incident['incident_id'] == rca['incident_id'], \
        f"Incident ID mismatch: {incident['incident_id']} vs {rca['incident_id']}"
    print(f"✅ Incident ID matches RCA ID: {incident['incident_id']}")
    
    # Check that client is consistent
    assert alert['client'] == incident['client'], \
        f"Client mismatch: {alert['client']} vs {incident['client']}"
    print(f"✅ Client consistent across stages: {alert['client']}")
    
    # Test 7: Check for incorrect claims
    print("\n[Test 7] Checking for incorrect claims...")
    
    issues = []
    
    # Check evidence is marked as MOCK
    evidence = rca.get('evidence', [])
    if evidence:
        mock_count = sum(1 for e in evidence if e.get('is_mock', False))
        if mock_count != len(evidence):
            issues.append(f"Not all evidence marked as MOCK: {mock_count}/{len(evidence)}")
        else:
            print(f"✅ All {len(evidence)} evidence items marked as MOCK")
    
    # Check diagnosis_status is appropriate
    if rca['diagnosis_status'] == 'sufficient_evidence':
        issues.append("Diagnosis status is 'sufficient_evidence' - should be ambiguous/insufficient with MOCK data")
    else:
        print(f"✅ Diagnosis status appropriate: {rca['diagnosis_status']}")
    
    # Check telemetry_is_mock flag if it exists
    if 'telemetry_is_mock' in rca:
        if rca['telemetry_is_mock'] != True:
            issues.append("telemetry_is_mock is not True")
        else:
            print(f"✅ telemetry_is_mock flag is True")
    
    # Summary
    print("\n" + "=" * 80)
    if issues:
        print("❌ SMOKE TEST FOUND ISSUES:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ ALL SMOKE TESTS PASSED")
        print("=" * 80)
        return True


def test_terminology():
    """Check that correct terminology is used in the codebase."""
    print("\n" + "=" * 80)
    print("TERMINOLOGY VERIFICATION")
    print("=" * 80)
    
    issues = []
    
    # Read UI files
    ui_files = [
        'pages/1_Alerts.py',
        'pages/2_Incidents.py',
        'pages/3_RCA.py',
        'app.py',
        'data_loader.py'
    ]
    
    for filename in ui_files:
        filepath = Path(__file__).parent / filename
        if filepath.exists():
            content = filepath.read_text()
            
            # Check for incorrect terminology (excluding correct negations like "NOT confirmed root cause")
            if 'production-ready' in content.lower() and 'not production-ready' not in content.lower():
                issues.append(f"{filename}: Claims 'production-ready'")
            
            # Check for positive claims (not negations)
            if 'confirmed root cause' in content.lower():
                # Allow negations like "NOT confirmed root cause" or "not confirmed root causes"
                if not any(neg in content.lower() for neg in ['not confirmed root cause', 'not a confirmed root cause']):
                    issues.append(f"{filename}: Claims 'confirmed root cause'")
            
            if 'calibrated probability' in content.lower():
                # Allow negations like "NOT calibrated probability"
                if not any(neg in content.lower() for neg in ['not calibrated probability', 'not a calibrated probability']):
                    issues.append(f"{filename}: Claims 'calibrated probability'")
            
            if 'rca accuracy' in content.lower():
                # Allow negations like "no RCA accuracy"
                if 'no rca accuracy' not in content.lower():
                    issues.append(f"{filename}: Claims 'RCA accuracy'")
            
            if 'correlation accuracy' in content.lower():
                # Allow negations like "no correlation accuracy"
                if 'no correlation accuracy' not in content.lower():
                    issues.append(f"{filename}: Claims 'correlation accuracy'")
    
    if issues:
        print("❌ TERMINOLOGY ISSUES FOUND:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ No incorrect terminology found in UI files")
        return True


if __name__ == "__main__":
    success1 = smoke_test()
    success2 = test_terminology()
    
    print("\n" + "=" * 80)
    if success1 and success2:
        print("✅ FRONTEND VERIFICATION COMPLETE - ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ FRONTEND VERIFICATION FAILED - SEE ISSUES ABOVE")
        sys.exit(1)
