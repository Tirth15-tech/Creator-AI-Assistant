"""
YouTube Provider

Implements the SocialProvider interface for YouTube using Google OAuth 2.0.
OAuth: Google OAuth 2.0.
Publish: YouTube Data API v3 (videos.insert).
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

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_API_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeProvider(SocialProvider):
    """YouTube provider implementation (Google OAuth)."""

    @property
    def platform(self) -> PlatformType:
        return PlatformType.YOUTUBE

    @property
    def name(self) -> str:
        return "YouTube Data API"

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate the Google OAuth authorization URL for YouTube."""
        scope = settings.YOUTUBE_SCOPES.replace(" ", "%20")
        return (
            f"{GOOGLE_AUTH_URL}"
            f"?response_type=code"
            f"&client_id={settings.YOUTUBE_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scope}"
            f"&state={state}"
            f"&access_type=offline"
            f"&prompt=consent"
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange the authorization code for an access token (+ refresh token)."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.YOUTUBE_CLIENT_ID,
                    "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            channel = await self.get_account_info(data["access_token"])
            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 0),
                "platform_user_id": channel.get("platform_user_id", ""),
                "username": channel.get("username", ""),
                "display_name": channel.get("display_name", ""),
                "profile_picture_url": channel.get("profile_picture_url", ""),
                "followers_count": channel.get("followers_count", 0),
            }

    async def get_account_info(self, access_token: str) -> dict:
        """Get the connected YouTube channel (via mine=true)."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{YT_API_URL}/channels",
                params={
                    "part": "snippet,statistics",
                    "mine": "true",
                    "access_token": access_token,
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return {
                    "platform_user_id": "",
                    "username": "",
                    "display_name": "",
                    "profile_picture_url": "",
                    "followers_count": 0,
                    "account_type": "personal",
                }
            ch = items[0]
            snippet = ch.get("snippet", {})
            return {
                "platform_user_id": ch.get("id", ""),
                "username": snippet.get("customUrl", "").lstrip("@"),
                "display_name": snippet.get("title", ""),
                "profile_picture_url": (snippet.get("thumbnails", {}).get("default", {}) or {}).get("url", ""),
                "followers_count": int(ch.get("statistics", {}).get("subscriberCount", 0)),
                "account_type": "personal",
            }

    async def publish_post(self, account: SocialAccount, payload: PostPayload) -> PublishResult:
        """Upload a video to YouTube. Community text posts are not supported by the API."""
        if not account.access_token:
            return PublishResult(success=False, error_message="No access token available", error_code="NO_TOKEN")

        if payload.media_type != "video":
            return PublishResult(
                success=False,
                error_message="YouTube publishing requires a video file (community text posts are not supported).",
                error_code="MEDIA_TYPE_NOT_SUPPORTED",
            )

        try:
            with open(payload.media_path, "rb") as f:
                media_bytes = f.read()

            async with httpx.AsyncClient(timeout=600) as client:
                headers = {
                    "Authorization": f"Bearer {account.access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                }
                init_body = {
                    "snippet": {
                        "title": (payload.caption or "Untitled")[:100],
                        "description": payload.caption or "",
                    },
                    "status": {"privacyStatus": "public"},
                }
                init_resp = await client.post(
                    f"{YT_API_URL}/videos?part=snippet,status&uploadType=resumable",
                    json=init_body,
                    headers={**headers, "X-Upload-Content-Type": "video/*"},
                )
                init_resp.raise_for_status()

                upload_url = init_resp.headers.get("Location")
                if not upload_url:
                    return PublishResult(success=False, error_message="Could not start resumable upload")

                upload_resp = await client.put(
                    upload_url,
                    content=media_bytes,
                    headers={"Content-Type": "video/*"},
                )
                upload_resp.raise_for_status()
                video_id = upload_resp.json().get("id", "")

                return PublishResult(
                    success=True,
                    platform_post_id=video_id,
                    platform_url=f"https://www.youtube.com/watch?v={video_id}",
                )
        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            try:
                error_msg = e.response.json().get("error", {}).get("message", str(e))
            except Exception:
                pass
            return PublishResult(success=False, error_message=error_msg, error_code="HTTP_ERROR")
        except Exception as e:
            logger.error("YouTube publish error: %s", e)
            return PublishResult(success=False, error_message=str(e), error_code="EXCEPTION")

    async def delete_post(self, account: SocialAccount, platform_post_id: str) -> bool:
        """Delete a YouTube video."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(
                    f"{YT_API_URL}/videos",
                    params={"id": platform_post_id, "access_token": account.access_token},
                )
                return resp.status_code in (200, 204)
        except Exception as e:
            logger.error("YouTube delete error: %s", e)
            return False

    async def get_post_metrics(self, account: SocialAccount, platform_post_id: str) -> dict:
        """Get engagement metrics for a YouTube video."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{YT_API_URL}/videos",
                    params={
                        "part": "statistics",
                        "id": platform_post_id,
                        "access_token": account.access_token,
                    },
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                if not items:
                    return {"likes": 0, "comments": 0, "shares": 0, "impressions": 0, "reach": 0}
                s = items[0].get("statistics", {})
                return {
                    "likes": int(s.get("likeCount", 0)),
                    "comments": int(s.get("commentCount", 0)),
                    "shares": 0,
                    "impressions": 0,
                    "reach": int(s.get("viewCount", 0)),
                }
        except Exception as e:
            logger.error("YouTube metrics error: %s", e)
            return {"likes": 0, "comments": 0, "shares": 0, "impressions": 0, "reach": 0}

    def supports_publishing(self, account_type: str) -> bool:
        """YouTube supports video publishing for all account types."""
        return True

    async def refresh_token(self, account: SocialAccount) -> dict:
        """Refresh the Google access token using the refresh token."""
        if not getattr(account, "refresh_token", None):
            raise NotImplementedError("No refresh token available. Re-connect the account.")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": account.refresh_token,
                    "client_id": settings.YOUTUBE_CLIENT_ID,
                    "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            return resp.json()
