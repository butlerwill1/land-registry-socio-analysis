import {
  Check,
  ChevronLeft,
  ChevronRight,
  Info,
  Layers3,
  Search,
} from "lucide-react";
import { useMemo, useState } from "react";
import { metricDefinitions, priceMetricKeys } from "../lib/metrics";
import type { AppMetadata, DistrictRecord, MetricKey } from "../types";

interface ControlRailProps {
  metadata: AppMetadata;
  districts: DistrictRecord[];
  metric: MetricKey;
  year: number;
  selectedDistrict: string;
  lsoaEnabled: boolean;
  lsoaLoading: boolean;
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
  onMetricChange,
  onYearChange,
  onDistrictChange,
  onLsoaChange,
}: ControlRailProps) {
  const [query, setQuery] = useState(selectedDistrict);
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

  const selectDistrict = (district: DistrictRecord) => {
    setQuery(district.district);
    onDistrictChange(district.district);
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
          onChange={(event) => onMetricChange(event.target.value as MetricKey)}
        >
          {["Property market", "Socioeconomic context"].map((group) => (
            <optgroup key={group} label={group}>
              {metricDefinitions
                .filter((definition) => definition.group === group)
                .map((definition) => (
                  <option key={definition.key} value={definition.key}>
                    {definition.label}
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
          {year > metadata.latestCompleteYear && <span className="partial-inline">Partial</span>}
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
          <span>{metadata.latestCompleteYear}</span>
          <span>{metadata.latestYear}</span>
        </div>
      </section>

      <section className="control-section">
        <span className="control-label">
          Map detail <Info size={14} aria-label="Boundary level" />
        </span>
        <div className="segmented-control" role="group" aria-label="Boundary level">
          <button
            type="button"
            className={!lsoaEnabled ? "active" : ""}
            onClick={() => onLsoaChange(false)}
          >
            Districts
          </button>
          <button
            type="button"
            className={lsoaEnabled ? "active" : ""}
            onClick={() => onLsoaChange(true)}
          >
            {lsoaLoading ? "Loading…" : "LSOAs (2021)"}
          </button>
        </div>
        {isPriceMetric && !lsoaEnabled && (
          <p className="control-hint">LSOA detail switches the map to overall deprivation.</p>
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
            value={query}
            autoComplete="off"
            placeholder="Postcode district or borough"
            onFocus={() => setQuery(query || selectedDistrict)}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        {query !== selectedDistrict && results.length > 0 && (
          <div className="search-results" role="listbox" aria-label="District results">
            {results.map((district) => (
              <button
                type="button"
                role="option"
                aria-selected={district.district === selectedDistrict}
                key={district.district}
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
        <span>Prices are nominal · Crown copyright and database rights 2025</span>
      </footer>
    </aside>
  );
}
