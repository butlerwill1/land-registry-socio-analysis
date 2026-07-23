from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas import DistrictRecord

from .conftest import district_record


def test_development_entitlement_headers_are_disabled_by_default(tmp_path: Path) -> None:
    settings = Settings(app_env="test", data_dir=tmp_path)
    assert settings.allow_dev_entitlements is False


def test_production_rejects_development_entitlements(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Development entitlements"):
        Settings(
            app_env="production",
            allow_dev_entitlements=True,
            data_dir=tmp_path,
        )


def test_partial_oidc_configuration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="configured together"):
        Settings(
            app_env="test",
            data_dir=tmp_path,
            oidc_issuer="https://issuer.example.test",
        )


def test_partial_stripe_configuration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Stripe settings"):
        Settings(
            app_env="test",
            data_dir=tmp_path,
            stripe_monthly_price_id="price_month",
        )


def test_partial_pro_access_code_configuration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Pro access code"):
        Settings(
            app_env="test",
            data_dir=tmp_path,
            pro_access_code="friend-code",
        )


def test_short_pro_access_signing_secret_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            app_env="test",
            data_dir=tmp_path,
            pro_access_code="friend-code",
            pro_access_signing_secret="too-short",
            pro_access_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )


def test_pro_access_code_requires_a_timezone_aware_expiry(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="expiry"):
        Settings(
            app_env="test",
            data_dir=tmp_path,
            pro_access_code="friend-code",
            pro_access_signing_secret="a-signing-secret-that-is-at-least-32-characters",
        )
    with pytest.raises(ValidationError, match="timezone"):
        Settings(
            app_env="test",
            data_dir=tmp_path,
            pro_access_code="friend-code",
            pro_access_signing_secret="a-signing-secret-that-is-at-least-32-characters",
            pro_access_expires_at=datetime.now(),
        )


def test_district_history_must_be_sorted_and_unique() -> None:
    payload = district_record("SW11")
    payload["history"] = [payload["history"][1], payload["history"][0]]
    with pytest.raises(ValidationError, match="unique and sorted"):
        DistrictRecord.model_validate(payload)


def test_invalid_postcode_district_is_rejected() -> None:
    payload = district_record("SW11")
    payload["district"] = "../../etc"
    with pytest.raises(ValidationError, match="at most 5 characters"):
        DistrictRecord.model_validate(payload)


def test_generated_public_bundle_contains_only_free_data() -> None:
    project_root = Path(__file__).resolve().parents[2]
    public_records = json.loads(
        (project_root / "web" / "public" / "data" / "districts.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(public_records) == 314
    allowed_years = {2021, 2022, 2023, 2024, 2025}
    assert all(len(record["history"]) <= 5 for record in public_records)
    assert {
        item["year"] for record in public_records for item in record["history"]
    } == allowed_years
    sw11 = next(record for record in public_records if record["district"] == "SW11")
    assert {item["year"] for item in sw11["history"]} == allowed_years
    for record in public_records:
        assert record["income"] is None
        assert record["populationDensity"] is None
        assert record["environment"] is None
    assert not (project_root / "web" / "public" / "data" / "lsoa-boundaries.geojson").exists()
