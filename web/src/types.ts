export type PriceMetricKey = "medianPrice" | "averagePrice" | "transactions";
export type SocioMetricKey =
  | "overall"
  | "income"
  | "employment"
  | "education"
  | "health"
  | "crime"
  | "housingBarriers"
  | "environment"
  | "populationDensity";
export type MetricKey = PriceMetricKey | SocioMetricKey;

export interface TransactionYear {
  year: number;
  transactions: number;
  averagePrice: number | null;
  medianPrice: number | null;
}

export interface DistrictRecord {
  district: string;
  areaName: string;
  hasSocioeconomicSummary: boolean;
  lsoaCount: number;
  excludedLsoaCount: number;
  meanOverlapShare: number | null;
  areaKm2: number;
  population: number | null;
  populationDensity: number | null;
  overall: number | null;
  income: number | null;
  employment: number | null;
  education: number | null;
  health: number | null;
  crime: number | null;
  housingBarriers: number | null;
  environment: number | null;
  history: TransactionYear[];
  percentiles?: Partial<Record<SocioMetricKey, number>> | null;
}

export interface AppMetadata {
  dataAsOf: string;
  boundarySource: string;
  boundarySources: Array<{
    name: string;
    role: string;
    url: string;
    licence: string;
    attribution?: string;
  }>;
  boundaryMethod: string;
  boundarySourceRetrievedOn: string;
  centralBoundaryCoverageShare: number;
  centralBoundaryDistrictMatchShare: number;
  districtCount: number;
  lsoaCount: number;
  years: number[];
  latestCompleteYear: number;
  latestYear: number;
  latestYearIsPartial: boolean;
  transactionCount: number;
}

export type AtlasFeatureCollection = FeatureCollection<
  Geometry,
  Record<string, string | number | boolean | null>
>;

export interface MapMetricResponse {
  metric: MetricKey;
  year: number;
  plan: "free" | "pro";
  values: Array<{ district: string; value: number | null }>;
}

export interface EntitlementResponse {
  plan: "free" | "pro";
  authenticated: boolean;
  features: string[];
}
import type { FeatureCollection, Geometry } from "geojson";
