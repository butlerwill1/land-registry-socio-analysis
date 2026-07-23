from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Subscription, upsert_user
from app.entitlements import resolve_plan
from app.schemas import Principal


def test_malformed_authorization_header_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/account/entitlements", headers={"Authorization": "Basic abc"}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_bearer_token_requires_oidc_configuration(client: TestClient) -> None:
    response = client.get(
        "/api/account/entitlements", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 503
    assert response.json()["error"] == "Authentication is not configured."


def test_active_and_trialing_subscriptions_grant_pro(client: TestClient) -> None:
    engine = client.app.state.engine
    with Session(engine) as session:
        user = upsert_user(session, "paid-user", "paid@example.test")
        session.add(
            Subscription(
                user_id=user.id,
                stripe_subscription_id="sub_paid",
                stripe_price_id="price_month",
                status="active",
            )
        )
        session.commit()
        assert resolve_plan(
            session,
            Principal(subject="paid-user", authenticated=True),
            client.app.state.settings,
        ) == "pro"
        subscription = session.query(Subscription).filter_by(user_id=user.id).one()
        subscription.status = "trialing"
        session.commit()
        assert resolve_plan(
            session,
            Principal(subject="paid-user", authenticated=True),
            client.app.state.settings,
        ) == "pro"


def test_cancelled_and_past_due_subscriptions_are_free(client: TestClient) -> None:
    engine = client.app.state.engine
    with Session(engine) as session:
        user = upsert_user(session, "cancelled-user", None)
        subscription = Subscription(
            user_id=user.id,
            stripe_subscription_id="sub_cancelled",
            status="cancelled",
        )
        session.add(subscription)
        session.commit()
        principal = Principal(subject="cancelled-user", authenticated=True)
        assert resolve_plan(session, principal, client.app.state.settings) == "free"
        subscription.status = "past_due"
        session.commit()
        assert resolve_plan(session, principal, client.app.state.settings) == "free"


def test_active_subscription_with_unrecognised_price_is_free(client: TestClient) -> None:
    engine = client.app.state.engine
    with Session(engine) as session:
        user = upsert_user(session, "wrong-price-user", None)
        session.add(
            Subscription(
                user_id=user.id,
                stripe_subscription_id="sub_wrong_price",
                stripe_price_id="price_unrelated",
                status="active",
            )
        )
        session.commit()
        assert (
            resolve_plan(
                session,
                Principal(subject="wrong-price-user", authenticated=True),
                client.app.state.settings,
            )
            == "free"
        )


def test_any_eligible_active_subscription_grants_pro(client: TestClient) -> None:
    engine = client.app.state.engine
    with Session(engine) as session:
        user = upsert_user(session, "multi-sub-user", None)
        session.add_all(
            [
                Subscription(
                    user_id=user.id,
                    stripe_subscription_id="sub_old",
                    stripe_price_id="price_month",
                    status="canceled",
                ),
                Subscription(
                    user_id=user.id,
                    stripe_subscription_id="sub_current",
                    stripe_price_id="price_year",
                    status="active",
                ),
            ]
        )
        session.commit()
        assert (
            resolve_plan(
                session,
                Principal(subject="multi-sub-user", authenticated=True),
                client.app.state.settings,
            )
            == "pro"
        )
