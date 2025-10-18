"""
Crawler Router
Handles LinkedIn and web scraping endpoints with AI-powered sentiment analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
import logging
import os
import re
import json
import time
import hashlib
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from apify_client import ApifyClient
from openai import OpenAI
from pydantic import BaseModel, Field

from core.database import SessionLocal
from models import SocialMediaPost, Company, Alert, CrawlerLog, Hashtag
from schemas import CrawlResponse
from services.web_crawler import (
    fetch_xml, is_sitemap_index, extract_sitemap_urls, 
    extract_urls_from_sitemap, crawl_sitemaps_recursive, 
    get_page_info, SITEMAP_URLS
)

load_dotenv()

# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/crawler", tags=["crawler"])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HASHTAG_REGEX = re.compile(r"#(\w+)")


# ============================================================================
# PYDANTIC MODELS FOR AI RESPONSES
# ============================================================================

class SentimentResponseModel(BaseModel):
    label: str = Field(..., description="one of: positive/neutral/negative")
    score: float = Field(..., ge=0.0, le=1.0, description="normalized confidence score 0..1")
    explanation: Optional[str] = Field(None, description="brief explanation for the label")


class AlertResponseModel(BaseModel):
    title: str = Field(..., description="Title of the alert in 10 words or less")
    message: str = Field(..., description="Detailed message of the alert")
    severity: str = Field(..., description="Severity level of the alert (low|medium|high)")


# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================

def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# DATE PARSING UTILITIES
# ============================================================================

def parse_posted_at(raw_time: Optional[str]) -> datetime:
    """Parse various date string formats and return a timezone-aware datetime."""
    if not raw_time:
        return datetime.now(timezone.utc)
    
    s = str(raw_time).strip()
    
    # Try ISO format parsing
    try:
        s_cleaned = s.replace("Z", "+00:00")
        if "." in s_cleaned:
            parts = s_cleaned.split(".")
            microseconds = parts[1].split("+")[0]
            if len(microseconds) > 6:
                s_cleaned = f"{parts[0]}.{microseconds[:6]}+{parts[1].split('+')[1]}"
        dt = datetime.fromisoformat(s_cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, IndexError):
        pass
    
    # Try relative time format (e.g., "2 days ago")
    rel_match = re.search(r"(\d+)\s*(d|day|days|h|hour|hours|m|minute|minutes)\b", s, flags=re.I)
    if rel_match:
        qty = int(rel_match.group(1))
        unit = rel_match.group(2).lower()
        now = datetime.now(timezone.utc)
        
        if unit.startswith("d"):
            return now - timedelta(days=qty)
        if unit.startswith("h"):
            return now - timedelta(hours=qty)
        return now - timedelta(minutes=qty)
    
    logger.warning(f"Could not parse date string: '{s}'. Defaulting to now().")
    return datetime.now(timezone.utc)


# ============================================================================
# AI ANALYSIS FUNCTIONS
# ============================================================================

def analyze_post_sentiment(openai_client: OpenAI, post_text: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """Analyze the sentiment of a post using OpenAI API."""
    try:
        prompt = (
            "Analyze the sentiment of the following LinkedIn post. "
            "Respond ONLY with a valid JSON object containing: label (positive/neutral/negative), "
            "score (0..1), and a brief explanation.\n\n"
            f"Post: \"{post_text}\""
        )
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        return result, None
    
    except Exception as e:
        return (
            {"label": "neutral", "score": 0.5, "explanation": "AI analysis failed."},
            str(e),
        )


def analyze_post_alert(openai_client: OpenAI, post_text: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """Analyze a post for potential competitive alerts using OpenAI API."""
    try:
        prompt = (
            "You are an expert in competitive intelligence. "
            "Given the following LinkedIn post, determine if it contains important news or updates "
            "that competitors should be aware of. "
            "Respond with a JSON object containing: title (10 words or less), "
            "message (detailed explanation, less than 15 words), and severity (low|medium|high).\n\n"
            f"Post: \"{post_text}\""
        )
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        return result, None
    
    except Exception as json_err:
        return (
            {"title": "No Alert", "message": "AI response was not valid JSON.", "severity": "low"},
            str(json_err),
        )
    
    except Exception as e:
        return (
            {"title": "No Alert", "message": "AI analysis failed.", "severity": "low"},
            str(e),
        )


# ============================================================================
# POST PROCESSING UTILITIES
# ============================================================================

def process_hashtags(db: Session, post: SocialMediaPost, post_text: str):
    """Extract and link hashtags to a post."""
    if not post_text:
        return
    
    hashtags = HASHTAG_REGEX.findall(post_text)
    for tag in hashtags:
        hashtag_obj = db.query(Hashtag).filter(Hashtag.tag == tag.lower()).first()
        
        if not hashtag_obj:
            hashtag_obj = Hashtag(tag=tag.lower())
            db.add(hashtag_obj)
            db.commit()
            db.refresh(hashtag_obj)
        
        if hashtag_obj not in post.hashtags:
            post.hashtags.append(hashtag_obj)


def create_alert_if_needed(db: Session, openai_client: OpenAI, company_id: int, 
                          post_id: int, post_text: str) -> int:
    """Create an alert if the post content warrants one."""
    alert_result, _ = analyze_post_alert(openai_client, post_text)
    
    if alert_result and alert_result.get("message"):
        new_alert = Alert(
            company_id=company_id,
            post_id=post_id,
            alert_message=alert_result.get("message"),
            severity=alert_result.get("severity"),
        )
        db.add(new_alert)
        return 1
    
    return 0


# ============================================================================
# LINKEDIN CRAWLING ENDPOINTS
# ============================================================================

@router.post("/crawl/linkedin/all", response_model=Dict[str, Any])
def crawl_linkedin_yesterday_all_companies(
    day: str = Query("yesterday", enum=["yesterday", "today"]),
    db: Session = Depends(get_db),
    max_posts_per_company: int = 5
):
    """
    Crawl yesterday's LinkedIn posts for all companies in the database.
    Processes companies sequentially and returns detailed results per company.
    """
    log = CrawlerLog()
    db.add(log)
    db.commit()
    db.refresh(log)
    log_id = log.log_id
    
    # Calculate yesterday's date range
    yesterday = datetime.now(timezone.utc).date() if day == "today" else datetime.now(timezone.utc).date() - timedelta(days=1)
    yesterday_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
    yesterday_end = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=timezone.utc)
    
    logger.info(f"Crawling LinkedIn posts from yesterday: {yesterday} (UTC)")
    
    try:
        companies = db.query(Company).all()
        
        if not companies:
            log.status = "completed_no_companies"
            log.end_time = datetime.utcnow()
            db.commit()
            return {
                "message": "No companies found in database.",
                "log_id": log_id,
                "total_companies": 0,
                "companies_processed": 0,
                "total_posts_scraped": 0,
                "total_posts_saved": 0,
                "total_alerts_saved": 0,
                "company_results": []
            }
        
        # Initialize API clients
        apify_token = os.getenv("APIFY_API_TOKEN")
        openai_key = os.getenv("OPENAI_API_KEY")
        if not apify_token or not openai_key:
            raise RuntimeError("Required environment variables (APIFY_API_TOKEN, OPENAI_API_KEY) are not set.")
        
        apify_client = ApifyClient(apify_token)
        openai_client = OpenAI(api_key=openai_key)
        
        # Track overall statistics
        total_posts_scraped = 0
        total_posts_saved = 0
        total_alerts_saved = 0
        companies_processed = 0
        company_results = []
        
        # Process each company
        for company in companies:
            company_result = _process_company_yesterday(
                db, apify_client, openai_client, company,
                yesterday_start, yesterday_end, max_posts_per_company
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
            f"Crawl completed: {companies_processed}/{len(companies)} companies processed, "
            f"{total_posts_scraped} total posts scraped, "
            f"{total_posts_saved} posts saved, "
            f"{total_alerts_saved} alerts created"
        )
        
        return {
            "message": f"LinkedIn yesterday crawl completed for {companies_processed}/{len(companies)} companies.",
            "log_id": log_id,
            "date_crawled": yesterday.isoformat(),
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
        logger.exception("LinkedIn yesterday crawl failed")
        raise HTTPException(status_code=500, detail=f"LinkedIn yesterday crawl failed: {str(e)}")


def _process_company_yesterday(
    db: Session,
    apify_client: ApifyClient,
    openai_client: OpenAI,
    company: Company,
    yesterday_start: datetime,
    yesterday_end: datetime,
    max_posts: int
) -> Dict[str, Any]:
    """Process a single company for yesterday's posts."""
    company_result = {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "status": "pending",
        "posts_scraped": 0,
        "posts_from_yesterday": 0,
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
        
        # Process posts from yesterday
        posts_saved = 0
        alerts_saved = 0
        posts_from_yesterday = 0
        
        for item in scraped_items:
            # Parse posted date
            raw_posted_at = item.get("posted_at")
            if raw_posted_at and isinstance(raw_posted_at, dict):
                raw_posted_at = raw_posted_at.get('date')
            
            posted_at = parse_posted_at(raw_posted_at)
            
            # Filter: only posts from yesterday
            if not (yesterday_start <= posted_at <= yesterday_end):
                continue
            
            posts_from_yesterday += 1
            
            if posts_saved >= max_posts:
                break
            
            # Get UID
            uid = item.get("full_urn") or item.get("postUrn") or item.get("urn")
            if not uid:
                logger.warning(f"Skipping post without UID for {company.company_name}")
                continue
            
            # Check for duplicates
            existing_post = db.query(SocialMediaPost).filter(SocialMediaPost.uid == uid).first()
            if existing_post:
                logger.info(f"Skipping existing post (UID: {uid}) for {company.company_name}")
                continue
            
            # Extract post data
            post_text = item.get("text", "")
            sentiment_result, _ = analyze_post_sentiment(openai_client, post_text)
            stats = item.get("stats", {})
            
            # Create post
            post_data = {
                "uid": uid,
                "company_id": company.company_id,
                "post_url": item.get("post_url"),
                "post_description": post_text,
                "posted_at": posted_at,
                "likes": stats.get("total_reactions", 0),
                "comments_count": stats.get("comments", 0),
                "shares": stats.get("reposts", 0),
                "sentiment_label": sentiment_result.get("label"),
                "sentiment_score": sentiment_result.get("score"),
            }
            
            new_post = SocialMediaPost(**post_data)
            db.add(new_post)
            db.flush()
            posts_saved += 1
            
            # Process hashtags
            process_hashtags(db, new_post, post_text)
            
            # Create alert if needed
            alerts_saved += create_alert_if_needed(
                db, openai_client, company.company_id, new_post.id, post_text
            )
        
        db.commit()
        
        company_result["posts_from_yesterday"] = posts_from_yesterday
        company_result["posts_saved"] = posts_saved
        company_result["alerts_saved"] = alerts_saved
        company_result["status"] = "completed"
        
        logger.info(
            f"Completed {company.company_name}: "
            f"{posts_from_yesterday} posts from yesterday, "
            f"{posts_saved} saved, {alerts_saved} alerts"
        )
    
    except Exception as e:
        db.rollback()
        company_result["status"] = "failed"
        company_result["error"] = str(e)
        logger.error(f"Error processing {company.company_name}: {e}")
    
    return company_result


@router.post("/crawl/linkedin/{company_id}", response_model=CrawlResponse)
def crawl_linkedin_by_company(
    company_id: int, 
    db: Session = Depends(get_db), 
    max_posts: int = 25
):
    """
    Trigger the LinkedIn crawler for a specific company using Apify.
    """
    log = CrawlerLog(company_id=company_id)
    db.add(log)
    db.commit()
    db.refresh(log)
    log_id = log.log_id
    
    try:
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail=f"Company id={company_id} not found")
        
        # Initialize API clients
        apify_token = os.getenv("APIFY_API_TOKEN")
        openai_key = os.getenv("OPENAI_API_KEY")
        if not apify_token or not openai_key:
            raise RuntimeError("Required environment variables (APIFY_API_TOKEN, OPENAI_API_KEY) are not set.")
        
        apify_client = ApifyClient(apify_token)
        openai_client = OpenAI(api_key=openai_key)
        
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
            db.commit()
            return CrawlResponse(
                message="No posts scraped from Apify.",
                log_id=log_id,
                posts_scraped=0,
                posts_saved=0,
                alerts_saved=0,
                sample=[],
            )
        
        # Process scraped items
        posts_saved = 0
        alerts_saved = 0
        sample = []
        
        for item in scraped_items:
            uid = item.get("full_urn") or item.get("postUrn") or item.get("urn")
            if not uid:
                logger.warning(f"Skipping post without UID. Item: {item}")
                continue
            
            # Check for duplicates
            existing_post = db.query(SocialMediaPost).filter(SocialMediaPost.uid == uid).first()
            if existing_post:
                logger.info(f"Skipping already existing post with UID: {uid}")
                continue
            
            # Extract and analyze post
            post_text = item.get("text", "")
            sentiment_result, _ = analyze_post_sentiment(openai_client, post_text)
            stats = item.get("stats", {})
            
            # Create post data
            post_data = {
                "uid": uid,
                "company_id": company_id,
                "post_url": item.get("post_url"),
                "post_description": post_text,
                "posted_at": parse_posted_at(item.get("posted_at", {}).get('date')),
                "likes": stats.get("total_reactions", 0),
                "comments_count": stats.get("comments", 0),
                "shares": stats.get("reposts", 0),
                "sentiment_label": sentiment_result.get("label"),
                "sentiment_score": sentiment_result.get("score"),
            }
            
            sample.append(post_data)
            new_post = SocialMediaPost(**post_data)
            db.add(new_post)
            posts_saved += 1
            db.flush()
            
            # Process hashtags
            process_hashtags(db, new_post, post_text)
            
            # Create alert if needed
            alerts_saved += create_alert_if_needed(
                db, openai_client, company_id, new_post.id, post_text
            )
        
        db.commit()
        
        # Update log
        log.end_time = datetime.utcnow()
        log.status = "completed"
        log.posts_scraped = len(scraped_items)
        log.posts_saved = posts_saved
        log.alerts_saved = alerts_saved
        db.commit()
        
        return CrawlResponse(
            message="Crawl completed successfully using Apify.",
            log_id=log_id,
            posts_scraped=len(scraped_items),
            posts_saved=posts_saved,
            alerts_saved=alerts_saved,
            sample=sample,
        )
    
    except Exception as e:
        db.rollback()
        log.end_time = datetime.utcnow()
        log.status = "failed"
        log.error_message = str(e)
        db.commit()
        logger.exception("Crawler run failed")
        raise HTTPException(status_code=500, detail=f"Crawler failed: {str(e)}")


# ============================================================================
# WEB SCRAPING ENDPOINTS
# ============================================================================

@router.post("/scroll_companies", response_model=CrawlResponse)
def scroll_companies(
    db: Session = Depends(get_db), 
    max_posts_per_company: int = 5,
    day: str = Query("yesterday", enum=["yesterday", "today"])
):
    """
    Scroll through company websites (via sitemaps) and collect posts from yesterday.
    Performs sentiment analysis and stores results.
    """
    log = CrawlerLog()
    db.add(log)
    db.commit()
    db.refresh(log)
    log_id = log.log_id
    
    try:
        # Initialize OpenAI client
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
        openai_client = OpenAI(api_key=openai_key)
        
        # Get yesterday's date
        yesterday = datetime.now(timezone.utc).date() if day == "today" else datetime.now(timezone.utc).date() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        logger.info(f"Scrolling for posts from: {yesterday_str}")
        
        total_posts_scraped = 0
        total_posts_saved = 0
        alerts_saved = 0
        all_samples = []
        
        # Process each company with a sitemap
        for company_name, sitemap_url in SITEMAP_URLS.items():
            logger.info(f"Processing company: {company_name}")
            
            # Fetch company from database
            company = db.query(Company).filter(Company.company_name == company_name).first()
            
            if not company:
                logger.warning(f"Company '{company_name}' not found in database. Skipping.")
                continue
            
            try:
                # Crawl sitemap for yesterday's URLs
                all_urls = _crawl_sitemaps_for_yesterday(sitemap_url, yesterday_str)
                
                if not all_urls:
                    logger.info(f"No posts found for {company_name} from yesterday.")
                    continue
                
                logger.info(f"Found {len(all_urls)} posts for {company_name}")
                total_posts_scraped += len(all_urls)
                
                # Limit posts per company
                urls_to_process = all_urls[:max_posts_per_company]
                
                # Process each post
                for idx, post_item in enumerate(urls_to_process, 1):
                    result = _process_web_post(
                        db, openai_client, company.company_id, post_item, idx, len(urls_to_process)
                    )
                    
                    if result["saved"]:
                        total_posts_saved += 1
                        all_samples.append(result["post_data"])
                        alerts_saved += result["alerts_created"]
                
                time.sleep(1)
            
            except Exception as e:
                logger.error(f"Error processing company {company_name}: {e}")
                continue
        
        # Commit all changes
        db.commit()
        
        # Update crawler log
        log.end_time = datetime.utcnow()
        log.status = "completed"
        log.posts_scraped = total_posts_scraped
        log.posts_saved = total_posts_saved
        db.commit()
        
        logger.info(
            f"Crawl completed: {total_posts_scraped} posts scraped, "
            f"{total_posts_saved} posts saved"
        )
        
        return CrawlResponse(
            message=f"Web scroll completed successfully for {len(SITEMAP_URLS)} companies.",
            log_id=log_id,
            posts_scraped=total_posts_scraped,
            posts_saved=total_posts_saved,
            alerts_saved=alerts_saved,
            sample=all_samples[:10],
        )
    
    except Exception as e:
        db.rollback()
        log.end_time = datetime.utcnow()
        log.status = "failed"
        log.error_message = str(e)
        db.commit()
        logger.exception("Web scroll run failed")
        raise HTTPException(status_code=500, detail=f"Web scroll failed: {str(e)}")


def _crawl_sitemaps_for_yesterday(sitemap_url: str, yesterday_str: str) -> List[Dict]:
    """Crawl sitemaps and filter for posts from yesterday only."""
    logger.info(f"Fetching sitemap: {sitemap_url}")
    
    root = fetch_xml(sitemap_url)
    if root is None:
        return []
    
    all_urls = []
    
    if is_sitemap_index(root):
        logger.info("Detected sitemap index")
        sitemap_urls = extract_sitemap_urls(root)
        logger.info(f"Found {len(sitemap_urls)} child sitemaps")
        
        for child_url in sitemap_urls:
            child_urls = crawl_sitemaps_recursive(child_url, depth=0)
            all_urls.extend(child_urls)
            time.sleep(0.3)
    else:
        logger.info("Processing regular sitemap")
        all_urls = extract_urls_from_sitemap(root)
    
    # Filter for yesterday's date
    yesterday_posts = []
    for url_item in all_urls:
        if isinstance(url_item, dict):
            lastmod = url_item.get("lastmod")
        else:
            lastmod = None
        
        if lastmod:
            lastmod_date = str(lastmod).split("T")[0]
            if lastmod_date == yesterday_str:
                yesterday_posts.append(url_item)
    
    logger.info(f"Filtered {len(yesterday_posts)} posts from yesterday ({yesterday_str})")
    return yesterday_posts


def _process_web_post(
    db: Session,
    openai_client: OpenAI,
    company_id: int,
    post_item: Dict,
    idx: int,
    total: int
) -> Dict[str, Any]:
    """Process a single web post."""
    result = {
        "saved": False,
        "post_data": None,
        "alerts_created": 0
    }
    
    try:
        post_url = post_item.get("url")
        lastmod = post_item.get("lastmod")
        
        if not post_url or not lastmod:
            logger.warning(f"Skipping post: missing URL or lastmod")
            return result
        
        # Generate UID
        uid = hashlib.md5(post_url.encode()).hexdigest()
        
        # Check for duplicates
        existing_post = db.query(SocialMediaPost).filter(SocialMediaPost.uid == uid).first()
        if existing_post:
            logger.info(f"Post already exists (UID: {uid}). Skipping.")
            return result
        
        # Fetch page info
        page_data = get_page_info(post_url)
        title = page_data.get("title", "No title")
        description = page_data.get("description", "")
        
        # Concatenate for sentiment analysis
        web_text = f"{title} {description}".strip()
        
        if not web_text:
            logger.warning(f"No text content for sentiment analysis. Skipping {post_url}")
            return result
        
        # Perform analyses
        sentiment_result, sentiment_error = analyze_post_sentiment(openai_client, web_text)
        if sentiment_error:
            logger.warning(f"Sentiment analysis error: {sentiment_error}")
        
        # Parse posted_at date
        posted_at = parse_posted_at(lastmod)
        
        # Create post record
        post_data = {
            "uid": uid,
            "company_id": company_id,
            "post_url": post_url,
            "post_description": title,
            "posted_at": posted_at,
            "likes": 0,
            "comments_count": 0,
            "shares": 0,
            "sentiment_label": sentiment_result.get("label"),
            "sentiment_score": sentiment_result.get("score"),
        }
        
        # Save to database
        new_post = SocialMediaPost(**post_data)
        db.add(new_post)
        db.flush()
        
        logger.info(
            f"[{idx}/{total}] Saved: {title[:60]}... "
            f"(Sentiment: {sentiment_result.get('label')})"
        )
        
        # Create alert if needed
        alerts_created = create_alert_if_needed(
            db, openai_client, company_id, new_post.id, web_text
        )
        
        result["saved"] = True
        result["post_data"] = post_data
        result["alerts_created"] = alerts_created
    
    except Exception as e:
        logger.error(f"Error processing post: {e}")
    
    return result