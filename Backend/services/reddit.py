#services/reddit.py
import os
import logging
from dotenv import load_dotenv
from services.reddit_trend_miner import fetch_reddit_data
from services.trend_analyzer import analyze_trends
from core.database import SessionLocal
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def load_config(keywords_override=None):
    """Load configuration from .env file"""
    load_dotenv()
    
    # Validate required environment variables
    required_vars = [
        "REDDIT_CLIENT_ID",
        "REDDIT_CLIENT_SECRET", 
        "REDDIT_USER_AGENT",
        "OPENAI_API_KEY"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Reddit configuration
    reddit_config = {
        "client_id": os.getenv("REDDIT_CLIENT_ID"),
        "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
        "user_agent": os.getenv("REDDIT_USER_AGENT"),
        "posts_limit": int(os.getenv("POSTS_LIMIT", "100")),
        "top_subs": int(os.getenv("TOP_SUBS", "3"))
    }
    
    # OpenAI API key setup
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    
    # Keywords configuration - use override if provided, else from env
    if keywords_override:
        keywords = keywords_override
    else:
        keywords_str = os.getenv("KEYWORDS", "")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    
    if not keywords:
        raise ValueError("Keywords not provided and KEYWORDS environment variable is empty")
    
    # Analysis configuration
    analysis_config = {
        "window_days": int(os.getenv("WINDOW_DAYS", "14")),
        "weight_engagement": float(os.getenv("WEIGHT_ENGAGEMENT", "0.4")),
        "weight_freshness": float(os.getenv("WEIGHT_FRESHNESS", "0.35")),
        "weight_frequency": float(os.getenv("WEIGHT_FREQUENCY", "0.25"))
    }
    
    return reddit_config, keywords, analysis_config

def get_trending_report(start_date, end_date, keywords_override=None):
    """
    Main function to get trending report from Reddit for a specific time period.
    
    Args:
        start_date: Start date in format "YYYY-MM-DD"
        end_date: End date in format "YYYY-MM-DD"
        keywords_override: Optional list of keywords to override .env
    
    Returns:
        Dict containing raw posts and the complete trending report with clusters
    
    Example:
        report = get_trending_report("2025-10-24", "2025-10-25", ["certification", "course"])
    """
    try:
        # Load configuration
        logger.info("Loading configuration from .env file...")
        reddit_config, keywords, analysis_config = load_config(keywords_override)
        
        logger.info(f"Configuration loaded successfully")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Date range: {start_date} to {end_date}")
        
        # Step 1: Fetch Reddit data
        logger.info("="*50)
        logger.info("STEP 1: Fetching Reddit data...")
        logger.info("="*50)
        raw_data = fetch_reddit_data(reddit_config, keywords, start_date, end_date)
        
        if not raw_data:
            logger.warning("No data fetched from Reddit")
            return {
                "status": "no_data",
                "message": "No posts found for the specified date range and keywords",
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "keywords": keywords,
                "raw_posts": [],
                "trending_report": None
            }
        
        # Step 2: Analyze trends and generate report
        logger.info("="*50)
        logger.info("STEP 2: Analyzing trends and generating summaries...")
        logger.info("="*50)
        report = analyze_trends(raw_data, analysis_config)
        
        # Add metadata
        report["date_range"] = {
            "start": start_date,
            "end": end_date
        }
        report["keywords"] = keywords
        report["status"] = "success"
        
        logger.info("="*50)
        logger.info("REPORT GENERATION COMPLETE")
        logger.info("="*50)
        
        return {
            "status": "success",
            "raw_posts": raw_data,
            "trending_report": report
        }
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error generating trending report: {e}")
        raise