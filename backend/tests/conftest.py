from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.data_repository import DataRepository
from app.main import create_app
from app.rate_limit import FixedWindowRateLimiter


def district_record(code: str, offset: int = 0) -> dict[str, Any]:
    return {
        "district": code,
        "areaName": f"Area {code}",
        "hasSocioeconomicSummary": True,
        "lsoaCount": 1,
        "excludedLsoaCount": 1,
        "meanOverlapShare": 0.98,
        "areaKm2": 4.5,
        "population": 10_000 + offset,
        "populationDensity": 2_000 + offset,
        "overall": 20 + offset,
        "income": round(0.2 + offset / 100, 2),
        "employment": round(0.1 + offset / 100, 2),
        "education": 12 + offset,
        "health": round(-0.2 + offset / 100, 2),
        "crime": round(0.3 + offset / 100, 2),
        "housingBarriers": 18 + offset,
        "environment": 30 + offset,
        "history": [
            {
                "year": year,
                "transactions": 100 + year - 2020 + offset,
                "averagePrice": 400_000 + (year - 2020) * 10_000 + offset,
                "medianPrice": 390_000 + (year - 2020) * 10_000 + offset,
            }
            for year in range(2020, 2027)
        ],
    }


def write_test_data(data_dir: Path) -> None:
    data_dir.mkdir(parents=True)
    metadata = {
        "generatedFrom": {"transactions": "test.csv"},
        "dataAsOf": "2026-01-30",
        "boundarySource": "Test boundaries",
        "boundarySources": [
            {
                "name": "Test",
                "role": "tests",
                "url": "https://example.test",
                "licence": "Test licence",
            }
        ],
        "boundaryMethod": "Test method",
        "boundarySourceRetrievedOn": "2026-01-01",
        "centralBoundaryCoverageShare": 1,
        "centralBoundaryDistrictMatchShare": 1,
        "districtCount": 2,
        "lsoaCount": 3,
        "years": list(range(2020, 2027)),
        "latestCompleteYear": 2025,
        "latestYear": 2026,
        "latestYearIsPartial": True,
        "transactionCount": 2_000,
    }
    lsoa_features = [
        {
            "type": "Feature",
            "id": "E01000001",
            "properties": {
                "lsoaCode": "E01000001",
                "lsoaName": "Test 001",
                "district": "SW11",
                "overlapShare": 1,
                "assignmentConfidence": "high",
                "includedInDistrictSummary": True,
                "overall": 10,
                "income": 0.1,
                "employment": 0.2,
                "education": 11,
                "health": -0.3,
                "crime": 0.4,
                "housingBarriers": 20,
                "environment": 30,
                "population": 1_500,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]],
            },
        },
        {
            "type": "Feature",
            "id": "E01000002",
            "properties": {
                "lsoaCode": "E01000002",
                "lsoaName": "Excluded",
                "district": "SW11",
                "overlapShare": 0.6,
                "assignmentConfidence": "medium",
                "includedInDistrictSummary": False,
                "overall": 99,
                "income": 0.9,
                "employment": 0.9,
                "education": 99,
                "health": 2,
                "crime": 2,
                "housingBarriers": 99,
                "environment": 99,
                "population": 1_500,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]],
            },
        },
        {
            "type": "Feature",
            "id": "E01000003",
            "properties": {
                "lsoaCode": "E01000003",
                "lsoaName": "Other district",
                "district": "E8",
                "overlapShare": 1,
                "assignmentConfidence": "high",
                "includedInDistrictSummary": True,
                "overall": 30,
                "income": 0.3,
                "employment": 0.3,
                "education": 30,
                "health": 0,
                "crime": 0.5,
                "housingBarriers": 40,
                "environment": 50,
                "population": 1_500,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]],
            },
        },
    ]
    (data_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (data_dir / "districts.private.json").write_text(
        json.dumps([district_record("SW11"), district_record("E8", 10)]),
        encoding="utf-8",
    )
    (data_dir / "lsoa.private.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": lsoa_features}),
        encoding="utf-8",
    )


class FakeBillingGateway:
    def __init__(self) -> None:
        self.customers: list[tuple[str | None, str]] = []
        self.checkouts: list[dict[str, str]] = []
        self.portals: list[dict[str, str]] = []
        self.event: dict[str, Any] | None = None
        self.current_subscription: dict[str, Any] | None = None
        self.subscription_retrievals: list[str] = []
        self.construct_error: Exception | None = None

    def create_customer(self, email: str | None, user_id: str) -> str:
        self.customers.append((email, user_id))
        return "cus_test"

    def create_checkout(self, **kwargs: str) -> str:
        self.checkouts.append(kwargs)
        return "https://checkout.stripe.test/session"

    def create_portal(self, **kwargs: str) -> str:
        self.portals.append(kwargs)
        return "https://billing.stripe.test/portal"

    def construct_event(self, payload: bytes, signature: str) -> dict[str, Any]:
        if self.construct_error:
            raise self.construct_error
        if self.event is None:
            raise ValueError("No event configured")
        return self.event

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        self.subscription_retrievals.append(subscription_id)
        if self.current_subscription is not None:
            return self.current_subscription
        if self.event is None:
            raise ValueError("No subscription configured")
        return self.event["data"]["object"]


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    write_test_data(path)
    return path


@pytest.fixture
def repository(data_dir: Path) -> DataRepository:
    value = DataRepository(data_dir)
    value.load()
    return value


@pytest.fixture
def settings(tmp_path: Path, data_dir: Path) -> Settings:
    return Settings(
        app_env="test",
        data_dir=data_dir,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        allow_dev_entitlements=True,
        pro_access_code=SecretStr("friend-code"),
        pro_access_signing_secret=SecretStr("test-signing-secret-that-is-at-least-32-characters"),
        pro_access_expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        stripe_secret_key=SecretStr("sk_test_example"),
        stripe_webhook_secret=SecretStr("whsec_example"),
        stripe_monthly_price_id="price_month",
        stripe_yearly_price_id="price_year",
        data_rate_limit_requests=100,
    )


@pytest.fixture
def billing_gateway() -> FakeBillingGateway:
    return FakeBillingGateway()


@pytest.fixture
def client(
    settings: Settings,
    repository: DataRepository,
    billing_gateway: FakeBillingGateway,
) -> TestClient:
    app = create_app(
        settings=settings,
        repository=repository,
        billing_gateway=billing_gateway,
        rate_limiter=FixedWindowRateLimiter(100, 60),
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def pro_headers() -> dict[str, str]:
    return {
        "X-Dev-Plan": "pro",
        "X-Dev-User": "test-user",
        "X-Dev-Email": "user@example.test",
    }


@pytest.fixture
def free_headers() -> dict[str, str]:
    return {"X-Dev-Plan": "free", "X-Dev-User": "test-user"}
