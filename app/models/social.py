from datetime import datetime, timezone, timedelta
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class SocialAccount(Base):
    """A user's connected social media account (Instagram, Facebook, etc.)."""
    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    platform = Column(String(50), nullable=False)           # instagram, facebook, linkedin, twitter
    account_type = Column(String(50), default="personal")   # personal, business, creator

    platform_user_id = Column(String(255), nullable=False)  # platform's unique ID
    username = Column(String(255), nullable=False)
    display_name = Column(String(255), default="")
    profile_picture_url = Column(String(500), default="")
    followers_count = Column(Integer, default=0)

    # OAuth tokens
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, default=True, index=True)
    raw_data = Column(JSON, nullable=True)  # platform-specific extra data
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="social_accounts")
    scheduled_posts = relationship("ScheduledPost", backref="account", cascade="all, delete-orphan")
    posting_history = relationship("PostingHistory", backref="account", cascade="all, delete-orphan")


class Draft(Base):
    """A saved content draft, ready for editing or scheduling."""
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)

    title = Column(String(255), default="")
    caption = Column(Text, default="")
    long_caption = Column(Text, default="")
    short_caption = Column(Text, default="")
    hashtags = Column(Text, default="")
    emojis = Column(Text, default="")
    media_path = Column(String(500), default="")
    media_type = Column(String(50), default="image")

    target_platforms = Column(JSON, default=list)   # ["instagram", "facebook"]
    notes = Column(Text, default="")
    status = Column(String(50), default="draft")    # draft, ready

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="drafts")


class ScheduledPost(Base):
    """A post scheduled to be published at a specific time.
    Supports one-time and recurring schedules."""
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("social_accounts.id"), nullable=False, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=True)

    caption = Column(Text, default="")
    hashtags = Column(Text, default="")
    media_path = Column(String(500), default="")
    media_type = Column(String(50), default="image")

    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(50), default="scheduled", index=True)  # scheduled, publishing, published, failed, cancelled
    platform_post_id = Column(String(255), nullable=True)   # ID once published
    platform_url = Column(String(500), nullable=True)       # URL once published
    error_message = Column(Text, nullable=True)

    # Recurring schedule (design only)
    is_recurring = Column(Boolean, default=False)
    recur_frequency = Column(String(50), nullable=True)     # daily, weekly, monthly
    recur_interval = Column(Integer, default=1)             # every N days/weeks/months
    recur_end_date = Column(DateTime(timezone=True), nullable=True)
    recur_count = Column(Integer, nullable=True)            # max occurrences (null = unlimited)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="scheduled_posts")


class PostingHistory(Base):
    """Completed/posted content history for analytics and review."""
    __tablename__ = "posting_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("social_accounts.id"), nullable=False, index=True)

    platform_post_id = Column(String(255), nullable=False)
    platform_url = Column(String(500), default="")
    caption = Column(Text, default="")
    hashtags = Column(Text, default="")
    media_path = Column(String(500), default="")
    media_type = Column(String(50), default="image")

    posted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Engagement metrics (updated periodically)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    last_metrics_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(50), default="published")  # published, failed, deleted

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Notification(Base):
    """User notifications about post status, scheduling, errors."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), default="info")   # info, success, warning, error
    is_read = Column(Boolean, default=False, index=True)
    link = Column(String(500), nullable=True)                # optional deep link

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="notifications")
