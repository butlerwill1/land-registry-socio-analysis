from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest, new
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


class ProAccessCodeService:
    cookie_name = "atlas_pro_access"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _code_fingerprint(self, code: str) -> str:
        signing_secret = self._settings.pro_access_signing_secret
        assert signing_secret is not None
        return new(
            signing_secret.get_secret_value().encode("utf-8"),
            code.encode("utf-8"),
            sha256,
        ).hexdigest()

    def redeem(self, code: str) -> tuple[str, datetime]:
        if not self._settings.pro_access_enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pro access codes are not available.",
            )
        expected_code = self._settings.pro_access_code
        signing_secret = self._settings.pro_access_signing_secret
        assert expected_code is not None and signing_secret is not None
        if not compare_digest(code, expected_code.get_secret_value()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="That access code is not valid.",
            )
        expires_at = self._settings.pro_access_expires_at
        assert expires_at is not None
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This access code has expired.",
            )
        token = jwt.encode(
            {
                "scope": "pro_access",
                "code_fingerprint": self._code_fingerprint(code),
                "exp": expires_at,
            },
            signing_secret.get_secret_value(),
            algorithm="HS256",
        )
        return token, expires_at

    def has_valid_access(self, token: str | None) -> bool:
        if not token or not self._settings.pro_access_enabled:
            return False
        signing_secret = self._settings.pro_access_signing_secret
        assert signing_secret is not None
        try:
            claims = jwt.decode(
                token,
                signing_secret.get_secret_value(),
                algorithms=["HS256"],
                options={"require": ["exp"]},
            )
        except jwt.PyJWTError:
            return False
        expected_code = self._settings.pro_access_code
        assert expected_code is not None
        return (
            claims.get("scope") == "pro_access"
            and isinstance(claims.get("code_fingerprint"), str)
            and compare_digest(
                claims["code_fingerprint"],
                self._code_fingerprint(expected_code.get_secret_value()),
            )
        )


def get_principal(request: Request) -> Principal:
    settings: Settings = request.app.state.settings
    access_code_service: ProAccessCodeService = request.app.state.pro_access_code_service
    code_plan = (
        "pro"
        if access_code_service.has_valid_access(
            request.cookies.get(access_code_service.cookie_name)
        )
        else None
    )
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
            codePlan=code_plan,
        )

    if code_plan is not None:
        return Principal(codePlan=code_plan)

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
