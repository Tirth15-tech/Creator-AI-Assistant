"""Tests for the Post Preview & Publish workflow (added feature)."""
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import TestSessionLocal
from app.models.post import Post, GeneratedContent
from app.models.social import Draft, PostingHistory
from app.api.social import _is_valid_post_url


def _make_post(db, media_type="image", media_path="uploads/photo.jpg"):
    post = Post(user_id=1, media_type=media_type, media_path=media_path,
                original_text="An amazing travel destination.")
    db.add(post)
    db.commit()
    db.refresh(post)
    gen = GeneratedContent(
        post_id=post.id,
        caption="Amazing caption",
        hashtags="#travel #wanderlust",
        keywords="travel, beach",
        hook="You won't believe this place!",
        cta="Tap like!",
        seo_tags="travel guide, hidden gem",
        alt_text="A beach at sunset",
    )
    db.add(gen)
    db.commit()
    return post


def _connect_demo(client, platform="instagram"):
    r = client.get(f"/api/social/connect/{platform}")
    assert r.status_code == 200
    body = r.json()
    assert body["demo"] is True
    cb = client.get(body["auth_url"], follow_redirects=False)
    assert cb.status_code in (301, 302, 307)


def test_valid_post_url_helper():
    assert _is_valid_post_url("https://www.instagram.com/p/abc123/") is True
    assert _is_valid_post_url("") is False
    assert _is_valid_post_url("not-a-url") is False
    assert _is_valid_post_url("https://www.instagram.com/p/demo_d8293115/") is False


def test_preview_returns_content_accounts_and_drafts(auth_client):
    db = TestSessionLocal()
    try:
        _make_post(db)
        db.commit()
    finally:
        db.close()

    r = auth_client.get("/api/social/preview/1")
    assert r.status_code == 200
    body = r.json()
    assert body["post"]["id"] == 1
    assert body["generated"]["caption"] == "Amazing caption"
    assert body["generated"]["keywords"] == "travel, beach"
    assert body["generated"]["hook"] == "You won't believe this place!"
    assert body["generated"]["cta"] == "Tap like!"
    assert body["generated"]["seo_tags"] == "travel guide, hidden gem"
    assert body["accounts"] == []


def test_preview_404_for_other_users_post(auth_client):
    r = auth_client.get("/api/social/preview/999")
    assert r.status_code == 404


def test_preview_draft_save_load_update_delete(auth_client):
    db = TestSessionLocal()
    try:
        _make_post(db)
        db.commit()
    finally:
        db.close()

    payload = {
        "post_id": 1,
        "title": "Draft title",
        "caption": "Edited caption",
        "hashtags": "#new",
        "keywords": "k1, k2",
        "hook": "A hook",
        "cta": "Follow me",
        "seo": "seo tags here",
        "media_path": "uploads/photo.jpg",
        "media_type": "image",
    }
    r = auth_client.post("/api/social/preview/drafts", json=payload)
    assert r.status_code == 200, r.text
    draft_id = r.json()["id"]

    r = auth_client.get("/api/social/preview/1")
    drafts = r.json()["drafts"]
    assert len(drafts) == 1
    d = drafts[0]
    assert d["caption"] == "Edited caption"
    assert d["keywords"] == "k1, k2"
    assert d["hook"] == "A hook"
    assert d["cta"] == "Follow me"
    assert d["seo"] == "seo tags here"

    r = auth_client.put(f"/api/social/preview/drafts/{draft_id}",
                        json={"caption": "Newer caption", "keywords": "k3"})
    assert r.status_code == 200

    r = auth_client.get("/api/social/preview/1")
    d = r.json()["drafts"][0]
    assert d["caption"] == "Newer caption"
    assert d["keywords"] == "k3"
    assert d["hook"] == "A hook"

    r = auth_client.delete(f"/api/social/preview/drafts/{draft_id}")
    assert r.status_code == 200
    r = auth_client.get("/api/social/preview/1")
    assert r.json()["drafts"] == []


def test_preview_draft_put_404(auth_client):
    r = auth_client.put("/api/social/preview/drafts/999", json={"caption": "x"})
    assert r.status_code == 404


def test_preview_publish_demo_records_history_without_broken_link(auth_client):
    db = TestSessionLocal()
    try:
        _make_post(db)
        db.commit()
    finally:
        db.close()

    _connect_demo(auth_client, "instagram")

    r = auth_client.get("/api/social/accounts")
    account = [a for a in r.json()["accounts"] if a["platform"] == "instagram"][0]

    r = auth_client.post("/api/social/preview/publish", json={
        "account_id": account["id"],
        "caption": "Final caption",
        "hashtags": "#final",
        "keywords": "k",
        "hook": "h",
        "cta": "c",
        "seo": "s",
        "media_path": "uploads/photo.jpg",
        "media_type": "image",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["demo"] is True
    assert body["view_url"] == "", "demo publish must NOT expose a broken link"
    assert "demo simulation" in body["status_text"]

    db = TestSessionLocal()
    try:
        history = db.query(PostingHistory).order_by(PostingHistory.id.desc()).first()
        assert history is not None
        assert history.caption == "Final caption"
        assert history.platform_url == "", "history must not keep a broken demo link"
    finally:
        db.close()


def test_preview_publish_requires_valid_account(auth_client):
    r = auth_client.post("/api/social/preview/publish", json={
        "account_id": 999,
        "caption": "Hi",
    })
    assert r.status_code == 404


def test_preview_page_renders(auth_client):
    r = auth_client.get("/preview?post_id=1")
    assert r.status_code == 200
    assert "Post Preview" in r.text
