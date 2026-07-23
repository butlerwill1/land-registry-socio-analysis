import { describe, expect, it } from "vitest";
import {
  getMetricValue,
  getPercentile,
  getQuantileBreaks,
  getYearOnYear,
} from "./metrics";
import type { DistrictRecord } from "../types";

const district: DistrictRecord = {
  district: "SW11",
  areaName: "Wandsworth",
  hasSocioeconomicSummary: true,
  lsoaCount: 1,
  excludedLsoaCount: 0,
  meanOverlapShare: 1,
  areaKm2: 1,
  population: 1,
  populationDensity: 1,
  overall: 22,
  income: 0.2,
  employment: 0.1,
  education: 10,
  health: -1,
  crime: 0.5,
  housingBarriers: 20,
  environment: 30,
  history: [
    { year: 2024, transactions: 100, averagePrice: 520_000, medianPrice: 500_000 },
    { year: 2025, transactions: 90, averagePrice: 572_000, medianPrice: 550_000 },
  ],
};

describe("map metric helpers", () => {
  it("reads year-specific and district-level values", () => {
    expect(getMetricValue(district, "medianPrice", 2025)).toBe(550_000);
    expect(getMetricValue(district, "medianPrice", 2023)).toBeNull();
    expect(getMetricValue(district, "overall", 2025)).toBe(22);
  });

  it("calculates the median-price year-on-year change", () => {
    expect(getYearOnYear(district, 2025)).toBe(10);
    expect(getYearOnYear(district, 2024)).toBeNull();
  });

  it("builds stable quantile breaks and percentiles", () => {
    const breaks = getQuantileBreaks([60, 10, 20, 30, 40, 50]);
    expect(breaks).toHaveLength(5);
    expect(breaks[0]).toBeCloseTo(18.33, 2);
    expect(breaks[4]).toBeCloseTo(51.67, 2);
    expect(getPercentile(30, [10, 20, 30, 40, 50])).toBe(50);
    expect(getPercentile(null, [10, 20, null, 40])).toBeNull();
  });
});
