from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from backend.app.database import get_db
from backend.app.schemas import Token, AnalystOut, AnalystCreate
from backend.app.crud import get_analyst_by_username, create_analyst
from backend.app.auth import verify_password, create_access_token, get_current_user, get_admin_user
from backend.app.models import Analyst

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_analyst_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=AnalystOut)
def read_users_me(current_user: Analyst = Depends(get_current_user)):
    return current_user

@router.post("/register", response_model=AnalystOut, status_code=status.HTTP_201_CREATED)
def register_analyst(
    analyst: AnalystCreate, 
    db: Session = Depends(get_db), 
    current_admin: Analyst = Depends(get_admin_user)
):
    existing_user = get_analyst_by_username(db, analyst.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    return create_analyst(db, analyst)
