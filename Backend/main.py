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
from pytz import timezone, UTC

from core.database import Base, engine

from routers import crawler, company, company_social, auth, dashboard, alert_sentiments, comparisons, reddit

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

def run_weekly_analysis_job():
    """Run competitor analysis for all companies weekly"""
    from core.database import SessionLocal
    from services.competitor_analyzer import crawl_website, analyze_with_openai
    from models import Company, CompetitorAnalysis
    import json

    db = SessionLocal()
    try:
        companies = db.query(Company).all()
        if not companies:
            logger.info("No companies found for weekly competitor analysis.")
            return

        for company in companies:
            if not company.website:
                continue

            raw_data = crawl_website(company.website)
            if not raw_data:
                continue

            insights = analyze_with_openai(raw_data)

            analysis = CompetitorAnalysis(
                company_id=company.company_id,
                company_name=company.company_name,
                website_url=company.website,
                raw_data=json.dumps(raw_data, indent=2),
                analysis_json=json.dumps(insights, indent=2),
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
            logger.info(f"✓ Weekly analysis completed for {company.company_name}")

    except Exception as e:
        logger.error(f"Error in weekly competitor analysis job: {str(e)}", exc_info=True)
    finally:
        db.close()

def start_scheduler():
    """Initialize and start the background scheduler"""
    global scheduler
    try:
        scheduler = BackgroundScheduler(timezone=UTC)
        # Schedule job to run at 2 AM IST daily
        daily_trigger = CronTrigger(hour=2, minute=0, timezone=UTC)
        scheduler.add_job(
            run_crawler_job,
            trigger=daily_trigger,
            id="daily_crawler_job",
            name="Daily LinkedIn & Web Crawler",
            replace_existing=True
        )

        weekly_trigger = CronTrigger(day_of_week="sun", hour=3, minute=30, timezone=UTC)  
        scheduler.add_job(
            run_weekly_analysis_job,
            trigger=weekly_trigger,
            id="weekly_competitor_analysis",
            name="Weekly Competitor Analysis",
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

# Reddit router (open access)
app.include_router(reddit.router, prefix="/api", tags=["reddit"])
@app.get("/")
def read_root():
    """Health check endpoint"""
    return {"message": "Competitor AI Agent is running"}