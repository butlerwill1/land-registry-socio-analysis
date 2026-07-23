# London Flat Atlas API

FastAPI service for premium data access, account entitlements, and Stripe Billing.

## Responsibilities

- validates private district and LSOA exports with Pydantic at startup
- returns only one requested map cross-section, district, or LSOA layer
- enforces Free and Pro entitlements on the server
- verifies production OIDC bearer tokens
- creates Stripe Checkout and Customer Portal sessions
- verifies and processes Stripe webhooks idempotently
- persists users and subscriptions in SQLite or PostgreSQL
- rate-limits data endpoints per authenticated user or client IP
- optionally grants anonymous Pro access through one shared, expiring access code

The public browser bundle remains under `web/public/data`. It contains five complete
transaction years, overall IMD, and no premium socioeconomic fields. Full district
history and LSOA data live under the configured private data directory and are never
served as static files.

Private files under `backend/data` are deliberately ignored by Git. Generate them
locally with `scripts/export_web_data.py`; in production, build the container in a
private pipeline or mount/download the files from a private S3 location. Do not add
them to a public repository.

## Local development

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".\backend[test]"
cd web
.\start-local.ps1
```

The script starts FastAPI on `http://127.0.0.1:8000` and Vite on
`http://127.0.0.1:4173`. Vite proxies `/api` to FastAPI.

FastAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Tests

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q --cov=app --cov-report=term-missing
```

## Configuration

Copy `.env.example` to `.env` and provide production values outside source control.
All variables use the `ATLAS_` prefix.

Production authentication expects RS256 OIDC access tokens and requires issuer,
audience, and JWKS URL settings. Development-only `X-Dev-Plan` headers are rejected
when `ATLAS_ALLOW_DEV_ENTITLEMENTS=false`, which is mandatory in production.

The React single-page app uses the OIDC Authorization Code flow with PKCE. Configure
its matching public-client values at build time:

```text
VITE_OIDC_AUTHORITY=https://your-tenant.eu.auth0.com
VITE_OIDC_CLIENT_ID=your-spa-client-id
VITE_OIDC_AUDIENCE=https://api.your-domain.example
VITE_OIDC_REDIRECT_URI=https://your-domain.example/
```

The provider's access-token issuer and audience must match the backend settings.
Register the deployed URL as an allowed callback and logout URL with the provider.

## Shared Pro access code

For private previews, set a shared code and a separate long random signing secret:

```text
ATLAS_PRO_ACCESS_CODE=your-shareable-code
ATLAS_PRO_ACCESS_SIGNING_SECRET=long-random-secret-kept-private
ATLAS_PRO_ACCESS_EXPIRES_AT=2026-12-31T23:59:59Z
```

The browser sends the code once to FastAPI. On success, FastAPI stores an HttpOnly
Pro-access cookie that expires at the configured UTC date and time; no account, email,
or Stripe interaction is required. The endpoint limits attempts by client IP. Changing
the code or signing secret revokes every existing code-access session immediately.
Once the configured expiry passes, code redemption returns an expiry message while the
rest of the API remains available; set a later expiry to issue a new code again.

The built-in attempt limiter is intended for one small application instance. When the
app is placed behind a proxy or scaled to multiple instances, apply an equivalent
IP-based rate limit at the hosting layer or use shared rate-limit storage.

SQLite is the local default. PostgreSQL is selected with a URL such as:

```text
ATLAS_DATABASE_URL=postgresql+psycopg://atlas:password@database/atlas
```

## Stripe

Create monthly and annual recurring Prices in Stripe test mode, then configure:

```text
ATLAS_STRIPE_SECRET_KEY=sk_test_...
ATLAS_STRIPE_WEBHOOK_SECRET=whsec_...
ATLAS_STRIPE_MONTHLY_PRICE_ID=price_...
ATLAS_STRIPE_YEARLY_PRICE_ID=price_...
```

Forward test events with the Stripe CLI:

```powershell
stripe listen --forward-to http://127.0.0.1:8000/api/billing/webhook
```

The service uses Checkout Sessions in subscription mode, the Stripe Customer Portal,
the `2026-02-25.clover` API version, raw-body signature verification, and an
idempotency table keyed by Stripe event ID. Subscription events are serialised per
user and reconciled against Stripe's current subscription object before entitlement
state is committed.

## API surface

```text
GET  /api/health
GET  /api/account/entitlements
POST /api/account/access-code
GET  /api/data/districts/{district}
GET  /api/data/map?metric={metric}&year={year}
GET  /api/data/lsoas/{district}?metric={metric}
POST /api/billing/checkout
POST /api/billing/portal
POST /api/billing/webhook
```

An API reduces bulk exposure but cannot make displayed values impossible to copy.
Request scoping, authentication, rate limits, and server-side entitlements are the
enforcement boundary.
