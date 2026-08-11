import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.core.config import get_settings
from app.core.database import engine, Base, SessionLocal
from app.models.user import User
from app.models.post import Post, GeneratedContent
from app.models.social import SocialAccount, Draft, ScheduledPost, PostingHistory, Notification
from app.api.auth import router as auth_router
from app.api.pages import router as pages_router
from app.api.posts import router as posts_router
from app.api.admin import router as admin_router
from app.api.export import router as export_router
from app.api.social import router as social_router
from app.api.analytics import router as analytics_router
from app.core.rate_limit import RateLimitMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=10,
    window_seconds=60,
    limit_paths=["/api/auth/login", "/api/auth/register"],
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("static/css", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(posts_router)
app.include_router(admin_router)
app.include_router(export_router)
app.include_router(social_router)
app.include_router(analytics_router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@contentai.com").first()
        if not admin:
            from app.core.security import hash_password
            admin = User(
                email="admin@contentai.com",
                password_hash=hash_password("admin123"),
                is_admin=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Admin user created: admin@contentai.com / admin123")
    finally:
        db.close()

    try:
        from app.services.image_analyzer import _get_yolo
        logger.info("Preloading YOLOv8 model...")
        _get_yolo()
        logger.info("YOLOv8 ready.")
    except Exception as e:
        logger.warning("Could not preload YOLOv8: %s", e)
    try:
        from app.services.audio_transcriber import _get_whisper
        logger.info("Preloading Whisper model...")
        _get_whisper()
        logger.info("Whisper ready.")
    except Exception as e:
        logger.warning("Could not preload Whisper: %s", e)
    logger.info("ContentAI started successfully.")

    # Meta / Instagram configuration validation (no secrets are logged).
    try:
        from app.social.registry import platform_config_errors
        if not get_settings().SOCIAL_DEMO_MODE:
            problems = platform_config_errors("instagram")
            if problems:
                logger.warning("Instagram integration is not ready: %s", "; ".join(problems))
            else:
                logger.info("Instagram integration is configured correctly.")
    except Exception as e:
        logger.debug("Config validation skipped: %s", e)

    # Start the background scheduler for scheduled posts
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning("Scheduler could not start: %s", e)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
