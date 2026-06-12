import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from backend.app.models import Transaction

# Constants
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")
FEATURE_COLS = ['amount', 'rolling_avg_amount', 'velocity_1h', 'zip_mismatch', 'amount_deviation_ratio']

class MLEngine:
    _model = None
    _scaler = None

    @classmethod
    def load_model(cls):
        """Loads model and scaler from joblib file if exists."""
        if cls._model is not None and cls._scaler is not None:
            return True
        
        if os.path.exists(MODEL_PATH):
            try:
                data = joblib.load(MODEL_PATH)
                cls._model = data.get('model')
                cls._scaler = data.get('scaler')
                print("[ML ENGINE] Loaded trained Isolation Forest model successfully.")
                return True
            except Exception as e:
                print(f"[WARNING] ML Engine: Failed to load model from path: {e}")
        return False

    @classmethod
    def train_model(cls, db: Session) -> bool:
        """Trains StandardScaler and IsolationForest on historical data, and serializes it."""
        print("[ML ENGINE] Initiating model training pipeline...")
        # Get all transactions from DB
        tx_list = db.query(Transaction).all()
        if len(tx_list) < 100:
            print("[WARNING] ML Engine: Insufficient transaction history to fit model (needs >= 100). Skipping training.")
            return False

        # Load into DataFrame
        data = []
        for tx in tx_list:
            data.append({
                'amount': tx.amount,
                'rolling_avg_amount': tx.rolling_avg_amount,
                'velocity_1h': tx.velocity_1h,
                'zip_mismatch': tx.zip_mismatch,
                'amount_deviation_ratio': tx.amount_deviation_ratio
            })
        df = pd.DataFrame(data)
        
        # Fit scaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df[FEATURE_COLS])

        # Fit Isolation Forest
        model = IsolationForest(contamination=0.015, random_state=42)
        model.fit(X_scaled)

        # Save to class attributes
        cls._model = model
        cls._scaler = scaler

        # Serialize
        try:
            joblib.dump({'model': model, 'scaler': scaler}, MODEL_PATH)
            print(f"[ML ENGINE] Saved trained model and scaler to {MODEL_PATH}")
            return True
        except Exception as e:
            print(f"[WARNING] ML Engine: Failed to save model: {e}")
            return False

    @classmethod
    def score_transaction(cls, amount: float, rolling_avg: float, velocity_1h: int, zip_mismatch: int) -> tuple[int, float]:
        """
        Scores a live transaction using the trained Isolation Forest model.
        Returns:
            ml_predicted_anomaly: 0 (Normal) or 1 (Anomaly)
            risk_score: 0.0 - 100.0 (percentage anomaly risk score)
        """
        # Ensure model is loaded
        loaded = cls.load_model()
        
        # Calculate spending deviation ratio
        deviation_ratio = round(amount / max(rolling_avg, 0.01), 2)

        # Basic fallback scoring if ML model is not trained/available
        if not loaded or cls._model is None or cls._scaler is None:
            # Fallback heuristic scoring
            risk = 10.0
            if zip_mismatch == 1:
                risk += 30.0
            if deviation_ratio > 3.0:
                risk += 40.0
            if velocity_1h > 4:
                risk += 20.0
            is_anomaly = 1 if risk >= 75.0 else 0
            return is_anomaly, min(risk, 100.0)

        # Prepare feature vector
        x_raw = np.array([[amount, rolling_avg, velocity_1h, zip_mismatch, deviation_ratio]])
        
        try:
            # Scale features
            x_scaled = cls._scaler.transform(x_raw)
            
            # Predict outlier (1 = inlier, -1 = outlier)
            pred = cls._model.predict(x_scaled)[0]
            ml_predicted_anomaly = 1 if pred == -1 else 0
            
            # Score sample (closer to 0 is normal, negative values are anomalies)
            raw_score = cls._model.score_samples(x_scaled)[0]
            
            # Map score in [-0.75, -0.45] to [100.0, 0.0]% risk.
            score_clamped = max(-0.75, min(-0.45, raw_score))
            risk_pct = round(( -0.45 - score_clamped ) / 0.30 * 100.0, 1)
            
            return ml_predicted_anomaly, risk_pct
        except Exception as e:
            print(f"[WARNING] ML Engine: Error during scoring: {e}. Falling back to heuristics.")
            # Fallback
            risk = 10.0 + (30.0 if zip_mismatch else 0.0) + (40.0 if deviation_ratio > 3.0 else 0.0)
            return (1 if risk >= 75.0 else 0), min(risk, 100.0)
