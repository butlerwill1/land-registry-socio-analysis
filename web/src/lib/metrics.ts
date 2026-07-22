import type {
  DistrictRecord,
  MetricKey,
  PriceMetricKey,
  SocioMetricKey,
  TransactionYear,
} from "../types";

export interface MetricDefinition {
  key: MetricKey;
  label: string;
  shortLabel: string;
  group: "Property market" | "Socioeconomic context";
  format: (value: number) => string;
}

const currency = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});
const compactCurrency = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  notation: "compact",
  maximumFractionDigits: 1,
});
const integer = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

export const metricDefinitions: MetricDefinition[] = [
  { key: "medianPrice", label: "Median sale price", shortLabel: "Median price", group: "Property market", format: currency.format },
  { key: "averagePrice", label: "Average sale price", shortLabel: "Average price", group: "Property market", format: currency.format },
  { key: "transactions", label: "Number of transactions", shortLabel: "Transactions", group: "Property market", format: integer.format },
  { key: "overall", label: "Overall deprivation score", shortLabel: "IMD score", group: "Socioeconomic context", format: decimal.format },
  { key: "income", label: "Income deprivation", shortLabel: "Income", group: "Socioeconomic context", format: decimal.format },
  { key: "employment", label: "Employment deprivation", shortLabel: "Employment", group: "Socioeconomic context", format: decimal.format },
  { key: "education", label: "Education deprivation", shortLabel: "Education", group: "Socioeconomic context", format: decimal.format },
  { key: "health", label: "Health deprivation", shortLabel: "Health", group: "Socioeconomic context", format: decimal.format },
  { key: "crime", label: "Crime deprivation", shortLabel: "Crime", group: "Socioeconomic context", format: decimal.format },
  { key: "housingBarriers", label: "Housing and services barriers", shortLabel: "Housing barriers", group: "Socioeconomic context", format: decimal.format },
  { key: "environment", label: "Living environment deprivation", shortLabel: "Environment", group: "Socioeconomic context", format: decimal.format },
  { key: "populationDensity", label: "Population density", shortLabel: "Population density", group: "Socioeconomic context", format: (value) => `${integer.format(value)}/km²` },
];

export const metricByKey = Object.fromEntries(
  metricDefinitions.map((definition) => [definition.key, definition]),
) as Record<MetricKey, MetricDefinition>;

export const priceMetricKeys = new Set<MetricKey>([
  "medianPrice",
  "averagePrice",
  "transactions",
]);

export const socioeconomicMetricKeys: SocioMetricKey[] = [
  "overall",
  "income",
  "employment",
  "education",
  "health",
  "crime",
  "housingBarriers",
  "environment",
];

export function getYearRecord(
  district: DistrictRecord,
  year: number,
): TransactionYear | undefined {
  return district.history.find((record) => record.year === year);
}

export function getMetricValue(
  district: DistrictRecord,
  metric: MetricKey,
  year: number,
): number | null {
  if (priceMetricKeys.has(metric)) {
    const yearRecord = getYearRecord(district, year);
    return yearRecord?.[metric as PriceMetricKey] ?? null;
  }
  return district[metric as SocioMetricKey] ?? null;
}

export function getQuantileBreaks(values: number[], bucketCount = 6): number[] {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (sorted.length === 0) return [];
  return Array.from({ length: bucketCount - 1 }, (_, index) => {
    const position = ((index + 1) / bucketCount) * (sorted.length - 1);
    const lower = Math.floor(position);
    const upper = Math.ceil(position);
    const weight = position - lower;
    return sorted[lower] * (1 - weight) + sorted[upper] * weight;
  });
}

export function getYearOnYear(district: DistrictRecord, year: number): number | null {
  const current = getYearRecord(district, year)?.medianPrice;
  const previous = getYearRecord(district, year - 1)?.medianPrice;
  if (!current || !previous) return null;
  return ((current - previous) / previous) * 100;
}

export function formatCompactCurrency(value: number): string {
  return compactCurrency.format(value);
}

export function getPercentile(value: number, values: number[]): number {
  const valid = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (valid.length < 2) return 50;
  const belowOrEqual = valid.filter((candidate) => candidate <= value).length;
  return Math.round(((belowOrEqual - 1) / (valid.length - 1)) * 100);
}
