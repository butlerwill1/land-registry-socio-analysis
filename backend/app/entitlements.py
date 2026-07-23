from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .database import Subscription, User
from .schemas import EntitlementResponse, PlanId, Principal


PRO_STATUSES = frozenset({"active", "trialing"})
FREE_FEATURES = [
    "district_summary",
    "five_year_transaction_history",
    "overall_deprivation",
]
PRO_FEATURES = FREE_FEATURES + [
    "full_transaction_history",
    "lsoa_detail",
    "socioeconomic_domains",
]


def resolve_plan(
    session: Session, principal: Principal, settings: Settings
) -> PlanId:
    if principal.devPlan is not None:
        return principal.devPlan
    if not principal.authenticated or principal.subject is None:
        return "free"
    user = session.scalar(
        select(User).where(User.external_subject == principal.subject)
    )
    if user is None:
        return "free"
    eligible_prices = {
        price_id
        for price_id in (
            settings.stripe_monthly_price_id,
            settings.stripe_yearly_price_id,
        )
        if price_id is not None
    }
    if not eligible_prices:
        return "free"
    subscription = session.scalar(
        select(Subscription.id).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(PRO_STATUSES),
            Subscription.stripe_price_id.in_(eligible_prices),
        )
    )
    return "pro" if subscription is not None else "free"


def entitlement_response(
    session: Session, principal: Principal, settings: Settings
) -> EntitlementResponse:
    plan = resolve_plan(session, principal, settings)
    return EntitlementResponse(
        plan=plan,
        authenticated=principal.authenticated,
        features=PRO_FEATURES if plan == "pro" else FREE_FEATURES,
    )
