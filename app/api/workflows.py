"""
n8n workflow callbacks and job visibility.

Security model:
- /callback is NOT user-authenticated; it is authenticated by an HMAC-SHA256
  signature over the raw body using N8N_WEBHOOK_SECRET (shared secret).
- A callback can only touch the single WorkflowJob it names. Ownership of any
  affected ContentAI record is derived from the server-side job row
  (job.user_id), never from callback data.
- Tokens and secrets are never accepted in or returned by this API.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.post import Post, GeneratedContent
from app.models.social import ScheduledPost
from app.models.workflow import WorkflowJob
from app.services.n8n_client import verify_signature

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_ALLOWED_STATUSES = {"processing", "completed", "failed", "cancelled"}
_STATUS_ALIASES = {
    "running": "processing",
    "in_progress": "processing",
    "success": "completed",
    "succeeded": "completed",
    "error": "failed",
}

# Structured generation result -> GeneratedContent column mapping.
_RESULT_FIELD_MAP = {
    "caption": "caption",
    "hook": "hook",
    "cta": "cta",
    "hashtags": "hashtags",
    "keywords": "keywords",
    "emojis": "emojis",
    "alt_text": "alt_text",
    "seo": "seo_tags",
    "description": "summary",
}


def _new_job_id() -> str:
    return uuid.uuid4().hex


def create_workflow_job(
    db: Session,
    *,
    user_id: int,
    workflow_type: str,
    content_id: Optional[int] = None,
    scheduled_post_id: Optional[int] = None,
    payload: Optional[dict] = None,
) -> WorkflowJob:
    """Create a pending workflow job. Called only from trusted backend code."""
    job = WorkflowJob(
        job_id=_new_job_id(),
        user_id=user_id,
        workflow_type=workflow_type,
        content_id=content_id,
        scheduled_post_id=scheduled_post_id,
        payload=payload or {},
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _as_string_list(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "").strip()


def _merge_generation_result(db: Session, job: WorkflowJob, result: dict) -> None:
    """Merge a structured AI result into the job's own GeneratedContent row.

    Only fields explicitly provided (and owned via job.user_id) are updated;
    existing values the user may have edited are never overwritten with empty.
    """
    if not job.content_id:
        return

    post = db.query(Post).filter(
        Post.id == job.content_id, Post.user_id == job.user_id
    ).first()
    if not post:
        return

    gen = db.query(GeneratedContent).filter(
        GeneratedContent.post_id == post.id
    ).first()
    if gen is None:
        gen = GeneratedContent(post_id=post.id)
        db.add(gen)

    for source_key, column in _RESULT_FIELD_MAP.items():
        if source_key not in result:
            continue
        value = result[source_key]
        if isinstance(value, (list, tuple)):
            value = _as_string_list(value)
        if value:
            setattr(gen, column, str(value))

    db.commit()


def _mark_job(job: WorkflowJob, status: str, result=None, error_message: str = "") -> None:
    now = datetime.now(timezone.utc)
    job.status = status
    if status == "processing" and job.started_at is None:
        job.started_at = now
    if status in ("completed", "failed", "cancelled"):
        job.completed_at = now
    if result is not None:
        job.result = result
    if error_message:
        job.error_message = error_message[:2000]


@router.post("/callback")
async def workflow_callback(request: Request, db: Session = Depends(get_db)):
    """Secure n8n -> ContentAI callback.

    Body:
    {
      "job_id": "...",            # required, references a server-created job
      "status": "processing|completed|failed|cancelled",
      "result": {...},            # optional structured result
      "error_message": "...",     # optional, safe text
      "action": "update|publish_due"   # optional, defaults to "update"
    }
    """
    raw = await request.body()
    signature = request.headers.get("X-ContentAI-Signature", "")

    if not get_settings().N8N_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Workflow callbacks are not configured")
    if not verify_signature(raw, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        import json
        data = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    job_id = str(data.get("job_id") or "")
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id is required")

    job = db.query(WorkflowJob).filter(WorkflowJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")

    action = str(data.get("action") or "update")

    # ── Scheduled publishing due: execute through the real provider ──
    if action == "publish_due":
        if job.workflow_type != "publish" or not job.scheduled_post_id:
            raise HTTPException(status_code=400, detail="Job does not support publish_due")

        post = db.query(ScheduledPost).filter(
            ScheduledPost.id == job.scheduled_post_id,
            ScheduledPost.user_id == job.user_id,   # ownership re-check
        ).first()
        if not post:
            raise HTTPException(status_code=404, detail="Scheduled post not found")
        if post.status != "scheduled":
            # Already handled elsewhere (local scheduler won the race, or cancelled)
            _mark_job(job, "cancelled", error_message=f"Scheduled post status is '{post.status}'")
            db.commit()
            return {"success": False, "detail": f"Scheduled post is '{post.status}'"}

        from app.services.scheduler import _publish_scheduled_post
        _mark_job(job, "processing")
        db.commit()
        success = await _publish_scheduled_post(db, post)

        db.refresh(post)
        db.refresh(job)
        _mark_job(
            job,
            "completed" if success else "failed",
            result={"scheduled_post_status": post.status},
            error_message=post.error_message or "",
        )
        db.commit()
        return {"success": success, "status": post.status}

    # ── Default: plain status/result update ──
    status_raw = str(data.get("status") or "").lower()
    status = _STATUS_ALIASES.get(status_raw, status_raw)
    if status and status not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    result = data.get("result")
    if result is not None and not isinstance(result, dict):
        raise HTTPException(status_code=400, detail="result must be an object")

    error_message = str(data.get("error_message") or "")

    if status:
        _mark_job(job, status, result=result, error_message=error_message)
    elif result is not None:
        job.result = result

    if (
        job.workflow_type == "content_generation"
        and job.status == "completed"
        and isinstance(result, dict)
    ):
        _merge_generation_result(db, job, result)

    db.commit()
    return {"success": True, "job_id": job.job_id, "status": job.status}


@router.get("/jobs")
def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's workflow jobs (safe fields only)."""
    jobs = db.query(WorkflowJob).filter(
        WorkflowJob.user_id == current_user.id,
    ).order_by(WorkflowJob.created_at.desc()).limit(100).all()

    return {
        "jobs": [{
            "job_id": j.job_id,
            "workflow_type": j.workflow_type,
            "content_id": j.content_id,
            "scheduled_post_id": j.scheduled_post_id,
            "status": j.status,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "error_message": j.error_message,
        } for j in jobs]
    }
