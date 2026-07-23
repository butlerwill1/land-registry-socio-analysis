import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { AlertTriangle, LoaderCircle } from "lucide-react";
import { AppHeader } from "./components/AppHeader";
import { ControlRail } from "./components/ControlRail";
import { loadInitialData, loadLsoaBoundaries } from "./lib/data";
import { priceMetricKeys } from "./lib/metrics";
import { isMetricAvailable, type PlanId } from "./lib/plans";
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
const PricingDialog = lazy(() =>
  import("./components/PricingDialog").then((module) => ({ default: module.PricingDialog })),
);

function getInitialPlan(): PlanId {
  if (!import.meta.env.DEV) return "free";
  return new URLSearchParams(window.location.search).get("demoPlan") === "pro" ? "pro" : "free";
}

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
  const [lsoaError, setLsoaError] = useState<string>();
  const [lsoaBoundaries, setLsoaBoundaries] = useState<AtlasFeatureCollection>();
  const [plan, setPlan] = useState<PlanId>(getInitialPlan);
  const [pricingOpen, setPricingOpen] = useState(false);

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
    setLsoaError(undefined);
    if (priceMetricKeys.has(metric) || metric === "populationDensity") setMetric("overall");
    if (lsoaBoundaries) return;
    setLsoaLoading(true);
    try {
      setLsoaBoundaries(await loadLsoaBoundaries());
    } catch (reason) {
      setLsoaError(
        reason instanceof Error ? reason.message : "The LSOA layer could not be loaded.",
      );
      setLsoaEnabled(false);
    } finally {
      setLsoaLoading(false);
    }
  };

  const handleMetricChange = (nextMetric: MetricKey) => {
    if (!isMetricAvailable(plan, nextMetric)) {
      setPricingOpen(true);
      return;
    }
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
      <AppHeader
        metadata={data.metadata}
        plan={plan}
        onOpenPricing={() => setPricingOpen(true)}
        onExitPreview={
          plan === "pro" && import.meta.env.DEV
            ? () => {
                setPlan("free");
                setLsoaEnabled(false);
                if (!isMetricAvailable("free", metric)) setMetric("medianPrice");
              }
            : undefined
        }
      />
      <div className="workspace">
        <ControlRail
          metadata={data.metadata}
          districts={data.districts}
          metric={metric}
          year={year}
          selectedDistrict={selectedDistrict}
          lsoaEnabled={lsoaEnabled}
          lsoaLoading={lsoaLoading}
          lsoaError={lsoaError}
          plan={plan}
          onUpgrade={() => setPricingOpen(true)}
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
          <DetailPanel
            district={selected}
            districts={data.districts}
            year={year}
            plan={plan}
            onUpgrade={() => setPricingOpen(true)}
          />
        </Suspense>
      </div>
      <Suspense fallback={null}>
        <PricingDialog
          open={pricingOpen}
          currentPlan={plan}
          allowLocalPreview={import.meta.env.DEV}
          onClose={() => setPricingOpen(false)}
          onPreviewPro={() => setPlan("pro")}
        />
      </Suspense>
    </div>
  );
}
