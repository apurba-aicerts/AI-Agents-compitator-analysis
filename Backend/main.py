# # main.py
# from fastapi import FastAPI,Depends
# from core.database import Base, engine
# from routers import crawler, company, company_social, auth,dashboard,alert_sentiments, comparisons
# from core.auth import get_current_user


# Base.metadata.create_all(bind=engine)

# app = FastAPI(title="Competitor AI Agent")

# # app.include_router(auth.router, prefix="/api", tags=["auth"])
# # app.include_router(crawler.router, prefix="/api", tags=["crawler"],dependencies=[Depends(get_current_user)])
# # app.include_router(company.router, prefix="/api", tags=["companies"],dependencies=[Depends(get_current_user)])
# # app.include_router(company_social.router, prefix="/api", tags=["company_socials"],dependencies=[Depends(get_current_user)])
# # app.include_router(dashboard.router, prefix="/api", dependencies=[Depends(get_current_user)])
# # app.include_router(alert_sentiments.router, prefix="/api", dependencies=[Depends(get_current_user)])
# # app.include_router(comparisons.router, prefix="/api", dependencies=[Depends(get_current_user)])

# app.include_router(auth.router, prefix="/api", tags=["auth"])
# app.include_router(crawler.router, prefix="/api", tags=["crawler"])
# app.include_router(company.router, prefix="/api", tags=["companies"])
# app.include_router(company_social.router, prefix="/api", tags=["company_socials"])
# app.include_router(dashboard.router, prefix="/api")
# app.include_router(alert_sentiments.router, prefix="/api")
# app.include_router(comparisons.router, prefix="/api")

import os
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from core.database import Base, engine

from routers import crawler, company, company_social, auth, dashboard, alert_sentiments, comparisons

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
Base.metadata.create_all(bind=engine)

# Global scheduler instance
scheduler = None

def run_crawler_job():
    """Execute crawler job by calling service functions directly"""
    try:
        logger.info("Starting scheduled crawler job...")
        from services.crawler_service import crawl_linkedin_all, scroll_companies
        
        crawl_result = crawl_linkedin_all(day="yesterday")
        scroll_result = scroll_companies(day="yesterday")
        
        logger.info(f"Crawl Result: {crawl_result.get('message')}")
        logger.info(f"Scroll Result: {scroll_result.get('message')}")
        logger.info(
            f"✓ Scheduled crawler job completed: "
            f"Posts Scraped: {crawl_result.get('total_posts_scraped', 0) + scroll_result.get('posts_scraped', 0)}, "
            f"Posts Saved: {crawl_result.get('total_posts_saved', 0) + scroll_result.get('posts_saved', 0)}, "
            f"Alerts Created: {crawl_result.get('total_alerts_saved', 0) + scroll_result.get('alerts_saved', 0)}"
        )
    except Exception as e:
        logger.error(f"Error in scheduled crawler job: {str(e)}", exc_info=True)

def start_scheduler():
    """Initialize and start the background scheduler"""
    global scheduler
    try:
        scheduler = BackgroundScheduler(timezone=timezone("Asia/Kolkata"))
        # Schedule job to run at 2 AM IST daily
        trigger = CronTrigger(hour=2, minute=0, timezone="Asia/Kolkata")
        scheduler.add_job(
            run_crawler_job,
            trigger=trigger,
            id="daily_crawler_job",
            name="Daily LinkedIn & Web Crawler",
            replace_existing=True
        )
        scheduler.start()
        logger.info("Scheduler started successfully. Job scheduled for 2 AM IST daily.")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {str(e)}", exc_info=True)

def stop_scheduler():
    """Gracefully shutdown the scheduler"""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown events"""
    start_scheduler()
    yield
    stop_scheduler()

# Initialize FastAPI app with lifespan
app = FastAPI(title="Competitor AI Agent", lifespan=lifespan)

# Auth router (no authentication required)
app.include_router(auth.router, prefix="/api", tags=["auth"])

# All routes
app.include_router(crawler.router, prefix="/api", tags=["crawler"])
app.include_router(company.router, prefix="/api", tags=["companies"])
app.include_router(company_social.router, prefix="/api", tags=["company_socials"])
app.include_router(dashboard.router, prefix="/api")
app.include_router(alert_sentiments.router, prefix="/api")
app.include_router(comparisons.router, prefix="/api")

@app.get("/")
def read_root():
    """Health check endpoint"""
    return {"message": "Competitor AI Agent is running"}