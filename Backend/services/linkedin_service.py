"""
LinkedIn Service
Handles LinkedIn post crawling via Apify with AI-powered analysis.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from models import SocialMediaPost, Company, CrawlerLog
from core.database import SessionLocal
from services.helpers import parse_posted_at, process_hashtags, get_api_clients
from services.llm_service import create_alert_if_needed

logger = logging.getLogger(__name__)


# ============================================================================
# MAIN CRAWL FUNCTIONS
# ============================================================================

def crawl_linkedin_company(
    db: Session, 
    company_id: int, 
    max_posts: int = 25
) -> Dict[str, Any]:
    """
    Crawl LinkedIn posts for a specific company using Apify.
    
    Args:
        db: Database session
        company_id: Company ID to crawl
        max_posts: Maximum number of posts to retrieve
        
    Returns:
        Dictionary with crawl results and sample posts
    """
    log = CrawlerLog(company_id=company_id)
    db.add(log)
    db.commit()
    db.refresh(log)
    log_id = log.log_id
    
    try:
        # Get company
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if not company:
            raise ValueError(f"Company id={company_id} not found")
        
        # Initialize API clients
        apify_client, openai_client = get_api_clients()
        
        logger.info(f"Starting Apify actor for {company.company_name}")
        
        # Run Apify actor
        actor_run_input = {
            "company_name": company.company_name.lower().replace(" ", "-"),
            "page_number": 1,
            "limit": max_posts,
            "sort": "recent",
        }
        
        actor = apify_client.actor("apimaestro/linkedin-company-posts")
        run = actor.call(run_input=actor_run_input)
        scraped_items = list(apify_client.dataset(run["defaultDatasetId"]).iterate_items())
        
        if not scraped_items:
            log.status = "completed_no_posts"
            log.end_time = datetime.utcnow()
            db.commit()
            return {
                "message": "No posts scraped from Apify.",
                "log_id": log_id,
                "posts_scraped": 0,
                "posts_saved": 0,
                "alerts_saved": 0,
                "sample": [],
            }
        
        # Process scraped items
        posts_saved = 0
        alerts_saved = 0
        sample = []
        
        for item in scraped_items:
            result = _process_linkedin_post(db, openai_client, company_id, item)
            
            if result["saved"]:
                posts_saved += 1
                sample.append(result["post_data"])
                alerts_saved += result["alerts_created"]
        
        db.commit()
        
        # Update log
        log.end_time = datetime.utcnow()
        log.status = "completed"
        log.posts_scraped = len(scraped_items)
        log.posts_saved = posts_saved
        log.alerts_saved = alerts_saved
        db.commit()
        
        logger.info(
            f"Crawl completed for {company.company_name}: "
            f"{len(scraped_items)} scraped, {posts_saved} saved, {alerts_saved} alerts"
        )
        
        return {
            "message": "Crawl completed successfully using Apify.",
            "log_id": log_id,
            "posts_scraped": len(scraped_items),
            "posts_saved": posts_saved,
            "alerts_saved": alerts_saved,
            "sample": sample,
        }
    
    except Exception as e:
        db.rollback()
        log.end_time = datetime.utcnow()
        log.status = "failed"
        log.error_message = str(e)
        db.commit()
        logger.exception("Crawler run failed")
        raise


def crawl_linkedin_all(day: str = "yesterday", max_posts_per_company: int = 5) -> Dict[str, Any]:
    """
    Crawl LinkedIn posts for all companies in the database from target date.
    
    Args:
        day: "yesterday" or "today" to determine date range
        max_posts_per_company: Maximum posts to process per company
        
    Returns:
        Dictionary with crawl results including per-company details
    """
    db = SessionLocal()
    log = CrawlerLog()
    
    try:
        db.add(log)
        db.commit()
        db.refresh(log)
        log_id = log.log_id
        
        # Calculate date range
        target_date = (
            datetime.now(timezone.utc).date()
            if day == "today"
            else datetime.now(timezone.utc).date() - timedelta(days=1)
        )
        date_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        date_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        logger.info(f"Crawling LinkedIn posts from {day}: {target_date} (UTC)")
        
        # Fetch all companies
        companies = db.query(Company).all()
        
        if not companies:
            log.status = "completed_no_companies"
            log.end_time = datetime.utcnow()
            db.commit()
            logger.info("No companies found in database.")
            return {
                "message": "No companies found in database.",
                "log_id": log_id,
                "date_crawled": target_date.isoformat(),
                "total_companies": 0,
                "companies_processed": 0,
                "total_posts_scraped": 0,
                "total_posts_saved": 0,
                "total_alerts_saved": 0,
                "company_results": []
            }
        
        # Initialize API clients
        apify_client, openai_client = get_api_clients()
        
        # Track statistics
        total_posts_scraped = 0
        total_posts_saved = 0
        total_alerts_saved = 0
        companies_processed = 0
        company_results = []
        
        # Process each company
        for company in companies:
            company_result = _process_company_for_date(
                db, apify_client, openai_client, company,
                date_start, date_end, max_posts_per_company
            )
            
            company_results.append(company_result)
            total_posts_scraped += company_result["posts_scraped"]
            total_posts_saved += company_result["posts_saved"]
            total_alerts_saved += company_result["alerts_saved"]
            
            if company_result["status"] == "completed":
                companies_processed += 1
            
            time.sleep(2)  # Rate limiting
        
        # Update crawler log
        log.end_time = datetime.utcnow()
        log.status = "completed"
        log.posts_scraped = total_posts_scraped
        log.posts_saved = total_posts_saved
        log.alerts_saved = total_alerts_saved
        db.commit()
        
        logger.info(
            f"LinkedIn crawl completed: {companies_processed}/{len(companies)} companies, "
            f"{total_posts_scraped} scraped, {total_posts_saved} saved, "
            f"{total_alerts_saved} alerts created"
        )
        
        return {
            "message": f"LinkedIn crawl completed for {companies_processed}/{len(companies)} companies.",
            "log_id": log_id,
            "date_crawled": target_date.isoformat(),
            "total_companies": len(companies),
            "companies_processed": companies_processed,
            "total_posts_scraped": total_posts_scraped,
            "total_posts_saved": total_posts_saved,
            "total_alerts_saved": total_alerts_saved,
            "company_results": company_results
        }
    
    except Exception as e:
        db.rollback()
        log.end_time = datetime.utcnow()
        log.status = "failed"
        log.error_message = str(e)
        db.commit()
        logger.exception("LinkedIn crawl failed")
        raise
    
    finally:
        db.close()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _process_company_for_date(
    db: Session,
    apify_client,
    openai_client,
    company: Company,
    date_start: datetime,
    date_end: datetime,
    max_posts: int
) -> Dict[str, Any]:
    """Process a single company for posts from target date."""
    company_result = {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "status": "pending",
        "posts_scraped": 0,
        "posts_from_target_date": 0,
        "posts_saved": 0,
        "alerts_saved": 0,
        "error": None
    }
    
    try:
        logger.info(f"Processing company: {company.company_name} (ID: {company.company_id})")
        
        # Run Apify actor
        actor_run_input = {
            "company_name": company.company_name.lower().replace(" ", "-"),
            "page_number": 1,
            "limit": max_posts * 2,
            "sort": "recent",
        }
        
        actor = apify_client.actor("apimaestro/linkedin-company-posts")
        run = actor.call(run_input=actor_run_input)
        scraped_items = list(apify_client.dataset(run["defaultDatasetId"]).iterate_items())
        
        company_result["posts_scraped"] = len(scraped_items)
        
        if not scraped_items:
            company_result["status"] = "completed_no_posts"
            logger.info(f"No posts scraped for {company.company_name}")
            return company_result
        
        # Process posts from target date
        posts_saved = 0
        alerts_saved = 0
        posts_from_target = 0
        
        for item in scraped_items:
            # Parse posted date
            raw_posted_at = item.get("posted_at")
            if raw_posted_at and isinstance(raw_posted_at, dict):
                raw_posted_at = raw_posted_at.get('date')
            
            posted_at = parse_posted_at(raw_posted_at)
            
            # Filter: only posts from target date
            if not (date_start <= posted_at <= date_end):
                continue
            
            posts_from_target += 1
            
            if posts_saved >= max_posts:
                break
            
            # Process post
            result = _process_linkedin_post(db, openai_client, company.company_id, item)
            
            if result["saved"]:
                posts_saved += 1
                alerts_saved += result["alerts_created"]
        
        db.commit()
        
        company_result["posts_from_target_date"] = posts_from_target
        company_result["posts_saved"] = posts_saved
        company_result["alerts_saved"] = alerts_saved
        company_result["status"] = "completed"
        
        logger.info(
            f"Completed {company.company_name}: "
            f"{posts_from_target} from target date, {posts_saved} saved, {alerts_saved} alerts"
        )
    
    except Exception as e:
        db.rollback()
        company_result["status"] = "failed"
        company_result["error"] = str(e)
        logger.error(f"Error processing {company.company_name}: {e}")
    
    return company_result


def _process_linkedin_post(
    db: Session,
    openai_client,
    company_id: int,
    item: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a single LinkedIn post item."""
    result = {
        "saved": False,
        "post_data": None,
        "alerts_created": 0
    }
    
    try:
        # Get UID
        uid = item.get("full_urn") or item.get("postUrn") or item.get("urn")
        if not uid:
            logger.warning(f"Skipping post without UID. Item: {item}")
            return result
        
        # Check for duplicates
        existing_post = db.query(SocialMediaPost).filter(SocialMediaPost.uid == uid).first()
        if existing_post:
            logger.info(f"Skipping existing post (UID: {uid})")
            return result
        
        # Extract post data
        post_text = item.get("text", "")
        stats = item.get("stats", {})
        
        # Parse date
        raw_posted_at = item.get("posted_at")
        if raw_posted_at and isinstance(raw_posted_at, dict):
            raw_posted_at = raw_posted_at.get('date')
        posted_at = parse_posted_at(raw_posted_at)
        
        # Create post data
        post_data = {
            "uid": uid,
            "company_id": company_id,
            "post_url": item.get("post_url"),
            "post_description": post_text,
            "posted_at": posted_at,
            "likes": stats.get("total_reactions", 0),
            "comments_count": stats.get("comments", 0),
            "shares": stats.get("reposts", 0),
            "sentiment_label": "positive",
            "sentiment_score": 1,
        }
        
        # Save to database
        new_post = SocialMediaPost(**post_data)
        db.add(new_post)
        db.flush()
        
        # Process hashtags
        process_hashtags(db, new_post, post_text)
        
        # Create alert if needed
        post_text_with_engagement = (
            f"{post_text}\n"
            f"Engagement: Likes: {stats.get('total_reactions', 0)}, "
            f"Shares: {stats.get('reposts', 0)}, "
            f"Comments: {stats.get('comments', 0)}"
        )
        alerts_created = create_alert_if_needed(
            db, openai_client, company_id, new_post.id, post_text_with_engagement
        )
        
        result["saved"] = True
        result["post_data"] = post_data
        result["alerts_created"] = alerts_created
        
        logger.info(f"Saved LinkedIn post (UID: {uid})")
    
    except Exception as e:
        logger.error(f"Error processing LinkedIn post: {e}")
    
    return result