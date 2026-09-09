from pathlib import Path

from pydantic_settings import BaseSettings
from functools import lru_cache

# Project root = <repo>/app/core/config.py -> parents[2]. Resolving .env relative
# to this module (instead of the process CWD) guarantees the right file is loaded
# even when uvicorn is started from another directory.
_BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = "ContentAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite:///./contentai.db"

    JWT_SECRET_KEY: str = "super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:4b"

    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    CORS_ORIGINS: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    # Public base URL used to build absolute media URLs for the social
    # providers (Instagram Graph API requires publicly reachable media URLs).
    # When the app is only reachable locally, expose it via a tunnel (e.g.
    # ngrok) and set this to that public URL before publishing media posts.
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Phase 3: Social Media OAuth — one module per platform
    #
    # Instagram publishing uses the Instagram Graph API. The client id/secret
    # are the Facebook App ID / App Secret of the app that has the Instagram
    # Graph API use case enabled (Business/Creator account required).
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    INSTAGRAM_REDIRECT_URI: str = "http://localhost:8000/api/social/instagram/callback"
    INSTAGRAM_API_VERSION: str = "v22.0"
    INSTAGRAM_SCOPES: str = "instagram_basic,instagram_content_publish,pages_show_list"

    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    FACEBOOK_REDIRECT_URI: str = "http://localhost:8000/api/social/facebook/callback"
    FACEBOOK_SCOPES: str = "pages_show_list,pages_read_engagement,pages_manage_posts,publish_video"

    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/api/social/linkedin/callback"
    LINKEDIN_SCOPES: str = "openid,profile,email,w_member_social"

    TWITTER_CLIENT_ID: str = ""
    TWITTER_CLIENT_SECRET: str = ""
    TWITTER_REDIRECT_URI: str = "http://localhost:8000/api/social/x/callback"
    TWITTER_SCOPES: str = "tweet.read tweet.write users.read offline.access"

    THREADS_CLIENT_ID: str = ""
    THREADS_CLIENT_SECRET: str = ""
    THREADS_REDIRECT_URI: str = "http://localhost:8000/api/social/threads/callback"
    THREADS_SCOPES: str = "threads_basic,threads_content_publish"

    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/social/youtube/callback"
    YOUTUBE_SCOPES: str = "https://www.googleapis.com/auth/youtube.force-ssl"

    # Token encryption key (Fernet). Leave empty to derive from JWT_SECRET_KEY.
    TOKEN_ENCRYPTION_KEY: str = ""

    # When a platform has no API credentials configured, allow a simulated
    # "demo" connection so the rest of the app can still be used and tested.
    # Set to false to show a configuration error instead.
    SOCIAL_DEMO_MODE: bool = True

    # Scheduling
    SCHEDULER_INTERVAL_SECONDS: int = 60  # how often the scheduler checks for due posts

    # n8n automation layer (optional). When enabled, ContentAI notifies the
    # n8n webhook about jobs and delegates scheduled publishing orchestration.
    # All secrets stay in ContentAI; n8n only orchestrates and calls back.
    N8N_ENABLED: bool = False
    N8N_BASE_URL: str = ""                 # e.g. http://localhost:5678 (no trailing slash)
    N8N_WEBHOOK_SECRET: str = ""           # shared secret for signing both directions
    N8N_TIMEOUT_SECONDS: float = 10.0

    model_config = {
        "env_file": str(_BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
