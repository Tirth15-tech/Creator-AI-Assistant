import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from io import BytesIO
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.post import Post, GeneratedContent
from app.services.exporter import export_as_text, export_as_csv, export_as_docx, export_as_pdf, export_as_json
from app.services.quality_checker import check_image_quality, check_video_quality

router = APIRouter(prefix="/api/posts", tags=["export"])


@router.get("/{post_id}/export/{fmt}")
def export_post(
    post_id: int,
    fmt: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    gen = db.query(GeneratedContent).filter(GeneratedContent.post_id == post_id).first()
    if not gen:
        raise HTTPException(status_code=404, detail="No generated content")

    post_data = {
        "id": post.id,
        "media_type": post.media_type,
        "original_text": post.original_text,
        "created_at": post.created_at.isoformat() if post.created_at else "",
    }
    gen_data = {
        "caption": gen.caption or "",
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

    if fmt == "txt":
        content = export_as_text(post_data, gen_data)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=contentai_post_{post_id}.txt"},
        )
    elif fmt == "csv":
        content = export_as_csv([{"post": post_data, "generated": gen_data}])
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=contentai_post_{post_id}.csv"},
        )
    elif fmt == "docx":
        content = export_as_docx(post_data, gen_data)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=contentai_post_{post_id}.docx"},
        )
    elif fmt == "pdf":
        content = export_as_pdf(post_data, gen_data)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=contentai_post_{post_id}.pdf"},
        )
    elif fmt == "json":
        content = export_as_json(post_data, gen_data)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=contentai_post_{post_id}.json"},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}. Use txt, csv, docx, pdf, or json.")


@router.get("/export-all/csv")
def export_all_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    posts = (
        db.query(Post)
        .filter(Post.user_id == current_user.id)
        .order_by(Post.created_at.desc())
        .all()
    )
    items = []
    for post in posts:
        gen = db.query(GeneratedContent).filter(GeneratedContent.post_id == post.id).first()
        items.append({
            "post": {
                "id": post.id,
                "media_type": post.media_type,
                "original_text": post.original_text,
                "created_at": post.created_at.isoformat() if post.created_at else "",
            },
            "generated": {
                "caption": gen.caption or "",
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
            } if gen else {},
        })
    content = export_as_csv(items)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contentai_all_posts.csv"},
    )


@router.get("/{post_id}/quality")
def get_quality_report(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not post.media_path or not os.path.exists(post.media_path):
        raise HTTPException(status_code=404, detail="Media file not found")

    if post.media_type == "image":
        return check_image_quality(post.media_path)
    elif post.media_type == "video":
        return check_video_quality(post.media_path)
    else:
        return {"message": "Quality check only available for images and videos"}
