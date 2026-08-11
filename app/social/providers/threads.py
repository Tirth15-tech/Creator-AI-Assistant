"""
Threads Provider

Implements the SocialProvider interface for Threads using the Meta Threads API.
OAuth: Meta (Instagram) login dialog with threads scopes.
Publish: graph.threads.net (POST /{user_id}/threads, then /threads_publish).
"""

import httpx
import logging
from typing import Optional

from app.social.base import (
    SocialProvider, PlatformType,
    PublishResult, PostPayload, SocialAccount,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

THREADS_API_URL = "https://graph.threads.net/v1.0"


class ThreadsProvider(SocialProvider):
    """Threads (Meta) provider implementation."""

    @property
    def platform(self) -> PlatformType:
        return PlatformType.THREADS

    @property
    def name(self) -> str:
        return "Threads API"

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate the Threads OAuth URL via Meta login."""
        scopes = settings.THREADS_SCOPES.replace(",", "%2C")
        return (
            f"https://www.facebook.com/v19.0/dialog/oauth"
            f"?client_id={settings.THREADS_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&scope={scopes}"
            f"&response_type=code"
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange the authorization code for a long-lived Threads token."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{THREADS_API_URL}/oauth/access_token",
                params={
                    "client_id": settings.THREADS_CLIENT_ID,
                    "client_secret": settings.THREADS_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            short_token = data["access_token"]

            # Long-lived token (60 days)
            resp = await client.get(
                f"{THREADS_API_URL}/refresh_access_token",
                params={
                    "grant_type": "th_refresh_token",
                    "access_token": short_token,
                },
            )
            resp.raise_for_status()
            long_data = resp.json()
            long_token = long_data["access_token"]

            me = await client.get(
                f"{THREADS_API_URL}/me",
                params={
                    "fields": "id,username,name,threads_profile_picture_url",
                    "access_token": long_token,
                },
            )
            me.raise_for_status()
            profile = me.json()

            return {
                "access_token": long_token,
                "short_lived_token": short_token,
                "expires_in": long_data.get("expires_in", 0),
                "platform_user_id": profile.get("id", ""),
                "username": profile.get("username", ""),
                "display_name": profile.get("name", ""),
                "profile_picture_url": profile.get("threads_profile_picture_url", ""),
            }

    async def get_account_info(self, access_token: str) -> dict:
        """Get the connected Threads user profile."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{THREADS_API_URL}/me",
                params={
                    "fields": "id,username,name,threads_profile_picture_url,followers_count",
                    "access_token": access_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "platform_user_id": data.get("id", ""),
                "username": data.get("username", ""),
                "display_name": data.get("name", ""),
                "profile_picture_url": data.get("threads_profile_picture_url", ""),
                "followers_count": data.get("followers_count", 0),
                "account_type": "personal",
            }

    async def publish_post(self, account: SocialAccount, payload: PostPayload) -> PublishResult:
        """Publish a Thread (text, image or video)."""
        if not account.access_token:
            return PublishResult(success=False, error_message="No access token available", error_code="NO_TOKEN")

        user_id = account.platform_user_id
        token = account.access_token

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                params = {"access_token": token}
                text = payload.caption
                if payload.hashtags:
                    text = f"{text}\n\n{payload.hashtags}"

                if payload.media_type == "video" and payload.media_path:
                    params["media_type"] = "VIDEO"
                    params["video_url"] = payload.media_path
                    params["text"] = text
                elif payload.media_path:
                    params["media_type"] = "IMAGE"
                    params["image_url"] = payload.media_path
                    params["text"] = text
                else:
                    params["media_type"] = "TEXT"
                    params["text"] = text

                container_resp = await client.post(
                    f"{THREADS_API_URL}/{user_id}/threads",
                    data=params,
                )
                container_resp.raise_for_status()
                container_id = container_resp.json().get("id")
                if not container_id:
                    return PublishResult(success=False, error_message="Failed to create thread container")

                # Wait for processing
                import asyncio
                ready = False
                for _ in range(10):
                    status_resp = await client.get(
                        f"{THREADS_API_URL}/{container_id}",
                        params={"fields": "status", "access_token": token},
                    )
                    if status_resp.status_code == 200 and status_resp.json().get("status") == "FINISHED":
                        ready = True
                        break
                    await asyncio.sleep(2)
                if not ready:
                    return PublishResult(success=False, error_message="Thread media processing timed out")

                publish_resp = await client.post(
                    f"{THREADS_API_URL}/{user_id}/threads_publish",
                    data={"creation_id": container_id, "access_token": token},
                )
                publish_resp.raise_for_status()
                thread_id = publish_resp.json().get("id", "")

                return PublishResult(
                    success=True,
                    platform_post_id=thread_id,
                    platform_url=f"https://www.threads.net/@{account.username or 'i'}/post/{thread_id}",
                )
        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("error", {}).get("message", str(e))
            error_code = error_data.get("error", {}).get("code", "HTTP_ERROR")
            logger.error("Threads publish HTTP error: %s (%s)", error_msg, error_code)
            return PublishResult(success=False, error_message=error_msg, error_code=error_code)
        except Exception as e:
            logger.error("Threads publish error: %s", e)
            return PublishResult(success=False, error_message=str(e), error_code="EXCEPTION")

    async def delete_post(self, account: SocialAccount, platform_post_id: str) -> bool:
        """Delete a Thread."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(
                    f"{THREADS_API_URL}/{platform_post_id}",
                    params={"access_token": account.access_token},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Threads delete error: %s", e)
            return False

    async def get_post_metrics(self, account: SocialAccount, platform_post_id: str) -> dict:
        """Get engagement metrics for a Thread."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{THREADS_API_URL}/{platform_post_id}",
                    params={"fields": "like_count,reply_count,permalink", "access_token": account.access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "likes": data.get("like_count", 0),
                    "comments": data.get("reply_count", 0),
                    "shares": 0,
                    "impressions": 0,
                    "reach": 0,
                    "permalink": data.get("permalink", ""),
                }
        except Exception as e:
            logger.error("Threads metrics error: %s", e)
            return {"likes": 0, "comments": 0, "shares": 0, "impressions": 0, "reach": 0}

    def supports_publishing(self, account_type: str) -> bool:
        """Threads supports publishing for all account types."""
        return True

    async def refresh_token(self, account: SocialAccount) -> dict:
        """Refresh the Threads long-lived token."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{THREADS_API_URL}/refresh_access_token",
                params={
                    "grant_type": "th_refresh_token",
                    "access_token": account.access_token,
                },
            )
            resp.raise_for_status()
            return resp.json()
