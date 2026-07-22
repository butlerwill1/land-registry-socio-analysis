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
  lsoaCount: number;
  excludedLsoaCount: number;
  meanOverlapShare: number;
  areaKm2: number;
  population: number;
  populationDensity: number;
  overall: number;
  income: number;
  employment: number;
  education: number;
  health: number;
  crime: number;
  housingBarriers: number;
  environment: number;
  history: TransactionYear[];
}

export interface AppMetadata {
  districtCount: number;
  lsoaCount: number;
  years: number[];
  latestCompleteYear: number;
  latestYear: number;
  transactionCount: number;
}

export type AtlasFeatureCollection = FeatureCollection<
  Geometry,
  Record<string, string | number | boolean | null>
>;
import type { FeatureCollection, Geometry } from "geojson";
