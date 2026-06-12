from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base

class Analyst(Base):
    __tablename__ = "analysts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="ANALYST")  # ADMIN, ANALYST
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    alerts = relationship("Alert", back_populates="analyst")
    audit_logs = relationship("AuditLog", back_populates="analyst")

class Transaction(Base):
    __tablename__ = "banking_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(50), unique=True, index=True, nullable=False)
    customer_id = Column(String(50), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    merchant_zip = Column(Integer, nullable=False)
    customer_zip = Column(Integer, nullable=False)
    
    # Feature engineered fields
    rolling_avg_amount = Column(Float, nullable=False)
    velocity_1h = Column(Integer, nullable=False)
    zip_mismatch = Column(Integer, nullable=False)
    amount_deviation_ratio = Column(Float, nullable=False)
    
    # ML & Rule engine scoring
    risk_score = Column(Float, default=0.0)
    ml_predicted_anomaly = Column(Integer, default=0)
    actual_ground_truth_fraud = Column(Integer, default=0)
    is_flagged = Column(Integer, default=0)

    # Relationship
    alert = relationship("Alert", back_populates="transaction", uselist=False)

class Rule(Base):
    __tablename__ = "fraud_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    field_name = Column(String(50), nullable=False)  # amount, velocity_1h, zip_mismatch, amount_deviation_ratio
    operator = Column(String(10), nullable=False)    # >, <, ==, !=
    threshold_value = Column(Float, nullable=False)
    risk_modifier = Column(Float, nullable=False)    # Score delta (+20, +50, etc.)
    is_active = Column(Boolean, default=True)

class Alert(Base):
    __tablename__ = "system_alerts"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(50), ForeignKey("banking_transactions.transaction_id"), nullable=False, unique=True)
    risk_score = Column(Float, nullable=False)
    status = Column(String(20), default="OPEN")  # OPEN, UNDER_REVIEW, RESOLVED_SAFE, RESOLVED_FRAUD
    analyst_id = Column(Integer, ForeignKey("analysts.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transaction = relationship("Transaction", back_populates="alert")
    analyst = relationship("Analyst", back_populates="alerts")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    analyst_id = Column(Integer, ForeignKey("analysts.id"), nullable=False)
    action = Column(String(100), nullable=False)  # e.g., CLAIM_ALERT, RESOLVE_ALERT, CREATE_RULE
    target_type = Column(String(50), nullable=False)  # e.g., ALERT, RULE, TRANSACTION
    target_id = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationship
    analyst = relationship("Analyst", back_populates="audit_logs")
