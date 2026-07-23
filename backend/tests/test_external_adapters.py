from __future__ import annotations

from types import SimpleNamespace

import jwt
import pytest
import stripe
from pydantic import SecretStr

from app.auth import OidcTokenVerifier
from app.billing import BillingNotConfiguredError, StripeBillingGateway
from app.config import Settings


def oidc_settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        data_dir=tmp_path,
        oidc_issuer="https://issuer.example.test",
        oidc_audience="atlas-api",
        oidc_jwks_url="https://issuer.example.test/.well-known/jwks.json",
    )


def stripe_settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        data_dir=tmp_path,
        stripe_secret_key=SecretStr("sk_test_example"),
        stripe_webhook_secret=SecretStr("whsec_example"),
        stripe_monthly_price_id="price_month",
        stripe_yearly_price_id="price_year",
    )


def test_oidc_verifier_uses_jwks_issuer_and_audience(monkeypatch, tmp_path) -> None:
    settings = oidc_settings(tmp_path)
    verifier = OidcTokenVerifier(settings)
    verifier._client = SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key="public-key")
    )
    captured = {}

    def fake_decode(token, key, **kwargs):
        captured.update({"token": token, "key": key, **kwargs})
        return {"sub": "user-1", "email": "person@example.test"}

    monkeypatch.setattr("app.auth.jwt.decode", fake_decode)
    assert verifier.verify("signed-token")["sub"] == "user-1"
    assert captured["audience"] == "atlas-api"
    assert captured["issuer"] == "https://issuer.example.test"
    assert captured["algorithms"] == ["RS256"]


def test_oidc_verifier_rejects_expired_token(monkeypatch, tmp_path) -> None:
    verifier = OidcTokenVerifier(oidc_settings(tmp_path))
    verifier._client = SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key="public-key")
    )

    def expired(*args, **kwargs):
        raise jwt.ExpiredSignatureError()

    monkeypatch.setattr("app.auth.jwt.decode", expired)
    with pytest.raises(Exception) as error:
        verifier.verify("expired")
    assert error.value.status_code == 401


def test_disabled_stripe_gateway_fails_closed(tmp_path) -> None:
    gateway = StripeBillingGateway(
        Settings(app_env="test", data_dir=tmp_path, allow_dev_entitlements=True)
    )
    with pytest.raises(BillingNotConfiguredError):
        gateway.create_customer("person@example.test", "user-1")


def test_stripe_gateway_creates_customer_checkout_and_portal(
    monkeypatch, tmp_path
) -> None:
    gateway = StripeBillingGateway(stripe_settings(tmp_path))
    calls = {}
    monkeypatch.setattr(
        stripe.Customer,
        "create",
        lambda **kwargs: calls.setdefault("customer", SimpleNamespace(id="cus_1")),
    )

    def create_checkout(**kwargs):
        calls["checkout"] = kwargs
        return SimpleNamespace(url="https://checkout.stripe.test/session")

    def create_portal(**kwargs):
        calls["portal"] = kwargs
        return SimpleNamespace(url="https://billing.stripe.test/portal")

    monkeypatch.setattr(stripe.checkout.Session, "create", create_checkout)
    monkeypatch.setattr(stripe.billing_portal.Session, "create", create_portal)

    assert gateway.create_customer("person@example.test", "user-1") == "cus_1"
    assert (
        gateway.create_checkout(
            customer_id="cus_1",
            user_id="user-1",
            price_id="price_month",
            success_url="https://example.test/success",
            cancel_url="https://example.test/cancel",
        )
        == "https://checkout.stripe.test/session"
    )
    assert calls["checkout"]["mode"] == "subscription"
    assert calls["checkout"]["line_items"] == [{"price": "price_month", "quantity": 1}]
    assert calls["checkout"]["subscription_data"]["metadata"]["user_id"] == "user-1"
    assert (
        gateway.create_portal(
            customer_id="cus_1", return_url="https://example.test/account"
        )
        == "https://billing.stripe.test/portal"
    )


def test_stripe_gateway_rejects_checkout_without_url(monkeypatch, tmp_path) -> None:
    gateway = StripeBillingGateway(stripe_settings(tmp_path))
    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        lambda **kwargs: SimpleNamespace(url=None),
    )
    with pytest.raises(RuntimeError, match="Checkout URL"):
        gateway.create_checkout(
            customer_id="cus_1",
            user_id="user-1",
            price_id="price_month",
            success_url="https://example.test/success",
            cancel_url="https://example.test/cancel",
        )


def test_stripe_gateway_verifies_raw_webhook(monkeypatch, tmp_path) -> None:
    gateway = StripeBillingGateway(stripe_settings(tmp_path))
    captured = {}

    class Event:
        def to_dict_recursive(self):
            return {"id": "evt_1", "type": "invoice.paid", "data": {"object": {}}}

    def construct(payload, signature, secret):
        captured.update(
            {"payload": payload, "signature": signature, "secret": secret}
        )
        return Event()

    monkeypatch.setattr(stripe.Webhook, "construct_event", construct)
    event = gateway.construct_event(b'{"id":"evt_1"}', "signature")
    assert event["id"] == "evt_1"
    assert captured == {
        "payload": b'{"id":"evt_1"}',
        "signature": "signature",
        "secret": "whsec_example",
    }


def test_stripe_gateway_retrieves_current_subscription(monkeypatch, tmp_path) -> None:
    gateway = StripeBillingGateway(stripe_settings(tmp_path))

    class Subscription:
        def to_dict_recursive(self):
            return {"id": "sub_1", "status": "active"}

    monkeypatch.setattr(
        stripe.Subscription,
        "retrieve",
        lambda subscription_id: Subscription(),
    )
    assert gateway.retrieve_subscription("sub_1") == {
        "id": "sub_1",
        "status": "active",
    }
