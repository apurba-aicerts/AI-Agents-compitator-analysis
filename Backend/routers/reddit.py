# router/reddit.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging
import json

import schemas
import models
from core.database import SessionLocal
from services.reddit import get_trending_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reddit", tags=["reddit"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/analyze", response_model=schemas.RedditAnalyzeResponse, status_code=status.HTTP_200_OK)
def analyze_reddit_trends(
    payload: schemas.RedditAnalyzeRequest,
    db: Session = Depends(get_db)
):
    """
    Fetch Reddit data, analyze trends, create clusters, and save to database.
    
    - **start_date**: Start date in YYYY-MM-DD format
    - **end_date**: End date in YYYY-MM-DD format
    - **keywords**: Optional list of keywords (overrides .env if provided)
    
    Returns complete trending report with clusters and summaries.
    """
    try:
        # Validate date format
        start_dt = datetime.strptime(payload.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(payload.end_date, "%Y-%m-%d")
        
        # Check if analysis already exists for this date range
        existing_clusters = db.query(models.RedditCluster).filter(
            models.RedditCluster.start_date == start_dt,
            models.RedditCluster.end_date == end_dt
        ).first()
        
        if existing_clusters:
            logger.info(f"Analysis already exists for date range {payload.start_date} to {payload.end_date}. Skipping.")
            return {
                "status": "skipped",
                "message": "Analysis already exists for this date range. Use GET /reddit/report to retrieve it.",
                "posts_fetched": 0,
                "posts_saved": 0,
                "clusters_created": 0,
                "date_range": {
                    "start": payload.start_date,
                    "end": payload.end_date
                },
                "keywords": payload.keywords or [],
                "trending_report": {}
            }
        
        logger.info(f"Starting Reddit analysis for {payload.start_date} to {payload.end_date}")
        
        # Call the main analysis function
        result = get_trending_report(
            start_date=payload.start_date,
            end_date=payload.end_date,
            keywords_override=payload.keywords
        )
        
        if result["status"] == "no_data":
            return {
                "status": "no_data",
                "message": result["message"],
                "posts_fetched": 0,
                "posts_saved": 0,
                "clusters_created": 0,
                "date_range": result["date_range"],
                "keywords": result["keywords"],
                "trending_report": {}
            }
        
        # Extract data
        raw_posts = result["raw_posts"]
        trending_report = result["trending_report"]
        
        # Save Reddit posts to database
        posts_saved = 0
        post_id_map = {}  # Map reddit_id to database id
        
        for post_data in raw_posts:
            # Check if post already exists
            existing_post = db.query(models.RedditPost).filter(
                models.RedditPost.reddit_id == post_data["id"]
            ).first()
            
            if existing_post:
                post_id_map[post_data["id"]] = existing_post.id
                continue
            
            # Parse created_utc
            created_utc = datetime.strptime(post_data["created_utc"], "%Y-%m-%d %H:%M:%S")
            
            # Create new post
            reddit_post = models.RedditPost(
                reddit_id=post_data["id"],
                title=post_data["title"],
                selftext=post_data.get("selftext"),
                author=post_data.get("author"),
                author_fullname=post_data.get("author_fullname"),
                subreddit=post_data["subreddit"],
                subreddit_name_prefixed=post_data.get("subreddit_name_prefixed"),
                url=post_data.get("url"),
                permalink=post_data.get("permalink"),
                score=post_data.get("score", 0),
                ups=post_data.get("ups", 0),
                downs=post_data.get("downs", 0),
                comments=post_data.get("comments", 0),
                upvote_ratio=post_data.get("upvote_ratio"),
                created_utc=created_utc,
                is_self=post_data.get("is_self", True),
                over_18=post_data.get("over_18", False),
                stickied=post_data.get("stickied", False),
                is_video=post_data.get("is_video", False),
                link_flair_text=post_data.get("link_flair_text"),
                thumbnail=post_data.get("thumbnail"),
                additional_data={
                    "link_flair_richtext": post_data.get("link_flair_richtext"),
                    "all_awardings": post_data.get("all_awardings"),
                    "preview_images": post_data.get("preview_images")
                }
            )
            
            db.add(reddit_post)
            db.flush()  # Get the ID without committing
            
            post_id_map[post_data["id"]] = reddit_post.id
            posts_saved += 1
        
        db.commit()
        logger.info(f"Saved {posts_saved} new Reddit posts to database")
        
        # Save clusters to database with post associations
        clusters_created = 0
        trending_topics = trending_report.get("trending_topics", [])
        clusters_with_titles = trending_report.get("clusters_with_titles", [])
        
        # Build a title-to-reddit_id mapping from raw_posts
        title_to_reddit_id = {post["title"]: post["id"] for post in raw_posts}
        
        for topic in trending_topics:
            cluster_name = topic["topic_cluster"]
            summary = topic["summary"]
            relevance_score = topic["relevance_score"]
            rank = topic["rank"]
            metrics = topic["metrics"]
            
            # Create cluster
            reddit_cluster = models.RedditCluster(
                cluster_name=cluster_name,
                summary=summary,
                relevance_score=relevance_score,
                rank=rank,
                metrics=metrics,
                start_date=start_dt,
                end_date=end_dt,
                keywords=trending_report["keywords"]
            )
            
            db.add(reddit_cluster)
            db.flush()  # Get the ID
            
            # Find which posts belong to this cluster by matching cluster_name
            cluster_titles = []
            for cluster_data in clusters_with_titles:
                if cluster_data["cluster_name"] == cluster_name:
                    cluster_titles = cluster_data["titles"]
                    break
            
            # Associate posts with this cluster
            for title in cluster_titles:
                reddit_id = title_to_reddit_id.get(title)
                if reddit_id and reddit_id in post_id_map:
                    post_db_id = post_id_map[reddit_id]
                    # Get the post object and add to cluster
                    post_obj = db.query(models.RedditPost).filter(
                        models.RedditPost.id == post_db_id
                    ).first()
                    if post_obj:
                        reddit_cluster.posts.append(post_obj)
            
            clusters_created += 1
        
        db.commit()
        logger.info(f"Created {clusters_created} clusters with post associations in database")
        
        return {
            "status": "success",
            "message": "Reddit analysis completed and data saved successfully",
            "posts_fetched": len(raw_posts),
            "posts_saved": posts_saved,
            "clusters_created": clusters_created,
            "date_range": trending_report["date_range"],
            "keywords": trending_report["keywords"],
            "trending_report": trending_report
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during Reddit analysis: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/report", response_model=schemas.RedditReportResponse)
def get_reddit_report(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """
    Retrieve stored Reddit trending report for a date range.
    
    - **start_date**: Start date in YYYY-MM-DD format
    - **end_date**: End date in YYYY-MM-DD format
    
    Returns stored clusters with their associated posts.
    """
    try:
        # Validate and parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Query clusters for this date range
        clusters = db.query(models.RedditCluster).filter(
            models.RedditCluster.start_date == start_dt,
            models.RedditCluster.end_date == end_dt
        ).order_by(models.RedditCluster.rank).all()
        
        if not clusters:
            raise HTTPException(
                status_code=404,
                detail=f"No Reddit analysis found for date range {start_date} to {end_date}. Run POST /reddit/analyze first."
            )
        
        # Build response
        total_posts = 0
        cluster_list = []
        
        for cluster in clusters:
            # Get posts associated with this cluster
            posts = cluster.posts
            total_posts += len(posts)
            
            cluster_dict = {
                "id": cluster.id,
                "cluster_name": cluster.cluster_name,
                "summary": cluster.summary,
                "relevance_score": cluster.relevance_score,
                "rank": cluster.rank,
                "metrics": cluster.metrics,
                "start_date": cluster.start_date,
                "end_date": cluster.end_date,
                "keywords": cluster.keywords,
                "analysis_timestamp": cluster.analysis_timestamp,
                "posts": [
                    {
                        "id": post.id,
                        "reddit_id": post.reddit_id,
                        "title": post.title,
                        "selftext": post.selftext,
                        "author": post.author,
                        "subreddit": post.subreddit,
                        "url": post.url,
                        "permalink": post.permalink,
                        "score": post.score,
                        "comments": post.comments,
                        "upvote_ratio": post.upvote_ratio,
                        "created_utc": post.created_utc,
                        "fetched_at": post.fetched_at
                    }
                    for post in posts
                ]
            }
            cluster_list.append(cluster_dict)
        
        return {
            "status": "success",
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "total_clusters": len(clusters),
            "total_posts": total_posts,
            "clusters": cluster_list
        }
        
    except ValueError as e:
        logger.error(f"Date validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving Reddit report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve report: {str(e)}")