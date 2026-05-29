import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

def run_pipeline():
    np.random.seed(42)

    # 1. Generate Mock Credit Card Transactions
    print("💳 Step 1: Synthesizing transaction pipeline ledger stream...")
    customer_ids = [f'CUST_{i:03d}' for i in range(1, 101)]
    customer_home_zip = {cid: np.random.randint(10000, 99999) for cid in customer_ids}

    num_tx = 5000
    start_date = datetime.now() - timedelta(days=30)
    tx_data = []

    for i in range(num_tx):
        cid = np.random.choice(customer_ids)
        tx_time = start_date + timedelta(seconds=int(np.random.uniform(0, 30*24*3600)))
        amount = np.random.exponential(scale=35.0) + 2.0 
        is_fraud = 0
        merchant_zip = customer_home_zip[cid]

        fraud_roll = np.random.rand()
        if fraud_roll < 0.005: 
            amount = np.random.uniform(1500, 5000)
            is_fraud = 1
        elif fraud_roll < 0.010: 
            merchant_zip = np.random.randint(10000, 99999)
            while merchant_zip == customer_home_zip[cid]:
                merchant_zip = np.random.randint(10000, 99999)
            amount = np.random.uniform(200, 800)
            is_fraud = 1

        tx_data.append({
            'transaction_id': f'TX_{i:05d}',
            'customer_id': cid,
            'timestamp': tx_time.strftime('%Y-%m-%d %H:%M:%S'),
            'amount': round(amount, 2),
            'merchant_zip': merchant_zip,
            'customer_zip': customer_home_zip[cid],
            'actual_ground_truth_fraud': is_fraud 
        })

    df_transactions = pd.DataFrame(tx_data).sort_values(by='timestamp').reset_index(drop=True)
    df_transactions.to_csv('raw_transactions.csv', index=False)

    # 2. Database Ingestion (Assumes local MySQL running instance)
    print("📂 Step 2: Streaming transactional logs to MySQL instance...")
    # NOTE: Update credentials ('root:root') according to local configurations if required
    engine = create_engine('mysql+pymysql://root:root@localhost/pricing_system')
    df_transactions.to_sql('banking_transactions', engine, if_exists='replace', index=False)

    # 3. Database Feature Engineering via Window Views
    print("📊 Step 3: Fabricating database feature metrics engineering...")
    fraud_feature_query = """
    CREATE OR REPLACE VIEW v_transaction_features AS
    WITH behavioral_baseline AS (
        SELECT
            transaction_id, customer_id, timestamp, amount, merchant_zip, customer_zip, actual_ground_truth_fraud,
            AVG(amount) OVER(
                PARTITION BY customer_id
                ORDER BY STR_TO_DATE(timestamp, '%Y-%m-%d %H:%M:%S')
                ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
            ) as rolling_avg_amount,
            COUNT(transaction_id) OVER(
                PARTITION BY customer_id
                ORDER BY STR_TO_DATE(timestamp, '%Y-%m-%d %H:%M:%S')
                RANGE BETWEEN INTERVAL 1 HOUR PRECEDING AND CURRENT ROW
            ) as velocity_1h,
            CASE WHEN merchant_zip != customer_zip THEN 1 ELSE 0 END as zip_mismatch
        FROM banking_transactions
    )
    SELECT
        transaction_id, customer_id, timestamp, amount,
        COALESCE(rolling_avg_amount, amount) as rolling_avg_amount,
        velocity_1h, zip_mismatch,
        ROUND(amount / COALESCE(rolling_avg_amount, amount), 2) as amount_deviation_ratio,
        actual_ground_truth_fraud
    FROM behavioral_baseline;
    """
    with engine.connect() as connection:
        connection.execute(text(fraud_feature_query))

    # 4. Fetch Matrix & Train Unsupervised Machine Learning Outlier Model
    print("🤖 Step 4: Initiating Isolation Forest anomaly analytics processing...")
    df_features = pd.read_sql_query("SELECT * FROM v_transaction_features;", engine)
    
    feature_cols = ['amount', 'rolling_avg_amount', 'velocity_1h', 'zip_mismatch', 'amount_deviation_ratio']
    X = df_features[feature_cols]
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = IsolationForest(contamination=0.015, random_state=42)
    df_features['ml_predicted_anomaly'] = model.fit_predict(X_scaled)
    df_features['ml_predicted_anomaly'] = df_features['ml_predicted_anomaly'].map({1: 0, -1: 1})
    
    raw_scores = model.score_samples(X_scaled)
    scaled_scores = (1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min())) * 100
    df_features['risk_score_%'] = np.round(scaled_scores, 1)
    
    df_features.to_csv('evaluated_fraud_transactions.csv', index=False)
    print("🎯 Analytics Engine Complete! Matrix metrics exported to 'evaluated_fraud_transactions.csv'.")
    print(classification_report(df_features['actual_ground_truth_fraud'], df_features['ml_predicted_anomaly']))

if __name__ == '__main__':
    run_pipeline()
