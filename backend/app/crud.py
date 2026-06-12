from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import Optional, List
from backend.app.models import Analyst, Transaction, Rule, Alert, AuditLog
from backend.app.schemas import AnalystCreate, TransactionCreate, RuleCreate, RuleUpdate
from backend.app.auth import get_password_hash

# 1. Analyst CRUD
def get_analyst_by_id(db: Session, analyst_id: int) -> Optional[Analyst]:
    return db.query(Analyst).filter(Analyst.id == analyst_id).first()

def get_analyst_by_username(db: Session, username: str) -> Optional[Analyst]:
    return db.query(Analyst).filter(Analyst.username == username).first()

def create_analyst(db: Session, analyst: AnalystCreate) -> Analyst:
    hashed_pwd = get_password_hash(analyst.password)
    db_analyst = Analyst(
        username=analyst.username,
        hashed_password=hashed_pwd,
        role=analyst.role
    )
    db.add(db_analyst)
    db.commit()
    db.refresh(db_analyst)
    return db_analyst

# 2. Transaction CRUD
def get_transaction_by_id(db: Session, tx_id: str) -> Optional[Transaction]:
    return db.query(Transaction).filter(Transaction.transaction_id == tx_id).first()

def get_transactions(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    customer_id: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    only_flagged: Optional[bool] = False
) -> List[Transaction]:
    query = db.query(Transaction)
    if customer_id:
        query = query.filter(Transaction.customer_id == customer_id)
    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)
    if only_flagged:
        query = query.filter(Transaction.is_flagged == 1)
        
    return query.order_by(desc(Transaction.timestamp)).offset(skip).limit(limit).all()

def create_transaction(db: Session, tx: Transaction, commit: bool = True) -> Transaction:
    db.add(tx)
    if commit:
        db.commit()
        db.refresh(tx)
    return tx

# 3. Rule CRUD
def get_rule(db: Session, rule_id: int) -> Optional[Rule]:
    return db.query(Rule).filter(Rule.id == rule_id).first()

def get_rules(db: Session, skip: int = 0, limit: int = 100, only_active: bool = False) -> List[Rule]:
    query = db.query(Rule)
    if only_active:
        query = query.filter(Rule.is_active == True)
    return query.offset(skip).limit(limit).all()

def create_rule(db: Session, rule: RuleCreate) -> Rule:
    db_rule = Rule(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule

def update_rule(db: Session, rule_id: int, rule_update: RuleUpdate) -> Optional[Rule]:
    db_rule = get_rule(db, rule_id)
    if not db_rule:
        return None
    
    update_data = rule_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rule, key, value)
        
    db.commit()
    db.refresh(db_rule)
    return db_rule

def delete_rule(db: Session, rule_id: int) -> bool:
    db_rule = get_rule(db, rule_id)
    if not db_rule:
        return False
    db.delete(db_rule)
    db.commit()
    return True

# 4. Alert CRUD
def get_alert_by_id(db: Session, alert_id: int) -> Optional[Alert]:
    return db.query(Alert).filter(Alert.id == alert_id).first()

def get_alert_by_transaction_id(db: Session, tx_id: str) -> Optional[Alert]:
    return db.query(Alert).filter(Alert.transaction_id == tx_id).first()

def get_alerts(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    status: Optional[str] = None,
    min_risk: Optional[float] = None
) -> List[Alert]:
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    if min_risk is not None:
        query = query.filter(Alert.risk_score >= min_risk)
        
    return query.order_by(desc(Alert.risk_score)).offset(skip).limit(limit).all()

def create_alert(db: Session, alert: Alert) -> Alert:
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert

def update_alert_status(db: Session, alert_id: int, status_str: str, notes: str, analyst_id: int) -> Optional[Alert]:
    db_alert = get_alert_by_id(db, alert_id)
    if not db_alert:
        return None
    
    db_alert.status = status_str
    db_alert.notes = notes
    db_alert.analyst_id = analyst_id
    db_alert.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_alert)
    return db_alert

# 5. AuditLog CRUD
def create_audit_log(db: Session, analyst_id: int, action: str, target_type: str, target_id: str) -> AuditLog:
    db_log = AuditLog(
        analyst_id=analyst_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id)
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_audit_logs(db: Session, skip: int = 0, limit: int = 100) -> List[AuditLog]:
    return db.query(AuditLog).order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()
