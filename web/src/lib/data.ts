import type {
  AppMetadata,
  AtlasFeatureCollection,
  DistrictRecord,
  EntitlementResponse,
  MapMetricResponse,
  MetricKey,
} from "../types";
import { fetchApi } from "./api";
import type { PlanId } from "./plans";

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Could not load ${path} (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function loadInitialData() {
  const [metadata, districts, districtBoundaries] = await Promise.all([
    fetchJson<AppMetadata>("/data/metadata.json"),
    fetchJson<DistrictRecord[]>("/data/districts.json"),
    fetchJson<AtlasFeatureCollection>("/data/district-boundaries.geojson"),
  ]);
  return { metadata, districts, districtBoundaries };
}

export function loadEntitlements(plan: PlanId): Promise<EntitlementResponse> {
  return fetchApi<EntitlementResponse>("/api/account/entitlements", plan);
}

export function redeemProAccessCode(code: string): Promise<EntitlementResponse> {
  return fetchApi<EntitlementResponse>("/api/account/access-code", "free", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
}

export function loadDistrictDetail(
  district: string,
  plan: PlanId,
  signal?: AbortSignal,
): Promise<DistrictRecord> {
  return fetchApi<DistrictRecord>(
    `/api/data/districts/${encodeURIComponent(district)}`,
    plan,
    { signal },
  );
}

export function loadMapMetric(
  metric: MetricKey,
  year: number,
  plan: PlanId,
  signal?: AbortSignal,
): Promise<MapMetricResponse> {
  const query = new URLSearchParams({ metric, year: String(year) });
  return fetchApi<MapMetricResponse>(`/api/data/map?${query}`, plan, { signal });
}

export function loadLsoaBoundaries(
  district: string,
  metric: MetricKey,
  plan: PlanId,
  signal?: AbortSignal,
): Promise<AtlasFeatureCollection> {
  const query = new URLSearchParams({ metric });
  return fetchApi<AtlasFeatureCollection>(
    `/api/data/lsoas/${encodeURIComponent(district)}?${query}`,
    plan,
    { signal },
  );
}
