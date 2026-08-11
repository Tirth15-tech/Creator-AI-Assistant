"""
X (Twitter) Provider

Implements the SocialProvider interface for X (Twitter) using OAuth 2.0
Authorization Code flow with PKCE.
OAuth: X OAuth 2.0 (PKCE).
Publish: Twitter API v2 (POST /2/tweets).
"""

import base64
import hashlib
import os
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

OAUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
API_URL = "https://api.twitter.com/2"

# state -> PKCE code_verifier (needed when exchanging the authorization code)
_pkce_states: dict[str, str] = {}


class TwitterProvider(SocialProvider):
    """X (Twitter) provider implementation."""

    @property
    def platform(self) -> PlatformType:
        return PlatformType.TWITTER

    @property
    def name(self) -> str:
        return "X (Twitter) API"

    @staticmethod
    def _generate_pkce() -> tuple[str, str]:
        """Generate a PKCE code_verifier + code_challenge pair."""
        verifier = base64.urlsafe_b64encode(os.urandom(48)).rstrip(b"=").decode("ascii")
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        return verifier, challenge

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate the X OAuth 2.0 authorization URL (with PKCE)."""
        verifier, code_challenge = self._generate_pkce()
        _pkce_states[state] = verifier
        self.last_state = state
        scopes = settings.TWITTER_SCOPES.replace(" ", "%20")
        return (
            f"{OAUTH_URL}"
            f"?response_type=code"
            f"&client_id={settings.TWITTER_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scopes}"
            f"&state={state}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange the authorization code for an access token."""
        verifier = _pkce_states.pop(self.last_state, "")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.TWITTER_CLIENT_ID,
                    "code_verifier": verifier,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": "Basic " + base64.b64encode(
                        f"{settings.TWITTER_CLIENT_ID}:{settings.TWITTER_CLIENT_SECRET}".encode()
                    ).decode(),
                },
            )
            resp.raise_for_status()
            data = resp.json()

            me = await client.get(
                f"{API_URL}/users/me",
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
            me.raise_for_status()
            user = me.json().get("data", {})

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 0),
                "platform_user_id": user.get("id", ""),
                "username": user.get("username", ""),
                "display_name": user.get("name", ""),
            }

    async def get_account_info(self, access_token: str) -> dict:
        """Get the connected X user profile."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{API_URL}/users/me",
                params={"user.fields": "id,name,username,profile_image_url"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "platform_user_id": data.get("id", ""),
                "username": data.get("username", ""),
                "display_name": data.get("name", ""),
                "profile_picture_url": data.get("profile_image_url", "").replace("_normal", ""),
                "followers_count": 0,
                "account_type": "personal",
            }

    async def publish_post(self, account: SocialAccount, payload: PostPayload) -> PublishResult:
        """Publish a tweet. X API v2 supports text (and media upload via v1.1)."""
        if not account.access_token:
            return PublishResult(success=False, error_message="No access token available", error_code="NO_TOKEN")

        text = payload.caption
        if payload.hashtags:
            text = f"{text}\n\n{payload.hashtags}"

        body: dict = {"text": text}

        if payload.media_path:
            media_id = await self._upload_media(account.access_token, payload.media_path)
            if media_id:
                body["media"] = {"media_ids": [media_id]}

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{API_URL}/tweets",
                    json=body,
                    headers={"Authorization": f"Bearer {account.access_token}"},
                )
                resp.raise_for_status()
                tweet = resp.json().get("data", {})
                return PublishResult(
                    success=True,
                    platform_post_id=tweet.get("id", ""),
                    platform_url=f"https://x.com/{account.username or 'i'}/status/{tweet.get('id', '')}",
                )
        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            try:
                error_msg = e.response.json().get("detail", str(e))
            except Exception:
                pass
            return PublishResult(success=False, error_message=error_msg, error_code="HTTP_ERROR")
        except Exception as e:
            logger.error("X publish error: %s", e)
            return PublishResult(success=False, error_message=str(e), error_code="EXCEPTION")

    async def _upload_media(self, access_token: str, media_path: str) -> Optional[str]:
        """Upload media via the legacy Twitter API (requires OAuth 1.0a in production)."""
        try:
            with open(media_path, "rb") as f:
                file_data = f.read()
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    files={"media": file_data},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code == 200:
                    return resp.json().get("media_id_string", "")
        except Exception as e:
            logger.error("X media upload error: %s", e)
        return None

    async def delete_post(self, account: SocialAccount, platform_post_id: str) -> bool:
        """Delete a tweet."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(
                    f"{API_URL}/tweets/{platform_post_id}",
                    headers={"Authorization": f"Bearer {account.access_token}"},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("X delete error: %s", e)
            return False

    async def get_post_metrics(self, account: SocialAccount, platform_post_id: str) -> dict:
        """Get engagement metrics for a tweet."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{API_URL}/tweets/{platform_post_id}",
                    params={"tweet.fields": "public_metrics"},
                    headers={"Authorization": f"Bearer {account.access_token}"},
                )
                resp.raise_for_status()
                m = resp.json().get("data", {}).get("public_metrics", {})
                return {
                    "likes": m.get("like_count", 0),
                    "comments": m.get("reply_count", 0),
                    "shares": m.get("retweet_count", 0),
                    "impressions": m.get("impression_count", 0),
                    "reach": m.get("impression_count", 0),
                }
        except Exception as e:
            logger.error("X metrics error: %s", e)
            return {"likes": 0, "comments": 0, "shares": 0, "impressions": 0, "reach": 0}

    def supports_publishing(self, account_type: str) -> bool:
        """X supports publishing for all account types."""
        return True

    async def refresh_token(self, account: SocialAccount) -> dict:
        """Refresh an expired X access token using the refresh token."""
        if not getattr(account, "refresh_token", None):
            raise NotImplementedError("No refresh token available. Re-connect the account.")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": account.refresh_token,
                    "client_id": settings.TWITTER_CLIENT_ID,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": "Basic " + base64.b64encode(
                        f"{settings.TWITTER_CLIENT_ID}:{settings.TWITTER_CLIENT_SECRET}".encode()
                    ).decode(),
                },
            )
            resp.raise_for_status()
            return resp.json()
