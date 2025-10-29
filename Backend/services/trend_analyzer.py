#services/trend_analyzer.py
import json
import logging
from datetime import datetime
from openai import OpenAI
from pydantic import BaseModel
from typing import List
import time
from core.database import SessionLocal
logger = logging.getLogger(__name__)

# Pydantic models for structured LLM output
class Cluster(BaseModel):
    cluster_name: str
    titles: List[str]
    summary: str

class ClusteredOutput(BaseModel):
    clusters: List[Cluster]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def make_llm_call(prompt, response_model, max_retries=3):
    """Standardized LLM call with retry logic."""
    client = OpenAI()
    
    for attempt in range(max_retries):
        try:
            response = client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[{"role": "user", "content": prompt}],
                text_format=response_model,
                temperature=0.2
            )
            
            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                return parsed
            
            logger.warning(f"Retry {attempt+1}/{max_retries}: no parsed output")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            
        except Exception as e:
            logger.warning(f"Retry {attempt+1}/{max_retries}: API error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    logger.error("Failed to get valid LLM response after all retries")
    return None

def safe_date_parse(post):
    """Safely parse various date formats from post data"""
    try:
        if "created_utc" in post and post["created_utc"]:
            return datetime.fromisoformat(post["created_utc"].replace("Z", "+00:00"))
        elif "timestamp" in post and post["timestamp"]:
            return datetime.fromisoformat(post["timestamp"].replace("Z", "+00:00"))
        elif "post_date" in post and post["post_date"]:
            return datetime.fromisoformat(post["post_date"])
        else:
            return None
    except (ValueError, TypeError):
        return None

def calculate_freshness_score(posts, current_time, window_days):
    """Calculate freshness score based on post timestamps"""
    if not posts:
        return 0
    
    freshness_scores = []
    for post in posts:
        post_date = safe_date_parse(post)
        if post_date:
            days_ago = (current_time - post_date).days
            # Score decreases linearly over time window
            post_freshness = max(((window_days - days_ago) / window_days) * 100, 0)
            freshness_scores.append(post_freshness)
    
    return sum(freshness_scores) / len(freshness_scores) if freshness_scores else 50

def calculate_engagement_score(posts):
    """Calculate raw engagement score from post metrics"""
    if not posts:
        return 0
    
    total_engagement = 0
    for post in posts:
        # Handle different engagement field names
        upvotes = post.get('score', post.get('upvotes', 0))
        comments = post.get('num_comments', post.get('comments', 0))
        
        # Weighted engagement: upvotes worth more than comments
        engagement = (upvotes * 0.7) + (comments * 0.3)
        total_engagement += engagement
    
    return total_engagement

def extract_titles_and_posts(raw_data):
    """Extract titles and create post lookup dictionary"""
    titles = []
    posts_by_title = {}
    
    for post in raw_data:
        if isinstance(post, dict) and "title" in post:
            title = post["title"]
            titles.append(title)
            posts_by_title[title] = post
        else:
            logger.warning("Skipping invalid post structure")
    
    logger.info(f"Extracted {len(titles)} valid titles for clustering")
    return titles, posts_by_title

def perform_clustering_with_summaries(titles, posts_by_title):
    """Use LLM to cluster similar titles and generate summaries for each cluster"""
    
    # Build context with title + snippet for better clustering
    titles_with_context = []
    for title in titles:
        post = posts_by_title.get(title, {})
        selftext = post.get('selftext', '')[:200]  # First 200 chars
        titles_with_context.append({
            "title": title,
            "snippet": selftext
        })
    
    prompt = f"""
You are a research assistant specializing in thematic analysis of social media content.

Task: Analyze these post titles and group them into meaningful topic clusters, then provide a brief summary for each cluster.

Instructions:
1. Identify common themes, technologies, concepts, or discussion topics
2. Group similar titles together into clusters
3. Create descriptive cluster names (2-5 words)
4. For each cluster, write a brief summary (2-4 sentences) describing what's being discussed in that cluster
   - Focus on the main points of discussion
   - Mention key themes, questions, or concerns people are raising
   - Keep it concise and informative
5. Ensure each title is assigned to exactly one cluster
6. Aim for 5-15 clusters depending on content diversity
7. Focus on substantive themes, not superficial similarities

Posts to analyze:
{json.dumps(titles_with_context, indent=2)}
"""
    
    logger.info("Performing topic clustering with summaries via LLM...")
    result = make_llm_call(prompt, ClusteredOutput)
    
    if result is None:
        logger.error("Failed to perform clustering")
        return None
    
    # Convert to dict format
    clusters_data = []
    for cluster in result.clusters:
        cluster_dict = cluster.model_dump() if hasattr(cluster, "model_dump") else cluster.dict()
        clusters_data.append(cluster_dict)
    
    logger.info(f"Successfully clustered into {len(clusters_data)} topic groups with summaries")
    return clusters_data

def calculate_relevance_scores(clusters_data, posts_by_title, weights, window_days):
    """Calculate relevance scores for each cluster"""
    cluster_metrics = []
    current_time = datetime.now()
    
    # First pass: calculate raw metrics
    for cluster in clusters_data:
        cluster_name = cluster["cluster_name"]
        cluster_titles = cluster["titles"]
        cluster_summary = cluster.get("summary", "")
        
        # Get posts for this cluster
        cluster_posts = []
        for title in cluster_titles:
            if title in posts_by_title:
                cluster_posts.append(posts_by_title[title])
        
        if not cluster_posts:
            continue
        
        # Calculate metrics
        frequency = len(cluster_posts)
        raw_engagement = calculate_engagement_score(cluster_posts)
        freshness_score = calculate_freshness_score(cluster_posts, current_time, window_days)
        
        cluster_metrics.append({
            "topic_cluster": cluster_name,
            "summary": cluster_summary,
            "frequency": frequency,
            "raw_engagement": raw_engagement,
            "freshness_score": freshness_score,
            "post_count": len(cluster_posts)
        })
    
    # Find max values for normalization
    max_engagement = max((c["raw_engagement"] for c in cluster_metrics), default=1)
    max_frequency = max((c["frequency"] for c in cluster_metrics), default=1)
    
    logger.info(f"Normalization factors - Max engagement: {max_engagement}, Max frequency: {max_frequency}")
    
    # Second pass: normalize and calculate final relevance scores
    trending_topics = []
    for c in cluster_metrics:
        # Normalize engagement and frequency to 0-100 scale
        engagement_score = (c["raw_engagement"] / max_engagement) * 100 if max_engagement else 0
        normalized_frequency = (c["frequency"] / max_frequency) * 100 if max_frequency else 0
        
        # Calculate weighted relevance score
        relevance_score = (
            engagement_score * weights["engagement"] +
            c["freshness_score"] * weights["freshness"] +
            normalized_frequency * weights["frequency"]
        )
        
        trending_topics.append({
            "topic_cluster": c["topic_cluster"],
            "summary": c["summary"],
            "relevance_score": round(relevance_score, 2),
            "metrics": {
                "freshness_score": round(c["freshness_score"], 2),
                "engagement_score": round(engagement_score, 2),
                "frequency": c["frequency"],
                "total_engagement": c["raw_engagement"]
            }
        })
    
    # Sort by relevance score (highest first) and add rankings
    trending_topics.sort(key=lambda x: x["relevance_score"], reverse=True)
    for i, topic in enumerate(trending_topics, 1):
        topic["rank"] = i
    
    return trending_topics, cluster_metrics

def generate_report(trending_topics, cluster_metrics, total_titles, weights, window_days, clusters_with_titles):
    """Generate comprehensive trending topics report"""
    current_time = datetime.now()
    total_posts = sum(c["post_count"] for c in cluster_metrics)
    total_engagement = sum(c["raw_engagement"] for c in cluster_metrics)
    
    report = {
        "analysis_timestamp": current_time.isoformat(),
        "summary": {
            "total_clusters": len(cluster_metrics),
            "total_posts_analyzed": total_posts,
            "original_titles": total_titles,
            "total_engagement": total_engagement,
            "time_window_days": window_days
        },
        "scoring_weights": weights,
        "trending_topics": trending_topics,
        "clusters_with_titles": clusters_with_titles  # Add cluster-to-titles mapping
    }
    
    return report

def analyze_trends(raw_data, config):
    """
    Main function to analyze trends from raw Reddit data.
    
    Args:
        raw_data: List of post dictionaries
        config: Dict with weights and window_days
    
    Returns:
        Dict containing the complete trending report
    """
    logger.info("Starting trend analysis process...")
    
    if not raw_data:
        logger.error("No data provided for analysis")
        raise ValueError("No data provided for analysis")
    
    weights = {
        "engagement": config.get("weight_engagement", 0.4),
        "freshness": config.get("weight_freshness", 0.35),
        "frequency": config.get("weight_frequency", 0.25)
    }
    window_days = config.get("window_days", 14)
    
    try:
        # Extract titles and create lookup
        titles, posts_by_title = extract_titles_and_posts(raw_data)
        
        if not titles:
            logger.error("No valid titles found to process")
            raise ValueError("No valid titles found")
        
        # Perform clustering with summaries
        clusters_data = perform_clustering_with_summaries(titles, posts_by_title)
        if not clusters_data:
            raise Exception("Clustering failed")
        
        # Calculate relevance scores and rankings
        trending_topics, cluster_metrics = calculate_relevance_scores(
            clusters_data, posts_by_title, weights, window_days
        )
        
        # Generate comprehensive report
        report = generate_report(trending_topics, cluster_metrics, len(titles), weights, window_days)
        
        # Print summary
        print_summary(report)
        
        logger.info("Trend analysis completed successfully")
        return report
        
    except Exception as e:
        logger.error(f"Trend analysis failed: {e}")
        raise

def print_summary(report):
    """Print analysis summary"""
    trending_topics = report["trending_topics"]
    summary = report["summary"]
    
    logger.info("="*50)
    logger.info("TRENDING TOPICS ANALYSIS SUMMARY")
    logger.info("="*50)
    
    logger.info(f"Total clusters identified: {summary['total_clusters']}")
    logger.info(f"Total posts analyzed: {summary['total_posts_analyzed']}")
    logger.info(f"Total engagement: {summary['total_engagement']:,}")
    logger.info(f"Analysis time window: {summary['time_window_days']} days")
    
    logger.info("\nTop 5 trending topics:")
    for topic in trending_topics[:5]:
        logger.info(f"  {topic['rank']}. {topic['topic_cluster']} (Score: {topic['relevance_score']})")
        logger.info(f"     Summary: {topic['summary'][:100]}...")