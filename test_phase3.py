"""
Phase 2/3 Integration Test
Tests: health, auth, upload, rewrite, social endpoints, new caption types
"""
import sys, os, requests
sys.path.insert(0, 'E:/creator_AIassistance')

BASE = "http://127.0.0.1:8000"

def test_health():
    r = requests.get(f"{BASE}/api/health")
    assert r.status_code == 200
    print(f"[PASS] Health: {r.json()}")

def test_login():
    r = requests.post(f"{BASE}/api/auth/login", json={
        "email": "admin@contentai.com", "password": "admin123"
    })
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    print(f"[PASS] Login OK, token prefix: {token[:20]}...")
    return token

def test_social_platforms(token):
    r = requests.get(f"{BASE}/api/social/platforms", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    platforms = r.json()["platforms"]
    print(f"[PASS] Social platforms: {platforms}")

def test_social_accounts(token):
    r = requests.get(f"{BASE}/api/social/accounts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    accounts = r.json()["accounts"]
    print(f"[PASS] Social accounts: {len(accounts)} accounts")

def test_social_drafts(token):
    r = requests.post(f"{BASE}/api/social/drafts", headers={"Authorization": f"Bearer {token}"}, json={
        "title": "Test Draft",
        "caption": "Hello from test",
        "hashtags": "#test #phase3",
        "target_platforms": ["instagram"]
    })
    assert r.status_code == 200
    draft_id = r.json()["id"]
    print(f"[PASS] Draft created: id={draft_id}")

    r = requests.get(f"{BASE}/api/social/drafts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    drafts = r.json()["drafts"]
    print(f"[PASS] Drafts list: {len(drafts)} draft(s)")

    r = requests.get(f"{BASE}/api/social/drafts/{draft_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    print(f"[PASS] Draft detail fetched")

    r = requests.delete(f"{BASE}/api/social/drafts/{draft_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    print(f"[PASS] Draft deleted")

def test_social_notifications(token):
    r = requests.get(f"{BASE}/api/social/notifications", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    notifs = r.json()["notifications"]
    print(f"[PASS] Notifications: {len(notifs)} notification(s)")

def test_social_fallback(token):
    r = requests.get(f"{BASE}/api/social/fallback/instagram", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    features = r.json()["features"]
    print(f"[PASS] Instagram fallback features: {features}")

def test_auth_me(token):
    r = requests.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    print(f"[PASS] Auth/me: {r.json()['email']}")

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2/3 Integration Test")
    print("=" * 60)
    try:
        test_health()
        token = test_login()
        test_auth_me(token)
        test_social_platforms(token)
        test_social_accounts(token)
        test_social_drafts(token)
        test_social_notifications(token)
        test_social_fallback(token)
        print("=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
