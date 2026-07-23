# London Flat Atlas

Local React and TypeScript application for exploring London flat transactions and 2025 socioeconomic indicators by postcode district and 2021 LSOA.

## Run locally

From PowerShell:

```powershell
cd web
.\start-local.ps1
```

Open `http://127.0.0.1:4173`. The base map uses OpenStreetMap tiles and therefore needs an internet connection; all analysis data is served locally.

## Refresh the app data

From the repository root, rebuild and export the source data:

```powershell
.\.venv\Scripts\python.exe 2_local_processing\postcode_boundaries.py --refresh
.\.venv\Scripts\python.exe 2_local_processing\rebuild_london_transactions.py
.\.venv\Scripts\python.exe 2_local_processing\rebuild_london_lsoa2021.py
.\.venv\Scripts\python.exe scripts\export_web_data.py
```

This generates compact, simplified browser assets under `web/public/data`. Source data remains under `2_local_processing/3_gold`.

The boundary refresh uses the public GLA postcode-unit layer for EC, WC, W1 and
SW1 and validates it against official February 2026 ONS live-postcode centroids.
The transaction rebuild reads the validated HM Land Registry Parquet archive from
`s3://landregistryproject/silver/land_registry_data.parquet/`.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd web
pnpm build
pnpm test
pnpm test:e2e
```

## Freemium development preview

The local app starts on the Free plan. Select a locked metric or LSOA detail to open the pricing
dialog, then use **Preview Pro locally** to exercise premium features without a Stripe account.
You can also open `http://127.0.0.1:4173/?demoPlan=pro`.

The UI calls server-side `/api/billing/checkout` and `/api/billing/portal` contracts, but those
endpoints are intentionally not supplied by the static Vite application. See
[`docs/freemium-stripe.md`](docs/freemium-stripe.md) for the production security and billing rollout.
