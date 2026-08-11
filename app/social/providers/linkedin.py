"""
LinkedIn Provider

Implements the SocialProvider interface for LinkedIn using LinkedIn OAuth 2.0.
OAuth: LinkedIn OAuth 2.0 (Microsoft Entra).
Publish: UGC Posts API (v2/ugcPosts).
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

API_BASE = "https://api.linkedin.com"
OAUTH_URL = "https://www.linkedin.com/oauth/v2"
OPENID_API = "https://api.linkedin.com/v2/userinfo"


class LinkedInProvider(SocialProvider):
    """LinkedIn provider implementation."""

    @property
    def platform(self) -> PlatformType:
        return PlatformType.LINKEDIN

    @property
    def name(self) -> str:
        return "LinkedIn API"

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate the LinkedIn OAuth 2.0 authorization URL."""
        scopes = settings.LINKEDIN_SCOPES.replace(" ", "%20")
        return (
            f"{OAUTH_URL}/authorization"
            f"?response_type=code"
            f"&client_id={settings.LINKEDIN_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&scope={scopes}"
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange the authorization code for an access token."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{OAUTH_URL}/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.LINKEDIN_CLIENT_ID,
                    "client_secret": settings.LINKEDIN_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

            me = await client.get(
                OPENID_API,
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
            me.raise_for_status()
            profile = me.json()

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 0),
                "platform_user_id": profile.get("sub", ""),
                "username": profile.get("preferred_username", profile.get("sub", "")),
                "display_name": " ".join(filter(None, [profile.get("given_name", ""), profile.get("family_name", "")])),
                "profile_picture_url": profile.get("picture", ""),
            }

    async def get_account_info(self, access_token: str) -> dict:
        """Get the connected LinkedIn profile information."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                OPENID_API,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "platform_user_id": data.get("sub", ""),
                "username": data.get("preferred_username", data.get("sub", "")),
                "display_name": " ".join(filter(None, [data.get("given_name", ""), data.get("family_name", "")])),
                "profile_picture_url": data.get("picture", ""),
                "followers_count": 0,
                "account_type": "personal",
                "bio": data.get("bio", ""),
            }

    async def publish_post(self, account: SocialAccount, payload: PostPayload) -> PublishResult:
        """Publish a text post to LinkedIn."""
        if not account.access_token:
            return PublishResult(success=False, error_message="No access token available", error_code="NO_TOKEN")

        author = f"urn:li:person:{account.platform_user_id}"
        text = payload.caption
        if payload.hashtags:
            text = f"{text}\n\n{payload.hashtags}"

        share_commentary = {"text": text}

        if payload.media_path:
            upload = await self._upload_media(account.access_token, payload.media_path, payload.media_type)
            if not upload:
                return PublishResult(
                    success=False,
                    error_message="Media upload failed. LinkedIn requires a registered image/video asset.",
                    error_code="MEDIA_UPLOAD_FAILED",
                )
            share_media = {"media": [{"status": "READY", "description": {"text": payload.caption}, "media": upload}]}
        else:
            share_media = {}

        body = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": share_commentary,
                    "shareMediaCategory": "ARTICLE" if not payload.media_path else "IMAGE",
                    **share_media,
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{API_BASE}/v2/ugcPosts",
                    json=body,
                    headers={"Authorization": f"Bearer {account.access_token}"},
                )
                resp.raise_for_status()
                post_id = resp.json().get("id", "")
                return PublishResult(
                    success=True,
                    platform_post_id=post_id,
                    platform_url=f"https://www.linkedin.com/feed/update/{post_id}",
                )
        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            try:
                error_msg = e.response.json().get("message", str(e))
            except Exception:
                pass
            return PublishResult(success=False, error_message=error_msg, error_code="HTTP_ERROR")
        except Exception as e:
            logger.error("LinkedIn publish error: %s", e)
            return PublishResult(success=False, error_message=str(e), error_code="EXCEPTION")

    async def _upload_media(self, access_token: str, media_path: str, media_type: str) -> Optional[str]:
        """Register an image asset for a LinkedIn post (returns the asset URN)."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                register_resp = await client.post(
                    f"{API_BASE}/v2/assets?action=registerUpload",
                    json={
                        "registerUploadRequest": {
                            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                            "owner": "urn:li:person:placeholder",
                            "serviceRelationships": [
                                {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                            ],
                        }
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-Restli-Protocol-Version": "2.0.0",
                    },
                )
                if register_resp.status_code != 200:
                    return None
                data = register_resp.json()
                upload_url = data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset_urn = data["value"]["asset"]

                with open(media_path, "rb") as f:
                    file_data = f.read()

                upload_resp = await client.put(upload_url, content=file_data)
                if upload_resp.status_code not in (200, 201):
                    return None
                return asset_urn
        except Exception as e:
            logger.error("LinkedIn media upload error: %s", e)
            return None

    async def delete_post(self, account: SocialAccount, platform_post_id: str) -> bool:
        """Delete a LinkedIn post (UGC posts are soft-deleted via post delete API)."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{API_BASE}/rest/posts?action=delete",
                    json={"id": platform_post_id},
                    headers={
                        "Authorization": f"Bearer {account.access_token}",
                        "X-Restli-Protocol-Version": "2.0.0",
                    },
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("LinkedIn delete error: %s", e)
            return False

    async def get_post_metrics(self, account: SocialAccount, platform_post_id: str) -> dict:
        """LinkedIn does not expose per-post analytics via the public API."""
        return {"likes": 0, "comments": 0, "shares": 0, "impressions": 0, "reach": 0}

    def supports_publishing(self, account_type: str) -> bool:
        """LinkedIn supports publishing for all account types."""
        return True
