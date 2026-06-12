from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

# Analyst Schemas
class AnalystBase(BaseModel):
    username: str

class AnalystCreate(AnalystBase):
    password: str
    role: Optional[str] = "ANALYST"

class AnalystOut(AnalystBase):
    id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

# Transaction Schemas
class TransactionBase(BaseModel):
    customer_id: str
    amount: float
    merchant_zip: int
    customer_zip: int
    timestamp: Optional[str] = None  # Expected format: YYYY-MM-DD HH:MM:SS

class TransactionCreate(TransactionBase):
    actual_ground_truth_fraud: Optional[int] = 0

class TransactionOut(BaseModel):
    id: int
    transaction_id: str
    customer_id: str
    timestamp: datetime
    amount: float
    merchant_zip: int
    customer_zip: int
    rolling_avg_amount: float
    velocity_1h: int
    zip_mismatch: int
    amount_deviation_ratio: float
    risk_score: float
    ml_predicted_anomaly: int
    actual_ground_truth_fraud: int
    is_flagged: int

    class Config:
        from_attributes = True

# Rule Schemas
class RuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    field_name: str  # amount, velocity_1h, zip_mismatch, amount_deviation_ratio
    operator: str    # >, <, ==, !=
    threshold_value: float
    risk_modifier: float
    is_active: Optional[bool] = True

class RuleCreate(RuleBase):
    pass

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    field_name: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[float] = None
    risk_modifier: Optional[float] = None
    is_active: Optional[bool] = None

class RuleOut(RuleBase):
    id: int

    class Config:
        from_attributes = True

# Alert Schemas
class AlertOut(BaseModel):
    id: int
    transaction_id: str
    risk_score: float
    status: str
    analyst_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    transaction: Optional[TransactionOut] = None
    analyst: Optional[AnalystBase] = None

    class Config:
        from_attributes = True

class AlertResolve(BaseModel):
    status: str  # RESOLVED_SAFE, RESOLVED_FRAUD
    notes: str

# Audit Log Schema
class AuditLogOut(BaseModel):
    id: int
    analyst_id: int
    action: str
    target_type: str
    target_id: str
    timestamp: datetime

    class Config:
        from_attributes = True

# Analytics Dashboard Schemas
class SystemMetrics(BaseModel):
    total_traffic: int
    active_alerts: int
    system_baseline_risk: float
    engine_detection_accuracy: float

class ScatterPoint(BaseModel):
    transaction_id: str
    amount: float
    amount_deviation_ratio: float
    velocity_1h: int
    risk_score: float
    ml_predicted_anomaly: int
    actual_ground_truth_fraud: int

class AlertTrendPoint(BaseModel):
    date: str
    total_alerts: int
    fraud_resolved: int

class RiskHistogramPoint(BaseModel):
    bucket: int
    non_fraud_count: int
    fraud_count: int
