import { describe, expect, it } from "vitest";
import {
  formatPlanPrice,
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

  it("formats prices in pounds sterling", () => {
    expect(formatPlanPrice("free", "month")).toBe("£0");
    expect(formatPlanPrice("pro", "month")).toBe("£15");
    expect(formatPlanPrice("pro", "year")).toBe("£144");
  });
});
