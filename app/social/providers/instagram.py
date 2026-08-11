"""
Phase 3B: Instagram Provider

Implements the SocialProvider interface for Instagram using the
Instagram Graph API (Facebook Login).

Real publishing requires:
- A Facebook App with the "Instagram Graph API" use case enabled
- An Instagram Business or Creator account linked to a Facebook Page
- The `instagram_basic`, `instagram_content_publish` and `pages_show_list`
  scopes (see INSTAGRAM_SCOPES in app/core/config.py)

Personal Instagram accounts cannot publish via any API — they fall back to
manual publishing (copy caption/media and post in the app).
"""

import asyncio
import logging
from typing import Optional

import httpx

from app.social.base import (
    SocialProvider, PlatformType,
    PublishResult, PostPayload, SocialAccount,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

INSTAGRAM_GRAPH_URL = "https://graph.facebook.com"
INSTAGRAM_DIALOG_URL = "https://www.facebook.com/dialog/oauth"

# How long to wait (seconds) for a media container to be ready after
# container creation, before publishing it.
_MEDIA_STATUS_POLL_SECONDS = 5
_MEDIA_STATUS_MAX_ATTEMPTS = 15


def _api_version() -> str:
    return getattr(settings, "INSTAGRAM_API_VERSION", "v22.0").strip() or "v22.0"


def _graph_url(node: str) -> str:
    return f"{INSTAGRAM_GRAPH_URL}/{_api_version()}/{node}"


class InstagramProvider(SocialProvider):
    """Instagram provider using the Instagram Graph API (Facebook Login)."""

    @property
    def platform(self) -> PlatformType:
        return PlatformType.INSTAGRAM

    @property
    def name(self) -> str:
        return "Instagram Graph API"

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate the Facebook Login authorization URL for Instagram."""
        scope = settings.INSTAGRAM_SCOPES.replace(" ", "").replace(",", ",")
        return (
            f"{INSTAGRAM_DIALOG_URL}"
            f"?client_id={settings.INSTAGRAM_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scope}"
            f"&response_type=code"
            f"&state={state}"
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange the authorization code for a long-lived access token.

        Flow:
        1. POST graph.facebook.com/.../oauth/access_token (short-lived token)
        2. Exchange the short-lived token for a long-lived token (60 days)
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _graph_url("oauth/access_token"),
                data={
                    "client_id": settings.INSTAGRAM_CLIENT_ID,
                    "client_secret": settings.INSTAGRAM_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            _raise_graph_error(resp, "token exchange")
            data = resp.json()
            short_token = data["access_token"]

            long_resp = await client.get(
                _graph_url("oauth/access_token"),
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.INSTAGRAM_CLIENT_ID,
                    "client_secret": settings.INSTAGRAM_CLIENT_SECRET,
                    "fb_exchange_token": short_token,
                },
            )
            _raise_graph_error(long_resp, "long-lived token exchange")
            long_data = long_resp.json()
            long_token = long_data.get("access_token", short_token)

            return {
                "access_token": long_token,
                "short_lived_token": short_token,
                "expires_in": long_data.get("expires_in", 0),
                "platform_user_id": "",
            }

    async def get_account_info(self, access_token: str) -> dict:
        """Get the connected Instagram Business/Creator account information."""
        async with httpx.AsyncClient(timeout=15) as client:
            # 1. Find the Facebook Pages that expose an Instagram business account.
            pages_resp = await client.get(
                _graph_url("me/accounts"),
                params={
                    "fields": "name,instagram_business_account{id,username,media_count,followers_count,account_type}",
                    "access_token": access_token,
                },
            )
            _raise_graph_error(pages_resp, "listing pages")
            pages_data = pages_resp.json()

            ig_account = None
            for page in pages_data.get("data", []):
                ig = page.get("instagram_business_account") or {}
                if ig.get("id"):
                    ig_account = ig
                    break

            if not ig_account:
                raise RuntimeError(
                    "No Instagram Business/Creator account found. Link an "
                    "Instagram account to a Facebook Page in Facebook Business "
                    "Settings, then reconnect."
                )

            return {
                "platform_user_id": str(ig_account.get("id", "")),
                "username": ig_account.get("username", ""),
                "display_name": ig_account.get("username", ""),
                "profile_picture_url": "",
                "followers_count": int(ig_account.get("followers_count", 0) or 0),
                "media_count": int(ig_account.get("media_count", 0) or 0),
                "account_type": (ig_account.get("account_type") or "business").lower(),
                "bio": "",
            }

    async def publish_post(self, account: SocialAccount, payload: PostPayload) -> PublishResult:
        """Publish an image, video or carousel post via the Graph API."""
        token = account.access_token
        if not token:
            return PublishResult(success=False, error_message="No access token on account.")

        ig_user_id = str(getattr(account, "platform_user_id", "") or "")
        if not ig_user_id:
            return PublishResult(success=False, error_message="No Instagram account id on record.")

        caption = _build_caption(payload.caption, payload.hashtags)

        try:
            media_type = (payload.media_type or "image").lower()
            if not (payload.media_path or payload.carousel_media):
                return PublishResult(
                    success=False,
                    error_message=(
                        "Instagram posts require an image or video. Attach media "
                        "to the post before publishing."
                    ),
                )

            # Refuse to call the Instagram API unless the media is reachable
            # from Instagram's servers (public HTTPS URL, not localhost).
            urls_to_check = [payload.media_path] + list(payload.carousel_media or [])
            check_kind = "video" if media_type in ("video", "reels") else "image"
            for path in urls_to_check:
                if not path:
                    continue
                url = _media_url(path)
                error = await self._validate_public_media_url(url, check_kind)
                if error:
                    return PublishResult(success=False, error_message=error)

            if media_type in ("video", "reels"):
                creation_id = await self._create_video_container(ig_user_id, payload, caption, token)
            elif media_type in ("carousel", "multiple", "album"):
                creation_id = await self._create_carousel_container(ig_user_id, payload, caption, token)
            else:
                creation_id = await self._create_image_container(ig_user_id, payload, caption, token)

            if not creation_id:
                return PublishResult(
                    success=False,
                    error_message="Could not create the media container on Instagram.",
                )

            await self._wait_media_ready(creation_id, token)

            media_id = await self._publish_container(ig_user_id, creation_id, token)
            if not media_id:
                return PublishResult(
                    success=False,
                    error_message="Instagram did not return a media ID after publishing.",
                )

            permalink = await self._fetch_permalink(media_id, token)

            return PublishResult(
                success=True,
                platform_post_id=str(media_id),
                platform_url=permalink,
            )
        except Exception as e:
            logger.error("Instagram publish failed: %s", e)
            return PublishResult(success=False, error_message=str(e))

    async def delete_post(self, account: SocialAccount, platform_post_id: str) -> bool:
        """Deleting posts requires the marketing/ads API; unsupported."""
        return False

    async def get_post_metrics(self, account: SocialAccount, platform_post_id: str) -> dict:
        """Instagram Graph API does not expose per-post metrics with these scopes."""
        return {"likes": 0, "comments": 0, "shares": 0, "impressions": 0, "reach": 0}

    def supports_publishing(self, account_type: str) -> bool:
        """Business and Creator accounts support publishing; Personal do not."""
        return (account_type or "").lower() in ("business", "creator")

    def get_personal_fallback_features(self) -> list[str]:
        """Features available for Instagram personal accounts (no API publishing)."""
        return [
            "copy_caption",
            "copy_hashtags",
            "download_media",
            "open_in_app",
            "qr_code_share",
        ]

    # ─────────────────────────────────────────
    # Graph API helpers
    # ─────────────────────────────────────────

    async def _create_image_container(self, ig_user_id: str, payload: PostPayload, caption: str, token: str) -> str:
        media_url = _media_url(payload.media_path)
        return await self._create_container(ig_user_id, {
            "media_type": "IMAGE",
            "image_url": media_url,
            "caption": caption,
            "access_token": token,
        })

    async def _create_video_container(self, ig_user_id: str, payload: PostPayload, caption: str, token: str) -> str:
        media_url = _media_url(payload.media_path)
        media_type = "REELS" if (payload.media_type or "").lower() == "reels" else "VIDEO"
        return await self._create_container(ig_user_id, {
            "media_type": media_type,
            "video_url": media_url,
            "caption": caption,
            "access_token": token,
        })

    async def _create_carousel_container(self, ig_user_id: str, payload: PostPayload, caption: str, token: str) -> str:
        children = []
        for url in _carousel_urls(payload):
            child_id = await self._create_container(ig_user_id, {
                "media_type": "IMAGE",
                "image_url": url,
                "access_token": token,
            })
            if not child_id:
                return ""
            children.append(child_id)
        if not children:
            return ""
        return await self._create_container(ig_user_id, {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": token,
        })

    async def _create_container(self, ig_user_id: str, data: dict) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(_graph_url(f"{ig_user_id}/media"), data=data)
            _raise_graph_error(resp, "creating media container")
            return str(resp.json().get("id", ""))

    async def _wait_media_ready(self, creation_id: str, token: str) -> None:
        """Poll the container directly until its status_code is FINISHED.

        Raises a RuntimeError on ERROR/EXPIRED status or after the poll window
        so we never publish a container Instagram hasn't finished processing.
        """
        last_status = ""
        for _ in range(_MEDIA_STATUS_MAX_ATTEMPTS):
            await asyncio.sleep(_MEDIA_STATUS_POLL_SECONDS)
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _graph_url(str(creation_id)),
                    params={"fields": "status_code", "access_token": token},
                )
                _raise_graph_error(resp, "checking media status")
                status = (resp.json().get("status_code") or "").upper()
                last_status = status
                if status in ("FINISHED", "PUBLISHED"):
                    return
                if status in ("ERROR", "EXPIRED"):
                    raise RuntimeError(
                        f"Instagram failed to process the media container (status: {status})."
                    )
        raise RuntimeError(
            f"Instagram is still processing the media (last status: {last_status or 'unknown'}). "
            "Try again in a moment."
        )

    async def _publish_container(self, ig_user_id: str, creation_id: str, token: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _graph_url(f"{ig_user_id}/media_publish"),
                data={"creation_id": creation_id, "access_token": token},
            )
            _raise_graph_error(resp, "publishing media")
            return str(resp.json().get("id", ""))

    async def _fetch_permalink(self, media_id: str, token: str) -> str:
        """Fetch the real permalink for a published media ID from the API.

        Returns "" when Instagram has no permalink yet; callers must then show
        the media ID instead of a guessed URL.
        """
        for _ in range(5):
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _graph_url(str(media_id)),
                    params={"fields": "permalink", "access_token": token},
                )
                if resp.status_code < 400:
                    permalink = (resp.json().get("permalink") or "").strip()
                    if permalink:
                        return str(permalink)
            await asyncio.sleep(2)
        return ""

    async def _validate_public_media_url(self, url: str, kind: str) -> Optional[str]:
        """Return an error string if a media URL is not publicly reachable."""
        base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
        if not base:
            return "PUBLIC_BASE_URL is not configured in .env. Set it to a public HTTPS URL."
        if "localhost" in base or "127.0.0.1" in base:
            return (
                "Media URL is not publicly accessible. Start the configured HTTPS "
                "tunnel or deploy the application."
            )
        if not url.startswith("https://"):
            return "Media URL must be HTTPS so Instagram can fetch it."
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url)
        except Exception as e:
            return (
                f"Media URL is not publicly accessible ({e}). "
                "Start the configured HTTPS tunnel or deploy the application."
            )
        if resp.status_code != 200:
            return (
                f"Media URL is not publicly accessible (HTTP {resp.status_code}). "
                "Start the configured HTTPS tunnel or deploy the application."
            )
        content_type = (resp.headers.get("content-type") or "").lower()
        if kind == "image" and "image/" not in content_type:
            return f"Media URL did not return an image (content-type: {content_type or 'unknown'})."
        if kind == "video" and "video/" not in content_type:
            return f"Media URL did not return a video (content-type: {content_type or 'unknown'})."
        return None


# ─────────────────────────────────────────
# Module helpers
# ─────────────────────────────────────────

def _raise_graph_error(resp: httpx.Response, action: str) -> None:
    """Raise a readable error for a failed Graph API call."""
    if resp.status_code < 400:
        return
    try:
        body = resp.json()
        error = body.get("error", body)
        message = error.get("message") or str(body)
        code = error.get("code", "")
    except Exception:
        message = resp.text or resp.reason_phrase or "unknown error"
        code = ""
    raise RuntimeError(f"Instagram API {action} failed (HTTP {resp.status_code}{f' code {code}' if code else ''}): {message}")


def _build_caption(caption: str, hashtags: str) -> str:
    parts = [c for c in (caption, hashtags) if c and c.strip()]
    return "\n\n".join(parts) if parts else ""


def _media_url(media_path: str) -> str:
    """Build an absolute, publicly reachable URL for a media path."""
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    path = (media_path or "").lstrip("/")
    return f"{base}/{path}"


def _carousel_urls(payload: PostPayload) -> list:
    urls = [m for m in (payload.carousel_media or []) if m]
    if not urls and payload.media_path:
        urls = [payload.media_path]
    return [_media_url(u) for u in urls]
