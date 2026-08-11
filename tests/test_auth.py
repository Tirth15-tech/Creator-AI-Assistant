class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "ContentAI"


class TestAuth:
    def test_register(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "pass1234"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert "id" in data

    def test_register_duplicate(self, client):
        client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "pass1234"},
        )
        resp = client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "pass1234"},
        )
        assert resp.status_code == 400

    def test_login(self, client):
        client.post(
            "/api/auth/register",
            json={"email": "login@example.com", "password": "pass1234"},
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "pass1234"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post(
            "/api/auth/register",
            json={"email": "wrong@example.com", "password": "pass1234"},
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": "wrong@example.com", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    def test_get_me(self, auth_client):
        resp = auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"

    def test_refresh_token(self, client):
        client.post(
            "/api/auth/register",
            json={"email": "refresh@example.com", "password": "pass1234"},
        )
        login_resp = client.post(
            "/api/auth/login",
            json={"email": "refresh@example.com", "password": "pass1234"},
        )
        refresh_token = login_resp.json()["refresh_token"]
        resp = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_unauthorized_access(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestPages:
    def test_landing_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_login_page(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_register_page(self, client):
        resp = client.get("/register")
        assert resp.status_code == 200


class TestAdmin:
    def test_admin_stats(self, admin_client):
        resp = admin_client.get("/api/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "total_posts" in data

    def test_admin_users(self, admin_client):
        resp = admin_client.get("/api/admin/users")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_admin_required(self, auth_client):
        resp = auth_client.get("/api/admin/stats")
        assert resp.status_code == 403
