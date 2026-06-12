import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
import joblib

# Add current project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import Analyst, Transaction, Rule, Alert, AuditLog
from backend.app.auth import get_password_hash
from backend.app.redis_client import RedisTracker, redis_conn
from backend.app.ml_engine import MODEL_PATH, FEATURE_COLS

def seed_db():
    print("[SEEDER] Re-initializing MySQL Database Schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # 1. Seed Analysts
        print("[SEEDER] Provisioning security credentials (analyst profiles)...")
        admin = Analyst(
            username="admin",
            hashed_password=get_password_hash("admin"),
            role="ADMIN"
        )
        analyst = Analyst(
            username="analyst",
            hashed_password=get_password_hash("analyst"),
            role="ANALYST"
        )
        db.add(admin)
        db.add(analyst)
        db.commit()

        # 2. Seed Default Scoring Rules
        print("[SEEDER] Seeding default static fraud heuristic rules...")
        default_rules = [
            Rule(
                name="Extreme Transaction Amount",
                description="Flags transactions over $2,500 with a critical modifier.",
                field_name="amount",
                operator=">",
                threshold_value=2500.0,
                risk_modifier=50.0,
                is_active=True
            ),
            Rule(
                name="Address Zip Mismatch Check",
                description="Applies risk modifier if cardholder address zip doesn't match merchant zip.",
                field_name="zip_mismatch",
                operator="==",
                threshold_value=1.0,
                risk_modifier=15.0,
                is_active=True
            ),
            Rule(
                name="High Short-Term Velocity",
                description="Flags rapid transactions within a 1-hour window (velocity > 4).",
                field_name="velocity_1h",
                operator=">",
                threshold_value=4.0,
                risk_modifier=25.0,
                is_active=True
            ),
            Rule(
                name="Spending Deviation Ratio Trigger",
                description="Flags transactions that are 3x higher than customer's rolling 10-tx average.",
                field_name="amount_deviation_ratio",
                operator=">",
                threshold_value=3.0,
                risk_modifier=30.0,
                is_active=True
            )
        ]
        db.add_all(default_rules)
        db.commit()

        # 3. Synthesize Mock Transaction Data
        print("[SEEDER] Synthesizing transaction pipeline ledger stream...")
        np.random.seed(42)
        customer_ids = [f'CUST_{i:03d}' for i in range(1, 101)]
        customer_home_zip = {cid: np.random.randint(10000, 99999) for cid in customer_ids}
        
        num_tx = 2500  # Seeding 2500 is fast and enough to train an initial model
        start_date = datetime.now() - timedelta(days=15)
        tx_data = []

        # We keep track of customer state in-memory during synthesis to calculate window aggregates
        customer_history = {cid: [] for cid in customer_ids}

        for i in range(num_tx):
            cid = np.random.choice(customer_ids)
            # Generate spread timestamps
            tx_time = start_date + timedelta(seconds=int(np.random.uniform(0, 15*24*3600)))
            amount = np.random.exponential(scale=35.0) + 2.0
            is_fraud = 0
            merchant_zip = customer_home_zip[cid]

            # Injected anomalies
            fraud_roll = np.random.rand()
            if fraud_roll < 0.005:
                amount = np.random.uniform(1500, 4500)
                is_fraud = 1
            elif fraud_roll < 0.010:
                merchant_zip = np.random.randint(10000, 99999)
                while merchant_zip == customer_home_zip[cid]:
                    merchant_zip = np.random.randint(10000, 99999)
                amount = np.random.uniform(200, 800)
                is_fraud = 1

            tx_entry = {
                'transaction_id': f'TX_{i:05d}',
                'customer_id': cid,
                'timestamp': tx_time,
                'amount': round(amount, 2),
                'merchant_zip': merchant_zip,
                'customer_zip': customer_home_zip[cid],
                'actual_ground_truth_fraud': is_fraud
            }
            tx_data.append(tx_entry)

        # Sort all synthesized data chronologically to build accurate features
        tx_data.sort(key=lambda x: x['timestamp'])

        print("[SEEDER] Calculating rolling baseline windows...")
        processed_txs = []
        for tx in tx_data:
            cid = tx['customer_id']
            t_time = tx['timestamp']
            amt = tx['amount']
            
            # Retrieve customer history
            hist = customer_history[cid]
            
            # Velocity in the last hour
            hour_ago = t_time - timedelta(hours=1)
            vel_1h = sum(1 for prev_tx in hist if prev_tx['timestamp'] >= hour_ago) + 1  # include current
            
            # Rolling average amount of last 10 transactions
            prev_10 = hist[-10:] if len(hist) > 0 else []
            rolling_avg = sum(prev_tx['amount'] for prev_tx in prev_10) / len(prev_10) if prev_10 else amt
            
            # Zip mismatch
            zip_mismatch = 1 if tx['merchant_zip'] != tx['customer_zip'] else 0
            
            # Deviation ratio
            deviation_ratio = round(amt / max(rolling_avg, 0.01), 2)
            
            tx.update({
                'rolling_avg_amount': round(rolling_avg, 2),
                'velocity_1h': vel_1h,
                'zip_mismatch': zip_mismatch,
                'amount_deviation_ratio': deviation_ratio
            })
            
            # Add to memory history
            hist.append(tx)
            processed_txs.append(tx)

        # 4. Train standard scaler and Isolation Forest on generated features
        print("[SEEDER] Training StandardScaler and Isolation Forest model...")
        df_fit = pd.DataFrame(processed_txs)
        X = df_fit[FEATURE_COLS]
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Fit Isolation Forest
        model = IsolationForest(contamination=0.015, random_state=42)
        model.fit(X_scaled)
        
        # Save model
        joblib.dump({'model': model, 'scaler': scaler}, MODEL_PATH)
        print(f"[SEEDER] Model serialized successfully to {MODEL_PATH}")

        # Compute risk scores
        print("[SEEDER] Computing and inserting evaluation matrices...")
        raw_scores = model.score_samples(X_scaled)
        # Map raw scores to [0.0, 100.0]
        score_clamped = np.clip(raw_scores, -0.75, -0.45)
        scaled_scores = np.round(( -0.45 - score_clamped ) / 0.30 * 100.0, 1)

        # Evaluate rules and combined risk score
        rules_in_db = db.query(Rule).all()
        
        db_transactions = []
        db_alerts = []
        
        for idx, tx in enumerate(processed_txs):
            ml_anomaly = 1 if model.predict(X_scaled[idx:idx+1])[0] == -1 else 0
            ml_risk = scaled_scores[idx]
            
            # Rules modifier evaluation
            rule_mod = 0.0
            for r in rules_in_db:
                val = tx[r.field_name]
                if r.operator == ">" and val > r.threshold_value:
                    rule_mod += r.risk_modifier
                elif r.operator == "==" and val == r.threshold_value:
                    rule_mod += r.risk_modifier
            
            final_risk = round(max(0.0, min(100.0, ml_risk + rule_mod)), 1)
            is_flagged = 1 if final_risk >= 75.0 else 0

            db_tx = Transaction(
                transaction_id=tx['transaction_id'],
                customer_id=tx['customer_id'],
                timestamp=tx['timestamp'],
                amount=tx['amount'],
                merchant_zip=tx['merchant_zip'],
                customer_zip=tx['customer_zip'],
                rolling_avg_amount=tx['rolling_avg_amount'],
                velocity_1h=tx['velocity_1h'],
                zip_mismatch=tx['zip_mismatch'],
                amount_deviation_ratio=tx['amount_deviation_ratio'],
                risk_score=final_risk,
                ml_predicted_anomaly=ml_anomaly,
                actual_ground_truth_fraud=tx['actual_ground_truth_fraud'],
                is_flagged=is_flagged
            )
            db_transactions.append(db_tx)

        # Bulk save transactions to MySQL
        db.bulk_save_objects(db_transactions)
        db.commit()

        # Build alerts for flagged transactions
        print("[SEEDER] Generating security alert queues...")
        # Query saved transactions to link Alert primary keys correctly
        saved_txs = db.query(Transaction).filter(Transaction.is_flagged == 1).all()
        for s_tx in saved_txs:
            # Let some older alerts be resolved to make the UI look good
            status = "OPEN"
            notes = None
            analyst_id = None
            
            # Generate random statuses for historical alerts
            prob = np.random.rand()
            if prob < 0.4:
                status = "RESOLVED_SAFE"
                notes = "Customer confirmed transaction. False positive."
                analyst_id = 2  # analyst user
            elif prob < 0.7:
                status = "RESOLVED_FRAUD"
                notes = "Confirmed card compromise. Card blocked."
                analyst_id = 2
            elif prob < 0.85:
                status = "UNDER_REVIEW"
                notes = "Analyst reviewing customer spending history."
                analyst_id = 2
                
            db_alert = Alert(
                transaction_id=s_tx.transaction_id,
                risk_score=s_tx.risk_score,
                status=status,
                analyst_id=analyst_id,
                notes=notes,
                created_at=s_tx.timestamp
            )
            db_alerts.append(db_alert)

        db.bulk_save_objects(db_alerts)
        db.commit()

        # 5. Populate Redis Cache
        # Clear keys first
        print("[SEEDER] Initializing Redis hot cache tables...")
        try:
            redis_conn.ping()
            for cid in customer_ids:
                hist = customer_history[cid]
                # Clear existing
                redis_conn.delete(f"customer:{cid}:tx_amounts", f"customer:{cid}:tx_velocity")
                
                # Fetch recent 10 transactions
                recent_txs = hist[-10:]
                for tx in recent_txs:
                    t_str = tx['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    RedisTracker.log_transaction(cid, tx['amount'], t_str)
            print("[REDIS] Redis seed completed successfully.")
        except Exception as e:
            print(f"[WARNING] Redis cache seeding failed: {e}")

        # Add Audit Logs
        db.add(AuditLog(
            analyst_id=1,
            action="SYSTEM_INIT",
            target_type="SYSTEM",
            target_id="DATABASE",
            timestamp=datetime.utcnow()
        ))
        db.commit()

        print("[SUCCESS] Database successfully initialized, seeded, and caches initialized!")
        
    except Exception as e:
        print(f"[ERROR] Seeding process encountered error: {e}")
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == '__main__':
    seed_db()
