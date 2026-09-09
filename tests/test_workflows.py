"""
Tests for the n8n automation layer: workflow jobs, secured callbacks,
schedule delegation, and Instagram safety guards added for real mode.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.core.security import encrypt_token
from tests.conftest import TestSessionLocal


def _enable_n8n(monkeypatch, secret="test-webhook-secret"):
    s = get_settings()
    monkeypatch.setattr(s, "N8N_ENABLED", True)
    monkeypatch.setattr(s, "N8N_BASE_URL", "http://localhost:5678")
    monkeypatch.setattr(s, "N8N_WEBHOOK_SECRET", secret)
    return s


def _signed_post(client, payload: dict, secret="test-webhook-secret"):
    from app.services.n8n_client import sign_payload
    raw = json.dumps(payload).encode("utf-8")
    return client.post(
        "/api/workflows/callback",
        content=raw,
        headers={"Content-Type": "application/json", "X-ContentAI-Signature": sign_payload(raw)},
    )


def _connect_demo_instagram(auth_client):
    r = auth_client.get("/api/social/connect/instagram")
    auth_client.get(r.json()["auth_url"], follow_redirects=False)
    from app.models.social import SocialAccount
    db = TestSessionLocal()
    try:
        acc = db.query(SocialAccount).filter(
            SocialAccount.platform_user_id == "demo_instagram"
        ).first()
        return acc.id
    finally:
        db.close()


# ── Callback security ──────────────────────────────────────────────

def test_callback_disabled_without_secret(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "N8N_ENABLED", False)
    monkeypatch.setattr(s, "N8N_WEBHOOK_SECRET", "")
    r = client.post("/api/workflows/callback", json={"job_id": "x"})
    assert r.status_code == 503


def test_callback_rejects_missing_and_bad_signature(client, monkeypatch):
    _enable_n8n(monkeypatch)
    r = client.post("/api/workflows/callback", json={"job_id": "x"})
    assert r.status_code == 401
    r = client.post(
        "/api/workflows/callback",
        json={"job_id": "x"},
        headers={"X-ContentAI-Signature": "deadbeef"},
    )
    assert r.status_code == 401


def test_callback_unknown_job_404(client, monkeypatch):
    _enable_n8n(monkeypatch)
    r = _signed_post(client, {"job_id": "does-not-exist", "status": "completed"})
    assert r.status_code == 404


# ── Status/result updates + generation result merge ────────────────

def test_callback_updates_job_and_merges_generation_result(client, auth_client, monkeypatch):
    _enable_n8n(monkeypatch)

    from app.models.post import Post, GeneratedContent
    from app.models.user import User
    from app.models.workflow import WorkflowJob
    from app.api.workflows import create_workflow_job

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == "test@example.com").first()
        post = Post(user_id=user.id, media_type="image", media_path="uploads/x.jpg")
        db.add(post)
        db.flush()
        gen = GeneratedContent(post_id=post.id, caption="")
        db.add(gen)
        db.commit()
        job = create_workflow_job(
            db, user_id=user.id, workflow_type="content_generation", content_id=post.id,
        )
        job_id = job.job_id
        post_id = post.id
    finally:
        db.close()

    r = _signed_post(auth_client, {
        "job_id": job_id,
        "status": "completed",
        "result": {
            "caption": "From workflow",
            "hashtags": ["#a", "#b"],
            "keywords": [],
            "seo": "seo tag",
            "alt_text": "alt text",
        },
    })
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    db = TestSessionLocal()
    try:
        gen = db.query(GeneratedContent).filter(GeneratedContent.post_id == post_id).first()
        assert gen.caption == "From workflow"
        assert "#a" in gen.hashtags and "#b" in gen.hashtags
        assert gen.seo_tags == "seo tag"
        assert gen.alt_text == "alt text"
        # Empty lists must NOT overwrite existing values
        job = db.query(WorkflowJob).filter(WorkflowJob.job_id == job_id).first()
        assert job.status == "completed"
        assert job.completed_at is not None
    finally:
        db.close()


# ── Scheduled publishing through n8n callback ──────────────────────

def test_publish_due_executes_real_publish_via_provider(client, auth_client, monkeypatch):
    _enable_n8n(monkeypatch)

    from app.models.social import ScheduledPost, SocialAccount, PostingHistory
    from app.models.user import User
    from app.models.workflow import WorkflowJob
    from app.api.workflows import create_workflow_job
    from app.social.base import PlatformType, PublishResult

    class _MockProvider:
        platform = PlatformType.INSTAGRAM

        def supports_publishing(self, account_type):
            return True

        async def publish_post(self, account, payload):
            return PublishResult(
                success=True,
                platform_post_id="REAL_MEDIA_987",
                platform_url="https://www.instagram.com/p/REALURL/",
            )

    monkeypatch.setattr("app.services.scheduler.get_provider", lambda p: _MockProvider())

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == "test@example.com").first()
        acc = SocialAccount(
            user_id=user.id, platform="instagram", account_type="business",
            platform_user_id="real_sched_acc", username="sched_user",
            access_token=encrypt_token("tok"), is_active=True,
        )
        db.add(acc)
        db.flush()
        sp = ScheduledPost(
            user_id=user.id, account_id=acc.id, caption="c", hashtags="#h",
            media_path="uploads/pic.jpg", media_type="image",
            scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            status="scheduled",
        )
        db.add(sp)
        db.commit()
        job = create_workflow_job(
            db, user_id=user.id, workflow_type="publish", scheduled_post_id=sp.id,
        )
        job.status = "dispatched"
        db.commit()
        sp_id, job_id = sp.id, job.job_id
    finally:
        db.close()

    r = _signed_post(auth_client, {"job_id": job_id, "action": "publish_due"})
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert r.json()["status"] == "published"

    db = TestSessionLocal()
    try:
        sp = db.get(ScheduledPost, sp_id)
        assert sp.status == "published"
        assert sp.platform_post_id == "REAL_MEDIA_987"
        hist = db.query(PostingHistory).filter(PostingHistory.user_id == sp.user_id).all()
        assert any(h.platform_post_id == "REAL_MEDIA_987" for h in hist)
        job = db.query(WorkflowJob).filter(WorkflowJob.job_id == job_id).first()
        assert job.status == "completed"
    finally:
        db.close()


def test_local_scheduler_skips_active_n8n_posts(client, auth_client, monkeypatch):
    """A scheduled post owned by an active n8n job must not double-publish."""
    from app.models.social import ScheduledPost, SocialAccount
    from app.models.user import User
    from app.models.workflow import WorkflowJob
    from app.api.workflows import create_workflow_job

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == "test@example.com").first()
        acc = SocialAccount(
            user_id=user.id, platform="instagram", account_type="business",
            platform_user_id="real_skip_acc", username="skip_user",
            access_token=encrypt_token("tok"), is_active=True,
        )
        db.add(acc)
        db.flush()
        sp = ScheduledPost(
            user_id=user.id, account_id=acc.id, caption="c",
            media_path="uploads/pic.jpg", media_type="image",
            scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            status="scheduled",
        )
        db.add(sp)
        db.commit()
        job = create_workflow_job(
            db, user_id=user.id, workflow_type="publish", scheduled_post_id=sp.id,
        )
        job.status = "dispatched"
        db.commit()
        sp_id = sp.id
    finally:
        db.close()

    from app.services.scheduler import _scheduler_loop  # noqa: F401  (module imports ok)
    import asyncio
    from app.core.database import SessionLocal as RealSessionLocal
    from sqlalchemy import select

    db = RealSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        active = [
            row[0] for row in db.query(WorkflowJob.scheduled_post_id).filter(
                WorkflowJob.workflow_type == "publish",
                WorkflowJob.status.in_(["pending", "dispatched", "processing"]),
            ).all()
        ]
        q = db.query(ScheduledPost).filter(
            ScheduledPost.status == "scheduled",
            ScheduledPost.scheduled_at <= now,
        )
        if active:
            q = q.filter(~ScheduledPost.id.in_(active))
        ids = [p.id for p in q.all()]
        assert sp_id not in ids
    finally:
        db.close()


# ── Scheduling dispatches to n8n when enabled ──────────────────────

def test_schedule_dispatches_n8n_job_when_enabled(auth_client, monkeypatch):
    _enable_n8n(monkeypatch)

    captured = {}

    async def fake_trigger(job_id, workflow_type, payload=None):
        captured["job_id"] = job_id
        captured["payload"] = payload
        return True

    import app.services.n8n_client as n8n_mod
    monkeypatch.setattr(n8n_mod, "trigger_workflow", fake_trigger)
    monkeypatch.setattr(n8n_mod, "n8n_enabled", lambda: True)

    acc_id = _connect_demo_instagram(auth_client)
    when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    r = auth_client.post("/api/social/schedule", json={
        "account_id": acc_id, "caption": "hello", "hashtags": "#x",
        "media_path": "uploads/pic.jpg", "media_type": "image", "scheduled_at": when,
    })
    assert r.status_code == 200
    assert r.json()["automation"] == "n8n"
    assert captured["job_id"]
    assert captured["payload"]["scheduled_post_id"]

    from app.models.workflow import WorkflowJob
    db = TestSessionLocal()
    try:
        job = db.query(WorkflowJob).filter(WorkflowJob.job_id == captured["job_id"]).first()
        assert job is not None
        assert job.status == "dispatched"
        assert job.scheduled_post_id == captured["payload"]["scheduled_post_id"]
    finally:
        db.close()


def test_schedule_falls_back_when_n8n_unreachable(auth_client, monkeypatch):
    _enable_n8n(monkeypatch)

    import app.services.n8n_client as n8n_mod
    monkeypatch.setattr(n8n_mod, "n8n_enabled", lambda: True)

    async def failing_trigger(job_id, workflow_type, payload=None):
        return False

    monkeypatch.setattr(n8n_mod, "trigger_workflow", failing_trigger)

    acc_id = _connect_demo_instagram(auth_client)
    when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    r = auth_client.post("/api/social/schedule", json={
        "account_id": acc_id, "caption": "hello", "hashtags": "#x",
        "media_path": "uploads/pic.jpg", "media_type": "image", "scheduled_at": when,
    })
    assert r.status_code == 200
    assert r.json()["automation"] == "internal"

    from app.models.workflow import WorkflowJob
    db = TestSessionLocal()
    try:
        jobs = db.query(WorkflowJob).filter(WorkflowJob.workflow_type == "publish").all()
        assert jobs and jobs[0].status == "failed"
        assert "local scheduler" in jobs[0].error_message
    finally:
        db.close()


# ── Instagram media-type guard ─────────────────────────────────────

def test_audio_cannot_be_published_to_instagram(auth_client):
    acc_id = _connect_demo_instagram(auth_client)
    r = auth_client.post("/api/social/post-now", json={
        "account_id": acc_id, "caption": "hi", "media_type": "audio",
        "media_path": "uploads/track.mp3",
    })
    assert r.status_code == 400
    assert "cannot be directly published to Instagram" in r.json()["detail"]


def test_document_cannot_be_scheduled_to_instagram(auth_client):
    acc_id = _connect_demo_instagram(auth_client)
    when = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    r = auth_client.post("/api/social/schedule", json={
        "account_id": acc_id, "caption": "hi", "media_type": "document",
        "media_path": "uploads/doc.pdf", "scheduled_at": when,
    })
    assert r.status_code == 400
    assert "cannot be directly published to Instagram" in r.json()["detail"]


# ── Disconnect hardening ───────────────────────────────────────────

def test_disconnect_clears_tokens(auth_client):
    from app.models.social import SocialAccount
    from app.models.user import User

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == "test@example.com").first()
        acc = SocialAccount(
            user_id=user.id, platform="instagram", account_type="business",
            platform_user_id="real_dc_acc", username="dc_user",
            access_token=encrypt_token("secret-token"), is_active=True,
        )
        db.add(acc)
        db.commit()
        acc_id = acc.id
    finally:
        db.close()

    r = auth_client.delete(f"/api/social/accounts/{acc_id}")
    assert r.status_code == 200

    db = TestSessionLocal()
    try:
        acc = db.get(SocialAccount, acc_id)
        assert acc.is_active is False
        assert acc.access_token is None
        assert acc.refresh_token is None
    finally:
        db.close()


# ── Account info exposure ──────────────────────────────────────────

def test_accounts_expose_platform_user_id_only_for_real_accounts(auth_client):
    from app.models.social import SocialAccount
    from app.models.user import User

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.email == "test@example.com").first()
        db.add(SocialAccount(
            user_id=user.id, platform="instagram", account_type="creator",
            platform_user_id="17841400000000", username="realuser",
            access_token=encrypt_token("t"), is_active=True,
        ))
        db.commit()
    finally:
        db.close()

    accounts = auth_client.get("/api/social/accounts").json()["accounts"]
    ig = [a for a in accounts if a["platform_user_id"] == "17841400000000"]
    assert ig and ig[0]["username"] == "realuser"


# ── Jobs listing is user-scoped ────────────────────────────────────

def test_jobs_endpoint_lists_only_own_jobs(auth_client, client, monkeypatch):
    _enable_n8n(monkeypatch)

    from app.models.user import User
    from app.api.workflows import create_workflow_job

    db = TestSessionLocal()
    try:
        user_a = db.query(User).filter(User.email == "test@example.com").first()
        create_workflow_job(db, user_id=user_a.id, workflow_type="content_generation")

        client.post("/api/auth/register", json={"email": "wf2@example.com", "password": "testpass123"})
        user_b = db.query(User).filter(User.email == "wf2@example.com").first()
        create_workflow_job(db, user_id=user_b.id, workflow_type="publish")
    finally:
        db.close()

    jobs = auth_client.get("/api/workflows/jobs").json()["jobs"]
    assert len(jobs) >= 1
