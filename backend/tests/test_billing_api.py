from __future__ import annotations

from typing import Any

import stripe
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import ProcessedWebhook, Subscription, User


def checkout_event(event_id: str = "evt_checkout") -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test",
                "client_reference_id": None,
                "customer": "cus_test",
                "metadata": {},
            }
        },
    }


def subscription_event(
    *,
    event_id: str,
    status: str,
    user_id: str,
    customer_id: str = "cus_test",
    subscription_id: str = "sub_test",
    created: int = 1_700_000_000,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "created": created,
        "data": {
            "object": {
                "id": subscription_id,
                "customer": customer_id,
                "status": status,
                "current_period_end": 1_800_000_000,
                "cancel_at_period_end": False,
                "metadata": {"user_id": user_id},
                "items": {"data": [{"price": {"id": "price_month"}}]},
            }
        },
    }


def test_checkout_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/billing/checkout", json={"plan": "pro", "interval": "month"}
    )
    assert response.status_code == 401


def test_checkout_creates_customer_and_uses_selected_price(
    client: TestClient, free_headers: dict[str, str], billing_gateway
) -> None:
    response = client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "year"},
        headers=free_headers,
    )
    assert response.status_code == 200
    assert response.json()["url"] == "https://checkout.stripe.test/session"
    assert len(billing_gateway.customers) == 1
    assert billing_gateway.checkouts[0]["price_id"] == "price_year"
    assert billing_gateway.checkouts[0]["customer_id"] == "cus_test"

    second = client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    assert second.status_code == 200
    assert len(billing_gateway.customers) == 1
    assert billing_gateway.checkouts[1]["price_id"] == "price_month"


def test_checkout_rejects_client_selected_unknown_plan(
    client: TestClient, free_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/billing/checkout",
        json={"plan": "enterprise", "interval": "month"},
        headers=free_headers,
    )
    assert response.status_code == 422


def test_checkout_sanitises_stripe_service_errors(
    client: TestClient, free_headers: dict[str, str], billing_gateway
) -> None:
    def fail_checkout(**kwargs):
        raise stripe.StripeError("sensitive provider details")

    billing_gateway.create_checkout = fail_checkout
    response = client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    assert response.status_code == 502
    assert response.json()["error"] == "Stripe Checkout is temporarily unavailable."
    assert "sensitive" not in response.text


def test_portal_requires_existing_customer(
    client: TestClient, pro_headers: dict[str, str]
) -> None:
    response = client.post("/api/billing/portal", headers=pro_headers)
    assert response.status_code == 409


def test_portal_returns_short_lived_stripe_url(
    client: TestClient,
    free_headers: dict[str, str],
    billing_gateway,
) -> None:
    client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    response = client.post("/api/billing/portal", headers=free_headers)
    assert response.status_code == 200
    assert response.json()["url"] == "https://billing.stripe.test/portal"
    assert billing_gateway.portals[0]["customer_id"] == "cus_test"


def test_portal_sanitises_stripe_service_errors(
    client: TestClient, free_headers: dict[str, str], billing_gateway
) -> None:
    client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )

    def fail_portal(**kwargs):
        raise stripe.StripeError("sensitive provider details")

    billing_gateway.create_portal = fail_portal
    response = client.post("/api/billing/portal", headers=free_headers)
    assert response.status_code == 502
    assert response.json()["error"] == "The Stripe customer portal is temporarily unavailable."


def test_webhook_requires_signature(client: TestClient) -> None:
    response = client.post("/api/billing/webhook", content=b"{}")
    assert response.status_code == 400


def test_checkout_and_subscription_webhooks_are_idempotent(
    client: TestClient,
    free_headers: dict[str, str],
    billing_gateway,
) -> None:
    client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    with Session(client.app.state.engine) as session:
        user = session.scalar(select(User).where(User.external_subject == "test-user"))
        assert user is not None
        user_id = user.id

    event = checkout_event()
    event["data"]["object"]["client_reference_id"] = user_id
    billing_gateway.event = event
    first = client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    )
    duplicate = client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    )
    assert first.json() == {"received": True, "duplicate": False}
    assert duplicate.json() == {"received": True, "duplicate": True}

    billing_gateway.event = subscription_event(
        event_id="evt_subscription", status="active", user_id=user_id
    )
    subscription_response = client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    )
    assert subscription_response.status_code == 200
    with Session(client.app.state.engine) as session:
        subscription = session.scalar(select(Subscription))
        assert subscription is not None
        assert subscription.status == "active"
        assert subscription.stripe_price_id == "price_month"
        assert session.query(ProcessedWebhook).count() == 2


def test_subscription_deletion_removes_pro_entitlement(
    client: TestClient,
    free_headers: dict[str, str],
    billing_gateway,
) -> None:
    client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    with Session(client.app.state.engine) as session:
        user = session.scalar(select(User).where(User.external_subject == "test-user"))
        assert user is not None
        user_id = user.id

    billing_gateway.event = subscription_event(
        event_id="evt_active", status="active", user_id=user_id
    )
    client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    )
    billing_gateway.event = subscription_event(
        event_id="evt_deleted",
        status="canceled",
        user_id=user_id,
        created=1_700_000_001,
    )
    billing_gateway.event["type"] = "customer.subscription.deleted"
    client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    )
    with Session(client.app.state.engine) as session:
        subscription = session.scalar(select(Subscription))
        assert subscription is not None
        assert subscription.status == "canceled"


def test_delayed_active_event_cannot_restore_deleted_subscription(
    client: TestClient,
    free_headers: dict[str, str],
    billing_gateway,
) -> None:
    client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    with Session(client.app.state.engine) as session:
        user = session.scalar(select(User).where(User.external_subject == "test-user"))
        assert user is not None
        user_id = user.id

    billing_gateway.event = subscription_event(
        event_id="evt_deleted_first",
        status="canceled",
        user_id=user_id,
        created=1_700_000_100,
    )
    billing_gateway.event["type"] = "customer.subscription.deleted"
    assert client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    ).status_code == 200

    billing_gateway.event = subscription_event(
        event_id="evt_delayed_active",
        status="active",
        user_id=user_id,
        created=1_700_000_099,
    )
    current = subscription_event(
        event_id="unused",
        status="canceled",
        user_id=user_id,
        created=1_700_000_100,
    )
    billing_gateway.current_subscription = current["data"]["object"]
    assert client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    ).status_code == 200
    with Session(client.app.state.engine) as session:
        subscription = session.scalar(select(Subscription))
        assert subscription is not None
        assert subscription.status == "canceled"


def test_same_second_update_reconciles_from_current_stripe_state(
    client: TestClient,
    free_headers: dict[str, str],
    billing_gateway,
) -> None:
    client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    with Session(client.app.state.engine) as session:
        user = session.scalar(select(User).where(User.external_subject == "test-user"))
        assert user is not None
        user_id = user.id

    billing_gateway.event = subscription_event(
        event_id="evt_same_second_active",
        status="active",
        user_id=user_id,
        created=1_700_000_200,
    )
    assert client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    ).status_code == 200

    stale_event = subscription_event(
        event_id="evt_same_second_stale_payload",
        status="active",
        user_id=user_id,
        created=1_700_000_200,
    )
    current = subscription_event(
        event_id="unused",
        status="past_due",
        user_id=user_id,
        created=1_700_000_200,
    )
    billing_gateway.event = stale_event
    billing_gateway.current_subscription = current["data"]["object"]
    assert client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    ).status_code == 200

    with Session(client.app.state.engine) as session:
        subscription = session.scalar(select(Subscription))
        assert subscription is not None
        assert subscription.status == "past_due"
    assert billing_gateway.subscription_retrievals == ["sub_test", "sub_test"]


def test_old_subscription_deletion_does_not_revoke_new_subscription(
    client: TestClient,
    free_headers: dict[str, str],
    billing_gateway,
) -> None:
    client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    with Session(client.app.state.engine) as session:
        user = session.scalar(select(User).where(User.external_subject == "test-user"))
        assert user is not None
        user_id = user.id

    for event in (
        subscription_event(
            event_id="evt_old_active",
            status="active",
            user_id=user_id,
            subscription_id="sub_old",
            created=1_700_000_000,
        ),
        subscription_event(
            event_id="evt_new_active",
            status="active",
            user_id=user_id,
            subscription_id="sub_new",
            created=1_700_000_010,
        ),
    ):
        billing_gateway.event = event
        client.post(
            "/api/billing/webhook",
            content=b"raw",
            headers={"Stripe-Signature": "valid"},
        )

    billing_gateway.event = subscription_event(
        event_id="evt_old_deleted",
        status="canceled",
        user_id=user_id,
        subscription_id="sub_old",
        created=1_700_000_020,
    )
    billing_gateway.event["type"] = "customer.subscription.deleted"
    client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    )
    with Session(client.app.state.engine) as session:
        statuses = {
            item.stripe_subscription_id: item.status
            for item in session.scalars(select(Subscription)).all()
        }
        assert statuses == {"sub_old": "canceled", "sub_new": "active"}


def test_unknown_subscription_customer_is_rejected_and_not_recorded(
    client: TestClient, billing_gateway
) -> None:
    billing_gateway.event = subscription_event(
        event_id="evt_unknown",
        status="active",
        user_id="missing-user",
        customer_id="cus_missing",
    )
    response = client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    )
    assert response.status_code == 400
    with Session(client.app.state.engine) as session:
        assert session.get(ProcessedWebhook, "evt_unknown") is None


def test_subscription_reconciliation_failure_is_retried(
    client: TestClient,
    free_headers: dict[str, str],
    billing_gateway,
) -> None:
    client.post(
        "/api/billing/checkout",
        json={"plan": "pro", "interval": "month"},
        headers=free_headers,
    )
    with Session(client.app.state.engine) as session:
        user = session.scalar(select(User).where(User.external_subject == "test-user"))
        assert user is not None
        user_id = user.id
    billing_gateway.event = subscription_event(
        event_id="evt_reconcile_failure",
        status="active",
        user_id=user_id,
    )

    def fail_retrieval(subscription_id: str):
        raise stripe.StripeError("provider unavailable")

    billing_gateway.retrieve_subscription = fail_retrieval
    response = client.post(
        "/api/billing/webhook",
        content=b"raw",
        headers={"Stripe-Signature": "valid"},
    )
    assert response.status_code == 502
    assert response.json()["error"] == (
        "Stripe subscription reconciliation is temporarily unavailable."
    )
    with Session(client.app.state.engine) as session:
        assert session.get(ProcessedWebhook, "evt_reconcile_failure") is None
