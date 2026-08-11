from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    media_type = Column(String(50), nullable=False)
    media_path = Column(String(500), nullable=True)
    original_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="posts")
    generated_content = relationship("GeneratedContent", backref="post", uselist=False)


class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)

    # Core content fields (Phase 1)
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    emojis = Column(Text, nullable=True)
    cta = Column(Text, nullable=True)
    hook = Column(Text, nullable=True)
    reel_title = Column(Text, nullable=True)
    seo_tags = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    translation = Column(Text, nullable=True)
    viral_score = Column(Integer, nullable=True)
    viral_score_reason = Column(Text, nullable=True)

    # Phase 2B: Advanced caption types
    long_caption = Column(Text, nullable=True)
    short_caption = Column(Text, nullable=True)
    funny_caption = Column(Text, nullable=True)
    professional_caption = Column(Text, nullable=True)
    travel_caption = Column(Text, nullable=True)
    business_caption = Column(Text, nullable=True)
    food_caption = Column(Text, nullable=True)
    luxury_caption = Column(Text, nullable=True)
    carousel_text = Column(Text, nullable=True)
    thumbnail_text = Column(String(200), nullable=True)
    alt_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
