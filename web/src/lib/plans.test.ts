import { describe, expect, it } from "vitest";
import {
  formatPlanPrice,
  getAvailableTransactionHistory,
  getAvailableTransactionYears,
  hasFeature,
  isMetricAvailable,
  monthlyEquivalent,
  productPlans,
} from "./plans";

describe("product plans", () => {
  it("keeps core market metrics available on the free plan", () => {
    expect(isMetricAvailable("free", "medianPrice")).toBe(true);
    expect(isMetricAvailable("free", "transactions")).toBe(true);
    expect(isMetricAvailable("free", "overall")).toBe(true);
  });

  it("gates detailed socioeconomic metrics on the free plan", () => {
    expect(isMetricAvailable("free", "income")).toBe(false);
    expect(isMetricAvailable("free", "populationDensity")).toBe(false);
  });

  it("makes every metric available on Pro", () => {
    expect(isMetricAvailable("pro", "income")).toBe(true);
    expect(isMetricAvailable("pro", "populationDensity")).toBe(true);
  });

  it("gates both premium capabilities", () => {
    expect(hasFeature("free", "lsoaDetail")).toBe(false);
    expect(hasFeature("free", "socioeconomicDomains")).toBe(false);
    expect(hasFeature("pro", "lsoaDetail")).toBe(true);
  });

  it("keeps annual pricing at a 20 percent discount", () => {
    expect(productPlans.pro.prices.month * 12).toBe(180);
    expect(productPlans.pro.prices.year).toBe(144);
    expect(monthlyEquivalent("pro", "year")).toBe(12);
  });

  it("limits Free to the latest five complete transaction years", () => {
    expect(
      getAvailableTransactionYears(
        "free",
        [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026],
        2025,
      ),
    ).toEqual([2021, 2022, 2023, 2024, 2025]);
  });

  it("keeps the full range, including a partial year, for Pro", () => {
    expect(getAvailableTransactionYears("pro", [2024, 2025, 2026], 2025)).toEqual([
      2024, 2025, 2026,
    ]);
  });

  it("applies the same Free limit to chart history", () => {
    const history = [2020, 2021, 2022, 2023, 2024, 2025, 2026].map((year) => ({
      year,
      transactions: year,
      averagePrice: year,
      medianPrice: year,
    }));
    expect(getAvailableTransactionHistory("free", history, 2025).map(({ year }) => year)).toEqual([
      2021, 2022, 2023, 2024, 2025,
    ]);
  });

  it("formats prices in pounds sterling", () => {
    expect(formatPlanPrice("free", "month")).toBe("£0");
    expect(formatPlanPrice("pro", "month")).toBe("£15");
    expect(formatPlanPrice("pro", "year")).toBe("£144");
  });
});
