"""
Phase 3: Social Media API Endpoints

Handles:
- OAuth connection flow for all platforms
- Listing/disconnecting social accounts
- Saving drafts and scheduled posts
- Posting history and metrics
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import secrets
import threading
import time
import re
import json
import logging

from app.core.database import get_db
from app.core.security import get_current_user, encrypt_token, decrypt_token
from app.core.config import get_settings
from app.models.user import User
from app.models.social import SocialAccount, Draft, ScheduledPost, PostingHistory, Notification
from app.social.registry import (
    get_provider, get_all_providers, get_supported_platforms,
    platform_credentials_missing,
)
from app.social.base import (
    PlatformType, PostPayload, PostStatus,
    is_demo_account, demo_publish_result, DEMO_ACCOUNT_PREFIX,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/social", tags=["social"])

# OAuth CSRF state store: state -> {"user_id": int, "expires_at": float, "demo": bool}
_oauth_states: dict[str, dict] = {}
_oauth_lock = threading.Lock()
_STATE_TTL_SECONDS = 15 * 60


def _store_oauth_state(state: str, user_id: int, demo: bool = False) -> None:
    with _oauth_lock:
        _oauth_states[state] = {
            "user_id": user_id,
            "expires_at": time.time() + _STATE_TTL_SECONDS,
            "demo": demo,
        }


def _consume_oauth_state(state: str) -> Optional[dict]:
    with _oauth_lock:
        entry = _oauth_states.pop(state, None)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            return None
        return entry


def _ready_account(account: SocialAccount) -> SocialAccount:
    """Decrypt a stored account's token in-place so providers can use it."""
    account.access_token = decrypt_token(account.access_token)
    if getattr(account, "refresh_token", None):
        account.refresh_token = decrypt_token(account.refresh_token)
    return account


def _redirect_uri_for(platform: str, request: Request) -> str:
    """Resolve the OAuth redirect URI for a platform.

    Prefers the platform's configured INSTAGRAM_REDIRECT_URI so the value
    matches what is registered in the Meta app console (required behind
    tunnels/proxies); falls back to deriving it from the incoming request.
    """
    settings = get_settings()
    if platform == "instagram":
        configured = (getattr(settings, "INSTAGRAM_REDIRECT_URI", "") or "").strip()
        if configured:
            return configured
    return str(request.base_url).rstrip("/") + f"/api/social/{platform}/callback"


_REFRESH_MARGIN = timedelta(days=7)


async def _maybe_refresh_token(db: Session, account: SocialAccount) -> None:
    """Silently refresh a soon-to-expire long-lived token on the backend.

    Users never need to trigger refresh manually. Failures are logged and
    ignored — publishing still proceeds with the current token while it is
    valid, and an expired token is rejected by _account_publish_error().
    """
    expires_at = getattr(account, "token_expires_at", None)
    if not expires_at:
        return
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > datetime.now(timezone.utc) + _REFRESH_MARGIN:
        return

    provider = get_provider(PlatformType(account.platform))
    if not provider:
        return

    try:
        token_data = await provider.refresh_token(account)
    except NotImplementedError:
        return  # platform has no refresh support; reconnect flow covers it
    except Exception as e:
        logger.info("Silent token refresh skipped for account %s: %s", account.id, e)
        return

    if token_data.get("access_token"):
        plain = token_data["access_token"]
        account.access_token = encrypt_token(plain)
        if token_data.get("refresh_token"):
            account.refresh_token = encrypt_token(token_data["refresh_token"])
        if token_data.get("expires_in"):
            account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=int(token_data["expires_in"])
            )
        db.commit()
        # Keep the plaintext token on the instance for immediate provider use.
        account.access_token = plain


_INSTAGRAM_PUBLISHABLE_MEDIA = {"image", "video", "reels", "carousel"}


def _instagram_media_error(media_type: str) -> Optional[str]:
    """Friendly error for media types the official Instagram API cannot publish."""
    media_type = (media_type or "").lower()
    if media_type in _INSTAGRAM_PUBLISHABLE_MEDIA or not media_type:
        return None
    return (
        "This file can be analyzed and used to generate content, but it cannot "
        "be directly published to Instagram in its current format."
    )


def _record_publish_event(
    db: Session,
    *,
    user_id: int,
    workflow_type: str,
    content_id=None,
    scheduled_post_id=None,
    payload: dict,
    status: str,
    result: dict = None,
    error_message: str = "",
):
    """Record a completed publish/schedule event and notify n8n (fire-and-forget).

    Never blocks or fails the calling request: n8n is optional automation.
    """
    try:
        from app.api.workflows import create_workflow_job
        from app.services.n8n_client import n8n_enabled, trigger_workflow

        safe_payload = {k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool, type(None)))}
        job = create_workflow_job(
            db,
            user_id=user_id,
            workflow_type=workflow_type,
            content_id=content_id,
            scheduled_post_id=scheduled_post_id,
            payload=safe_payload,
        )

        final_status = "completed" if status == "completed" else ("failed" if status == "failed" else "processing")
        now = datetime.now(timezone.utc)
        job.status = final_status
        job.started_at = now
        if final_status in ("completed", "failed"):
            job.completed_at = now
        if result:
            job.result = result
        if error_message:
            job.error_message = str(error_message)[:2000]
        db.commit()

        if n8n_enabled():
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                loop.create_task(trigger_workflow(job.job_id, workflow_type, {
                    **safe_payload,
                    "status": final_status,
                    "result": result or {},
                }))
    except Exception as e:
        logger.info("Publish event recording skipped: %s", e)


def _account_publish_error(account: SocialAccount) -> Optional[str]:
    """Return a readable error string if an account can't be used to publish.

    Checks token presence and expiry. Returns None when the account is ready.
    """
    if not account.is_active:
        return "Instagram account is disconnected. Reconnect it first."
    if not account.access_token:
        return "No access token stored for this account. Reconnect Instagram."
    expires_at = getattr(account, "token_expires_at", None)
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return "Instagram connection expired. Please reconnect Instagram."
    return None


def _connect_demo_account(db: Session, user_id: int, platform_type: PlatformType, username: str = ""):
    """Create (or update) a simulated demo account for a platform."""
    platform = platform_type.value
    pid = f"{DEMO_ACCOUNT_PREFIX}{platform}"
    clean_username = _sanitize_username(username) or f"demo.{platform}"
    display_names = {
        "instagram": "Demo Instagram Account",
        "facebook": "Demo Facebook Page",
        "linkedin": "Demo LinkedIn Profile",
        "twitter": "Demo X Profile",
        "threads": "Demo Threads Profile",
        "youtube": "Demo YouTube Channel",
    }

    account = db.query(SocialAccount).filter(
        SocialAccount.user_id == user_id,
        SocialAccount.platform == platform,
        SocialAccount.platform_user_id == pid,
    ).first()

    if account is None:
        account = SocialAccount(
            user_id=user_id,
            platform=platform,
            account_type="creator" if platform == "instagram" else "personal",
            platform_user_id=pid,
            username=clean_username,
            display_name=display_names.get(platform, f"Demo {platform} Account"),
            followers_count=1024,
            access_token=encrypt_token(f"demo-token-{platform}"),
            refresh_token=encrypt_token(f"demo-refresh-{platform}"),
            raw_data={"demo": True},
            is_active=True,
        )
        db.add(account)
    else:
        account.is_active = True
        account.username = clean_username
        account.access_token = encrypt_token(f"demo-token-{platform}")
        account.refresh_token = encrypt_token(f"demo-refresh-{platform}")
        account.raw_data = {"demo": True}

    db.commit()
    db.refresh(account)

    db.add(Notification(
        user_id=user_id,
        title=f"{platform.title()} Demo Connected",
        message=f"A demo {platform} account (@{account.username}) has been connected in demo mode. "
                f"Add real API keys to .env to connect your actual account.",
        notification_type="info",
    ))
    db.commit()

    return RedirectResponse(
        url=f"/dashboard?social_connected=true&platform={platform}&demo=true"
    )


def _sanitize_username(username: str) -> str:
    """Keep only safe characters for a demo account username."""
    cleaned = re.sub(r"[^A-Za-z0-9_.]", "", username or "").strip(".")
    return cleaned[:30]


# ─────────────────────────────────────
# Request/response models
# ─────────────────────────────────────

class DraftCreate(BaseModel):
    title: str = ""
    caption: str = ""
    hashtags: str = ""
    emojis: str = ""
    media_path: str = ""
    media_type: str = "image"
    target_platforms: list[str] = []
    notes: str = ""

class DraftUpdate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    emojis: Optional[str] = None
    media_path: Optional[str] = None
    media_type: Optional[str] = None
    target_platforms: Optional[list[str]] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class ScheduleCreate(BaseModel):
    account_id: int
    draft_id: Optional[int] = None
    caption: str = ""
    hashtags: str = ""
    media_path: str = ""
    media_type: str = "image"
    scheduled_at: str  # ISO 8601 datetime string

class PostNow(BaseModel):
    account_id: int
    caption: str = ""
    hashtags: str = ""
    media_path: str = ""
    media_type: str = "image"
    alt_text: str = ""
    location: str = ""


# ─────────────────────────────────────
# Supported Platforms
# ─────────────────────────────────────

@router.get("/platforms")
def list_platforms():
    """Get all supported social media platforms."""
    return {"platforms": get_supported_platforms()}


# ─────────────────────────────────────
# OAuth Flow
# ─────────────────────────────────────

@router.get("/connect/{platform}")
def connect_platform(
    platform: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Start OAuth connection for a platform. Returns a redirect URL."""
    try:
        platform_type = PlatformType(platform)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' not supported")

    provider = get_provider(platform_type)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' not supported")

    missing = platform_credentials_missing(platform_type.value)
    if missing:
        if not get_settings().SOCIAL_DEMO_MODE:
            raise HTTPException(
                status_code=400,
                detail={
                    "platform": platform,
                    "message": (
                        f"{platform_type.value.title()} is not configured yet. "
                        f"Add {', '.join('`' + v + '`' for v in missing)} to the .env file "
                        "and restart the server, then try again."
                    ),
                },
            )
        # Demo mode: credentials are missing, so simulate the OAuth flow by
        # redirecting straight to our own callback with a demo code.
        state = secrets.token_urlsafe(32)
        _store_oauth_state(state, current_user.id, demo=True)
        demo_auth_url = (
            str(request.base_url).rstrip("/")
            + f"/api/social/{platform}/callback?code=demo&state={state}"
        )
        return {
            "auth_url": demo_auth_url,
            "state": state,
            "platform": platform,
            "demo": True,
        }

    state = secrets.token_urlsafe(32)
    _store_oauth_state(state, current_user.id)
    redirect_uri = _redirect_uri_for(platform, request)

    auth_url = provider.get_oauth_url(redirect_uri, state)

    return {"auth_url": auth_url, "state": state, "platform": platform}


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    username: str = "",
    db: Session = Depends(get_db),
):
    """Handle OAuth callback from a social platform and save the connected account."""
    if error:
        return RedirectResponse(url=f"/dashboard?social_error={error}")

    if not code:
        return RedirectResponse(url="/dashboard?social_error=no_code")

    entry = _consume_oauth_state(state)
    if not entry:
        return RedirectResponse(url="/dashboard?social_error=invalid_state")

    user_id = entry["user_id"]

    try:
        platform_type = PlatformType(platform)
    except ValueError:
        return RedirectResponse(url="/dashboard?social_error=unknown_platform")

    if entry.get("demo"):
        return _connect_demo_account(db, user_id, platform_type, username)

    provider = get_provider(platform_type)
    if not provider:
        return RedirectResponse(url="/dashboard?social_error=unknown_platform")

    redirect_uri = _redirect_uri_for(platform, request)

    try:
        token_data = await provider.exchange_code(code, redirect_uri)
        account_info = await provider.get_account_info(token_data["access_token"])

        account_type = account_info.get("account_type", "personal")
        platform_user_id = account_info.get("platform_user_id") or token_data.get("platform_user_id", "")

        if not platform_user_id:
            return RedirectResponse(url="/dashboard?social_error=no_profile")

        # Upsert the social account for this user + platform
        account = db.query(SocialAccount).filter(
            SocialAccount.user_id == user_id,
            SocialAccount.platform == platform_type.value,
            SocialAccount.platform_user_id == platform_user_id,
        ).first()

        expires_at = None
        if token_data.get("expires_in"):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token_data["expires_in"]))

        if account is None:
            account = SocialAccount(
                user_id=user_id,
                platform=platform_type.value,
                account_type=account_type,
                platform_user_id=platform_user_id,
                username=account_info.get("username", platform_user_id),
                display_name=account_info.get("display_name", ""),
                profile_picture_url=account_info.get("profile_picture_url", ""),
                followers_count=account_info.get("followers_count", 0) or 0,
                access_token=encrypt_token(token_data["access_token"]),
                refresh_token=encrypt_token(token_data.get("refresh_token", "")),
                token_expires_at=expires_at,
                raw_data={"bio": account_info.get("bio", "")},
                is_active=True,
            )
            db.add(account)
        else:
            account.is_active = True
            account.account_type = account_type
            account.username = account_info.get("username", account.username)
            account.display_name = account_info.get("display_name", account.display_name)
            account.profile_picture_url = account_info.get("profile_picture_url", account.profile_picture_url)
            account.followers_count = account_info.get("followers_count", account.followers_count) or 0
            account.access_token = encrypt_token(token_data["access_token"])
            account.refresh_token = encrypt_token(token_data.get("refresh_token", "")) if token_data.get("refresh_token") else account.refresh_token
            account.token_expires_at = expires_at

        db.commit()
        db.refresh(account)

        db.add(Notification(
            user_id=user_id,
            title=f"{platform_type.value.title()} Connected",
            message=f"Your {platform_type.value} account @{account.username} has been connected.",
            notification_type="success",
        ))
        db.commit()

        return RedirectResponse(url=f"/dashboard?social_connected=true&platform={platform}")

    except Exception as e:
        logger.error("OAuth callback failed for %s: %s", platform, e)
        return RedirectResponse(url=f"/dashboard?social_error={str(e)}")


# ─────────────────────────────────────
# Social Accounts Management
# ─────────────────────────────────────

@router.get("/accounts")
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all connected social accounts for the current user."""
    accounts = db.query(SocialAccount).filter(
        SocialAccount.user_id == current_user.id,
        SocialAccount.is_active == True,
    ).all()

    result = []
    for acc in accounts:
        provider = get_provider(PlatformType(acc.platform))
        supports_publishing = False
        if provider:
            supports_publishing = provider.supports_publishing(acc.account_type)
        if is_demo_account(acc):
            supports_publishing = True

        result.append({
            "id": acc.id,
            "platform": acc.platform,
            "account_type": acc.account_type,
            "platform_user_id": acc.platform_user_id if not is_demo_account(acc) else "",
            "username": acc.username,
            "display_name": acc.display_name,
            "profile_picture_url": acc.profile_picture_url,
            "followers_count": acc.followers_count,
            "supports_publishing": supports_publishing,
            "is_active": acc.is_active,
            "token_expires_at": acc.token_expires_at.isoformat() if acc.token_expires_at else None,
            "profile_url": provider.profile_url if provider and hasattr(provider, "profile_url") else None,
            "connected_at": acc.created_at.isoformat() if acc.created_at else None,
            "is_demo": is_demo_account(acc),
        })

    return {"accounts": result}


@router.delete("/accounts/{account_id}")
async def disconnect_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect a social account."""
    account = db.query(SocialAccount).filter(
        SocialAccount.id == account_id,
        SocialAccount.user_id == current_user.id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Best-effort server-side revoke so Meta stops honoring the token.
    try:
        provider = get_provider(PlatformType(account.platform))
        if provider:
            _ready_account(account)
            await provider.disconnect(account)
    except Exception as e:
        logger.info("Token revoke on disconnect skipped for account %s: %s", account.id, e)

    account.is_active = False
    # Invalidate stored credentials immediately; reconnect issues new ones.
    account.access_token = None
    account.refresh_token = None
    account.token_expires_at = None
    db.commit()

    # Notify
    db.add(Notification(
        user_id=current_user.id,
        title="Account Disconnected",
        message=f"Your {account.platform} account (@{account.username}) has been disconnected.",
        notification_type="info",
    ))
    db.commit()

    return {"success": True}


@router.post("/accounts/{account_id}/refresh-token")
async def refresh_account_token(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually refresh an account's OAuth token."""
    account = db.query(SocialAccount).filter(
        SocialAccount.id == account_id,
        SocialAccount.user_id == current_user.id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    provider = get_provider(PlatformType(account.platform))
    if not provider:
        raise HTTPException(status_code=400, detail="Platform provider not available")

    _ready_account(account)

    # Instagram/Facebook/Threads use long-lived token exchange; others use refresh tokens
    try:
        try:
            token_data = await provider.refresh_token(account)
        except NotImplementedError:
            return {"message": "No refresh support for this platform; re-connect the account"}

        account.access_token = encrypt_token(token_data["access_token"])
        if token_data.get("refresh_token"):
            account.refresh_token = encrypt_token(token_data["refresh_token"])

        if "expires_in" in token_data:
            account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token_data["expires_in"]))

        db.commit()
        return {"success": True, "message": "Token refreshed"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token refresh failed: {e}")


@router.get("/accounts/{account_id}/status")
def account_status(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current connection status for an account."""
    account = db.query(SocialAccount).filter(
        SocialAccount.id == account_id,
        SocialAccount.user_id == current_user.id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    provider = get_provider(PlatformType(account.platform))
    status = provider.status(account) if provider else {
        "connected": account.is_active,
        "token_valid": bool(account.access_token),
        "platform": account.platform,
    }
    status["account_id"] = account.id
    return status


# ─────────────────────────────────────
# Drafts
# ─────────────────────────────────────

@router.post("/drafts")
def create_draft(
    data: DraftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a new draft."""
    draft = Draft(
        user_id=current_user.id,
        title=data.title,
        caption=data.caption,
        hashtags=data.hashtags,
        emojis=data.emojis,
        media_path=data.media_path,
        media_type=data.media_type,
        target_platforms=data.target_platforms,
        notes=data.notes,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return {
        "id": draft.id,
        "message": "Draft saved",
        "created_at": draft.created_at.isoformat(),
    }


@router.get("/drafts")
def list_drafts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all drafts for the current user."""
    drafts = db.query(Draft).filter(
        Draft.user_id == current_user.id,
    ).order_by(Draft.created_at.desc()).all()

    return {
        "drafts": [{
            "id": d.id,
            "title": d.title,
            "caption": d.caption[:100] + "..." if len(d.caption or "") > 100 else d.caption,
            "hashtags": d.hashtags,
            "media_path": d.media_path,
            "media_type": d.media_type,
            "target_platforms": d.target_platforms or [],
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        } for d in drafts]
    }


@router.get("/drafts/{draft_id}")
def get_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single draft by ID."""
    draft = db.query(Draft).filter(
        Draft.id == draft_id,
        Draft.user_id == current_user.id,
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {
        "id": draft.id,
        "title": draft.title,
        "caption": draft.caption,
        "long_caption": draft.long_caption,
        "short_caption": draft.short_caption,
        "hashtags": draft.hashtags,
        "emojis": draft.emojis,
        "media_path": draft.media_path,
        "media_type": draft.media_type,
        "target_platforms": draft.target_platforms or [],
        "notes": draft.notes,
        "status": draft.status,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


@router.put("/drafts/{draft_id}")
def update_draft(
    draft_id: int,
    data: DraftUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a draft."""
    draft = db.query(Draft).filter(
        Draft.id == draft_id,
        Draft.user_id == current_user.id,
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(draft, field, value)

    db.commit()
    db.refresh(draft)

    return {"success": True, "message": "Draft updated"}


@router.delete("/drafts/{draft_id}")
def delete_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a draft."""
    draft = db.query(Draft).filter(
        Draft.id == draft_id,
        Draft.user_id == current_user.id,
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    db.delete(draft)
    db.commit()

    return {"success": True, "message": "Draft deleted"}


# ─────────────────────────────────────
# Scheduled Posts
# ─────────────────────────────────────

@router.post("/schedule")
async def schedule_post(
    data: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Schedule a post for future publishing."""
    # Validate account exists and belongs to user
    account = db.query(SocialAccount).filter(
        SocialAccount.id == data.account_id,
        SocialAccount.user_id == current_user.id,
        SocialAccount.is_active == True,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    media_error = (
        _instagram_media_error(data.media_type)
        if account.platform == "instagram" else None
    )
    if media_error:
        raise HTTPException(status_code=400, detail=media_error)

    # Parse scheduled_at
    try:
        scheduled_at = datetime.fromisoformat(data.scheduled_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Schedule time must be in the future")

    # Check account supports publishing (demo accounts simulate publishing)
    provider = get_provider(PlatformType(account.platform))
    if provider and not is_demo_account(account) and not provider.supports_publishing(account.account_type):
        raise HTTPException(
            status_code=400,
            detail=f"{account.account_type.title()} Instagram accounts cannot publish via API. "
                   f"Connect a Business or Creator account, or use personal account fallback features."
        )

    scheduled = ScheduledPost(
        user_id=current_user.id,
        account_id=data.account_id,
        draft_id=data.draft_id,
        caption=data.caption,
        hashtags=data.hashtags,
        media_path=data.media_path,
        media_type=data.media_type,
        scheduled_at=scheduled_at,
    )
    db.add(scheduled)
    db.commit()
    db.refresh(scheduled)

    # Notify
    db.add(Notification(
        user_id=current_user.id,
        title="Post Scheduled",
        message=f"Your post has been scheduled for {scheduled_at.strftime('%Y-%m-%d %H:%M')} UTC.",
        notification_type="success",
    ))
    db.commit()

    # Optional n8n scheduling automation: n8n waits until the scheduled time
    # and calls back the secure backend, which re-validates ownership and runs
    # the real publish. If n8n is disabled or unreachable the built-in local
    # scheduler publishes the post instead (single-execution is guaranteed by
    # the scheduled->publishing status transition).
    n8n_dispatched = False
    try:
        from app.api.workflows import create_workflow_job
        from app.services.n8n_client import n8n_enabled, trigger_workflow

        if n8n_enabled():
            job = create_workflow_job(
                db,
                user_id=current_user.id,
                workflow_type="publish",
                scheduled_post_id=scheduled.id,
                payload={
                    "platform": account.platform,
                    "scheduled_at": scheduled_at.isoformat(),
                    "media_type": data.media_type,
                },
            )
            dispatched = await trigger_workflow(job.job_id, "publish", {
                "action": "publish_due",
                "scheduled_post_id": scheduled.id,
                "scheduled_at": scheduled_at.isoformat(),
                "platform": account.platform,
            })
            if dispatched:
                job.status = "dispatched"
                job.started_at = datetime.now(timezone.utc)
                db.commit()
                n8n_dispatched = True
            else:
                job.status = "failed"
                job.error_message = "n8n webhook unavailable; local scheduler will publish"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
    except Exception as e:
        logger.info("n8n schedule dispatch skipped for post %s: %s", scheduled.id, e)

    return {
        "id": scheduled.id,
        "message": "Post scheduled",
        "scheduled_at": scheduled_at.isoformat(),
        "automation": "n8n" if n8n_dispatched else "internal",
    }


@router.get("/schedule")
def list_scheduled(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all scheduled posts."""
    posts = db.query(ScheduledPost).filter(
        ScheduledPost.user_id == current_user.id,
    ).order_by(ScheduledPost.scheduled_at.asc()).all()

    return {
        "scheduled_posts": [{
            "id": p.id,
            "account_id": p.account_id,
            "caption": p.caption[:80] + "..." if len(p.caption or "") > 80 else p.caption,
            "media_path": p.media_path,
            "media_type": p.media_type,
            "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
            "status": p.status,
            "platform_post_id": p.platform_post_id,
            "platform_url": p.platform_url,
            "error_message": p.error_message,
        } for p in posts]
    }


@router.delete("/schedule/{post_id}")
def cancel_scheduled(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a scheduled post."""
    post = db.query(ScheduledPost).filter(
        ScheduledPost.id == post_id,
        ScheduledPost.user_id == current_user.id,
    ).first()

    if not post:
        raise HTTPException(status_code=404, detail="Scheduled post not found")

    if post.status not in ("scheduled",):
        raise HTTPException(status_code=400, detail="Only scheduled posts can be cancelled")

    post.status = "cancelled"
    db.commit()

    return {"success": True, "message": "Scheduled post cancelled"}


@router.post("/schedule/{post_id}/publish-now")
async def publish_now(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Immediately publish a scheduled post."""
    post = db.query(ScheduledPost).filter(
        ScheduledPost.id == post_id,
        ScheduledPost.user_id == current_user.id,
    ).first()

    if not post:
        raise HTTPException(status_code=404, detail="Scheduled post not found")

    if post.status != "scheduled":
        raise HTTPException(status_code=400, detail="Post is not in scheduled status")

    account = db.query(SocialAccount).filter(
        SocialAccount.id == post.account_id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Social account does not belong to this user")

    ready_error = _account_publish_error(account)
    if ready_error:
        raise HTTPException(status_code=400, detail=ready_error)

    media_error = (
        _instagram_media_error(post.media_type)
        if account.platform == "instagram" else None
    )
    if media_error:
        raise HTTPException(status_code=400, detail=media_error)

    _ready_account(account)
    await _maybe_refresh_token(db, account)

    # Attempt immediate publish
    try:
        provider = get_provider(PlatformType(account.platform))
        if not provider:
            raise HTTPException(status_code=400, detail="Platform not available")

        payload = PostPayload(
            caption=post.caption,
            media_path=post.media_path,
            media_type=post.media_type,
            hashtags=post.hashtags,
        )

        post.status = "publishing"
        db.commit()

        result = demo_publish_result(account) if is_demo_account(account) else await provider.publish_post(account, payload)

        if result.success:
            post.status = "published"
            post.platform_post_id = result.platform_post_id
            post.platform_url = result.platform_url

            # Add to history
            db.add(PostingHistory(
                user_id=current_user.id,
                account_id=account.id,
                platform_post_id=result.platform_post_id,
                platform_url=result.platform_url,
                caption=post.caption,
                hashtags=post.hashtags,
                media_path=post.media_path,
                media_type=post.media_type,
            ))
        else:
            post.status = "failed"
            post.error_message = result.error_message

        db.commit()
        return {"success": result.success, "message": result.error_message or "Published"}

    except Exception as e:
        post.status = "failed"
        post.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Publish failed: {e}")


@router.post("/post-now")
async def post_now(
    data: PostNow,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish content immediately to a connected account."""
    account = db.query(SocialAccount).filter(
        SocialAccount.id == data.account_id,
        SocialAccount.user_id == current_user.id,
        SocialAccount.is_active == True,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    provider = get_provider(PlatformType(account.platform))
    if not provider:
        raise HTTPException(status_code=400, detail="Platform not available")

    if not is_demo_account(account) and not provider.supports_publishing(account.account_type):
        raise HTTPException(
            status_code=400,
            detail=f"{account.account_type.title()} accounts cannot publish via API. "
                   f"Use the personal account fallback: copy caption and post manually."
        )

    ready_error = _account_publish_error(account)
    if ready_error:
        raise HTTPException(status_code=400, detail=ready_error)

    media_error = (
        _instagram_media_error(data.media_type)
        if account.platform == "instagram" else None
    )
    if media_error:
        raise HTTPException(status_code=400, detail=media_error)

    _ready_account(account)
    await _maybe_refresh_token(db, account)

    payload = PostPayload(
        caption=data.caption,
        media_path=data.media_path,
        media_type=data.media_type,
        hashtags=data.hashtags,
        alt_text=data.alt_text,
        location=data.location,
    )

    result = demo_publish_result(account) if is_demo_account(account) else await provider.publish_post(account, payload)

    if result.success:
        db.add(PostingHistory(
            user_id=current_user.id,
            account_id=account.id,
            platform_post_id=result.platform_post_id,
            platform_url=result.platform_url,
            caption=data.caption,
            hashtags=data.hashtags,
            media_path=data.media_path,
            media_type=data.media_type,
        ))
        db.commit()

    # Optional n8n automation hook (never blocks the response).
    if not is_demo_account(account):
        _record_publish_event(
            db,
            user_id=current_user.id,
            workflow_type="publish",
            payload={
                "platform": account.platform,
                "media_type": data.media_type,
                "success": result.success,
            },
            status="completed" if result.success else "failed",
            result={"platform_post_id": result.platform_post_id or ""},
            error_message=result.error_message or "",
        )

    return {
        "success": result.success,
        "platform_post_id": result.platform_post_id,
        "platform_url": result.platform_url,
        "error_message": result.error_message,
    }


# ─────────────────────────────────────
# Posting History
# ─────────────────────────────────────

@router.get("/history")
def list_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List posting history with engagement metrics."""
    history = db.query(PostingHistory).filter(
        PostingHistory.user_id == current_user.id,
    ).order_by(PostingHistory.posted_at.desc()).limit(50).all()

    account_ids = {h.account_id for h in history}
    accounts = {
        a.id: a for a in db.query(SocialAccount).filter(
            SocialAccount.id.in_(account_ids)
        ).all()
    } if account_ids else {}

    return {
        "history": [{
            "id": h.id,
            "platform": accounts[h.account_id].platform if h.account_id in accounts else "instagram",
            "username": accounts[h.account_id].username if h.account_id in accounts else "",
            "platform_post_id": h.platform_post_id,
            "platform_url": h.platform_url,
            "caption": h.caption[:80] + "..." if len(h.caption or "") > 80 else h.caption,
            "media_path": h.media_path,
            "media_type": h.media_type,
            "posted_at": h.posted_at.isoformat() if h.posted_at else None,
            "likes": h.likes,
            "comments": h.comments,
            "shares": h.shares,
            "impressions": h.impressions,
            "reach": h.reach,
            "status": h.status,
        } for h in history]
    }


@router.get("/history/{history_id}/metrics")
async def get_post_metrics(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch fresh engagement metrics for a post from the platform."""
    history = db.query(PostingHistory).filter(
        PostingHistory.id == history_id,
        PostingHistory.user_id == current_user.id,
    ).first()

    if not history:
        raise HTTPException(status_code=404, detail="Post not found")

    account = db.query(SocialAccount).filter(
        SocialAccount.id == history.account_id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    provider = get_provider(PlatformType(account.platform))
    if not provider:
        raise HTTPException(status_code=400, detail="Platform not available")

    _ready_account(account)
    await _maybe_refresh_token(db, account)

    try:
        metrics = await provider.get_post_metrics(account, history.platform_post_id)

        history.likes = metrics.get("likes", 0)
        history.comments = metrics.get("comments", 0)
        history.shares = metrics.get("shares", 0)
        history.impressions = metrics.get("impressions", 0)
        history.reach = metrics.get("reach", 0)
        history.last_metrics_at = datetime.now(timezone.utc)
        db.commit()

        return {"metrics": metrics}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch metrics: {e}")


# ─────────────────────────────────────
# Notifications
# ─────────────────────────────────────

@router.get("/notifications")
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent notifications."""
    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id,
    ).order_by(Notification.created_at.desc()).limit(50).all()

    return {
        "notifications": [{
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.notification_type,
            "is_read": n.is_read,
            "link": n.link,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        } for n in notifications]
    }


@router.post("/notifications/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"success": True}


# ─────────────────────────────────────
# Personal Account Fallback Features
# ─────────────────────────────────────

@router.get("/fallback/{platform}")
def get_fallback_features(
    platform: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get fallback features available for personal/non-business accounts."""
    try:
        platform_type = PlatformType(platform)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown platform")

    provider = get_provider(platform_type)
    if not provider:
        return {"features": ["copy_caption", "copy_hashtags", "download_media", "open_in_app"]}

    features = provider.get_personal_fallback_features()

    return {"features": features, "platform": platform}


# ─────────────────────────────────────
# Post Preview & Publish workflow
# (Added feature: preview, edit, draft, schedule, publish)
# ─────────────────────────────────────

_EXTRA_KEYS = ("keywords", "hook", "cta", "seo")


class PreviewPublish(BaseModel):
    """Content to publish from the Post Preview page."""
    account_id: int
    caption: str = ""
    hashtags: str = ""
    keywords: str = ""
    hook: str = ""
    cta: str = ""
    seo: str = ""
    media_path: str = ""
    media_type: str = "image"
    alt_text: str = ""


class PreviewDraftCreate(BaseModel):
    post_id: Optional[int] = None
    title: str = ""
    caption: str = ""
    hashtags: str = ""
    emojis: str = ""
    keywords: str = ""
    hook: str = ""
    cta: str = ""
    seo: str = ""
    media_path: str = ""
    media_type: str = "image"


class PreviewDraftUpdate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    emojis: Optional[str] = None
    keywords: Optional[str] = None
    hook: Optional[str] = None
    cta: Optional[str] = None
    seo: Optional[str] = None
    media_path: Optional[str] = None
    media_type: Optional[str] = None


def _pack_draft_extra(keywords: str = "", hook: str = "", cta: str = "", seo: str = "") -> str:
    """Store extra preview fields inside the Draft notes column as JSON."""
    return json.dumps(
        {"keywords": keywords or "", "hook": hook or "", "cta": cta or "", "seo": seo or ""},
        ensure_ascii=False,
    )


def _unpack_draft_extra(draft) -> dict:
    """Read the extra preview fields back out of a Draft's notes column."""
    notes = getattr(draft, "notes", None) or ""
    try:
        parsed = json.loads(notes)
        if isinstance(parsed, dict):
            return {
                "keywords": parsed.get("keywords", ""),
                "hook": parsed.get("hook", ""),
                "cta": parsed.get("cta", ""),
                "seo": parsed.get("seo", ""),
            }
    except (ValueError, TypeError):
        pass
    return {"keywords": "", "hook": "", "cta": "", "seo": ""}


def _is_valid_post_url(url: str) -> bool:
    """Only treat a returned platform URL as viewable when it is a real http(s) link."""
    url = (url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    if "demo_" in url:
        return False
    return True


def _preview_account_dict(account: SocialAccount) -> dict:
    provider = get_provider(PlatformType(account.platform))
    return {
        "id": account.id,
        "platform": account.platform,
        "username": account.username,
        "display_name": account.display_name,
        "account_type": account.account_type,
        "is_demo": is_demo_account(account),
        "supports_publishing": is_demo_account(account) or bool(
            provider and provider.supports_publishing(account.account_type)
        ),
    }


@router.get("/preview/{post_id}")
def get_preview(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return generated content, accounts and drafts for the Post Preview page."""
    from app.models.post import Post, GeneratedContent
    from app.api.posts import _gen_dict

    post = db.query(Post).filter(
        Post.id == post_id, Post.user_id == current_user.id
    ).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    gen = db.query(GeneratedContent).filter(GeneratedContent.post_id == post.id).first()
    generated = _gen_dict(gen) if gen else {}

    accounts = db.query(SocialAccount).filter(
        SocialAccount.user_id == current_user.id,
        SocialAccount.is_active == True,
    ).all()

    drafts = db.query(Draft).filter(
        Draft.user_id == current_user.id,
    ).order_by(Draft.created_at.desc()).all()

    return {
        "post": {
            "id": post.id,
            "media_type": post.media_type,
            "media_path": post.media_path,
            "original_text": post.original_text,
        },
        "generated": generated,
        "accounts": [_preview_account_dict(a) for a in accounts],
        "drafts": [{
            "id": d.id,
            "title": d.title,
            "caption": d.caption,
            "hashtags": d.hashtags,
            "emojis": d.emojis,
            "media_path": d.media_path,
            "media_type": d.media_type,
            "post_id": d.post_id,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            **_unpack_draft_extra(d),
        } for d in drafts],
    }


@router.post("/preview/drafts")
def create_preview_draft(
    data: PreviewDraftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save the current preview content as a draft."""
    draft = Draft(
        user_id=current_user.id,
        post_id=data.post_id,
        title=data.title,
        caption=data.caption,
        hashtags=data.hashtags,
        emojis=data.emojis,
        media_path=data.media_path,
        media_type=data.media_type,
        notes=_pack_draft_extra(data.keywords, data.hook, data.cta, data.seo),
        status="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return {"id": draft.id, "message": "Draft saved"}


@router.put("/preview/drafts/{draft_id}")
def update_preview_draft(
    draft_id: int,
    data: PreviewDraftUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a draft saved from the Post Preview page."""
    draft = db.query(Draft).filter(
        Draft.id == draft_id, Draft.user_id == current_user.id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    extras = _unpack_draft_extra(draft)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in _EXTRA_KEYS:
            extras[field] = value or ""
        else:
            setattr(draft, field, value)

    draft.notes = _pack_draft_extra(**extras)
    db.commit()
    return {"success": True, "message": "Draft updated"}


@router.delete("/preview/drafts/{draft_id}")
def delete_preview_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a draft saved from the Post Preview page."""
    draft = db.query(Draft).filter(
        Draft.id == draft_id, Draft.user_id == current_user.id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    db.delete(draft)
    db.commit()
    return {"success": True, "message": "Draft deleted"}


@router.post("/preview/publish")
async def preview_publish(
    data: PreviewPublish,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish now from the Post Preview page and record it in Post History.

    Only returns a viewable post link when the platform returns a real URL;
    otherwise returns a publishing status instead of a broken link.
    """
    account = db.query(SocialAccount).filter(
        SocialAccount.id == data.account_id,
        SocialAccount.user_id == current_user.id,
        SocialAccount.is_active == True,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    provider = get_provider(PlatformType(account.platform))
    if not provider:
        raise HTTPException(status_code=400, detail="Platform not available")

    if not is_demo_account(account) and not provider.supports_publishing(account.account_type):
        raise HTTPException(
            status_code=400,
            detail=f"{account.account_type.title()} accounts cannot publish via API. "
                   f"Connect a Business or Creator account."
        )

    ready_error = _account_publish_error(account)
    if ready_error:
        raise HTTPException(status_code=400, detail=ready_error)

    media_error = (
        _instagram_media_error(data.media_type)
        if account.platform == "instagram" else None
    )
    if media_error:
        raise HTTPException(status_code=400, detail=media_error)

    _ready_account(account)
    await _maybe_refresh_token(db, account)

    payload = PostPayload(
        caption=data.caption,
        media_path=data.media_path,
        media_type=data.media_type,
        hashtags=data.hashtags,
        alt_text=data.alt_text,
    )

    try:
        result = (
            demo_publish_result(account)
            if is_demo_account(account)
            else await provider.publish_post(account, payload)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Publish failed: {e}")

    if not result.success:
        if not is_demo_account(account):
            _record_publish_event(
                db,
                user_id=current_user.id,
                workflow_type="publish",
                payload={"platform": account.platform, "media_type": data.media_type},
                status="failed",
                error_message=result.error_message or "",
            )
        return {
            "success": False,
            "platform": account.platform,
            "platform_post_id": "",
            "view_url": "",
            "demo": is_demo_account(account),
            "status_text": result.error_message or "Publish failed",
        }

    valid_url = _is_valid_post_url(result.platform_url)
    is_demo = is_demo_account(account)

    db.add(PostingHistory(
        user_id=current_user.id,
        account_id=account.id,
        platform_post_id=result.platform_post_id,
        platform_url=result.platform_url if valid_url else "",
        caption=data.caption,
        hashtags=data.hashtags,
        media_path=data.media_path,
        media_type=data.media_type,
    ))
    db.commit()

    if not is_demo:
        _record_publish_event(
            db,
            user_id=current_user.id,
            workflow_type="publish",
            payload={"platform": account.platform, "media_type": data.media_type},
            status="completed",
            result={"platform_post_id": result.platform_post_id or ""},
        )

    return {
        "success": True,
        "platform": account.platform,
        "platform_post_id": result.platform_post_id,
        "view_url": result.platform_url if valid_url else "",
        "demo": is_demo,
        "status_text": (
            ("Published successfully. Instagram Media ID: " + result.platform_post_id)
            if (not is_demo and result.platform_post_id)
            else ("Published successfully" if not is_demo else "Published (demo simulation)")
        ),
    }
