import type { MetricKey } from "../types";

export type PlanId = "free" | "pro";
export type BillingInterval = "month" | "year";
export type PremiumFeature = "lsoaDetail" | "socioeconomicDomains";

export interface ProductPlan {
  id: PlanId;
  name: string;
  description: string;
  prices: Record<BillingInterval, number>;
  features: string[];
}

export const productPlans: Record<PlanId, ProductPlan> = {
  free: {
    id: "free",
    name: "Free",
    description: "Core London flat market research.",
    prices: { month: 0, year: 0 },
    features: [
      "All London postcode districts",
      "Sale prices and transaction volumes",
      "District-level overall IMD score",
      "Full price history",
    ],
  },
  pro: {
    id: "pro",
    name: "Pro",
    description: "Deeper location analysis for regular research.",
    prices: { month: 15, year: 144 },
    features: [
      "Everything in Free",
      "2021 LSOA-level map detail",
      "Seven socioeconomic domain layers",
      "Priority access to future exports",
    ],
  },
};

const premiumMetrics = new Set<MetricKey>([
  "income",
  "employment",
  "education",
  "health",
  "crime",
  "housingBarriers",
  "environment",
  "populationDensity",
]);

export function hasFeature(plan: PlanId, _feature: PremiumFeature): boolean {
  return plan === "pro";
}

export function isMetricAvailable(plan: PlanId, metric: MetricKey): boolean {
  return plan === "pro" || !premiumMetrics.has(metric);
}

export function formatPlanPrice(plan: PlanId, interval: BillingInterval): string {
  const price = productPlans[plan].prices[interval];
  if (price === 0) return "£0";
  return `£${price}`;
}

export function monthlyEquivalent(plan: PlanId, interval: BillingInterval): number {
  const price = productPlans[plan].prices[interval];
  return interval === "year" ? price / 12 : price;
}
