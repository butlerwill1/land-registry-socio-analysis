from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

import stripe
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import Settings
from .database import ProcessedWebhook, Subscription, User
from .schemas import BillingInterval


STRIPE_API_VERSION = "2026-02-25.clover"
SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)
SUBSCRIPTION_EVENT_RANK = {
    "customer.subscription.created": 1,
    "customer.subscription.updated": 2,
    "customer.subscription.deleted": 3,
}


class BillingNotConfiguredError(RuntimeError):
    pass


class BillingGateway(Protocol):
    def create_customer(self, email: str | None, user_id: str) -> str: ...

    def create_checkout(
        self,
        *,
        customer_id: str,
        user_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str: ...

    def create_portal(self, *, customer_id: str, return_url: str) -> str: ...

    def construct_event(self, payload: bytes, signature: str) -> dict[str, Any]: ...

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]: ...


class StripeBillingGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        if settings.stripe_secret_key is not None:
            stripe.api_key = settings.stripe_secret_key.get_secret_value()
            stripe.api_version = STRIPE_API_VERSION

    def _require_enabled(self) -> None:
        if not self._settings.billing_enabled:
            raise BillingNotConfiguredError(
                "Stripe billing is not configured for this environment."
            )

    def create_customer(self, email: str | None, user_id: str) -> str:
        self._require_enabled()
        customer = stripe.Customer.create(email=email, metadata={"user_id": user_id})
        return str(customer.id)

    def create_checkout(
        self,
        *,
        customer_id: str,
        user_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        self._require_enabled()
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            client_reference_id=user_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            metadata={"user_id": user_id},
            subscription_data={"metadata": {"user_id": user_id}},
        )
        if not checkout.url:
            raise RuntimeError("Stripe did not return a Checkout URL")
        return str(checkout.url)

    def create_portal(self, *, customer_id: str, return_url: str) -> str:
        self._require_enabled()
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return str(portal.url)

    def construct_event(self, payload: bytes, signature: str) -> dict[str, Any]:
        self._require_enabled()
        if self._settings.stripe_webhook_secret is None:
            raise BillingNotConfiguredError("Stripe webhook signing is not configured.")
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            self._settings.stripe_webhook_secret.get_secret_value(),
        )
        return event.to_dict_recursive()

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        self._require_enabled()
        subscription = stripe.Subscription.retrieve(subscription_id)
        return subscription.to_dict_recursive()


def price_id_for_interval(settings: Settings, interval: BillingInterval) -> str:
    value = (
        settings.stripe_monthly_price_id
        if interval == "month"
        else settings.stripe_yearly_price_id
    )
    if value is None:
        raise BillingNotConfiguredError(
            "Stripe billing is not configured for this environment."
        )
    return value


def process_webhook(
    session: Session,
    event: dict[str, Any],
    billing_gateway: BillingGateway,
) -> bool:
    event_id = _required_string(event, "id")
    event_type = _required_string(event, "type")
    if session.get(ProcessedWebhook, event_id) is not None:
        return True
    session.add(ProcessedWebhook(event_id=event_id, event_type=event_type))
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return True

    data = event.get("data")
    event_object = data.get("object") if isinstance(data, dict) else None
    if not isinstance(event_object, dict):
        raise ValueError("Stripe event has no data object")

    if event_type == "checkout.session.completed":
        _process_checkout_completed(session, event_object)
    elif event_type in SUBSCRIPTION_EVENTS:
        event_created = event.get("created")
        if not isinstance(event_created, int):
            raise ValueError("Subscription event is missing its creation timestamp")
        _process_subscription(
            session,
            event_object,
            event_created=event_created,
            event_rank=SUBSCRIPTION_EVENT_RANK[event_type],
            billing_gateway=billing_gateway,
        )

    session.commit()
    return False


def _process_checkout_completed(session: Session, event_object: dict[str, Any]) -> None:
    user_id = _optional_string(event_object.get("client_reference_id"))
    metadata = event_object.get("metadata")
    if user_id is None and isinstance(metadata, dict):
        user_id = _optional_string(metadata.get("user_id"))
    customer_id = _optional_string(event_object.get("customer"))
    if user_id is None or customer_id is None:
        raise ValueError("Completed Checkout Session is missing user or customer")
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("Completed Checkout Session references an unknown user")
    user.stripe_customer_id = customer_id


def _process_subscription(
    session: Session,
    event_object: dict[str, Any],
    *,
    event_created: int,
    event_rank: int,
    billing_gateway: BillingGateway,
) -> None:
    subscription_id = _required_string(event_object, "id")
    customer_id = _required_string(event_object, "customer")
    user = session.scalar(
        select(User)
        .where(User.stripe_customer_id == customer_id)
        .with_for_update()
    )
    if user is None:
        metadata = event_object.get("metadata")
        user_id = (
            _optional_string(metadata.get("user_id"))
            if isinstance(metadata, dict)
            else None
        )
        user = (
            session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user_id
            else None
        )
    if user is None:
        raise ValueError("Subscription references an unknown customer")
    if user.stripe_customer_id is None:
        user.stripe_customer_id = customer_id

    # Fetch after taking the user lock so concurrent events for this account all
    # write Stripe's latest state rather than racing stale webhook snapshots.
    event_object = billing_gateway.retrieve_subscription(subscription_id)
    if _required_string(event_object, "id") != subscription_id:
        raise ValueError("Stripe returned a different subscription")
    if _required_string(event_object, "customer") != customer_id:
        raise ValueError("Subscription customer changed during reconciliation")

    items = event_object.get("items")
    item_data = items.get("data") if isinstance(items, dict) else None
    price_id = None
    if isinstance(item_data, list) and item_data:
        price = item_data[0].get("price") if isinstance(item_data[0], dict) else None
        if isinstance(price, dict):
            price_id = _optional_string(price.get("id"))

    current_period_end = event_object.get("current_period_end")
    period_end = (
        datetime.fromtimestamp(current_period_end, timezone.utc)
        if isinstance(current_period_end, (int, float))
        else None
    )
    subscription = session.scalar(
        select(Subscription).where(
            Subscription.stripe_subscription_id == subscription_id
        ).with_for_update()
    )
    if subscription is None:
        subscription = Subscription(
            user_id=user.id,
            stripe_subscription_id=subscription_id,
            status=_required_string(event_object, "status"),
            last_event_created=event_created,
            last_event_rank=event_rank,
        )
        session.add(subscription)
    elif subscription.user_id != user.id:
        raise ValueError("Subscription owner does not match the Stripe customer")
    subscription.stripe_subscription_id = subscription_id
    subscription.stripe_price_id = price_id
    subscription.status = _required_string(event_object, "status")
    subscription.current_period_end = period_end
    subscription.cancel_at_period_end = bool(
        event_object.get("cancel_at_period_end", False)
    )
    if (event_created, event_rank) > (
        subscription.last_event_created,
        subscription.last_event_rank,
    ):
        subscription.last_event_created = event_created
        subscription.last_event_rank = event_rank


def _required_string(mapping: dict[str, Any], key: str) -> str:
    value = _optional_string(mapping.get(key))
    if value is None:
        raise ValueError(f"Stripe object is missing {key}")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
