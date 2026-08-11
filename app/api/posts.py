import os
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import get_settings
from app.models.user import User
from app.models.post import Post, GeneratedContent
from app.services.content_pipeline import (
    generate_from_image,
    generate_from_text,
    generate_from_document,
    generate_from_video,
    generate_from_audio,
    regenerate_field,
    translate_content,
    rewrite_content,
)
from app.services.ai_provider import ai_provider

settings = get_settings()

router = APIRouter(prefix="/api/posts", tags=["posts"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp", "image/heic", "image/heif"}
ALLOWED_DOC_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4", "audio/x-m4a", "audio/webm", "audio/aac", "audio/x-aac"}
MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_and_generate(
    text: str = Form(""),
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file and not text.strip():
        raise HTTPException(status_code=400, detail="Please provide a file or text content.")

    media_type = "text"
    media_path = None

    if file:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, detail=f"File too large. Max: {settings.MAX_UPLOAD_SIZE_MB}MB"
            )

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        ext = file.filename.split(".")[-1] if file.filename else "bin"
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(content)

        if file.content_type in ALLOWED_IMAGE_TYPES:
            media_type = "image"
        elif file.content_type in ALLOWED_DOC_TYPES or ext.lower() in ("pdf", "docx", "doc", "txt"):
            media_type = "document"
        elif file.content_type in ALLOWED_VIDEO_TYPES or ext.lower() in ("mp4", "mov", "avi", "webm", "mkv"):
            media_type = "video"
        elif file.content_type in ALLOWED_AUDIO_TYPES or ext.lower() in ("mp3", "wav", "ogg", "m4a", "webm"):
            media_type = "audio"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Allowed: Images, PDF, DOCX, Video (max 2 min), Audio",
            )
        media_path = filepath

    post = Post(
        user_id=current_user.id,
        media_type=media_type,
        media_path=media_path,
        original_text=text.strip() if text.strip() else None,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    if media_type == "video":
        from app.services.video_processor import validate_video
        error = validate_video(media_path)
        if error:
            db.delete(post)
            db.commit()
            raise HTTPException(status_code=400, detail=error)

    try:
        if media_type == "image":
            result = await generate_from_image(media_path, text)
        elif media_type == "document":
            result = await generate_from_document(media_path, text)
        elif media_type == "video":
            result = await generate_from_video(media_path, text)
        elif media_type == "audio":
            result = await generate_from_audio(media_path, text)
        else:
            result = await generate_from_text(text)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")

    generated = GeneratedContent(
        post_id=post.id,
        caption=result.get("caption", ""),
        long_caption=result.get("long_caption", ""),
        short_caption=result.get("short_caption", ""),
        funny_caption=result.get("funny_caption", ""),
        professional_caption=result.get("professional_caption", ""),
        travel_caption=result.get("travel_caption", ""),
        business_caption=result.get("business_caption", ""),
        food_caption=result.get("food_caption", ""),
        luxury_caption=result.get("luxury_caption", ""),
        carousel_text=result.get("carousel_text", ""),
        thumbnail_text=result.get("thumbnail_text", ""),
        alt_text=result.get("alt_text", ""),
        hashtags=result.get("hashtags", ""),
        keywords=result.get("keywords", ""),
        emojis=result.get("emojis", ""),
        cta=result.get("cta", ""),
        hook=result.get("hook", ""),
        reel_title=result.get("reel_title", ""),
        seo_tags=result.get("seo_tags", ""),
        summary=result.get("summary", ""),
        viral_score=result.get("viral_score", 0),
        viral_score_reason=result.get("viral_score_reason", ""),
    )
    db.add(generated)
    db.commit()
    db.refresh(generated)

    return {
        "post": {
            "id": post.id,
            "media_type": post.media_type,
            "media_path": post.media_path,
            "original_text": post.original_text,
            "created_at": post.created_at.isoformat(),
        },
        "generated": _gen_dict(generated),
    }


@router.post("/{post_id}/regenerate")
async def regenerate_single_field(
    post_id: int,
    field: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    gen = db.query(GeneratedContent).filter(GeneratedContent.post_id == post_id).first()
    if not gen:
        raise HTTPException(status_code=404, detail="No generated content for this post")

    valid_fields = {"caption", "long_caption", "short_caption", "funny_caption", "professional_caption", "travel_caption", "business_caption", "food_caption", "luxury_caption", "carousel_text", "thumbnail_text", "alt_text", "hashtags", "keywords", "emojis", "cta", "hook", "reel_title", "seo_tags", "summary", "viral_score_reason"}
    if field not in valid_fields:
        raise HTTPException(status_code=400, detail=f"Invalid field: {field}")

    context = f"Original text: {post.original_text or 'N/A'}\n"
    context += f"Current caption: {gen.caption}\nCurrent hashtags: {gen.hashtags}\nCurrent summary: {gen.summary}\n"

    if field == "viral_score_reason":
        prompt = (
            f"Rate the viral potential (1-100) of this content and give a short reason.\n"
            f"Context: {context}\n"
            f"Return ONLY a number between 1 and 100 on the first line, then the reason on the second line."
        )
        try:
            response = await ai_provider.generate_text(prompt)
            lines = response.strip().split("\n", 1)
            score = int(lines[0].strip().strip("*").strip("#").strip())
            score = max(1, min(100, score))
            reason = lines[1].strip() if len(lines) > 1 else "No reason provided"
            gen.viral_score = score
            gen.viral_score_reason = reason
            db.commit()
            return {"field": "viral_score", "value": score, "reason": reason}
        except (ValueError, IndexError):
            gen.viral_score = 50
            gen.viral_score_reason = "Unable to determine viral score"
            db.commit()
            return {"field": "viral_score", "value": 50, "reason": gen.viral_score_reason}
        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Viral score generation failed: {str(e)}")

    try:
        new_value = await regenerate_field(field, context)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")

    setattr(gen, field, new_value)
    db.commit()
    return {"field": field, "value": new_value}


@router.post("/{post_id}/update")
async def update_generated_content(
    post_id: int,
    field: str = Form(...),
    value: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    gen = db.query(GeneratedContent).filter(GeneratedContent.post_id == post_id).first()
    if not gen:
        raise HTTPException(status_code=404, detail="No generated content for this post")

    valid_fields = {"caption", "long_caption", "short_caption", "funny_caption", "professional_caption", "travel_caption", "business_caption", "food_caption", "luxury_caption", "carousel_text", "thumbnail_text", "alt_text", "hashtags", "keywords", "emojis", "cta", "hook", "reel_title", "seo_tags", "summary", "translation", "viral_score_reason"}
    if field not in valid_fields:
        raise HTTPException(status_code=400, detail=f"Invalid field: {field}")

    setattr(gen, field, value)
    db.commit()
    return {"field": field, "value": value}


@router.post("/{post_id}/translate")
async def translate_post(
    post_id: int,
    target_language: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    gen = db.query(GeneratedContent).filter(GeneratedContent.post_id == post_id).first()
    if not gen:
        raise HTTPException(status_code=404, detail="No generated content for this post")

    try:
        text_to_translate = f"Caption: {gen.caption}\nSummary: {gen.summary}"
        translated = await translate_content(text_to_translate, target_language)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

    gen.translation = translated
    db.commit()
    return {"translation": translated}


@router.post("/rewrite")
async def rewrite_text(
    text: str = Form(...),
    tone: str = Form(...),
    length: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    try:
        rewritten = await rewrite_content(text, tone, length)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rewrite failed: {str(e)}")

    return {"rewritten": rewritten}


@router.get("/history")
def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    total = db.query(Post).filter(Post.user_id == current_user.id).count()
    posts = (
        db.query(Post)
        .filter(Post.user_id == current_user.id)
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    results = []
    for post in posts:
        gen = db.query(GeneratedContent).filter(GeneratedContent.post_id == post.id).first()
        results.append({
            "post": {
                "id": post.id,
                "media_type": post.media_type,
                "media_path": post.media_path,
                "original_text": post.original_text,
                "created_at": post.created_at.isoformat(),
            },
            "generated": _gen_dict(gen) if gen else None,
        })
    return {"items": results, "total": total, "page": page, "page_size": page_size}


def _gen_dict(gen) -> dict:
    return {
        "id": gen.id,
        "caption": gen.caption or "",
        "long_caption": gen.long_caption or "",
        "short_caption": gen.short_caption or "",
        "funny_caption": gen.funny_caption or "",
        "professional_caption": gen.professional_caption or "",
        "travel_caption": gen.travel_caption or "",
        "business_caption": gen.business_caption or "",
        "food_caption": gen.food_caption or "",
        "luxury_caption": gen.luxury_caption or "",
        "carousel_text": gen.carousel_text or "",
        "thumbnail_text": gen.thumbnail_text or "",
        "alt_text": gen.alt_text or "",
        "hashtags": gen.hashtags or "",
        "keywords": gen.keywords or "",
        "emojis": gen.emojis or "",
        "cta": gen.cta or "",
        "hook": gen.hook or "",
        "reel_title": gen.reel_title or "",
        "seo_tags": gen.seo_tags or "",
        "summary": gen.summary or "",
        "translation": gen.translation or "",
        "viral_score": gen.viral_score or 0,
        "viral_score_reason": gen.viral_score_reason or "",
    }
