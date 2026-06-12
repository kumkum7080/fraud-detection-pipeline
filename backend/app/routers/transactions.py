from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from typing import List, Optional
from backend.app.database import get_db
from backend.app.schemas import TransactionCreate, TransactionOut
from backend.app.models import Transaction, Alert, Analyst
from backend.app.crud import get_transaction_by_id, get_transactions, create_transaction
from backend.app.redis_client import RedisTracker
from backend.app.ml_engine import MLEngine
from backend.app.rules_engine import RulesEngine
from backend.app.auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.post("/", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def score_and_create_transaction(tx: TransactionCreate, db: Session = Depends(get_db)):
    """
    Ingest, score, and persist a new financial transaction in real-time.
    Calculates window features dynamically using Redis, evaluates rules,
    runs the ML Isolation Forest outlier detector, and triggers alerts if risk is high.
    """
    # 1. Ensure unique transaction_id
    tx_id = f"TX_{uuid.uuid4().hex[:10].upper()}"
    
    # 2. Parse/generate timestamp
    t_str = tx.timestamp
    if not t_str:
        t_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        t_dt = datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
    else:
        try:
            t_dt = datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Timestamp must follow 'YYYY-MM-DD HH:MM:SS' format."
            )

    # 3. Retrieve baseline profile from Redis
    rolling_avg = RedisTracker.get_rolling_avg_10(tx.customer_id, tx.amount)
    
    # Velocity 1h from Redis (add 1 to include current transaction)
    velocity_1h = RedisTracker.get_velocity_1h(tx.customer_id, t_str) + 1
    
    # Zip mismatch
    zip_mismatch = 1 if tx.merchant_zip != tx.customer_zip else 0
    
    # Deviation ratio
    deviation_ratio = round(tx.amount / max(rolling_avg, 0.01), 2)

    # 4. Run Machine Learning Isolation Forest model
    ml_predicted_anomaly, ml_risk_score = MLEngine.score_transaction(
        amount=tx.amount,
        rolling_avg=rolling_avg,
        velocity_1h=velocity_1h,
        zip_mismatch=zip_mismatch
    )

    # 5. Evaluate custom rules and calculate combined risk score
    final_risk, should_alert = RulesEngine.evaluate_and_score(
        db=db,
        amount=tx.amount,
        rolling_avg=rolling_avg,
        velocity_1h=velocity_1h,
        zip_mismatch=zip_mismatch,
        ml_predicted_anomaly=ml_predicted_anomaly,
        ml_risk_score=ml_risk_score
    )

    # 6. Save transaction to database
    db_tx = Transaction(
        transaction_id=tx_id,
        customer_id=tx.customer_id,
        timestamp=t_dt,
        amount=tx.amount,
        merchant_zip=tx.merchant_zip,
        customer_zip=tx.customer_zip,
        rolling_avg_amount=round(rolling_avg, 2),
        velocity_1h=velocity_1h,
        zip_mismatch=zip_mismatch,
        amount_deviation_ratio=deviation_ratio,
        risk_score=final_risk,
        ml_predicted_anomaly=ml_predicted_anomaly,
        actual_ground_truth_fraud=tx.actual_ground_truth_fraud,
        is_flagged=1 if should_alert else 0
    )
    
    db_tx = create_transaction(db, db_tx, commit=True)

    # 7. Log transaction in Redis to update window states
    RedisTracker.log_transaction(tx.customer_id, tx.amount, t_str)

    # 8. Create Alert if risk exceeds threshold
    if should_alert:
        db_alert = Alert(
            transaction_id=tx_id,
            risk_score=final_risk,
            status="OPEN",
            created_at=t_dt
        )
        db.add(db_alert)
        db.commit()
        
    return db_tx

@router.get("/", response_model=List[TransactionOut])
def read_transactions(
    skip: int = 0, 
    limit: int = 100, 
    customer_id: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    only_flagged: Optional[bool] = False,
    db: Session = Depends(get_db),
    current_user: Analyst = Depends(get_current_user)
):
    """Retrieve historical transaction list, supports sorting & filtering (Analyst auth required)."""
    return get_transactions(
        db=db,
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        min_amount=min_amount,
        max_amount=max_amount,
        only_flagged=only_flagged
    )

@router.get("/{tx_id}", response_model=TransactionOut)
def read_transaction(
    tx_id: str, 
    db: Session = Depends(get_db),
    current_user: Analyst = Depends(get_current_user)
):
    """Retrieve details of a specific transaction by transaction_id (Analyst auth required)."""
    db_tx = get_transaction_by_id(db, tx_id)
    if not db_tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return db_tx
