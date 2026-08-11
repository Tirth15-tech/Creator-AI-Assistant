from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.social.base import PlatformType

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")

# URL slug -> platform enum value (route aliases)
_PLATFORM_ALIASES = {"x": "twitter", "youtube": "youtube"}


def _resolve_platform(slug: str):
    """Map a connect URL slug to a valid PlatformType value, or None."""
    platform = _PLATFORM_ALIASES.get(slug, slug)
    try:
        return PlatformType(platform).value
    except ValueError:
        return None


@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(request, "landing.html")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html")


@router.get("/connect/{platform}", response_class=HTMLResponse)
def connect_page(request: Request, platform: str):
    """Start the correct OAuth flow for a specific platform."""
    resolved = _resolve_platform(platform)
    if not resolved:
        return templates.TemplateResponse(
            request, "landing.html",
            {"platform": platform, "error": f"Unknown platform: {platform}"},
        )
    return templates.TemplateResponse(request, "connect.html", {"platform": resolved})


@router.get("/preview", response_class=HTMLResponse)
def preview_page(request: Request):
    """Post Preview page: edit content, save draft, schedule or publish."""
    return templates.TemplateResponse(request, "preview.html")
