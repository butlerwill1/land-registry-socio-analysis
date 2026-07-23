import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { AlertTriangle, LoaderCircle } from "lucide-react";
import { AppHeader } from "./components/AppHeader";
import { ControlRail } from "./components/ControlRail";
import {
  loadDistrictDetail,
  loadEntitlements,
  loadInitialData,
  loadLsoaBoundaries,
  loadMapMetric,
} from "./lib/data";
import { priceMetricKeys } from "./lib/metrics";
import {
  getAvailableTransactionYears,
  isMetricAvailable,
  type PlanId,
} from "./lib/plans";
import type {
  AppMetadata,
  AtlasFeatureCollection,
  DistrictRecord,
  MapMetricResponse,
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
  const [premiumDistrict, setPremiumDistrict] = useState<DistrictRecord>();
  const [mapMetric, setMapMetric] = useState<MapMetricResponse>();
  const [plan, setPlan] = useState<PlanId>(getInitialPlan);
  const [pricingOpen, setPricingOpen] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [authConfigured, setAuthConfigured] = useState(false);

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

  useEffect(() => {
    let active = true;
    const initialise = async () => {
      const initialPlan = getInitialPlan();
      if (!import.meta.env.DEV) {
        const auth = await import("./lib/auth");
        if (!active) return;
        setAuthConfigured(auth.isAuthConfigured());
        if (auth.isAuthConfigured()) await auth.initialiseAuthentication();
      }
      const entitlements = await loadEntitlements(initialPlan);
      if (!active) return;
      setAuthenticated(entitlements.authenticated);
      if (!import.meta.env.DEV) setPlan(entitlements.plan);
    };
    initialise().catch(() => {
      // Free static data remains usable when authentication or the API is unavailable.
    });
    return () => {
      active = false;
    };
  }, []);

  const publicSelected = useMemo(
    () => data?.districts.find((district) => district.district === selectedDistrict),
    [data, selectedDistrict],
  );
  const selected =
    plan === "pro" && premiumDistrict?.district === selectedDistrict
      ? premiumDistrict
      : publicSelected;
  const availableYears = useMemo(
    () =>
      data
        ? getAvailableTransactionYears(plan, data.metadata.years, data.metadata.latestCompleteYear)
        : [],
    [data, plan],
  );
  const selectedYear = availableYears.includes(year)
    ? year
    : (availableYears.at(-1) ?? year);

  useEffect(() => {
    if (plan !== "pro" || !data) {
      setPremiumDistrict(undefined);
      return;
    }
    const controller = new AbortController();
    loadDistrictDetail(selectedDistrict, plan, controller.signal)
      .then(setPremiumDistrict)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Premium district data could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [data, plan, selectedDistrict]);

  useEffect(() => {
    if (plan !== "pro" || !data) {
      setMapMetric(undefined);
      return;
    }
    const controller = new AbortController();
    loadMapMetric(metric, selectedYear, plan, controller.signal)
      .then(setMapMetric)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(
          reason instanceof Error ? reason.message : "Premium map data could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [data, metric, plan, selectedYear]);

  const lsoaMetric =
    priceMetricKeys.has(metric) || metric === "populationDensity" ? "overall" : metric;

  useEffect(() => {
    if (!lsoaEnabled || plan !== "pro") {
      setLsoaBoundaries(undefined);
      return;
    }
    const controller = new AbortController();
    setLsoaError(undefined);
    setLsoaLoading(true);
    loadLsoaBoundaries(selectedDistrict, lsoaMetric, plan, controller.signal)
      .then(setLsoaBoundaries)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setLsoaError(
          reason instanceof Error ? reason.message : "The LSOA layer could not be loaded.",
        );
        setLsoaEnabled(false);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLsoaLoading(false);
      });
    return () => controller.abort();
  }, [lsoaEnabled, lsoaMetric, plan, selectedDistrict]);

  const handleLsoaChange = (enabled: boolean) => {
    setLsoaEnabled(enabled);
    if (!enabled) return;
    if (priceMetricKeys.has(metric) || metric === "populationDensity") setMetric("overall");
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
                setYear(
                  getAvailableTransactionYears(
                    "free",
                    data.metadata.years,
                    data.metadata.latestCompleteYear,
                  ).at(-1) ?? data.metadata.latestCompleteYear,
                );
                if (!isMetricAvailable("free", metric)) setMetric("medianPrice");
              }
            : undefined
        }
      />
      <div className="workspace">
        <ControlRail
          metadata={data.metadata}
          availableYears={availableYears}
          districts={data.districts}
          metric={metric}
          year={selectedYear}
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
            year={selectedYear}
            lsoaEnabled={lsoaEnabled}
            lsoaBoundaries={lsoaBoundaries}
            mapMetric={mapMetric}
            onDistrictChange={setSelectedDistrict}
          />
        </Suspense>
        <Suspense fallback={<div className="detail-loading"><LoaderCircle className="spin" size={22} /> Loading analysis</div>}>
          <DetailPanel
            district={selected}
            districts={data.districts}
            year={selectedYear}
            plan={plan}
            latestCompleteYear={data.metadata.latestCompleteYear}
            onUpgrade={() => setPricingOpen(true)}
          />
        </Suspense>
      </div>
      <Suspense fallback={null}>
        <PricingDialog
          open={pricingOpen}
          currentPlan={plan}
          authenticated={authenticated}
          authConfigured={authConfigured}
          allowLocalPreview={import.meta.env.DEV}
          onClose={() => setPricingOpen(false)}
          onPreviewPro={() => setPlan("pro")}
          onSignIn={async () => {
            const { signIn } = await import("./lib/auth");
            await signIn();
          }}
        />
      </Suspense>
    </div>
  );
}
