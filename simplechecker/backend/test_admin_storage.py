import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["SESSION_SECRET"] = "test-secret"
os.environ["COOKIE_STORAGE_PASSWORD"] = "admin-pass"

for db_path in [Path(__file__).resolve().parent / "checked_cookies.db"]:
    if db_path.exists():
        db_path.unlink()

from main import app  # noqa: E402

client = TestClient(app)


def test_admin_store_requires_login():
    payload = {
        "bundle_number": 7,
        "cookies": [{"name": "a", "value": "1", "domain": ".netflix.com"}],
        "account": {"bundle_number": 7, "success": True, "email": "demo@example.com"},
        "token": {"bundle_number": 7, "success": True, "nftoken": "abc"},
    }

    response = client.post("/api/admin/checked-cookies", json=payload)
    assert response.status_code == 403


def test_admin_store_succeeds_after_login():
    login_response = client.post("/api/admin/login", json={"password": "admin-pass"})
    assert login_response.status_code == 200

    payload = {
        "bundle_number": 8,
        "cookies": [{"name": "a", "value": "1", "domain": ".netflix.com"}],
        "account": {"bundle_number": 8, "success": True, "email": "demo@example.com"},
        "token": {"bundle_number": 8, "success": True, "nftoken": "xyz"},
    }

    response = client.post("/api/admin/checked-cookies", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["bundle_number"] == 8

    list_response = client.get("/api/admin/checked-cookies")
    assert list_response.status_code == 200
    assert any(item["id"] for item in list_response.json()["items"])
