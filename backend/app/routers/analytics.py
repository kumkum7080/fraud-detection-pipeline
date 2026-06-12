from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List
from datetime import datetime, timedelta
from backend.app.database import get_db
from backend.app.schemas import SystemMetrics, ScatterPoint, AlertTrendPoint, RiskHistogramPoint
from backend.app.models import Transaction, Alert, Analyst
from backend.app.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Dashboard Telemetry Analytics"])

@router.get("/metrics", response_model=SystemMetrics)
def read_system_metrics(db: Session = Depends(get_db), current_user: Analyst = Depends(get_current_user)):
    """Retrieve high-level cyber telemetry metrics for indicator panels."""
    total_traffic = db.query(Transaction).count()
    active_alerts = db.query(Alert).filter(Alert.status.in_(["OPEN", "UNDER_REVIEW"])).count()
    
    avg_risk_res = db.query(func.avg(Transaction.risk_score)).scalar()
    system_baseline_risk = round(float(avg_risk_res), 1) if avg_risk_res is not None else 0.0
    
    # Engine Detection Accuracy (Recall Rate: Caught Fraud / Total Actual Fraud)
    true_positives = db.query(Transaction).filter(
        Transaction.ml_predicted_anomaly == 1, 
        Transaction.actual_ground_truth_fraud == 1
    ).count()
    total_actual = db.query(Transaction).filter(Transaction.actual_ground_truth_fraud == 1).count()
    
    engine_detection_accuracy = round((true_positives / total_actual * 100), 1) if total_actual > 0 else 100.0

    return {
        "total_traffic": total_traffic,
        "active_alerts": active_alerts,
        "system_baseline_risk": system_baseline_risk,
        "engine_detection_accuracy": engine_detection_accuracy
    }

@router.get("/scatter", response_model=List[ScatterPoint])
def read_scatter_data(db: Session = Depends(get_db), current_user: Analyst = Depends(get_current_user)):
    """Retrieve scatter plot mapping coordinates (Deviation Ratio vs velocity) for 500 recent transactions."""
    # We fetch the latest 500 transactions to map current state without overloading frontend
    txs = db.query(Transaction).order_by(Transaction.timestamp.desc()).limit(500).all()
    
    return [
        {
            "transaction_id": tx.transaction_id,
            "amount": tx.amount,
            "amount_deviation_ratio": tx.amount_deviation_ratio,
            "velocity_1h": tx.velocity_1h,
            "risk_score": tx.risk_score,
            "ml_predicted_anomaly": tx.ml_predicted_anomaly,
            "actual_ground_truth_fraud": tx.actual_ground_truth_fraud
        }
        for tx in txs
    ]

@router.get("/trends", response_model=List[AlertTrendPoint])
def read_alert_trends(db: Session = Depends(get_db), current_user: Analyst = Depends(get_current_user)):
    """Retrieve chronological 15-day alert trends split by daily counts and confirmed frauds."""
    # Run dynamic group-by query using MySQL raw extraction compatible with standard syntax
    query = """
        SELECT 
            DATE_FORMAT(created_at, '%Y-%m-%d') as alert_date, 
            COUNT(*) as total_count,
            SUM(CASE WHEN status = 'RESOLVED_FRAUD' THEN 1 ELSE 0 END) as fraud_count
        FROM system_alerts 
        GROUP BY DATE_FORMAT(created_at, '%Y-%m-%d') 
        ORDER BY alert_date ASC 
        LIMIT 15;
    """
    res = db.execute(text(query)).fetchall()
    
    # If database is empty or new, return placeholders
    if not res:
        today = datetime.utcnow().date()
        return [{"date": (today - timedelta(days=i)).strftime('%Y-%m-%d'), "total_alerts": 0, "fraud_resolved": 0} for i in range(5)]

    return [
        {
            "date": row[0],
            "total_alerts": int(row[1]),
            "fraud_resolved": int(row[2])
        }
        for row in res
    ]

@router.get("/histogram", response_model=List[RiskHistogramPoint])
def read_risk_histogram(db: Session = Depends(get_db), current_user: Analyst = Depends(get_current_user)):
    """Retrieve risk score frequency distributions grouped in decile buckets (0-10, 10-20, etc.)."""
    # Dynamic SQL decile aggregation
    query = """
        SELECT 
            FLOOR(risk_score / 10) * 10 as bucket,
            SUM(CASE WHEN actual_ground_truth_fraud = 0 THEN 1 ELSE 0 END) as non_fraud_count,
            SUM(CASE WHEN actual_ground_truth_fraud = 1 THEN 1 ELSE 0 END) as fraud_count
        FROM banking_transactions
        GROUP BY FLOOR(risk_score / 10) * 10
        ORDER BY bucket ASC;
    """
    res = db.execute(text(query)).fetchall()
    
    # We map decile buckets from 0 to 90
    buckets_map = {b: {"non_fraud_count": 0, "fraud_count": 0} for b in range(0, 100, 10)}
    for row in res:
        b_val = int(row[0]) if row[0] is not None else 0
        # safety check
        if b_val in buckets_map:
            buckets_map[b_val] = {
                "non_fraud_count": int(row[1]),
                "fraud_count": int(row[2])
            }
            
    return [
        {
            "bucket": b,
            "non_fraud_count": vals["non_fraud_count"],
            "fraud_count": vals["fraud_count"]
        }
        for b, vals in sorted(buckets_map.items())
    ]
