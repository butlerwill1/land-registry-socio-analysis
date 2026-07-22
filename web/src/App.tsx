import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { AlertTriangle, LoaderCircle } from "lucide-react";
import { AppHeader } from "./components/AppHeader";
import { ControlRail } from "./components/ControlRail";
import { loadInitialData, loadLsoaBoundaries } from "./lib/data";
import { priceMetricKeys } from "./lib/metrics";
import type {
  AppMetadata,
  AtlasFeatureCollection,
  DistrictRecord,
  MetricKey,
} from "./types";

const LondonMap = lazy(() => import("./components/LondonMap"));
const DetailPanel = lazy(() =>
  import("./components/DetailPanel").then((module) => ({ default: module.DetailPanel })),
);

interface LoadedData {
  metadata: AppMetadata;
  districts: DistrictRecord[];
  districtBoundaries: AtlasFeatureCollection;
}

export function App() {
  const [data, setData] = useState<LoadedData>();
  const [error, setError] = useState<string>();
  const [metric, setMetric] = useState<MetricKey>("medianPrice");
  const [year, setYear] = useState(2025);
  const [selectedDistrict, setSelectedDistrict] = useState("SW11");
  const [lsoaEnabled, setLsoaEnabled] = useState(false);
  const [lsoaLoading, setLsoaLoading] = useState(false);
  const [lsoaBoundaries, setLsoaBoundaries] = useState<AtlasFeatureCollection>();

  useEffect(() => {
    loadInitialData()
      .then((loaded) => {
        setData(loaded);
        setYear(loaded.metadata.latestCompleteYear);
        if (!loaded.districts.some((district) => district.district === selectedDistrict)) {
          setSelectedDistrict(loaded.districts[0]?.district ?? "");
        }
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "The atlas data could not be loaded.");
      });
  }, []);

  const selected = useMemo(
    () => data?.districts.find((district) => district.district === selectedDistrict),
    [data, selectedDistrict],
  );

  const handleLsoaChange = async (enabled: boolean) => {
    setLsoaEnabled(enabled);
    if (!enabled) return;
    if (priceMetricKeys.has(metric) || metric === "populationDensity") setMetric("overall");
    if (lsoaBoundaries) return;
    setLsoaLoading(true);
    try {
      setLsoaBoundaries(await loadLsoaBoundaries());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The LSOA layer could not be loaded.");
      setLsoaEnabled(false);
    } finally {
      setLsoaLoading(false);
    }
  };

  const handleMetricChange = (nextMetric: MetricKey) => {
    setMetric(nextMetric);
    if (priceMetricKeys.has(nextMetric) || nextMetric === "populationDensity") {
      setLsoaEnabled(false);
    }
  };

  if (error) {
    return (
      <div className="full-state error-state" role="alert">
        <AlertTriangle size={28} />
        <h1>London Flat Atlas could not start</h1>
        <p>{error}</p>
      </div>
    );
  }

  if (!data || !selected) {
    return (
      <div className="full-state" aria-live="polite">
        <LoaderCircle className="spin" size={28} />
        <h1>Loading London Flat Atlas</h1>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppHeader metadata={data.metadata} />
      <div className="workspace">
        <ControlRail
          metadata={data.metadata}
          districts={data.districts}
          metric={metric}
          year={year}
          selectedDistrict={selectedDistrict}
          lsoaEnabled={lsoaEnabled}
          lsoaLoading={lsoaLoading}
          onMetricChange={handleMetricChange}
          onYearChange={setYear}
          onDistrictChange={setSelectedDistrict}
          onLsoaChange={handleLsoaChange}
        />
        <Suspense fallback={<div className="map-loading"><LoaderCircle className="spin" size={26} /> Loading map</div>}>
          <LondonMap
            boundaries={data.districtBoundaries}
            districts={data.districts}
            selectedDistrict={selectedDistrict}
            metric={metric}
            year={year}
            lsoaEnabled={lsoaEnabled}
            lsoaBoundaries={lsoaBoundaries}
            onDistrictChange={setSelectedDistrict}
          />
        </Suspense>
        <Suspense fallback={<div className="detail-loading"><LoaderCircle className="spin" size={22} /> Loading analysis</div>}>
          <DetailPanel district={selected} districts={data.districts} year={year} />
        </Suspense>
      </div>
    </div>
  );
}
