import os

os.environ["RATE_LIMIT_ENABLED"] = "false"
# Demo-mode tests exercise the simulated OAuth/publish flow. The project .env
# keeps SOCIAL_DEMO_MODE=false for real Instagram testing; tests opt into demo
# mode here. Environment variables take precedence over the .env file.
os.environ["SOCIAL_DEMO_MODE"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_contentai.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """Register a user and return authenticated client."""
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def admin_client(client):
    """Login as admin and return authenticated client."""
    from app.core.security import hash_password
    from app.models.user import User
    db = TestSessionLocal()
    admin = User(email="admin@test.com", password_hash=hash_password("admin123"), is_admin=True)
    db.add(admin)
    db.commit()
    db.close()

    resp = client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
    )
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
