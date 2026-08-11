"""
Phase 3: Social Provider Registry

Central registry that maps platform types to their provider implementations.
When adding a new platform, register it here.
"""

from app.social.base import PlatformType, SocialProvider
from app.core.config import get_settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Global registry of providers
_providers: dict[PlatformType, SocialProvider] = {}

# Environment variable names holding OAuth credentials, per platform.
# The first value is the client id env var, the second the client secret.
PLATFORM_CREDENTIALS: dict[str, tuple[str, str]] = {
    "instagram": ("INSTAGRAM_CLIENT_ID", "INSTAGRAM_CLIENT_SECRET"),
    "facebook": ("FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET"),
    "linkedin": ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"),
    "twitter": ("TWITTER_CLIENT_ID", "TWITTER_CLIENT_SECRET"),
    "threads": ("THREADS_CLIENT_ID", "THREADS_CLIENT_SECRET"),
    "youtube": ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"),
}


def platform_credentials_missing(platform: str) -> list[str]:
    """Return the names of missing OAuth credential env vars for a platform.

    An empty list means the platform is fully configured.
    """
    names = PLATFORM_CREDENTIALS.get(platform)
    if not names:
        return []
    settings = get_settings()
    missing = []
    for env_name in names:
        value = getattr(settings, env_name, "")
        if not value:
            missing.append(env_name)
    return missing


def platform_config_errors(platform: str) -> list[str]:
    """Return a list of human-readable config problems for a platform.

    Checks credential env vars plus PUBLIIC base URL requirements for media
    publishing platforms (Instagram). Never includes secret values.
    """
    errors = []
    missing = platform_credentials_missing(platform)
    for name in missing:
        errors.append(f"{name} is not set in .env")

    settings = get_settings()
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip()
    if not base:
        errors.append(
            "PUBLIC_BASE_URL is not set in .env. Instagram's servers must be "
            "able to reach your media files through a public HTTPS URL."
        )
    elif "localhost" in base or "127.0.0.1" in base:
        errors.append(
            "PUBLIC_BASE_URL points to a local address. Configure an HTTPS "
            "tunnel (e.g. ngrok) so Instagram can fetch your media files."
        )
    return errors


def register_provider(provider: SocialProvider) -> None:
    """Register a social media provider."""
    _providers[provider.platform] = provider
    logger.info("Registered social provider: %s (%s)", provider.name, provider.platform.value)


def get_provider(platform: PlatformType) -> Optional[SocialProvider]:
    """Get the provider for a given platform."""
    return _providers.get(platform)


def get_all_providers() -> dict[PlatformType, SocialProvider]:
    """Get all registered providers."""
    return dict(_providers)


def get_supported_platforms() -> list[dict]:
    """Get info about all supported platforms."""
    result = []
    for platform_type, provider in _providers.items():
        result.append({
            "platform": platform_type.value,
            "name": provider.name,
            "supports_publishing": True,
            "configured": not platform_credentials_missing(platform_type.value),
        })
    return result


# ─────────────────────────────────────────────
# Auto-register available providers on import
# ─────────────────────────────────────────────

def _auto_register():
    """Attempt to register all built-in providers.

    Each provider is isolated in its own module under app/social/providers/.
    To add a new platform, create a provider module there and register it here —
    no other application code needs to change.
    """
    providers = [
        ("app.social.providers.instagram", "InstagramProvider"),
        ("app.social.providers.facebook", "FacebookProvider"),
        ("app.social.providers.linkedin", "LinkedInProvider"),
        ("app.social.providers.twitter", "TwitterProvider"),
        ("app.social.providers.threads", "ThreadsProvider"),
        ("app.social.providers.youtube", "YouTubeProvider"),
    ]

    for module_path, class_name in providers:
        try:
            module = __import__(module_path, fromlist=[class_name])
            provider_class = getattr(module, class_name)
            register_provider(provider_class())
        except Exception as e:
            logger.debug("%s provider not registered: %s", class_name, e)


_auto_register()
