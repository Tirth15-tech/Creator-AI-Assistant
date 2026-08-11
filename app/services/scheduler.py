"""
Phase 3C: Post Scheduler

Background task that periodically checks for scheduled posts
and publishes them when their scheduled time arrives.

Runs as a FastAPI lifespan task alongside the app.
"""

import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.social import ScheduledPost, SocialAccount, PostingHistory, Notification
from app.social.registry import get_provider
from app.social.base import (
    PlatformType, PostPayload, PostStatus,
    is_demo_account, demo_publish_result,
)

logger = logging.getLogger(__name__)

_scheduler_running = False
_scheduler_task = None


async def _publish_scheduled_post(db: Session, post: ScheduledPost) -> bool:
    """Attempt to publish a single scheduled post."""
    account = db.query(SocialAccount).filter(
        SocialAccount.id == post.account_id,
    ).first()

    if not account or not account.is_active:
        post.status = "failed"
        post.error_message = "Social account not found or disconnected"
        db.commit()
        return False

    if account.user_id != post.user_id:
        post.status = "failed"
        post.error_message = "Social account does not belong to the post owner"
        db.commit()
        return False

    provider = get_provider(PlatformType(account.platform))
    if not provider:
        post.status = "failed"
        post.error_message = f"Provider for {account.platform} not available"
        db.commit()
        return False

    if not provider.supports_publishing(account.account_type):
        post.status = "failed"
        post.error_message = f"{account.account_type.title()} accounts cannot publish via API"
        db.commit()
        return False

    from app.core.security import decrypt_token
    account.access_token = decrypt_token(account.access_token)

    payload = PostPayload(
        caption=post.caption,
        media_path=post.media_path,
        media_type=post.media_type,
        hashtags=post.hashtags,
    )

    try:
        post.status = "publishing"
        db.commit()

        result = (
            demo_publish_result(account)
            if is_demo_account(account)
            else await provider.publish_post(account, payload)
        )

        if result.success:
            post.status = "published"
            post.platform_post_id = result.platform_post_id
            post.platform_url = result.platform_url

            # Add to posting history
            db.add(PostingHistory(
                user_id=post.user_id,
                account_id=account.id,
                platform_post_id=result.platform_post_id,
                platform_url=result.platform_url,
                caption=post.caption,
                hashtags=post.hashtags,
                media_path=post.media_path,
                media_type=post.media_type,
            ))

            # Success notification
            db.add(Notification(
                user_id=post.user_id,
                title="Post Published",
                message=f"Your scheduled post was published to {account.platform} successfully!",
                notification_type="success",
                link=result.platform_url,
            ))
        else:
            post.status = "failed"
            post.error_message = result.error_message

            db.add(Notification(
                user_id=post.user_id,
                title="Post Failed",
                message=f"Your scheduled post to {account.platform} failed: {result.error_message}",
                notification_type="error",
            ))

        db.commit()
        return result.success

    except Exception as e:
        logger.error("Scheduler publish error for post %d: %s", post.id, e)
        post.status = "failed"
        post.error_message = str(e)
        db.commit()
        return False


async def _scheduler_loop():
    """Main scheduler loop that checks for due scheduled posts."""
    from app.core.config import get_settings
    settings = get_settings()
    interval = settings.SCHEDULER_INTERVAL_SECONDS

    logger.info("Scheduler started (interval: %ds)", interval)

    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)

                due_posts = db.query(ScheduledPost).filter(
                    ScheduledPost.status == "scheduled",
                    ScheduledPost.scheduled_at <= now,
                ).all()

                if due_posts:
                    logger.info("Found %d posts due for publishing", len(due_posts))

                for post in due_posts:
                    logger.info("Publishing scheduled post %d", post.id)
                    await _publish_scheduled_post(db, post)

            finally:
                db.close()

        except Exception as e:
            logger.error("Scheduler loop error: %s", e)

        await asyncio.sleep(interval)


def start_scheduler():
    """Start the background scheduler as an asyncio task."""
    global _scheduler_running, _scheduler_task

    if _scheduler_running:
        logger.info("Scheduler already running")
        return

    _scheduler_running = True
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Scheduler task created")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running, _scheduler_task

    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
    _scheduler_running = False
    logger.info("Scheduler stopped")
