from datetime import datetime, timezone
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.post import Post, GeneratedContent

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/users")
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "is_admin": u.is_admin,
            "is_banned": u.is_banned,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/stats")
def get_stats(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar()
    total_posts = db.query(func.count(Post.id)).scalar()
    total_generated = db.query(func.count(GeneratedContent.id)).scalar()
    media_counts = (
        db.query(Post.media_type, func.count(Post.id))
        .group_by(Post.media_type)
        .all()
    )
    posts_by_type = {mt: count for mt, count in media_counts}
    recent_posts = (
        db.query(Post)
        .order_by(Post.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "total_users": total_users,
        "total_posts": total_posts,
        "total_generated": total_generated,
        "posts_by_type": posts_by_type,
        "recent_posts": [
            {
                "id": p.id,
                "user_id": p.user_id,
                "media_type": p.media_type,
                "created_at": p.created_at.isoformat(),
            }
            for p in recent_posts
        ],
    }


@router.post("/users/{user_id}/ban")
def ban_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot ban yourself")
    user.is_banned = True
    db.commit()
    return {"message": f"User {user.email} banned"}


@router.post("/users/{user_id}/unban")
def unban_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = False
    db.commit()
    return {"message": f"User {user.email} unbanned"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    posts = db.query(Post).filter(Post.user_id == user_id).all()
    for post in posts:
        if post.media_path and os.path.exists(post.media_path):
            try:
                os.remove(post.media_path)
            except OSError:
                pass
        db.query(GeneratedContent).filter(GeneratedContent.post_id == post.id).delete()
    db.query(Post).filter(Post.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return {"message": f"User {user.email} and all their data deleted"}


@router.post("/make-admin/{user_id}")
def make_admin(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_admin = True
    db.commit()
    return {"message": f"User {user.email} is now an admin"}
