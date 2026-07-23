import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_authenticated
from ..billing import (
    BillingNotConfiguredError,
    price_id_for_interval,
    process_webhook,
)
from ..config import Settings
from ..database import User, upsert_user
from ..dependencies import get_current_principal, get_database_session
from ..schemas import (
    CheckoutRequest,
    Principal,
    RedirectResponse,
    WebhookResponse,
)


router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout", response_model=RedirectResponse)
def create_checkout(
    payload: CheckoutRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> RedirectResponse:
    principal = require_authenticated(principal)
    settings: Settings = request.app.state.settings
    try:
        user = upsert_user(session, principal.subject or "", principal.email)
        if user.stripe_customer_id is None:
            user.stripe_customer_id = request.app.state.billing_gateway.create_customer(
                principal.email, user.id
            )
            session.commit()
        checkout_url = request.app.state.billing_gateway.create_checkout(
            customer_id=user.stripe_customer_id,
            user_id=user.id,
            price_id=price_id_for_interval(settings, payload.interval),
            success_url=f"{settings.app_base_url}/?checkout=success",
            cancel_url=f"{settings.app_base_url}/?checkout=cancelled",
        )
        return RedirectResponse(url=checkout_url)
    except BillingNotConfiguredError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except stripe.StripeError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe Checkout is temporarily unavailable.",
        ) from exc


@router.post("/portal", response_model=RedirectResponse)
def create_portal(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> RedirectResponse:
    principal = require_authenticated(principal)
    user = session.scalar(
        select(User).where(User.external_subject == principal.subject)
    )
    if user is None or user.stripe_customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No Stripe customer exists for this account.",
        )
    try:
        url = request.app.state.billing_gateway.create_portal(
            customer_id=user.stripe_customer_id,
            return_url=f"{request.app.state.settings.app_base_url}/",
        )
        return RedirectResponse(url=url)
    except BillingNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The Stripe customer portal is temporarily unavailable.",
        ) from exc


@router.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    session: Session = Depends(get_database_session),
) -> WebhookResponse:
    if stripe_signature is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe-Signature header is required.",
        )
    try:
        event = request.app.state.billing_gateway.construct_event(
            await request.body(), stripe_signature
        )
        duplicate = process_webhook(
            session,
            event,
            request.app.state.billing_gateway,
        )
        return WebhookResponse(duplicate=duplicate)
    except BillingNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The Stripe webhook could not be verified or processed.",
        ) from exc
    except stripe.StripeError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe subscription reconciliation is temporarily unavailable.",
        ) from exc
