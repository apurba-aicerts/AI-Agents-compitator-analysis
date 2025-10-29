# models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Float,
    Boolean,
    Table,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base


# Association Table for the many-to-many relationship between SocialMediaPost and Hashtag
post_hashtag_association = Table(
    "post_hashtag_association",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("social_media_post.id")),
    Column("hashtag_id", Integer, ForeignKey("hashtag.id")),
)


class Hashtag(Base):
    __tablename__ = "hashtag"
    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String, unique=True, index=True)


class SocialMediaPost(Base):
    __tablename__ = "social_media_post"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String, unique=True, index=True)  # LinkedIn UID
    company_id = Column(Integer, ForeignKey("company.company_id"))
    post_platform = Column(String, default="linkedin")
    post_url = Column(String, nullable=True)
    post_description = Column(Text, nullable=True)
    posted_at = Column(DateTime, default=datetime.utcnow)
    likes = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    sentiment_label = Column(String, nullable=True)
    sentiment_score = Column(Float, nullable=True)

    # Relationship to the Hashtag model
    hashtags = relationship("Hashtag", secondary=post_hashtag_association)


class Company(Base):
    __tablename__ = "company"

    company_id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, unique=True, index=True)
    industry = Column(String(128), nullable=True)
    headquarters = Column(String(255), nullable=True)
    founded_year = Column(Integer, nullable=True)
    employee_count = Column(Integer, nullable=True)
    website = Column(String(512), nullable=True)

    # relationships
    socials = relationship(
        "CompanySocial", back_populates="company", cascade="all, delete-orphan"
    )


class CompanySocial(Base):
    __tablename__ = "company_social"

    social_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(
        Integer, ForeignKey("company.company_id", ondelete="CASCADE"), nullable=False
    )
    platform_name = Column(String(64), nullable=False)
    profile_url = Column(String(1024), nullable=False)

    company = relationship("Company", back_populates="socials")


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alert"

    alert_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company.company_id"))
    post_id = Column(Integer, ForeignKey("social_media_post.id"))
    alert_message = Column(String(512), nullable=False)
    severity = Column(String(50), default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)


class CrawlerLog(Base):
    __tablename__ = "crawler_log"

    log_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company.company_id"))
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="in_progress")
    posts_scraped = Column(Integer, default=0)
    posts_saved = Column(Integer, default=0)
    alerts_saved = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)


# Add these imports and models to your existing models.py file

from sqlalchemy import JSON

# Association Table for RedditCluster and RedditPost (many-to-many)
reddit_cluster_post_association = Table(
    "reddit_cluster_post_association",
    Base.metadata,
    Column("cluster_id", Integer, ForeignKey("reddit_cluster.id")),
    Column("post_id", Integer, ForeignKey("reddit_post.id")),
)


class RedditPost(Base):
    """Store raw Reddit posts"""
    __tablename__ = "reddit_post"

    id = Column(Integer, primary_key=True, index=True)
    reddit_id = Column(String, unique=True, index=True)  # Reddit post ID
    title = Column(Text, nullable=False)
    selftext = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    author_fullname = Column(String, nullable=True)
    
    # Subreddit info
    subreddit = Column(String, nullable=False, index=True)
    subreddit_name_prefixed = Column(String, nullable=True)
    
    # URLs
    url = Column(String, nullable=True)
    permalink = Column(String, nullable=True)
    
    # Engagement metrics
    score = Column(Integer, default=0)
    ups = Column(Integer, default=0)
    downs = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    upvote_ratio = Column(Float, nullable=True)
    
    # Post metadata
    created_utc = Column(DateTime, nullable=False, index=True)  # When posted on Reddit
    fetched_at = Column(DateTime, default=datetime.utcnow)  # When we fetched it
    
    # Additional fields
    is_self = Column(Boolean, default=True)
    over_18 = Column(Boolean, default=False)
    stickied = Column(Boolean, default=False)
    is_video = Column(Boolean, default=False)
    link_flair_text = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    
    # Store additional data as JSON
    additional_data = Column(JSON, nullable=True)
    
    # Relationship to clusters (many-to-many)
    clusters = relationship("RedditCluster", secondary=reddit_cluster_post_association, back_populates="posts")


class RedditCluster(Base):
    """Store Reddit trending topic clusters"""
    __tablename__ = "reddit_cluster"

    id = Column(Integer, primary_key=True, index=True)
    cluster_name = Column(String, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    
    # Scoring
    relevance_score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    
    # Metrics stored as JSON for flexibility
    metrics = Column(JSON, nullable=False)  # {freshness_score, engagement_score, frequency, total_engagement}
    
    # Date range for this analysis
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    
    # Keywords used for analysis
    keywords = Column(JSON, nullable=False)  # List of keywords
    
    # Analysis metadata
    analysis_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to posts (many-to-many)
    posts = relationship("RedditPost", secondary=reddit_cluster_post_association, back_populates="clusters")


from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from core.database import Base

class CompetitorAnalysis(Base):
    __tablename__ = "competitor_analysis"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company.company_id"))
    company_name = Column(String, nullable=False)
    website_url = Column(String, nullable=False)
    raw_data = Column(Text, nullable=False)   # Firecrawl extracted data
    analysis_json = Column(Text, nullable=False)  # OpenAI structured output
    created_at = Column(DateTime, default=datetime.utcnow)
