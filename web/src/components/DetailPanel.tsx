import {
  BadgePoundSterling,
  ChartNoAxesCombined,
  Database,
  Gauge,
} from "lucide-react";
import { getPercentile, getYearOnYear, getYearRecord, socioeconomicMetricKeys } from "../lib/metrics";
import type { DistrictRecord, SocioMetricKey } from "../types";
import { PriceTrend } from "./PriceTrend";

const currency = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});
const integer = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

const socioeconomicLabels: Record<SocioMetricKey, string> = {
  overall: "IMD overall score",
  income: "Income deprivation",
  employment: "Employment deprivation",
  education: "Education deprivation",
  health: "Health deprivation",
  crime: "Crime deprivation",
  housingBarriers: "Housing and services barriers",
  environment: "Living environment",
  populationDensity: "Population density",
};

export function DetailPanel({
  district,
  districts,
  year,
}: {
  district: DistrictRecord;
  districts: DistrictRecord[];
  year: number;
}) {
  const current = getYearRecord(district, year);
  const yearOnYear = getYearOnYear(district, year);

  const kpis = [
    {
      label: "Median price",
      value: current?.medianPrice ? currency.format(current.medianPrice) : "No data",
      icon: BadgePoundSterling,
    },
    {
      label: "Year on year",
      value: yearOnYear === null ? "No data" : `${yearOnYear >= 0 ? "+" : ""}${yearOnYear.toFixed(1)}%`,
      tone: yearOnYear !== null && yearOnYear < 0 ? "negative" : "positive",
      icon: ChartNoAxesCombined,
    },
    {
      label: "Transactions",
      value: current ? integer.format(current.transactions) : "No data",
      icon: Database,
    },
    {
      label: "IMD score",
      value: district.overall.toFixed(1),
      icon: Gauge,
    },
  ];

  return (
    <aside className="detail-panel" aria-label={`${district.district} analysis`}>
      <div className="detail-heading">
        <div>
          <h1>{district.district}</h1>
          <p>{district.areaName}</p>
        </div>
        <span>{year}</span>
      </div>

      <div className="kpi-grid">
        {kpis.map(({ label, value, icon: Icon, tone }) => (
          <div className="kpi" key={label}>
            <div className="kpi-label">
              <Icon size={15} aria-hidden="true" />
              {label}
            </div>
            <strong className={tone}>{value}</strong>
          </div>
        ))}
      </div>

      <section className="panel-section">
        <div className="section-heading">
          <h2>Price trend</h2>
          <span>Median flat price</span>
        </div>
        <PriceTrend history={district.history} year={year} />
      </section>

      <section className="panel-section socioeconomic-section">
        <div className="section-heading">
          <h2>Socioeconomic context</h2>
          <span>IMD 2025</span>
        </div>
        <div className="indicator-header" aria-hidden="true">
          <span>Indicator</span>
          <span>Score</span>
          <span>London percentile</span>
        </div>
        <div className="indicator-list">
          {socioeconomicMetricKeys.map((metric) => {
            const value = district[metric];
            const percentile = getPercentile(value, districts.map((item) => item[metric]));
            return (
              <div className="indicator-row" key={metric}>
                <span>{socioeconomicLabels[metric]}</span>
                <strong>{value.toFixed(1)}</strong>
                <span className="percentile-bar" title={`${percentile}th percentile in London`}>
                  <i style={{ width: `${percentile}%` }} />
                </span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="quality-strip" aria-label="Mapping quality">
        <span>
          <strong>{district.lsoaCount}</strong> LSOAs included
        </span>
        <span>
          <strong>{Math.round(district.meanOverlapShare * 100)}%</strong> mean overlap
        </span>
        <span>
          <strong>{district.excludedLsoaCount}</strong> excluded
        </span>
      </section>
    </aside>
  );
}
