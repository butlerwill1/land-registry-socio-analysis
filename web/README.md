# flAtlas

Local React and TypeScript application for exploring London flat transactions and 2025 socioeconomic indicators by postcode district and 2021 LSOA.

## Run locally

From PowerShell:

```powershell
cd web
.\start-local.ps1
```

Open `http://127.0.0.1:4173`. The script starts both Vite and the FastAPI backend.
The base map uses OpenStreetMap tiles and therefore needs an internet connection;
all analysis data is served locally.

## Refresh the app data

From the repository root, rebuild and export the source data:

```powershell
.\.venv\Scripts\python.exe 2_local_processing\postcode_boundaries.py --refresh
.\.venv\Scripts\python.exe 2_local_processing\rebuild_london_transactions.py
.\.venv\Scripts\python.exe 2_local_processing\rebuild_london_lsoa2021.py
.\.venv\Scripts\python.exe scripts\export_web_data.py
```

This generates a five-year Free browser bundle under `web/public/data` and private
premium assets under `backend/data`. Source data remains under
`2_local_processing/3_gold`.

The boundary refresh uses the public GLA postcode-unit layer for EC, WC, W1 and
SW1 and validates it against official February 2026 ONS live-postcode centroids.
The transaction rebuild reads the validated HM Land Registry Parquet archive from
`s3://landregistryproject/silver/land_registry_data.parquet/`.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd backend
..\.venv\Scripts\python.exe -m pytest -q --cov=app
cd web
pnpm build
pnpm test
pnpm test:e2e
```

## Freemium development preview

The local app starts on the Free plan. Select a locked metric or LSOA detail to open the pricing
dialog, then use **Preview Pro locally** to exercise premium features without a Stripe account.
You can also open `http://127.0.0.1:4173/?demoPlan=pro`.

## Shared access code

The Pro dialog accepts a shared server-configured access code and does not require
Stripe, an account, or an email address. Locally, enter `local-pro`; in production,
configure `ATLAS_PRO_ACCESS_CODE`, `ATLAS_PRO_ACCESS_SIGNING_SECRET`, and
`ATLAS_PRO_ACCESS_EXPIRES_AT` in the backend environment. The browser is granted Pro
through an HttpOnly cookie until that fixed expiry date.

Premium data, entitlements, Checkout, Customer Portal, and signed Stripe webhooks are
implemented by the FastAPI service under `backend`. See
[`docs/freemium-stripe.md`](docs/freemium-stripe.md) and
[`../backend/README.md`](../backend/README.md).

## Production sign-in

Copy `.env.example` to the deployment environment and set the OIDC authority, SPA
client ID, and callback URL. The browser uses Authorization Code with PKCE, holds
the access token in session storage, and sends it to FastAPI as a bearer token.
Local development does not require an identity provider.
