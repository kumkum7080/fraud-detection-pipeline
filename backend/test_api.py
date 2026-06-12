import os
import sys
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models import Transaction, Alert, Rule

client = TestClient(app)

def run_tests():
    print("[TEST RUNNER] Starting backend integration test suite...")

    # 1. Test Base Route
    print("[TEST] GET '/'")
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "online"
    print("   [PASS] Root status online verified.")

    # 2. Test Login
    print("[TEST] POST '/api/auth/login' (Admin login)")
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    token_data = r.json()
    assert "access_token" in token_data
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   [PASS] Admin JWT token retrieved.")

    # 3. Test Auth Me
    print("[TEST] GET '/api/auth/me'")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    user_info = r.json()
    assert user_info["username"] == "admin"
    assert user_info["role"] == "ADMIN"
    print("   [PASS] Auth payload parsed successfully.")

    # 4. Test Ingestion & Real-Time Scoring (Normal)
    print("[TEST] POST '/api/transactions/' (Normal Spending)")
    normal_payload = {
        "customer_id": "CUST_001",
        "amount": 25.50,
        "merchant_zip": 90210,
        "customer_zip": 90210,
        "actual_ground_truth_fraud": 0
    }
    r = client.post("/api/transactions/", json=normal_payload)
    assert r.status_code == 201
    tx_out = r.json()
    assert tx_out["transaction_id"].startswith("TX_")
    assert tx_out["is_flagged"] == 0
    print(f"   [PASS] Normal transaction scored: Risk Score = {tx_out['risk_score']}% (Is Flagged = {tx_out['is_flagged']})")

    # 5. Test Ingestion & Real-Time Scoring (High-Risk Anomaly)
    print("[TEST] POST '/api/transactions/' (Extreme Amount Outlier)")
    fraud_payload = {
        "customer_id": "CUST_001",
        "amount": 4900.00,  # Over $2500 rule limit, triggers rule + high ML risk
        "merchant_zip": 90210,
        "customer_zip": 90210,
        "actual_ground_truth_fraud": 1
    }
    r = client.post("/api/transactions/", json=fraud_payload)
    assert r.status_code == 201
    tx_fraud_out = r.json()
    assert tx_fraud_out["is_flagged"] == 1
    flagged_tx_id = tx_fraud_out["transaction_id"]
    print(f"   [PASS] Anomalous transaction scored: Risk Score = {tx_fraud_out['risk_score']}% (Is Flagged = {tx_fraud_out['is_flagged']})")

    # 6. Test Alert Retrieval
    print("[TEST] GET '/api/alerts/' (Retrieve open alerts)")
    r = client.get("/api/alerts/?status=OPEN", headers=headers)
    assert r.status_code == 200
    alerts = r.json()
    assert len(alerts) > 0
    # Find our newly generated alert
    new_alert = next((a for a in alerts if a["transaction_id"] == flagged_tx_id), None)
    assert new_alert is not None
    alert_id = new_alert["id"]
    print(f"   [PASS] Alert for TX verified in queue: Alert ID = {alert_id}")

    # 7. Test Alert Claiming
    print(f"[TEST] PUT '/api/alerts/{alert_id}/claim'")
    r = client.put(f"/api/alerts/{alert_id}/claim", headers=headers)
    assert r.status_code == 200
    claimed = r.json()
    assert claimed["status"] == "UNDER_REVIEW"
    print("   [PASS] Alert claimed successfully.")

    # 8. Test Alert Resolution
    print(f"[TEST] PUT '/api/alerts/{alert_id}/resolve'")
    resolve_payload = {
        "status": "RESOLVED_FRAUD",
        "notes": "Verified unauthorized card spending spike. Card deactivated."
    }
    r = client.put(f"/api/alerts/{alert_id}/resolve", json=resolve_payload, headers=headers)
    assert r.status_code == 200
    resolved = r.json()
    assert resolved["status"] == "RESOLVED_FRAUD"
    assert resolved["notes"] == resolve_payload["notes"]
    print("   [PASS] Alert resolved as RESOLVED_FRAUD.")

    # 9. Test Analytics Endpoints
    print("[TEST] GET '/api/analytics/metrics'")
    r = client.get("/api/analytics/metrics", headers=headers)
    assert r.status_code == 200
    metrics = r.json()
    assert "total_traffic" in metrics
    assert "active_alerts" in metrics
    print(f"   [PASS] Dashboard metrics parsed: Total Transactions = {metrics['total_traffic']}, Active Alerts = {metrics['active_alerts']}")

    # 10. Test Rules CRUD
    print("[TEST] GET '/api/rules/'")
    r = client.get("/api/rules/", headers=headers)
    assert r.status_code == 200
    rules = r.json()
    assert len(rules) >= 4
    print(f"   [PASS] Core rules verified in database. Count = {len(rules)}")

    print("\n[SUCCESS] ALL BACKEND INTEGRATION TESTS COMPLETED SUCCESSFULLY! \n")

if __name__ == '__main__':
    run_tests()
