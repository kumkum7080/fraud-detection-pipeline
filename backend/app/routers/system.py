import os
import time
import random
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db, SessionLocal
from backend.app.redis_client import RedisTracker
from backend.app.ml_engine import MLEngine, MODEL_PATH
from backend.app.auth import get_admin_user, get_current_user
from backend.app.models import Analyst, Transaction
from backend.app.routers.transactions import score_and_create_transaction
from backend.app.schemas import TransactionCreate

router = APIRouter(prefix="/system", tags=["System Controls & Live Simulation"])

# Global tracker for simulation task
_sim_task = None

async def run_simulation_loop():
    """Asynchronous loop generating mock credit card transactions dynamically."""
    print("[SIMULATOR] Transaction stream simulation STARTED.")
    db = SessionLocal()
    try:
        # Load customer base for random selection
        # (CUST_001 to CUST_100)
        customer_ids = [f'CUST_{i:03d}' for i in range(1, 101)]
        
        # Cache customer home zips to simulate geo-variance
        customer_zips = {}
        # Fetch from DB or generate if not found
        txs = db.query(Transaction).limit(100).all()
        for t in txs:
            customer_zips[t.customer_id] = t.customer_zip
            
        # Fallback values if DB is empty
        for cid in customer_ids:
            if cid not in customer_zips:
                customer_zips[cid] = random.randint(10000, 99999)

        while RedisTracker.get_simulator_status():
            # Create a mock transaction
            cid = random.choice(customer_ids)
            amount = round(random.expovariate(1/35.0) + 2.0, 2)
            is_fraud = 0
            merchant_zip = customer_zips[cid]

            # Injected anomalies (10% anomaly rate for active telemetry display)
            fraud_roll = random.random()
            if fraud_roll < 0.04:  # High amount outlier
                amount = round(random.uniform(1800, 4800), 2)
                is_fraud = 1
            elif fraud_roll < 0.09:  # Geographical variance outlier
                merchant_zip = random.randint(10000, 99999)
                while merchant_zip == customer_zips[cid]:
                    merchant_zip = random.randint(10000, 99999)
                amount = round(random.uniform(150, 750), 2)
                is_fraud = 1

            tx_payload = TransactionCreate(
                customer_id=cid,
                amount=amount,
                merchant_zip=merchant_zip,
                customer_zip=customer_zips[cid],
                timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                actual_ground_truth_fraud=is_fraud
            )

            try:
                # We scoring and write inside a dedicated session
                with SessionLocal() as session:
                    score_and_create_transaction(tx_payload, session)
            except Exception as e:
                print(f"[WARNING] Simulator: Ingestion error: {e}")

            # Stream delay (e.g. every 2 seconds)
            await asyncio.sleep(2.0)

    except Exception as e:
        print(f"[WARNING] Simulator: Thread loop exception: {e}")
    finally:
        db.close()
        print("[SIMULATOR] Transaction stream simulation TERMINATED.")

@router.get("/status")
def get_system_status(db: Session = Depends(get_db), current_user: Analyst = Depends(get_current_user)):
    """Retrieve machine learning model metadata details and live simulation state."""
    model_trained = os.path.exists(MODEL_PATH)
    last_trained = None
    if model_trained:
        mtime = os.path.getmtime(MODEL_PATH)
        last_trained = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

    # Count transaction count to check if model can be retrained
    tx_count = db.query(Transaction).count()

    return {
        "model_trained": model_trained,
        "model_last_trained": last_trained,
        "historical_tx_count": tx_count,
        "can_retrain": tx_count >= 100,
        "simulation_running": RedisTracker.get_simulator_status()
    }

@router.post("/retrain")
def retrain_ml_model(db: Session = Depends(get_db), current_admin: Analyst = Depends(get_admin_user)):
    """Triggers standard scaler and Isolation Forest retraining on historical data logs (Admin only)."""
    success = MLEngine.train_model(db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model retraining failed. Ensure at least 100 transactions exist in the database."
        )
    return {"message": "Isolation Forest model retrained and serialized successfully."}

@router.post("/simulation/start")
async def start_simulation(current_user: Analyst = Depends(get_current_user)):
    """Starts the real-time background credit card transaction streamer (Analyst auth required)."""
    global _sim_task
    
    if RedisTracker.get_simulator_status():
        return {"message": "Simulation is already running."}
        
    RedisTracker.set_simulator_status(True)
    
    # Launch async loop task
    _sim_task = asyncio.create_task(run_simulation_loop())
    
    return {"message": "Real-time mock transaction simulation stream started."}

@router.post("/simulation/stop")
async def stop_simulation(current_user: Analyst = Depends(get_current_user)):
    """Stops the real-time background transaction streamer (Analyst auth required)."""
    if not RedisTracker.get_simulator_status():
        return {"message": "Simulation is already stopped."}
        
    RedisTracker.set_simulator_status(False)
    return {"message": "Real-time mock transaction simulation stream stopped."}
