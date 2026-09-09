"""
n8n automation-layer client.

ContentAI stays the source of truth: it validates users, owns all tokens and
performs every sensitive operation itself. n8n is only *notified* about jobs
(content generation, scheduled publishing) so it can orchestrate background
work, retries and timing. n8n calls back the secure backend endpoint
(POST /api/workflows/callback) which verifies an HMAC signature before doing
anything.

No access tokens, client secrets or passwords are ever sent to n8n.
"""

import hashlib
import hmac
import json
import logging
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-ContentAI-Signature"
JOB_ID_HEADER = "X-ContentAI-Job-Id"


def n8n_enabled() -> bool:
    """True only when explicitly configured with base URL + shared secret."""
    settings = get_settings()
    return bool(
        settings.N8N_ENABLED
        and settings.N8N_BASE_URL.strip()
        and settings.N8N_WEBHOOK_SECRET.strip()
    )


def sign_payload(body_bytes: bytes) -> str:
    """HMAC-SHA256 hex digest of the raw request body using the shared secret."""
    secret = get_settings().N8N_WEBHOOK_SECRET.encode("utf-8")
    return hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()


def verify_signature(body_bytes: bytes, signature: str) -> bool:
    """Constant-time comparison of an incoming signature against the payload."""
    if not signature:
        return False
    expected = sign_payload(body_bytes)
    try:
        return hmac.compare_digest(expected, signature.strip().lower())
    except Exception:
        return False


def webhook_url() -> str:
    base = get_settings().N8N_BASE_URL.strip().rstrip("/")
    return f"{base}/webhook/contentai"


async def trigger_workflow(job_id: str, workflow_type: str, payload: Optional[dict[str, Any]] = None) -> bool:
    """Fire a signed job notification at the n8n webhook.

    Fire-and-forget by design: failures are logged (without secrets) and
    reported via the boolean result so callers can fall back to local
    processing. Never raises.
    """
    if not n8n_enabled():
        return False

    body = {
        "job_id": job_id,
        "workflow_type": workflow_type,
        **(payload or {}),
    }
    raw = json.dumps(body, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: sign_payload(raw),
        JOB_ID_HEADER: job_id,
    }

    try:
        async with httpx.AsyncClient(timeout=get_settings().N8N_TIMEOUT_SECONDS) as client:
            resp = await client.post(webhook_url(), content=raw, headers=headers)
        if resp.status_code >= 400:
            logger.warning(
                "n8n webhook for job %s returned HTTP %s", job_id, resp.status_code
            )
            return False
        return True
    except Exception as e:
        logger.warning("n8n webhook for job %s failed: %s", job_id, e)
        return False
