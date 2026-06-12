from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app.database import get_db
from backend.app.schemas import RuleCreate, RuleOut, RuleUpdate
from backend.app.models import Analyst
from backend.app.crud import get_rule, get_rules, create_rule, update_rule, delete_rule, create_audit_log
from backend.app.auth import get_current_user, get_admin_user

router = APIRouter(prefix="/rules", tags=["Rules Engine Management"])

@router.get("/", response_model=List[RuleOut])
def read_rules(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Analyst = Depends(get_current_user)
):
    """Retrieve all static fraud scoring rules (Analyst auth required)."""
    return get_rules(db=db, skip=skip, limit=limit)

@router.post("/", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def add_rule(
    rule: RuleCreate,
    db: Session = Depends(get_db),
    current_admin: Analyst = Depends(get_admin_user)
):
    """Create a new fraud rule configuration (Admin only)."""
    # Validate field name is supported
    valid_fields = ['amount', 'rolling_avg_amount', 'velocity_1h', 'zip_mismatch', 'amount_deviation_ratio']
    if rule.field_name not in valid_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Field name must be one of: {', '.join(valid_fields)}"
        )
        
    valid_operators = ['>', '<', '>=', '<=', '==', '!=']
    if rule.operator not in valid_operators:
        raise HTTPException(
            status_code=400,
            detail=f"Operator must be one of: {', '.join(valid_operators)}"
        )

    db_rule = create_rule(db, rule)
    
    # Audit log
    create_audit_log(
        db=db,
        analyst_id=current_admin.id,
        action="CREATE_RULE",
        target_type="RULE",
        target_id=str(db_rule.id)
    )
    
    return db_rule

@router.put("/{rule_id}", response_model=RuleOut)
def modify_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    current_admin: Analyst = Depends(get_admin_user)
):
    """Modify details or toggle status of an existing fraud rule (Admin only)."""
    # Validation checks
    if payload.field_name:
        valid_fields = ['amount', 'rolling_avg_amount', 'velocity_1h', 'zip_mismatch', 'amount_deviation_ratio']
        if payload.field_name not in valid_fields:
            raise HTTPException(status_code=400, detail="Invalid field_name")
    if payload.operator:
        valid_operators = ['>', '<', '>=', '<=', '==', '!=']
        if payload.operator not in valid_operators:
            raise HTTPException(status_code=400, detail="Invalid operator")

    db_rule = update_rule(db, rule_id, payload)
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    # Audit log
    create_audit_log(
        db=db,
        analyst_id=current_admin.id,
        action="UPDATE_RULE",
        target_type="RULE",
        target_id=str(db_rule.id)
    )
    
    return db_rule

@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_admin: Analyst = Depends(get_admin_user)
):
    """Delete a fraud scoring rule permanently (Admin only)."""
    success = delete_rule(db, rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    # Audit log
    create_audit_log(
        db=db,
        analyst_id=current_admin.id,
        action="DELETE_RULE",
        target_type="RULE",
        target_id=str(rule_id)
    )
    return None
