import type { AppMetadata, AtlasFeatureCollection, DistrictRecord } from "../types";

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

let lsoaPromise: Promise<AtlasFeatureCollection> | undefined;

export function loadLsoaBoundaries(): Promise<AtlasFeatureCollection> {
  lsoaPromise ??= fetchJson<AtlasFeatureCollection>("/data/lsoa-boundaries.geojson").catch(
    (error: unknown) => {
      lsoaPromise = undefined;
      throw error;
    },
  );
  return lsoaPromise;
}
