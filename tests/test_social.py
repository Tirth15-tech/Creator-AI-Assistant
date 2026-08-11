from fastapi.testclient import TestClient
from app.main import app
from app.social.registry import get_all_providers, get_supported_platforms
from app.social.providers.instagram import InstagramProvider
from app.core.security import encrypt_token, decrypt_token


class _FakeProvider:
    platform = None

    def supports_publishing(self, account_type):
        return True

    def get_oauth_url(self, redirect_uri, state):
        return f"https://example.com/oauth?platform={self.platform.value}&state={state}"

    async def exchange_code(self, code, redirect_uri):
        return {
            "access_token": "plain-secret-token",
            "expires_in": 3600,
            "platform_user_id": "ig_123",
        }

    async def get_account_info(self, access_token):
        return {
            "platform_user_id": "ig_123",
            "username": "testuser",
            "display_name": "Test User",
            "profile_picture_url": "",
            "followers_count": 10,
            "account_type": "business",
        }

    def status(self, account):
        return {"connected": True, "token_valid": bool(account.access_token), "platform": "instagram"}


def test_all_six_providers_registered():
    providers = get_all_providers()
    expected = {"instagram", "facebook", "linkedin", "twitter", "threads", "youtube"}
    assert {p.value for p in providers} == expected


def test_supported_platforms_endpoint_has_all_platforms(client):
    client.post(
        "/api/auth/register",
        json={"email": "social@example.com", "password": "testpass123"},
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "social@example.com", "password": "testpass123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/social/platforms", headers=headers)
    assert r.status_code == 200
    platforms = {p["platform"] for p in r.json()["platforms"]}
    assert platforms == {"instagram", "facebook", "linkedin", "twitter", "threads", "youtube"}
    for p in r.json()["platforms"]:
        assert "configured" in p


def test_connect_routes_use_demo_mode_when_unconfigured(auth_client):
    """Without .env credentials and with demo mode on, connect should start a
    simulated flow instead of erroring or dumping the user on a broken page."""
    for platform in ("instagram", "facebook", "linkedin", "twitter", "threads", "youtube"):
        r = auth_client.get(f"/api/social/connect/{platform}")
        assert r.status_code == 200
        body = r.json()
        assert body["platform"] == platform
        assert body["demo"] is True
        assert body["state"]
        # The demo flow redirects back to our own callback
        assert "/api/social/{}/callback".format(platform) in body["auth_url"]
        assert "code=demo" in body["auth_url"]


def test_connect_returns_error_when_demo_mode_disabled(auth_client, monkeypatch):
    """When demo mode is off and credentials are missing, a clear 400 is returned."""
    import app.api.social as social_api
    from app.social.registry import PLATFORM_CREDENTIALS

    class _NoDemoSettings:
        SOCIAL_DEMO_MODE = False

    def no_credentials(platform):
        return [PLATFORM_CREDENTIALS[platform][0]]

    monkeypatch.setattr(social_api, "platform_credentials_missing", no_credentials)
    monkeypatch.setattr(social_api, "get_settings", lambda: _NoDemoSettings())

    r = auth_client.get("/api/social/connect/instagram")
    assert r.status_code == 400
    assert "not configured" in r.json()["detail"]["message"].lower()


def test_connect_routes_generate_oauth_urls_when_configured(auth_client, monkeypatch):
    import app.api.social as social_api
    monkeypatch.setattr(social_api, "platform_credentials_missing", lambda platform: [])
    for platform in ("instagram", "facebook", "linkedin", "twitter", "threads", "youtube"):
        r = auth_client.get(f"/api/social/connect/{platform}")
        assert r.status_code == 200
        body = r.json()
        assert body["platform"] == platform
        assert body["auth_url"].startswith("http")
        assert body["state"]


def test_instagram_oauth_url_uses_facebook_login_for_graph_api():
    """Instagram Graph API publishing requires Facebook Login, not the
    read-only Instagram Login flow."""
    url = InstagramProvider().get_oauth_url("http://localhost:8000/api/social/instagram/callback", "test-state")
    assert "facebook.com/dialog/oauth" in url
    assert "instagram_content_publish" in url
    assert "state=test-state" in url


def test_connect_page_routes_render(auth_client):
    for slug in ("instagram", "facebook", "linkedin", "x", "threads", "youtube"):
        r = auth_client.get(f"/connect/{slug}")
        assert r.status_code == 200
        assert "Connecting" in r.text


def test_unknown_platform_rejected(auth_client):
    r = auth_client.get("/api/social/connect/unknown")
    assert r.status_code == 404


def test_token_encryption_roundtrip():
    secret = "super-secret-access-token"
    encrypted = encrypt_token(secret)
    assert encrypted != secret
    assert decrypt_token(encrypted) == secret


def test_token_encryption_backward_compatible():
    """Plaintext tokens written before encryption must still decrypt."""
    plain = "legacy-plaintext-token"
    assert decrypt_token(plain) == plain
    assert decrypt_token("") == ""


def test_account_status_endpoint_not_found(auth_client):
    r = auth_client.get("/api/social/accounts/999/status")
    assert r.status_code == 404


def test_oauth_callback_saves_account_with_encrypted_token(auth_client, monkeypatch):
    import app.api.social as social_api
    from app.models.social import SocialAccount
    from app.social.base import PlatformType

    fake = _FakeProvider()
    fake.platform = PlatformType.INSTAGRAM

    # Credentials are configured and the provider is swapped for a fake
    monkeypatch.setattr(social_api, "platform_credentials_missing", lambda platform: [])
    monkeypatch.setattr(social_api, "get_provider", lambda platform: fake)

    # Start the OAuth flow to obtain a CSRF state
    r = auth_client.get("/api/social/connect/instagram")
    assert r.status_code == 200
    state = r.json()["state"]

    # Simulate the platform redirecting back with a code
    cb = auth_client.get("/api/social/instagram/callback", params={"code": "test_code", "state": state}, follow_redirects=False)
    assert cb.status_code in (301, 302, 307)
    assert "social_connected=true" in cb.headers["location"]

    # Account must be saved with an encrypted token
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    try:
        acc = db.query(SocialAccount).filter(
            SocialAccount.platform == "instagram",
            SocialAccount.platform_user_id == "ig_123",
        ).first()
        assert acc is not None
        assert acc.access_token != "plain-secret-token"
        assert decrypt_token(acc.access_token) == "plain-secret-token"
    finally:
        db.close()

    # And it should appear in the accounts list
    accounts = auth_client.get("/api/social/accounts").json()["accounts"]
    assert any(a["platform"] == "instagram" and a["username"] == "testuser" for a in accounts)


def test_oauth_callback_rejects_unknown_state(auth_client, monkeypatch):
    r = auth_client.get(
        "/api/social/instagram/callback",
        params={"code": "x", "state": "forged-state"},
        follow_redirects=False,
    )
    assert r.status_code in (301, 302, 307)
    assert "invalid_state" in r.headers["location"]


def test_demo_callback_creates_demo_account(auth_client):
    """Following the demo auth_url must create a simulated connected account."""
    from tests.conftest import TestSessionLocal
    from app.models.social import SocialAccount
    from app.core.security import decrypt_token

    r = auth_client.get("/api/social/connect/youtube")
    assert r.status_code == 200
    body = r.json()
    assert body["demo"] is True

    # Follow the demo OAuth callback with an entered username
    cb = auth_client.get(body["auth_url"] + "&username=my_handle", follow_redirects=False)
    assert cb.status_code in (301, 302, 307)
    assert "social_connected=true" in cb.headers["location"]
    assert "demo=true" in cb.headers["location"]

    # Account must be saved and marked as demo, using the entered username
    db = TestSessionLocal()
    try:
        acc = db.query(SocialAccount).filter(
            SocialAccount.platform == "youtube",
            SocialAccount.platform_user_id == "demo_youtube",
        ).first()
        assert acc is not None
        assert acc.username == "my_handle"
        assert acc.raw_data.get("demo") is True
        assert decrypt_token(acc.access_token) == "demo-token-youtube"
    finally:
        db.close()

    # And it should be listed as a demo account with publishing support
    accounts = auth_client.get("/api/social/accounts").json()["accounts"]
    demo = [a for a in accounts if a["platform"] == "youtube"]
    assert demo and demo[0]["is_demo"] is True
    assert demo[0]["supports_publishing"] is True


def test_demo_account_publish_simulates_success(auth_client):
    """Publishing to a demo account must simulate success without hitting a real API."""
    from tests.conftest import TestSessionLocal
    from app.models.social import SocialAccount

    # Connect a demo account first
    r = auth_client.get("/api/social/connect/instagram")
    cb = auth_client.get(r.json()["auth_url"], follow_redirects=False)
    assert cb.status_code in (301, 302, 307)

    db = TestSessionLocal()
    try:
        acc = db.query(SocialAccount).filter(
            SocialAccount.platform == "instagram",
            SocialAccount.platform_user_id == "demo_instagram",
        ).first()
        acc_id = acc.id
    finally:
        db.close()

    resp = auth_client.post(
        "/api/social/post-now",
        json={"account_id": acc_id, "caption": "Demo post", "media_type": "image", "hashtags": "#demo"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["platform_post_id"].startswith("demo_")

    # It must be recorded in posting history
    history = auth_client.get("/api/social/history").json()["history"]
    assert any(h["caption"] == "Demo post" for h in history)


def test_instagram_graph_api_publish_flow(monkeypatch):
    """The Instagram provider must create a media container and then publish it."""
    import asyncio
    from app.social.base import PostPayload, SocialAccount

    calls = []
    post_bodies = []

    class _FakeResponse:
        status_code = 200
        headers = {"content-type": "image/jpeg"}

        def json(self):
            # First POST creates the media container, second publishes it.
            if calls[-1].endswith("/media_publish"):
                return {"id": "17895625368091450"}
            if calls[-1].endswith("/media"):
                return {"id": "17841405822304914"}
            if "fields=permalink" in calls[-1]:
                return {"permalink": "https://www.instagram.com/p/REALSHORTCODE/"}
            return {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a, **kw):
            return False

        async def post(self, url, data=None, params=None):
            calls.append(str(url))
            post_bodies.append(data or {})
            return _FakeResponse()

        async def get(self, url, params=None):
            calls.append(str(url) + (("?" + "&".join(f"{k}={v}" for k, v in (params or {}).items())) if params else ""))
            return _FakeResponse()

    class _FakeSettings:
        PUBLIC_BASE_URL = "https://contentai.example.com"

    import app.social.providers.instagram as instagram_mod
    monkeypatch.setattr(instagram_mod, "settings", _FakeSettings())
    monkeypatch.setattr(instagram_mod.httpx, "AsyncClient", _FakeAsyncClient)

    provider = InstagramProvider()

    async def _no_poll(*args, **kwargs):
        return None

    # Skip the media-status polling (it needs network responses).
    provider._wait_media_ready = _no_poll

    account = SocialAccount(
        id=1, user_id=1, platform="instagram", account_type="creator",
        platform_user_id="17841405822304914", username="testuser",
        access_token="ig-token",
    )
    payload = PostPayload(
        caption="Hello world",
        hashtags="#test",
        media_path="uploads/pic.jpg",
        media_type="image",
    )

    result = asyncio.run(provider.publish_post(account, payload))

    assert result.success is True
    assert result.platform_post_id == "17895625368091450"
    assert result.platform_url == "https://www.instagram.com/p/REALSHORTCODE/"
    assert any("/media_publish" in c for c in calls)
    assert any("/media" in c for c in calls)
    assert post_bodies[0]["image_url"] == "https://contentai.example.com/uploads/pic.jpg"
    assert "Hello world" in post_bodies[0]["caption"]


def test_instagram_publish_rejects_localhost_media_url(monkeypatch):
    """Publishing with a localhost PUBLIC_BASE_URL must fail before calling the API."""
    import asyncio
    from app.social.base import PostPayload, SocialAccount

    class _FakeSettings:
        PUBLIC_BASE_URL = "http://localhost:8000"

    import app.social.providers.instagram as instagram_mod
    monkeypatch.setattr(instagram_mod, "settings", _FakeSettings())

    provider = InstagramProvider()
    account = SocialAccount(
        id=1, user_id=1, platform="instagram", account_type="creator",
        platform_user_id="17841405822304914", username="testuser",
        access_token="ig-token",
    )
    payload = PostPayload(
        caption="Hello world",
        media_path="uploads/pic.jpg",
        media_type="image",
    )

    result = asyncio.run(provider.publish_post(account, payload))

    assert result.success is False
    assert "not publicly accessible" in result.error_message


def test_publish_now_rejects_other_users_account(auth_client, client):
    """A scheduled post must not publish through another user's social account."""
    from datetime import datetime, timezone
    from tests.conftest import TestSessionLocal
    from app.models.social import SocialAccount, ScheduledPost
    from app.core.security import encrypt_token

    # User B (second registration) owns an Instagram account.
    client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "testpass123"},
    )
    other_login = client.post(
        "/api/auth/login",
        json={"email": "other@example.com", "password": "testpass123"},
    ).json()
    other_headers = {"Authorization": f"Bearer {other_login['access_token']}"}

    db = TestSessionLocal()
    try:
        from app.models.user import User
        user_a = db.query(User).filter(User.email == "test@example.com").first()
        user_b = db.query(User).filter(User.email == "other@example.com").first()

        other_account = SocialAccount(
            user_id=user_b.id,
            platform="instagram",
            account_type="business",
            platform_user_id="real_account_b",
            username="user_b_ig",
            access_token=encrypt_token("b-token"),
            is_active=True,
        )
        db.add(other_account)
        db.flush()

        scheduled = ScheduledPost(
            user_id=user_a.id,
            account_id=other_account.id,
            caption="Borrowed account test",
            media_path="uploads/pic.jpg",
            media_type="image",
            scheduled_at=datetime.now(timezone.utc),
            status="scheduled",
        )
        db.add(scheduled)
        db.commit()
        scheduled_id = scheduled.id
    finally:
        db.close()

    resp = auth_client.post(f"/api/social/schedule/{scheduled_id}/publish-now")
    assert resp.status_code == 403
    assert "does not belong" in resp.json()["detail"]


def test_post_now_rejects_expired_token(auth_client):
    """Publishing with an expired stored token must return a reconnect message."""
    from datetime import datetime, timedelta, timezone
    from tests.conftest import TestSessionLocal
    from app.models.social import SocialAccount
    from app.core.security import encrypt_token

    db = TestSessionLocal()
    try:
        acc = SocialAccount(
            user_id=1,
            platform="instagram",
            account_type="business",
            platform_user_id="real_account_expired",
            username="expired_user",
            access_token=encrypt_token("expired-token"),
            token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            is_active=True,
        )
        db.add(acc)
        db.commit()
        acc_id = acc.id
    finally:
        db.close()

    resp = auth_client.post(
        "/api/social/post-now",
        json={"account_id": acc_id, "caption": "Hi", "media_type": "image"},
    )
    assert resp.status_code == 400
    assert "Instagram connection expired. Please reconnect Instagram." in resp.json()["detail"]


def test_scheduler_awaits_async_provider_publish(monkeypatch):
    """The scheduler must await the async provider so scheduled posts actually publish."""
    import asyncio
    from datetime import datetime, timezone
    from app.models.social import SocialAccount, ScheduledPost
    from app.social.base import PublishResult, PlatformType
    from app.core.security import encrypt_token
    from tests.conftest import TestSessionLocal

    calls = []

    class _MockProvider:
        platform = PlatformType.INSTAGRAM

        def supports_publishing(self, account_type):
            return True

        async def publish_post(self, account, payload):
            calls.append("published")
            return PublishResult(
                success=True,
                platform_post_id="REAL_MEDIA_123",
                platform_url="https://www.instagram.com/p/REALSHORT/",
            )

    monkeypatch.setattr("app.services.scheduler.get_provider", lambda platform: _MockProvider())

    db = TestSessionLocal()
    try:
        account = SocialAccount(
            user_id=1,
            platform="instagram",
            account_type="business",
            platform_user_id="real_account_sched",
            username="sched_user",
            access_token=encrypt_token("sched-token"),
            is_active=True,
        )
        db.add(account)
        db.flush()
        post = ScheduledPost(
            user_id=1,
            account_id=account.id,
            caption="Scheduled caption",
            media_path="uploads/pic.jpg",
            media_type="image",
            scheduled_at=datetime.now(timezone.utc),
            status="scheduled",
        )
        db.add(post)
        db.commit()
        post_id = post.id
    finally:
        db.close()

    import app.services.scheduler as scheduler_mod
    from app.services.scheduler import _publish_scheduled_post

    db2 = TestSessionLocal()
    try:
        post = db2.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        result = asyncio.run(_publish_scheduled_post(db2, post))
        db2.refresh(post)
        assert result is True
        assert post.status == "published"
        assert post.platform_post_id == "REAL_MEDIA_123"
        assert calls == ["published"]
    finally:
        db2.close()
