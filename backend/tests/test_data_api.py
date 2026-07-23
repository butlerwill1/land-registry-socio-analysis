from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.rate_limit import FixedWindowRateLimiter


def test_health_reports_loaded_data_and_database(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dataLoaded": True,
        "database": "ok",
    }


def test_anonymous_user_has_free_entitlement(client: TestClient) -> None:
    response = client.get("/api/account/entitlements")
    assert response.status_code == 200
    assert response.json()["plan"] == "free"
    assert response.json()["authenticated"] is False


def test_development_identity_can_preview_pro(
    client: TestClient, pro_headers: dict[str, str]
) -> None:
    response = client.get("/api/account/entitlements", headers=pro_headers)
    assert response.status_code == 200
    assert response.json()["plan"] == "pro"
    assert "lsoa_detail" in response.json()["features"]


def test_free_district_response_contains_no_premium_data(client: TestClient) -> None:
    body = client.get("/api/data/districts/SW11").json()
    assert [item["year"] for item in body["history"]] == [2021, 2022, 2023, 2024, 2025]
    assert body["income"] is None
    assert body["percentiles"] is None


def test_pro_district_response_is_scoped_to_one_district(
    client: TestClient, pro_headers: dict[str, str]
) -> None:
    response = client.get("/api/data/districts/SW11", headers=pro_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["district"] == "SW11"
    assert len(body["history"]) == 7
    assert body["income"] == 0.2
    assert body["percentiles"]["overall"] == 0


def test_unknown_district_returns_404(client: TestClient) -> None:
    response = client.get("/api/data/districts/ZZ99")
    assert response.status_code == 404
    assert "Unknown postcode district" in response.json()["error"]


def test_free_user_cannot_request_premium_map_metric(client: TestClient) -> None:
    response = client.get("/api/data/map?metric=income&year=2025")
    assert response.status_code == 403
    assert "requires the Pro plan" in response.json()["error"]


def test_free_user_cannot_request_old_year(client: TestClient) -> None:
    response = client.get("/api/data/map?metric=medianPrice&year=2020")
    assert response.status_code == 422
    assert "not available" in response.json()["error"]


def test_pro_user_can_request_one_map_cross_section(
    client: TestClient, pro_headers: dict[str, str]
) -> None:
    response = client.get(
        "/api/data/map?metric=income&year=2020", headers=pro_headers
    )
    assert response.status_code == 200
    assert response.json() == {
        "metric": "income",
        "year": 2020,
        "plan": "pro",
        "values": [
            {"district": "SW11", "value": 0.2},
            {"district": "E8", "value": 0.3},
        ],
    }


def test_lsoa_endpoint_requires_pro(client: TestClient) -> None:
    response = client.get("/api/data/lsoas/SW11?metric=overall")
    assert response.status_code == 403


def test_lsoa_endpoint_returns_only_selected_included_features(
    client: TestClient, pro_headers: dict[str, str]
) -> None:
    response = client.get(
        "/api/data/lsoas/SW11?metric=overall", headers=pro_headers
    )
    assert response.status_code == 200
    assert len(response.json()["features"]) == 1
    assert response.json()["features"][0]["properties"]["value"] == 10


def test_invalid_metric_is_rejected_without_reaching_repository(client: TestClient) -> None:
    response = client.get("/api/data/map?metric=not-a-metric&year=2025")
    assert response.status_code == 422
    assert response.json()["error"] == "The request was invalid."


def test_data_rate_limit_returns_429(
    settings, repository, billing_gateway, pro_headers
) -> None:
    app = create_app(
        settings=settings,
        repository=repository,
        billing_gateway=billing_gateway,
        rate_limiter=FixedWindowRateLimiter(2, 60),
    )
    with TestClient(app) as limited_client:
        assert limited_client.get("/api/data/districts/SW11", headers=pro_headers).status_code == 200
        assert limited_client.get("/api/data/districts/E8", headers=pro_headers).status_code == 200
        response = limited_client.get("/api/data/districts/SW11", headers=pro_headers)
    assert response.status_code == 429
    assert response.headers["Retry-After"]
