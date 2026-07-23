import {
  Check,
  ChevronLeft,
  ChevronRight,
  Info,
  Layers3,
  LockKeyhole,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { metricDefinitions, priceMetricKeys } from "../lib/metrics";
import { isMetricAvailable, type PlanId } from "../lib/plans";
import type { AppMetadata, DistrictRecord, MetricKey } from "../types";

interface ControlRailProps {
  metadata: AppMetadata;
  districts: DistrictRecord[];
  metric: MetricKey;
  year: number;
  selectedDistrict: string;
  lsoaEnabled: boolean;
  lsoaLoading: boolean;
  lsoaError?: string;
  plan: PlanId;
  onUpgrade: () => void;
  onMetricChange: (metric: MetricKey) => void;
  onYearChange: (year: number) => void;
  onDistrictChange: (district: string) => void;
  onLsoaChange: (enabled: boolean) => void;
}

export function ControlRail({
  metadata,
  districts,
  metric,
  year,
  selectedDistrict,
  lsoaEnabled,
  lsoaLoading,
  lsoaError,
  plan,
  onUpgrade,
  onMetricChange,
  onYearChange,
  onDistrictChange,
  onLsoaChange,
}: ControlRailProps) {
  const [query, setQuery] = useState(selectedDistrict);
  const [activeResultIndex, setActiveResultIndex] = useState(0);
  useEffect(() => {
    setQuery(selectedDistrict);
  }, [selectedDistrict]);
  const results = useMemo(() => {
    const normalised = query.trim().toLowerCase();
    if (!normalised) return [];
    return districts
      .filter(
        (district) =>
          district.district.toLowerCase().includes(normalised) ||
          district.areaName.toLowerCase().includes(normalised),
      )
      .slice(0, 5);
  }, [districts, query]);

  const selected = districts.find((district) => district.district === selectedDistrict);
  const yearIndex = metadata.years.indexOf(year);
  const isPriceMetric = priceMetricKeys.has(metric);
  const isPartialYear = year > metadata.latestCompleteYear;
  const showResults = query !== selectedDistrict && results.length > 0;

  const selectDistrict = (district: DistrictRecord) => {
    setQuery(district.district);
    setActiveResultIndex(0);
    onDistrictChange(district.district);
  };

  const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showResults) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveResultIndex((index) => Math.min(index + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveResultIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      selectDistrict(results[activeResultIndex]);
    } else if (event.key === "Escape") {
      setQuery(selectedDistrict);
    }
  };

  return (
    <aside className="control-rail" aria-label="Map controls">
      <section className="control-section">
        <label className="control-label" htmlFor="metric-select">
          Metric <Info size={14} aria-label="Map colour metric" />
        </label>
        <select
          id="metric-select"
          className="select-control"
          value={metric}
          onChange={(event) => {
            const nextMetric = event.target.value as MetricKey;
            if (!isMetricAvailable(plan, nextMetric)) {
              onUpgrade();
              return;
            }
            onMetricChange(nextMetric);
          }}
        >
          {["Property market", "Socioeconomic context"].map((group) => (
            <optgroup key={group} label={group}>
              {metricDefinitions
                .filter((definition) => definition.group === group)
                .map((definition) => (
                  <option key={definition.key} value={definition.key}>
                    {definition.label}
                    {!isMetricAvailable(plan, definition.key) ? " - Pro" : ""}
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
      </section>

      <section className="control-section">
        <div className="control-label-row">
          <label className="control-label" htmlFor="year-range">
            Year <Info size={14} aria-label="Transaction year" />
          </label>
          {isPartialYear && <span className="partial-inline">Partial</span>}
        </div>
        <div className="year-stepper">
          <button
            type="button"
            title="Previous year"
            aria-label="Previous year"
            disabled={yearIndex <= 0}
            onClick={() => onYearChange(metadata.years[yearIndex - 1])}
          >
            <ChevronLeft size={18} />
          </button>
          <output htmlFor="year-range">{year}</output>
          <button
            type="button"
            title="Next year"
            aria-label="Next year"
            disabled={yearIndex >= metadata.years.length - 1}
            onClick={() => onYearChange(metadata.years[yearIndex + 1])}
          >
            <ChevronRight size={18} />
          </button>
        </div>
        <input
          id="year-range"
          className="range-control"
          type="range"
          min={0}
          max={metadata.years.length - 1}
          value={yearIndex}
          onChange={(event) => onYearChange(metadata.years[Number(event.target.value)])}
        />
        <div className="range-labels" aria-hidden="true">
          <span>{metadata.years[0]}</span>
          <span>{metadata.years[Math.floor(metadata.years.length / 2)]}</span>
          <span>{metadata.latestYear}</span>
        </div>
        {isPartialYear && (
          <p className="control-hint partial-year-hint">
            Registered sales only. Recent totals will rise as HM Land Registry records complete.
          </p>
        )}
      </section>

      <section className="control-section">
        <span className="control-label">
          Map detail <Info size={14} aria-label="Boundary level" />
        </span>
        <div className="segmented-control" role="group" aria-label="Boundary level">
          <button
            type="button"
            className={!lsoaEnabled ? "active" : ""}
            aria-pressed={!lsoaEnabled}
            onClick={() => onLsoaChange(false)}
          >
            Districts
          </button>
          <button
            type="button"
            className={lsoaEnabled ? "active" : ""}
            aria-pressed={lsoaEnabled}
            onClick={() => {
              if (plan === "free") {
                onUpgrade();
                return;
              }
              onLsoaChange(true);
            }}
          >
            {plan === "free" && <LockKeyhole size={13} aria-hidden="true" />}
            {lsoaLoading ? "Loading..." : "LSOAs (2021)"}
          </button>
        </div>
        {isPriceMetric && !lsoaEnabled && (
          <p className="control-hint">LSOA detail switches the map to overall deprivation.</p>
        )}
        {lsoaError && (
          <p className="control-error" role="status">LSOA detail could not load. Select it to retry.</p>
        )}
      </section>

      <section className="control-section district-search">
        <label className="control-label" htmlFor="district-search">
          Find district
        </label>
        <div className="search-field">
          <Search size={17} aria-hidden="true" />
          <input
            id="district-search"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={showResults}
            aria-controls="district-search-results"
            aria-activedescendant={showResults ? `district-result-${activeResultIndex}` : undefined}
            value={query}
            autoComplete="off"
            placeholder="Postcode district or borough"
            onFocus={() => setQuery(query || selectedDistrict)}
            onChange={(event) => {
              setQuery(event.target.value);
              setActiveResultIndex(0);
            }}
            onKeyDown={handleSearchKeyDown}
          />
        </div>
        {showResults && (
          <div id="district-search-results" className="search-results" role="listbox" aria-label="District results">
            {results.map((district, index) => (
              <button
                id={`district-result-${index}`}
                type="button"
                role="option"
                aria-selected={index === activeResultIndex}
                key={district.district}
                onMouseEnter={() => setActiveResultIndex(index)}
                onClick={() => selectDistrict(district)}
              >
                <span>
                  <strong>{district.district}</strong>
                  <small>{district.areaName}</small>
                </span>
                {district.district === selectedDistrict && <Check size={16} />}
              </button>
            ))}
          </div>
        )}
        {selected && query === selectedDistrict && (
          <button type="button" className="selected-result" onClick={() => setQuery("")}>
            <Layers3 size={17} aria-hidden="true" />
            <span>
              <strong>{selected.district}</strong>
              <small>{selected.areaName}</small>
            </span>
            <Check size={16} aria-hidden="true" />
          </button>
        )}
      </section>

      <footer className="rail-footer">
        <span>{metadata.districtCount} postcode districts</span>
        <span>{metadata.lsoaCount.toLocaleString("en-GB")} mapped LSOAs</span>
        <span>Prices are nominal. Contains HM Land Registry data.</span>
      </footer>
    </aside>
  );
}
