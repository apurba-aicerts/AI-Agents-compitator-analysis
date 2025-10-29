"""
LLM Service
Handles all AI/LLM operations including sentiment analysis and alert generation.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from openai import OpenAI

from models import Alert
from schemas import AlertResult

logger = logging.getLogger(__name__)


# ============================================================================
# SENTIMENT ANALYSIS
# ============================================================================

def analyze_sentiment(openai_client: OpenAI, post_text: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Analyze the sentiment of a post using OpenAI API.
    
    Args:
        openai_client: OpenAI client instance
        post_text: Text content to analyze
        
    Returns:
        Tuple of (sentiment_result_dict, error_message)
        sentiment_result contains: label, score, explanation
    """
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
        logger.error(f"Sentiment analysis failed: {e}")
        return (
            {"label": "neutral", "score": 0.5, "explanation": "AI analysis failed."},
            str(e),
        )


# ============================================================================
# ALERT ANALYSIS
# ============================================================================

def analyze_alert(openai_client: OpenAI, post_text: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """
    Analyze a post for competitive intelligence alerts using OpenAI API.
    
    Args:
        openai_client: OpenAI client instance
        post_text: Post text including engagement metrics
        max_retries: Number of retry attempts
        
    Returns:
        Dictionary with 'insight' and 'severity' keys, or None if analysis fails
    """
    prompt = f"""
You are a competitive intelligence expert for AI Certs®, a company offering globally recognized certifications in Artificial Intelligence and Blockchain technologies.

Your job is to read a LinkedIn post (including its engagement data such as likes, shares, and comments) and produce a short, factual competitive insight.

Guidelines:
- Focus ONLY on posts mentioning new certifications, partnerships, programs, or announcements related to AI or Blockchain.
- Consider both technical (developer, engineer) and non-technical (executive, educator, ethics) certifications.
- The "insight" should describe why this matters to AI Certs — e.g., overlaps with AI Certs' offerings, new competitors, new specialization, or market movement.
- The "severity" should reflect how important or visible this update is:
    - high → major launch or strong engagement
    - medium → moderate relevance or engagement
    - low → minor update or limited engagement
- Engagement (likes, shares, comments) should influence severity, not tone or writing style.
- Keep "insight" under 25 words and factual (no hashtags, emojis, or fluff).

Post:
{post_text}
"""
    
    for attempt in range(max_retries):
        try:
            response = openai_client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[{"role": "user", "content": prompt}],
                text_format=AlertResult,
                temperature=0.2,
            )
            parsed = getattr(response, "output_parsed", None)
            
            if parsed is not None:
                result = parsed.model_dump()
                logger.info(f"Alert analysis successful: {result}")
                return result
                
        except Exception as e:
            logger.warning(f"Alert analysis attempt {attempt + 1}/{max_retries} failed: {e}")
            continue
    
    logger.error("Alert analysis failed after all retries")
    return None


# ============================================================================
# ALERT CREATION
# ============================================================================

def create_alert_if_needed(
    db: Session, 
    openai_client: OpenAI, 
    company_id: int,
    post_id: int, 
    post_text: str
) -> int:
    """
    Analyze post and create an alert in database if warranted.
    
    Args:
        db: Database session
        openai_client: OpenAI client instance
        company_id: Company ID
        post_id: Post ID
        post_text: Post content with engagement metrics
        
    Returns:
        1 if alert was created, 0 otherwise
    """
    alert_result = analyze_alert(openai_client, post_text)
    
    if alert_result and alert_result.get("insight"):
        new_alert = Alert(
            company_id=company_id,
            post_id=post_id,
            alert_message=alert_result.get("insight"),
            severity=alert_result.get("severity"),
        )
        db.add(new_alert)
        logger.info(f"Alert created for post {post_id}: {alert_result.get('severity')} severity")
        return 1
    
    return 0