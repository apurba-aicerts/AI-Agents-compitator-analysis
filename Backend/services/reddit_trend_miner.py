#services/reddit_trend_miner.py
import logging
from datetime import datetime
import praw
from prawcore.exceptions import NotFound, Forbidden, ResponseException
import time
from core.database import SessionLocal
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def search_subreddits_by_keyword(reddit, keyword, limit=10, max_retries=3):
    """Search for subreddits matching a keyword with retry logic."""
    subs = []
    for attempt in range(max_retries):
        try:
            for sub in reddit.subreddits.search(keyword, limit=limit):
                subs.append(sub.display_name)
            return subs
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{max_retries} - Error searching subreddits for '{keyword}': {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to search subreddits for '{keyword}' after {max_retries} attempts")
    return subs

def fetch_subreddit_posts(reddit, subreddit_name, start_date, end_date, posts_limit=50, max_retries=3):
    """Fetch posts from a subreddit within a date range with retry logic."""
    for attempt in range(max_retries):
        try:
            subreddit = reddit.subreddit(subreddit_name)
            _ = subreddit.display_name  # verify subreddit exists

            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())

            posts = []
            for post in subreddit.new(limit=posts_limit):
                if start_ts <= post.created_utc <= end_ts:
                    posts.append({
                        "id": post.id,
                        "title": post.title,
                        "selftext": post.selftext,
                        "author": str(post.author),
                        "author_fullname": getattr(post, "author_fullname", None),
                        "score": post.score,
                        "ups": post.ups,
                        "downs": post.downs,
                        "comments": post.num_comments,
                        "created_utc": datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d %H:%M:%S"),
                        "subreddit": str(post.subreddit),
                        "subreddit_name_prefixed": post.subreddit_name_prefixed,
                        "url": post.url,
                        "permalink": f"https://www.reddit.com{post.permalink}",
                        "is_self": post.is_self,
                        "over_18": post.over_18,
                        "stickied": post.stickied,
                        "link_flair_text": post.link_flair_text,
                        "link_flair_richtext": post.link_flair_richtext,
                        "thumbnail": post.thumbnail if post.thumbnail != "self" else None,
                        "upvote_ratio": post.upvote_ratio,
                        "all_awardings": post.all_awardings,
                        "is_video": post.is_video,
                        "preview_images": post.preview['images'] if hasattr(post, 'preview') and 'images' in post.preview else None
                    })

            logger.info(f"Fetched {len(posts)} posts from r/{subreddit_name} in range {start_date.date()} - {end_date.date()}")
            return posts

        except NotFound:
            logger.warning(f"Subreddit r/{subreddit_name} not found or is private")
            return []
        except Forbidden:
            logger.warning(f"Access forbidden to r/{subreddit_name}")
            return []
        except ResponseException as e:
            logger.warning(f"Attempt {attempt+1}/{max_retries} - API error for r/{subreddit_name}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Failed to fetch from r/{subreddit_name} after {max_retries} attempts")
                return []
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{max_retries} - Unexpected error for r/{subreddit_name}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Failed to fetch from r/{subreddit_name} after {max_retries} attempts: {e}")
                return []

def fetch_reddit_data(reddit_config, keywords, start_date_str, end_date_str):
    """
    Main function to fetch Reddit data based on keywords and date range.
    
    Args:
        reddit_config: Dict with client_id, client_secret, user_agent, posts_limit, top_subs
        keywords: List of keywords to search
        start_date_str: Start date in format "YYYY-MM-DD"
        end_date_str: End date in format "YYYY-MM-DD"
    
    Returns:
        List of post dictionaries
    """
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        
        # Set end date to end of day
        end_date = end_date.replace(hour=23, minute=59, second=59)
        
    except ValueError as e:
        logger.error(f"Invalid date format: {e}. Expected format: YYYY-MM-DD")
        raise

    reddit = praw.Reddit(
        client_id=reddit_config["client_id"],
        client_secret=reddit_config["client_secret"],
        user_agent=reddit_config["user_agent"]
    )

    all_posts = []
    posts_limit = reddit_config.get("posts_limit", 100)
    top_subs = reddit_config.get("top_subs", 3)

    logger.info(f"Starting Reddit data fetch for date range: {start_date_str} to {end_date_str}")
    logger.info(f"Keywords: {keywords}")

    for keyword in keywords:
        subreddits = search_subreddits_by_keyword(reddit, keyword, limit=top_subs)
        logger.info(f"Subreddits found for '{keyword}': {subreddits}")

        for sub in subreddits:
            posts = fetch_subreddit_posts(reddit, sub, start_date, end_date, posts_limit)
            all_posts.extend(posts)

    logger.info(f"Total posts fetched: {len(all_posts)}")
    return all_posts