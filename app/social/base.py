"""
Phase 3: Abstract Social Media Provider Interface

All social media integrations (Instagram, Facebook, LinkedIn, X, etc.)
must implement this interface. This ensures:
- Consistent API across all platforms
- Easy to add new platforms without changing backend architecture
- Unified error handling and logging
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

# Prefix used for simulated accounts created in demo mode.
DEMO_ACCOUNT_PREFIX = "demo_"


def is_demo_account(account) -> bool:
    """Return True if the account is a locally simulated demo account."""
    return str(getattr(account, "platform_user_id", "") or "").startswith(DEMO_ACCOUNT_PREFIX)


def demo_publish_result(account) -> PublishResult:
    """Simulate a successful publish for demo accounts."""
    platform = getattr(account, "platform", "social")
    if hasattr(platform, "value"):
        platform = platform.value
    pid = f"demo_{uuid4().hex[:12]}"
    urls = {
        "instagram": f"https://www.instagram.com/p/{pid}/",
        "facebook": f"https://www.facebook.com/{pid}",
        "linkedin": f"https://www.linkedin.com/feed/update/{pid}",
        "twitter": f"https://x.com/demo/status/{pid}",
        "threads": f"https://www.threads.net/@demo/post/{pid}",
        "youtube": f"https://www.youtube.com/watch?v={pid}",
    }
    return PublishResult(success=True, platform_post_id=pid, platform_url=urls.get(platform, "#"))


class PlatformType(str, Enum):
    """Supported social media platforms."""
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    THREADS = "threads"
    YOUTUBE = "youtube"


class AccountType(str, Enum):
    """Instagram account types."""
    PERSONAL = "personal"
    BUSINESS = "business"
    CREATOR = "creator"


class PostStatus(str, Enum):
    """Status of a social media post."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class SocialAccount:
    """Represents a connected social media account."""
    id: int
    user_id: int
    platform: PlatformType
    account_type: AccountType
    platform_user_id: str
    username: str
    display_name: str = ""
    profile_picture_url: str = ""
    followers_count: int = 0
    access_token: str = ""
    token_expires_at: Optional[str] = None
    is_active: bool = True
    raw_data: dict = field(default_factory=dict)


@dataclass
class PublishResult:
    """Result of a publish operation."""
    success: bool
    platform_post_id: str = ""
    platform_url: str = ""
    error_message: str = ""
    error_code: str = ""


@dataclass
class PostPayload:
    """Data needed to publish a post to any platform."""
    caption: str
    media_path: str = ""
    media_type: str = "image"  # image, video, carousel
    hashtags: str = ""
    alt_text: str = ""
    location: str = ""
    user_tags: list = field(default_factory=list)
    # For carousel posts
    carousel_media: list = field(default_factory=list)


class SocialProvider(ABC):
    """
    Abstract base class for all social media providers.

    To add a new platform:
    1. Create a new class that inherits from SocialProvider
    2. Implement all abstract methods
    3. Register it in the provider registry (social/registry.py)
    """

    @property
    @abstractmethod
    def platform(self) -> PlatformType:
        """Return the platform type this provider handles."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g., 'Instagram Graph API')."""
        ...

    @abstractmethod
    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate the OAuth authorization URL for this platform.

        Args:
            redirect_uri: Where to redirect after auth
            state: CSRF protection state parameter

        Returns:
            Full OAuth URL to redirect the user to
        """
        ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange an OAuth authorization code for access tokens.

        Returns:
            {
                "access_token": str,
                "refresh_token": str (optional),
                "expires_in": int,
                "platform_user_id": str,
            }
        """
        ...

    @abstractmethod
    async def get_account_info(self, access_token: str) -> dict:
        """Get connected account profile information.

        Returns:
            {
                "platform_user_id": str,
                "username": str,
                "display_name": str,
                "profile_picture_url": str,
                "followers_count": int,
                "account_type": str,
                "bio": str,
            }
        """
        ...

    @abstractmethod
    async def publish_post(self, account: SocialAccount, payload: PostPayload) -> PublishResult:
        """Publish content to the platform.

        Args:
            account: The connected social account
            payload: Content to publish

        Returns:
            PublishResult with success/failure info
        """
        ...

    @abstractmethod
    async def delete_post(self, account: SocialAccount, platform_post_id: str) -> bool:
        """Delete/unpublish a post from the platform."""
        ...

    @abstractmethod
    async def get_post_metrics(self, account: SocialAccount, platform_post_id: str) -> dict:
        """Get engagement metrics for a published post.

        Returns:
            {
                "likes": int,
                "comments": int,
                "shares": int,
                "impressions": int,
                "reach": int,
            }
        """
        ...

    @abstractmethod
    def supports_publishing(self, account_type: str) -> bool:
        """Check if this account type supports direct publishing.

        Instagram Personal accounts cannot publish via API.
        Business/Creator accounts can.
        """
        ...

    def get_personal_fallback_features(self) -> list[str]:
        """Return features available for personal accounts (non-API publishing).

        Override in providers that support personal accounts.
        """
        return ["copy_caption", "copy_hashtags", "download_media", "open_in_app"]

    # ─────────────────────────────────────────────
    # Convenience lifecycle API (shared by all providers)
    # ─────────────────────────────────────────────

    def connect(self, redirect_uri: str, state: str) -> dict:
        """Generate an OAuth authorization URL and return it as a dict.

        Returns:
            {"auth_url": str, "state": str}
        """
        return {"auth_url": self.get_oauth_url(redirect_uri, state), "state": state}

    async def disconnect(self, account: "SocialAccount") -> bool:
        """Revoke access / clean up when an account is disconnected.

        Default implementation is a no-op; providers may override to call
        platform revoke endpoints.
        """
        return True

    async def refresh_token(self, account: "SocialAccount") -> dict:
        """Refresh an expired access token.

        Returns:
            {
                "access_token": str,
                "refresh_token": str (optional),
                "expires_in": int,
            }

        Raises NotImplementedError if the platform does not support refresh.
        """
        raise NotImplementedError(
            f"{self.name} does not support token refresh. Re-connect the account."
        )

    def status(self, account: Optional["SocialAccount"]) -> dict:
        """Return connection status for an account.

        Returns:
            {
                "connected": bool,
                "token_valid": bool,
                "platform": str,
                "expires_at": str (optional),
            }
        """
        if account is None:
            return {"connected": False, "token_valid": False, "platform": self.platform.value}
        return {
            "connected": bool(getattr(account, "is_active", True)),
            "token_valid": bool(getattr(account, "access_token", "")),
            "platform": self.platform.value,
            "expires_at": str(account.token_expires_at) if getattr(account, "token_expires_at", None) else None,
        }

    async def schedule(self, account: "SocialAccount", payload: "PostPayload", scheduled_at: str) -> bool:
        """Request platform-native scheduling (not all platforms support it).

        The app-level background scheduler covers most platforms; providers
        that support native scheduled publishing should override this.
        """
        return False
