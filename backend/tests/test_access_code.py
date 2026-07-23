from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.auth import ProAccessCodeService
from app.main import create_app
from app.rate_limit import FixedWindowRateLimiter


def test_valid_access_code_sets_cookie_and_grants_pro(client: TestClient) -> None:
    response = client.post("/api/account/access-code", json={"code": "friend-code"})
    assert response.status_code == 200
    assert response.json()["plan"] == "pro"
    assert response.json()["authenticated"] is False
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "expires=" in response.headers["set-cookie"].lower()

    entitlement = client.get("/api/account/entitlements")
    assert entitlement.json()["plan"] == "pro"
    premium = client.get("/api/data/map?metric=income&year=2025")
    assert premium.status_code == 200
    client.cookies.clear()
    assert client.get("/api/data/map?metric=income&year=2025").status_code == 403


def test_rotating_access_code_revokes_existing_cookie(
    settings, repository, billing_gateway
) -> None:
    app = create_app(
        settings=settings,
        repository=repository,
        billing_gateway=billing_gateway,
    )
    with TestClient(app) as client:
        assert client.post("/api/account/access-code", json={"code": "friend-code"}).status_code == 200
        rotated_settings = settings.model_copy(
            update={"pro_access_code": SecretStr("new-friend-code")}
        )
        app.state.settings = rotated_settings
        app.state.pro_access_code_service = ProAccessCodeService(rotated_settings)
        assert client.get("/api/account/entitlements").json()["plan"] == "free"


def test_invalid_access_code_never_sets_a_cookie(client: TestClient) -> None:
    response = client.post("/api/account/access-code", json={"code": "wrong-code"})
    assert response.status_code == 401
    assert response.json()["error"] == "That access code is not valid."
    assert "set-cookie" not in response.headers
    assert client.get("/api/account/entitlements").json()["plan"] == "free"


def test_expired_access_cookie_is_free(client: TestClient) -> None:
    expired = jwt.encode(
        {
            "scope": "pro_access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        "test-signing-secret-that-is-at-least-32-characters",
        algorithm="HS256",
    )
    client.cookies.set("atlas_pro_access", expired)
    assert client.get("/api/account/entitlements").json()["plan"] == "free"


def test_expired_access_code_is_rejected_without_taking_down_the_api(
    settings, repository, billing_gateway
) -> None:
    expired_settings = settings.model_copy(
        update={"pro_access_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
    )
    app = create_app(
        settings=expired_settings,
        repository=repository,
        billing_gateway=billing_gateway,
    )
    with TestClient(app) as client:
        response = client.post("/api/account/access-code", json={"code": "friend-code"})
        health = client.get("/api/health")
    assert response.status_code == 410
    assert response.json()["error"] == "This access code has expired."
    assert "set-cookie" not in response.headers
    assert health.status_code == 200


def test_access_code_can_be_disabled(settings, repository, billing_gateway) -> None:
    disabled_settings = settings.model_copy(
        update={"pro_access_code": None, "pro_access_signing_secret": None}
    )
    app = create_app(
        settings=disabled_settings,
        repository=repository,
        billing_gateway=billing_gateway,
    )
    with TestClient(app) as client:
        response = client.post("/api/account/access-code", json={"code": "friend-code"})
    assert response.status_code == 404


def test_production_access_cookie_is_secure(settings, repository, billing_gateway) -> None:
    production_settings = settings.model_copy(update={"app_env": "production"})
    app = create_app(
        settings=production_settings,
        repository=repository,
        billing_gateway=billing_gateway,
    )
    with TestClient(app) as client:
        response = client.post("/api/account/access-code", json={"code": "friend-code"})
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_access_code_attempts_are_rate_limited(settings, repository, billing_gateway) -> None:
    limited_settings = settings.model_copy(
        update={"pro_access_rate_limit_requests": 1, "pro_access_rate_limit_window_seconds": 60}
    )
    app = create_app(
        settings=limited_settings,
        repository=repository,
        billing_gateway=billing_gateway,
        rate_limiter=FixedWindowRateLimiter(100, 60),
    )
    with TestClient(app) as client:
        assert client.post("/api/account/access-code", json={"code": "wrong"}).status_code == 401
        response = client.post("/api/account/access-code", json={"code": "wrong"})
    assert response.status_code == 429
    assert response.headers["Retry-After"]
