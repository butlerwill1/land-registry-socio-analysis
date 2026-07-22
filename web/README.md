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

After rebuilding the source GeoPackages, run:

```powershell
python scripts\export_web_data.py
```

This generates compact, simplified browser assets under `web/public/data`. Source data remains under `2_local_processing/3_gold`.

## Checks

```powershell
cd web
pnpm build
pnpm test
pnpm test:e2e
```
