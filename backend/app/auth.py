from __future__ import annotations

from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from .config import Settings
from .schemas import Principal


class OidcTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = (
            PyJWKClient(settings.oidc_jwks_url)
            if settings.oidc_jwks_url is not None
            else None
        )

    def verify(self, token: str) -> dict[str, Any]:
        if not self._settings.oidc_enabled or self._client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is not configured.",
            )
        try:
            signing_key = self._client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.oidc_audience,
                issuer=self._settings.oidc_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The access token is invalid or expired.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc


def get_principal(request: Request) -> Principal:
    settings: Settings = request.app.state.settings
    authorization = request.headers.get("authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A Bearer access token is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        claims = request.app.state.token_verifier.verify(token)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The access token has no subject.",
            )
        email = claims.get("email")
        return Principal(
            subject=subject,
            email=email if isinstance(email, str) else None,
            authenticated=True,
        )

    dev_plan = request.headers.get("x-dev-plan")
    if dev_plan is not None:
        if not settings.allow_dev_entitlements:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Development entitlements are disabled.",
            )
        if dev_plan not in {"free", "pro"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Dev-Plan must be free or pro.",
            )
        subject = request.headers.get("x-dev-user", "local-preview")
        return Principal(
            subject=subject,
            email=request.headers.get("x-dev-email", "local@example.test"),
            authenticated=True,
            devPlan=dev_plan,
        )

    return Principal()


def require_authenticated(principal: Principal) -> Principal:
    if not principal.authenticated or principal.subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal
