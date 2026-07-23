import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AppMetadata, DistrictRecord } from "../types";
import { ControlRail } from "./ControlRail";

const metadata: AppMetadata = {
  dataAsOf: "2026-01-30",
  boundarySource: "test",
  boundarySources: [],
  boundaryMethod: "test",
  boundarySourceRetrievedOn: "2026-01-30",
  centralBoundaryCoverageShare: 1,
  centralBoundaryDistrictMatchShare: 1,
  districtCount: 1,
  lsoaCount: 2,
  years: [2024, 2025],
  latestCompleteYear: 2025,
  latestYear: 2025,
  latestYearIsPartial: false,
  transactionCount: 10,
};

const district: DistrictRecord = {
  district: "SW11",
  areaName: "Battersea",
  hasSocioeconomicSummary: true,
  lsoaCount: 2,
  excludedLsoaCount: 0,
  meanOverlapShare: 1,
  areaKm2: 1,
  population: 100,
  populationDensity: 100,
  overall: 10,
  income: 10,
  employment: 10,
  education: 10,
  health: 10,
  crime: 10,
  housingBarriers: 10,
  environment: 10,
  history: [],
};

function renderRail(plan: "free" | "pro") {
  const onUpgrade = vi.fn();
  const onMetricChange = vi.fn();
  const onLsoaChange = vi.fn();
  render(
    <ControlRail
      metadata={metadata}
      districts={[district]}
      metric="medianPrice"
      year={2025}
      selectedDistrict="SW11"
      lsoaEnabled={false}
      lsoaLoading={false}
      plan={plan}
      onUpgrade={onUpgrade}
      onMetricChange={onMetricChange}
      onYearChange={vi.fn()}
      onDistrictChange={vi.fn()}
      onLsoaChange={onLsoaChange}
    />,
  );
  return { onUpgrade, onMetricChange, onLsoaChange };
}

describe("ControlRail plan gates", () => {
  it("opens pricing instead of enabling LSOA detail for Free", async () => {
    const callbacks = renderRail("free");
    await userEvent.click(screen.getByRole("button", { name: "LSOAs (2021)" }));
    expect(callbacks.onUpgrade).toHaveBeenCalledOnce();
    expect(callbacks.onLsoaChange).not.toHaveBeenCalled();
  });

  it("enables LSOA detail for Pro", async () => {
    const callbacks = renderRail("pro");
    await userEvent.click(screen.getByRole("button", { name: "LSOAs (2021)" }));
    expect(callbacks.onLsoaChange).toHaveBeenCalledWith(true);
    expect(callbacks.onUpgrade).not.toHaveBeenCalled();
  });

  it("marks premium metric options and gates their selection for Free", async () => {
    const callbacks = renderRail("free");
    const metric = screen.getByLabelText("Metric");
    expect(screen.getByRole("option", { name: "Income deprivation - Pro" })).toBeVisible();
    await userEvent.selectOptions(metric, "income");
    expect(callbacks.onUpgrade).toHaveBeenCalledOnce();
    expect(callbacks.onMetricChange).not.toHaveBeenCalled();
  });

  it("passes detailed metric selections through for Pro", async () => {
    const callbacks = renderRail("pro");
    await userEvent.selectOptions(screen.getByLabelText("Metric"), "income");
    expect(callbacks.onMetricChange).toHaveBeenCalledWith("income");
  });
});
