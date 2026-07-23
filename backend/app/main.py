from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import OidcTokenVerifier
from .billing import BillingGateway, StripeBillingGateway
from .config import Settings, get_settings
from .data_repository import DataRepository
from .database import build_engine, initialise_database
from .rate_limit import FixedWindowRateLimiter
from .routes import account, billing, data
from .schemas import HealthResponse


def create_app(
    *,
    settings: Settings | None = None,
    repository: DataRepository | None = None,
    billing_gateway: BillingGateway | None = None,
    token_verifier: OidcTokenVerifier | None = None,
    rate_limiter: FixedWindowRateLimiter | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    app_repository = repository or DataRepository(app_settings.data_dir)
    engine = build_engine(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialise_database(engine)
        if not app_repository.loaded:
            app_repository.load()
        yield
        engine.dispose()

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.repository = app_repository
    app.state.engine = engine
    app.state.billing_gateway = billing_gateway or StripeBillingGateway(app_settings)
    app.state.token_verifier = token_verifier or OidcTokenVerifier(app_settings)
    app.state.data_rate_limiter = rate_limiter or FixedWindowRateLimiter(
        app_settings.data_rate_limit_requests,
        app_settings.data_rate_limit_window_seconds,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Stripe-Signature",
            "X-Dev-Plan",
            "X-Dev-User",
            "X-Dev-Email",
        ],
    )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": str(exc.detail)},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "The request was invalid.", "details": exc.errors()},
        )

    @app.get(f"{app_settings.api_prefix}/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
        return HealthResponse(dataLoaded=app_repository.loaded, database="ok")

    app.include_router(account.router, prefix=app_settings.api_prefix)
    app.include_router(data.router, prefix=app_settings.api_prefix)
    app.include_router(billing.router, prefix=app_settings.api_prefix)
    return app


app = create_app()
