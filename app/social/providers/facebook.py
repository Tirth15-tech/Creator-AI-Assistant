"""
Facebook Graph API Provider

Implements the SocialProvider interface for Facebook Pages.
OAuth: Meta (Facebook) Login dialog.
Publish: Page feed (text), photos, videos.
"""

import httpx
import logging
from typing import Optional

from app.social.base import (
    SocialProvider, PlatformType, AccountType,
    PublishResult, PostPayload, SocialAccount,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GRAPH_API_URL = "https://graph.facebook.com/v19.0"


class FacebookProvider(SocialProvider):
    """Facebook Pages provider implementation."""

    @property
    def platform(self) -> PlatformType:
        return PlatformType.FACEBOOK

    @property
    def name(self) -> str:
        return "Facebook Graph API"

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate the Facebook OAuth authorization URL."""
        scopes = settings.FACEBOOK_SCOPES.replace(",", "%2C")
        return (
            f"https://www.facebook.com/v19.0/dialog/oauth"
            f"?client_id={settings.FACEBOOK_APP_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&scope={scopes}"
            f"&response_type=code"
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange the authorization code for a long-lived user token."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GRAPH_API_URL}/oauth/access_token",
                params={
                    "client_id": settings.FACEBOOK_APP_ID,
                    "client_secret": settings.FACEBOOK_APP_SECRET,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            short_token = resp.json()["access_token"]

            resp = await client.get(
                f"{GRAPH_API_URL}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.FACEBOOK_APP_ID,
                    "client_secret": settings.FACEBOOK_APP_SECRET,
                    "fb_exchange_token": short_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            long_token = data["access_token"]

            resp = await client.get(
                f"{GRAPH_API_URL}/me",
                params={
                    "fields": "id,name",
                    "access_token": long_token,
                },
            )
            resp.raise_for_status()
            me = resp.json()

            return {
                "access_token": long_token,
                "short_lived_token": short_token,
                "expires_in": data.get("expires_in", 0),
                "platform_user_id": me.get("id", ""),
                "username": me.get("name", ""),
            }

    async def get_account_info(self, access_token: str) -> dict:
        """Get the connected Facebook user/profile information."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{GRAPH_API_URL}/me",
                params={
                    "fields": "id,name,picture.type(large)",
                    "access_token": access_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            picture = data.get("picture", {}).get("data", {}).get("url", "")
            return {
                "platform_user_id": data.get("id", ""),
                "username": data.get("name", ""),
                "display_name": data.get("name", ""),
                "profile_picture_url": picture,
                "followers_count": 0,
                "account_type": "business",
            }

    async def publish_post(self, account: SocialAccount, payload: PostPayload) -> PublishResult:
        """Publish a post to the connected Facebook page."""
        if not account.access_token:
            return PublishResult(success=False, error_message="No access token available", error_code="NO_TOKEN")

        page_id = account.platform_user_id
        token = account.access_token

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # Resolve a page-scoped token for the target page if needed.
                token = await self._resolve_page_token(client, page_id, token)

                if payload.media_type == "video":
                    resp = await client.post(
                        f"{GRAPH_API_URL}/{page_id}/videos",
                        data={"url": payload.media_path, "access_token": token},
                    )
                elif payload.media_type == "image" and payload.media_path:
                    resp = await client.post(
                        f"{GRAPH_API_URL}/{page_id}/photos",
                        data={"url": payload.media_path, "access_token": token},
                    )
                else:
                    message = payload.caption
                    if payload.hashtags:
                        message = f"{message}\n\n{payload.hashtags}"
                    resp = await client.post(
                        f"{GRAPH_API_URL}/{page_id}/feed",
                        data={"message": message, "access_token": token},
                    )

                resp.raise_for_status()
                post_id = resp.json().get("id", "")

                return PublishResult(
                    success=True,
                    platform_post_id=post_id,
                    platform_url=f"https://www.facebook.com/{post_id}",
                )
        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("error", {}).get("message", str(e))
            error_code = error_data.get("error", {}).get("code", "HTTP_ERROR")
            logger.error("Facebook publish HTTP error: %s (%s)", error_msg, error_code)
            return PublishResult(success=False, error_message=error_msg, error_code=error_code)
        except Exception as e:
            logger.error("Facebook publish error: %s", e)
            return PublishResult(success=False, error_message=str(e), error_code="EXCEPTION")

    async def _resolve_page_token(self, client: httpx.AsyncClient, page_id: str, token: str) -> str:
        """Get a page-scoped access token for the given page, falling back to the user token."""
        try:
            resp = await client.get(
                f"{GRAPH_API_URL}/{page_id}",
                params={"fields": "access_token", "access_token": token},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("access_token"):
                    return data["access_token"]
        except Exception as e:
            logger.debug("Could not resolve page token for %s: %s", page_id, e)
        return token

    async def delete_post(self, account: SocialAccount, platform_post_id: str) -> bool:
        """Delete a Facebook post."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(
                    f"{GRAPH_API_URL}/{platform_post_id}",
                    params={"access_token": account.access_token},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Facebook delete error: %s", e)
            return False

    async def get_post_metrics(self, account: SocialAccount, platform_post_id: str) -> dict:
        """Get engagement metrics for a Facebook post."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{GRAPH_API_URL}/{platform_post_id}",
                    params={
                        "fields": "reactions.summary(true),comments.summary(true),shares,permalink_url",
                        "access_token": account.access_token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "likes": (data.get("reactions", {}).get("summary", {}) or {}).get("total_count", 0),
                    "comments": (data.get("comments", {}).get("summary", {}) or {}).get("total_count", 0),
                    "shares": (data.get("shares", {}) or {}).get("count", 0),
                    "impressions": 0,
                    "reach": 0,
                    "permalink": data.get("permalink_url", ""),
                }
        except Exception as e:
            logger.error("Facebook metrics error: %s", e)
            return {"likes": 0, "comments": 0, "shares": 0, "impressions": 0, "reach": 0}

    def supports_publishing(self, account_type: str) -> bool:
        """Facebook pages support direct publishing."""
        return True

    async def refresh_token(self, account: SocialAccount) -> dict:
        """Exchange a short-lived token for a long-lived one (60 days)."""
        async with httpx.AsyncClient(timeout=30) as client:
            token = decrypt_local(account.access_token)
            resp = await client.get(
                f"{GRAPH_API_URL}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.FACEBOOK_APP_ID,
                    "client_secret": settings.FACEBOOK_APP_SECRET,
                    "fb_exchange_token": token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "access_token": data["access_token"],
                "expires_in": data.get("expires_in", 0),
            }


def decrypt_local(token: str) -> str:
    """Decrypt a stored token (imported lazily to avoid a circular import)."""
    from app.core.security import decrypt_token
    return decrypt_token(token)
