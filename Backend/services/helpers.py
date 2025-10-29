"""
Helper Utilities
Shared utilities for date parsing, hashtag processing, URL filtering, and API client initialization.
"""

import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from apify_client import ApifyClient
from openai import OpenAI

from models import Hashtag, SocialMediaPost

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

import logging
logger = logging.getLogger(__name__)

HASHTAG_REGEX = re.compile(r"#(\w+)")


# ============================================================================
# DATE PARSING
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
# HASHTAG PROCESSING
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


# ============================================================================
# URL UTILITIES
# ============================================================================

def generate_uid_from_url(url: str) -> str:
    """Generate a unique identifier from a URL using MD5 hash."""
    return hashlib.md5(url.encode()).hexdigest()


def is_relevant_url(url: str) -> bool:
    """
    Check if the URL is related to AI courses or certifications.
    
    Args:
        url: The URL to check
        
    Returns:
        True if URL contains both AI-related and course/certification-related keywords
    """
    url_lower = url.lower()
    
    # Must contain at least one AI-related keyword
    ai_related = any(k in url_lower for k in [
        "ai", "artificial-intelligence", "machine-learning", 
        "data-science", "deep-learning"
    ])
    
    # Must contain at least one course/certification-related keyword
    course_related = any(k in url_lower for k in [
        "course", "certification", "training", "program"
    ])
    
    return ai_related and course_related


# ============================================================================
# API CLIENT INITIALIZATION
# ============================================================================

def get_api_clients() -> Tuple[ApifyClient, OpenAI]:
    """
    Initialize and return Apify and OpenAI clients from environment variables.
    
    Returns:
        Tuple of (ApifyClient, OpenAI)
        
    Raises:
        RuntimeError: If required environment variables are not set
    """
    apify_token = os.getenv("APIFY_API_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not apify_token or not openai_key:
        raise RuntimeError(
            "Required environment variables (APIFY_API_TOKEN, OPENAI_API_KEY) are not set."
        )
    
    apify_client = ApifyClient(apify_token)
    openai_client = OpenAI(api_key=openai_key)
    
    return apify_client, openai_client


def get_openai_client() -> OpenAI:
    """
    Initialize and return OpenAI client from environment variables.
    
    Returns:
        OpenAI client instance
        
    Raises:
        RuntimeError: If OPENAI_API_KEY is not set
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    
    return OpenAI(api_key=openai_key)