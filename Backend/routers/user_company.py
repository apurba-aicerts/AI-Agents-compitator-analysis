from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models
from core import auth as auth_core
from schemas import UserCompanyMonitoringCreate, UserCompanyMonitoringOut
# Get all companies monitored by any user
from sqlalchemy import distinct

router = APIRouter(prefix="/user-company", tags=["user_company"])

# Add a company to user's monitoring list
@router.post("/", response_model=UserCompanyMonitoringOut, status_code=status.HTTP_201_CREATED)
def add_company_monitoring(payload: UserCompanyMonitoringCreate, db: Session = Depends(auth_core.get_db)):
    existing = db.query(models.UserCompanyMonitoring).filter(
        models.UserCompanyMonitoring.user_id == payload.user_id,
        models.UserCompanyMonitoring.company_id == payload.company_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already monitoring this company")
    
    monitoring = models.UserCompanyMonitoring(
        user_id=payload.user_id,
        company_id=payload.company_id
    )
    db.add(monitoring)
    db.commit()
    db.refresh(monitoring)
    return monitoring

# Get all companies monitored by a user
@router.get("/{user_id}", response_model=list[UserCompanyMonitoringOut])
def get_user_companies(user_id: int, db: Session = Depends(auth_core.get_db)):
    companies = db.query(models.UserCompanyMonitoring).filter(
        models.UserCompanyMonitoring.user_id == user_id,
        models.UserCompanyMonitoring.is_active == True
    ).all()
    return companies


# Get all unique active company IDs monitored by any user
@router.get("/active-companies", response_model=list[int])
def get_active_companies(db: Session = Depends(auth_core.get_db)):
    companies = db.query(distinct(models.UserCompanyMonitoring.company_id)).filter(
        models.UserCompanyMonitoring.is_active == True
    ).all()
    # .all() returns list of tuples, convert to simple list
    return [c[0] for c in companies]

# Get all active company IDs monitored by a specific user
@router.get("/companies-by-user/{user_id}", response_model=list[int])
def get_companies_by_user(user_id: int, db: Session = Depends(auth_core.get_db)):
    companies = db.query(models.UserCompanyMonitoring.company_id).filter(
        models.UserCompanyMonitoring.user_id == user_id,
        models.UserCompanyMonitoring.is_active == True
    ).all()
    # .all() returns list of tuples, convert to simple list
    return [c[0] for c in companies]
