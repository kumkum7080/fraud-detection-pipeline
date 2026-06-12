from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from backend.app.database import get_db
from backend.app.schemas import AlertOut, AlertResolve
from backend.app.models import Alert, Analyst, Transaction
from backend.app.crud import get_alert_by_id, get_alerts, update_alert_status, create_audit_log
from backend.app.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["Incident Response Alerts"])

@router.get("/", response_model=List[AlertOut])
def read_alerts(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    min_risk: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: Analyst = Depends(get_current_user)
):
    """Retrieve security incident queues, filterable by status and risk (Analyst auth required)."""
    return get_alerts(db=db, skip=skip, limit=limit, status=status, min_risk=min_risk)

@router.get("/{alert_id}", response_model=AlertOut)
def read_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: Analyst = Depends(get_current_user)
):
    """Retrieve full detail of a specific alert, including transaction markers (Analyst auth required)."""
    alert = get_alert_by_id(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@router.put("/{alert_id}/claim", response_model=AlertOut)
def claim_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: Analyst = Depends(get_current_user)
):
    """Claims an open alert, setting status to 'UNDER_REVIEW' and assigning it to the analyst."""
    alert = get_alert_by_id(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    if alert.status != "OPEN":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot claim alert in '{alert.status}' state."
        )
        
    alert.status = "UNDER_REVIEW"
    alert.analyst_id = current_user.id
    alert.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)
    
    # Audit log
    create_audit_log(
        db=db,
        analyst_id=current_user.id,
        action="CLAIM_ALERT",
        target_type="ALERT",
        target_id=str(alert.id)
    )
    
    return alert

@router.put("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: int,
    payload: AlertResolve,
    db: Session = Depends(get_db),
    current_user: Analyst = Depends(get_current_user)
):
    """Resolves a claimed alert as either 'RESOLVED_SAFE' or 'RESOLVED_FRAUD'."""
    alert = get_alert_by_id(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    if alert.status == "OPEN":
        raise HTTPException(
            status_code=400,
            detail="Must claim alert and set to 'UNDER_REVIEW' before resolving."
        )
        
    if payload.status not in ["RESOLVED_SAFE", "RESOLVED_FRAUD"]:
        raise HTTPException(
            status_code=400,
            detail="Status must be either 'RESOLVED_SAFE' or 'RESOLVED_FRAUD'."
        )
        
    # Check authorization (only claimed analyst or admin can resolve)
    if alert.analyst_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot resolve an alert claimed by another analyst."
        )
        
    alert.status = payload.status
    alert.notes = payload.notes
    alert.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)
    
    # Audit log
    create_audit_log(
        db=db,
        analyst_id=current_user.id,
        action=f"RESOLVE_ALERT_{payload.status}",
        target_type="ALERT",
        target_id=str(alert.id)
    )
    
    return alert
