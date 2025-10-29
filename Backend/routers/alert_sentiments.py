from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, and_
from typing import List, Optional
from datetime import datetime, timedelta

from core.database import SessionLocal
from core.auth import get_current_user
import models
import schemas

# router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Dashboard APIs ---
@router.get("/alerts/today", response_model=List[schemas.CompanyDailyAlerts])
def get_today_alerts_grouped_by_company(
    db: Session = Depends(get_db)
):
    """
    Retrieves all alerts created today (UTC), grouped by company.
    Each company entry includes all its alerts with full post context.
    """
    # Calculate today's date range in UTC
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Query alerts created today with company and post details
    alerts_today = (
        db.query(models.Alert, models.Company, models.SocialMediaPost)
        .join(models.Company, models.Alert.company_id == models.Company.company_id)
        .outerjoin(models.SocialMediaPost, models.Alert.post_id == models.SocialMediaPost.id)
        .filter(models.Alert.created_at >= today_start)
        .filter(models.Alert.created_at < today_end)
        .order_by(models.Company.company_name, models.Alert.created_at.desc())
        .all()
    )
    
    # Group alerts by company
    company_alerts_map = {}
    
    for alert, company, post in alerts_today:
        company_id = company.company_id
        
        # Initialize company entry if not exists
        if company_id not in company_alerts_map:
            company_alerts_map[company_id] = {
                "company_id": company_id,
                "company_name": company.company_name,
                "alerts": []
            }
        
        # Build post details if post exists
        post_details = None
        if post:
            post_details = schemas.PostDetailsInAlert(
                post_id=post.id,
                post_url=post.post_url,
                post_description=post.post_description,
                posted_at=post.posted_at,
                likes=post.likes,
                comments_count=post.comments_count,
                shares=post.shares,
                sentiment_label=post.sentiment_label,
                sentiment_score=post.sentiment_score
            )
        
        # Build alert with post
        alert_with_post = schemas.AlertWithPost(
            alert_id=alert.alert_id,
            alert_message=alert.alert_message,
            severity=alert.severity,
            created_at=alert.created_at,
            post=post_details
        )
        
        company_alerts_map[company_id]["alerts"].append(alert_with_post)
    
    # Convert map to list and return
    result = [
        schemas.CompanyDailyAlerts(**company_data)
        for company_data in company_alerts_map.values()
    ]
    
    return result

@router.get("/alerts", response_model=List[schemas.AlertOut])
def get_alerts(
    db: Session = Depends(get_db),
    company_id: Optional[int] = Query(None),
    limit: int = Query(10, le=50)
):
    """
    Retrieves a list of alerts, optionally filtered by company ID.
    """
    query = db.query(models.Alert)
    if company_id:
        query = query.filter(models.Alert.company_id == company_id)

    alerts = query.order_by(models.Alert.created_at.desc()).limit(limit).all()
    return alerts

@router.get("/posts-with-alerts", response_model=List[schemas.PostWithAlert])
def get_posts_with_alerts(
    db: Session = Depends(get_db),
    company_id: Optional[int] = Query(None),
    limit: int = Query(10, le=50)
):
    """
    Retrieves posts that have associated alerts, combining data from both tables.
    """
    query = (
        db.query(models.SocialMediaPost, models.Alert)
        .join(models.Alert, models.SocialMediaPost.id == models.Alert.post_id)
    )

    if company_id:
        query = query.filter(and_(models.SocialMediaPost.company_id == company_id, models.Alert.company_id == company_id))

    posts_with_alerts = query.order_by(models.Alert.created_at.desc()).limit(limit).all()
    
    result = []
    for post, alert in posts_with_alerts:
        result.append(schemas.PostWithAlert(
            id=post.id,
            company_id=post.company_id,
            post_url=post.post_url,
            post_description=post.post_description,
            likes=post.likes,
            comments_count=post.comments_count,
            shares=post.shares,
            sentiment_label=post.sentiment_label,
            sentiment_score=post.sentiment_score,
            posted_at=post.posted_at,
            alert_id=alert.alert_id,
            alert_message=alert.alert_message,
            severity=alert.severity,
            alert_created_at=alert.created_at
        ))
    return result

@router.get("/sentiment-comparison", response_model=schemas.SentimentStats)
def get_sentiment_comparison(
    db: Session = Depends(get_db),
    company_id: int = Query(...),
    days: int = Query(30, ge=1, le=365)
):
    """
    Returns sentiment distribution for a given company over a time frame.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            models.SocialMediaPost.sentiment_label,
            func.count(models.SocialMediaPost.id),
        )
        .filter(models.SocialMediaPost.company_id == company_id)
        .filter(models.SocialMediaPost.posted_at >= cutoff)
        .group_by(models.SocialMediaPost.sentiment_label)
        .all()
    )

    stats = {"positive": 0, "neutral": 0, "negative": 0}
    for label, count in rows:
        if not label:
            continue
        label = label.lower()
        if "pos" in label:
            stats["positive"] += count
        elif "neg" in label:
            stats["negative"] += count
        else:
            stats["neutral"] += count

    return schemas.SentimentStats(**stats)

@router.get("/alerts/by-date", response_model=List[schemas.CompanyDailyAlerts])
def get_alerts_by_date_range(
    db: Session = Depends(get_db),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format")
):
    """
    Retrieves alerts grouped by company for a specific date or date range (UTC).
    If only `start_date` is provided, it fetches alerts for that single day.
    """

    # --- Handle date range ---
    if not start_date:
        raise HTTPException(status_code=400, detail="start_date is required")

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
    else:
        # If only start_date is given, fetch that single day's data
        end_dt = start_dt + timedelta(days=1)

    # --- Query alerts ---
    alerts_in_range = (
        db.query(models.Alert, models.Company, models.SocialMediaPost)
        .join(models.Company, models.Alert.company_id == models.Company.company_id)
        .outerjoin(models.SocialMediaPost, models.Alert.post_id == models.SocialMediaPost.id)
        .filter(models.Alert.created_at >= start_dt)
        .filter(models.Alert.created_at < end_dt)
        .order_by(models.Company.company_name, models.Alert.created_at.desc())
        .all()
    )

    # --- Group alerts by company ---
    company_alerts_map = {}

    for alert, company, post in alerts_in_range:
        company_id = company.company_id
        if company_id not in company_alerts_map:
            company_alerts_map[company_id] = {
                "company_id": company_id,
                "company_name": company.company_name,
                "alerts": []
            }

        post_details = None
        if post:
            post_details = schemas.PostDetailsInAlert(
                post_id=post.id,
                post_url=post.post_url,
                post_description=post.post_description,
                posted_at=post.posted_at,
                likes=post.likes,
                comments_count=post.comments_count,
                shares=post.shares,
                sentiment_label=post.sentiment_label,
                sentiment_score=post.sentiment_score
            )

        company_alerts_map[company_id]["alerts"].append(
            schemas.AlertWithPost(
                alert_id=alert.alert_id,
                alert_message=alert.alert_message,
                severity=alert.severity,
                created_at=alert.created_at,
                post=post_details
            )
        )

    # --- Return result ---
    return [
        schemas.CompanyDailyAlerts(**company_data)
        for company_data in company_alerts_map.values()
    ]
