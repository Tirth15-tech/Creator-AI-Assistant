from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.post import Post, GeneratedContent
from app.models.social import SocialAccount, PostingHistory, ScheduledPost, Draft

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
def get_analytics_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_posts = db.query(func.count(Post.id)).filter(Post.user_id == current_user.id).scalar()
    total_generated = db.query(func.count(GeneratedContent.id)).join(
        Post, GeneratedContent.post_id == Post.id
    ).filter(Post.user_id == current_user.id).scalar()

    media_counts = (
        db.query(Post.media_type, func.count(Post.id))
        .filter(Post.user_id == current_user.id)
        .group_by(Post.media_type)
        .all()
    )
    posts_by_type = {mt: count for mt, count in media_counts}

    total_drafts = db.query(func.count(Draft.id)).filter(Draft.user_id == current_user.id).scalar()
    total_scheduled = db.query(func.count(ScheduledPost.id)).filter(
        ScheduledPost.user_id == current_user.id
    ).scalar()

    connected_accounts = db.query(func.count(SocialAccount.id)).filter(
        SocialAccount.user_id == current_user.id,
        SocialAccount.is_active == True,
    ).scalar()

    total_published = db.query(func.count(PostingHistory.id)).filter(
        PostingHistory.user_id == current_user.id
    ).scalar()

    total_likes = db.query(func.coalesce(func.sum(PostingHistory.likes), 0)).filter(
        PostingHistory.user_id == current_user.id
    ).scalar()
    total_comments = db.query(func.coalesce(func.sum(PostingHistory.comments), 0)).filter(
        PostingHistory.user_id == current_user.id
    ).scalar()

    return {
        "total_posts": total_posts,
        "total_generated": total_generated,
        "posts_by_type": posts_by_type,
        "total_drafts": total_drafts,
        "total_scheduled": total_scheduled,
        "connected_accounts": connected_accounts,
        "total_published": total_published,
        "total_likes": total_likes,
        "total_comments": total_comments,
    }


@router.get("/engagement")
def get_engagement_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    history = (
        db.query(PostingHistory)
        .filter(
            PostingHistory.user_id == current_user.id,
            PostingHistory.posted_at >= since,
        )
        .all()
    )

    total_likes = sum(h.likes or 0 for h in history)
    total_comments = sum(h.comments or 0 for h in history)
    total_shares = sum(h.shares or 0 for h in history)
    total_impressions = sum(h.impressions or 0 for h in history)
    total_reach = sum(h.reach or 0 for h in history)
    post_count = len(history)

    return {
        "period_days": days,
        "total_posts": post_count,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_impressions": total_impressions,
        "total_reach": total_reach,
        "avg_likes_per_post": round(total_likes / post_count, 1) if post_count else 0,
        "avg_comments_per_post": round(total_comments / post_count, 1) if post_count else 0,
        "engagement_rate": round(
            (total_likes + total_comments) / max(total_impressions, 1) * 100, 2
        ) if total_impressions else 0,
    }


@router.get("/content-breakdown")
def get_content_breakdown(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    posts_7d = db.query(func.count(Post.id)).filter(
        Post.user_id == current_user.id,
        Post.created_at >= seven_days_ago,
    ).scalar()

    posts_30d = db.query(func.count(Post.id)).filter(
        Post.user_id == current_user.id,
        Post.created_at >= thirty_days_ago,
    ).scalar()

    avg_viral = db.query(func.avg(GeneratedContent.viral_score)).join(
        Post, GeneratedContent.post_id == Post.id
    ).filter(Post.user_id == current_user.id).scalar()

    return {
        "posts_last_7_days": posts_7d,
        "posts_last_30_days": posts_30d,
        "average_viral_score": round(float(avg_viral), 1) if avg_viral else 0,
    }
