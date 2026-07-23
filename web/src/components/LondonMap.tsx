import { useEffect, useMemo, useRef, useState } from "react";
import type { Feature } from "geojson";
import maplibregl, { type GeoJSONSource, type Map as MapLibreMap } from "maplibre-gl";
import { Layers3 } from "lucide-react";
import {
  getMetricValue,
  getQuantileBreaks,
  metricByKey,
  priceMetricKeys,
} from "../lib/metrics";
import type {
  AtlasFeatureCollection,
  DistrictRecord,
  MapMetricResponse,
  MetricKey,
} from "../types";

const COLOURS = ["#d9f1ed", "#b7e1da", "#82c9bd", "#4ba99a", "#1f8878", "#086354"];
const EMPTY_COLOUR = "#dfe5e2";

interface LondonMapProps {
  boundaries: AtlasFeatureCollection;
  districts: DistrictRecord[];
  selectedDistrict: string;
  metric: MetricKey;
  year: number;
  lsoaEnabled: boolean;
  lsoaBoundaries?: AtlasFeatureCollection;
  mapMetric?: MapMetricResponse;
  onDistrictChange: (district: string) => void;
}

function withValues(
  collection: AtlasFeatureCollection,
  records: Map<string, DistrictRecord>,
  metric: MetricKey,
  year: number,
  apiValues?: Map<string, number | null>,
): AtlasFeatureCollection {
  return {
    ...collection,
    features: collection.features.map((feature) => {
      const districtCode = String(feature.properties?.district ?? "");
      const district = records.get(districtCode);
      return {
        ...feature,
        properties: {
          ...feature.properties,
          value: apiValues
            ? (apiValues.get(districtCode) ?? null)
            : district
              ? getMetricValue(district, metric, year)
              : null,
        },
      };
    }),
  };
}

function withLsoaValues(
  collection: AtlasFeatureCollection,
  selectedDistrict: string,
  metric: MetricKey,
): AtlasFeatureCollection {
  return {
    ...collection,
    features: collection.features
      .filter(
        (feature) =>
          feature.properties?.district === selectedDistrict &&
          feature.properties?.includedInDistrictSummary === true,
      )
      .map((feature) => {
        const rawValue = feature.properties?.value ?? feature.properties?.[metric];
        return {
          ...feature,
          properties: {
            ...feature.properties,
            value: typeof rawValue === "number" ? rawValue : null,
          },
        };
      }),
  };
}

function colourExpression(breaks: number[]): any {
  if (breaks.length === 0) return EMPTY_COLOUR;
  const steps: unknown[] = [
    "step",
    ["to-number", ["get", "value"]],
    COLOURS[0],
  ];
  let previous = Number.NEGATIVE_INFINITY;
  breaks.forEach((value, index) => {
    if (value > previous) {
      steps.push(value, COLOURS[index + 1]);
      previous = value;
    }
  });
  return [
    "case",
    ["==", ["get", "value"], null],
    EMPTY_COLOUR,
    steps,
  ];
}

function getFeatureBounds(feature: Feature): maplibregl.LngLatBoundsLike | undefined {
  if (!feature.geometry || !("coordinates" in feature.geometry)) return undefined;
  const coordinates = feature.geometry.coordinates as unknown;
  const bounds = new maplibregl.LngLatBounds();

  const visit = (value: unknown) => {
    if (!Array.isArray(value)) return;
    if (typeof value[0] === "number" && typeof value[1] === "number") {
      bounds.extend([value[0], value[1]] as [number, number]);
      return;
    }
    value.forEach(visit);
  };
  visit(coordinates);
  return bounds.isEmpty() ? undefined : bounds;
}

export default function LondonMap({
  boundaries,
  districts,
  selectedDistrict,
  metric,
  year,
  lsoaEnabled,
  lsoaBoundaries,
  mapMetric,
  onDistrictChange,
}: LondonMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const onDistrictChangeRef = useRef(onDistrictChange);
  const metricRef = useRef(metric);
  const [mapReady, setMapReady] = useState(false);
  const recordMap = useMemo(
    () => new Map(districts.map((district) => [district.district, district])),
    [districts],
  );
  const apiValueMap = useMemo(
    () =>
      mapMetric && mapMetric.metric === metric && mapMetric.year === year
        ? new Map(mapMetric.values.map((item) => [item.district, item.value]))
        : undefined,
    [mapMetric, metric, year],
  );

  useEffect(() => {
    onDistrictChangeRef.current = onDistrictChange;
  }, [onDistrictChange]);

  useEffect(() => {
    metricRef.current = metric;
  }, [metric]);

  const districtData = useMemo(
    () => withValues(boundaries, recordMap, metric, year, apiValueMap),
    [apiValueMap, boundaries, metric, recordMap, year],
  );
  const values = useMemo(
    () =>
      (apiValueMap
        ? [...apiValueMap.values()]
        : districts.map((district) => getMetricValue(district, metric, year)))
        .filter((value): value is number => value !== null && Number.isFinite(value)),
    [apiValueMap, districts, metric, year],
  );
  const breaks = useMemo(() => getQuantileBreaks(values), [values]);

  const lsoaMetric = priceMetricKeys.has(metric) || metric === "populationDensity" ? "overall" : metric;
  const lsoaData = useMemo(
    () =>
      lsoaBoundaries
        ? withLsoaValues(lsoaBoundaries, selectedDistrict, lsoaMetric)
        : undefined,
    [lsoaBoundaries, lsoaMetric, selectedDistrict],
  );
  const lsoaBreaks = useMemo(
    () =>
      getQuantileBreaks(
        lsoaData?.features.map((feature) => Number(feature.properties?.value)) ?? [],
      ),
    [lsoaData],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      center: [-0.11, 51.505],
      zoom: 9.25,
      minZoom: 8.25,
      maxZoom: 15,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#eef2f0" } },
          { id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": 0.42, "raster-saturation": -0.8 } },
        ],
      },
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");

    map.on("load", () => {
      map.addSource("districts", { type: "geojson", data: districtData });
      map.addLayer({
        id: "district-fill",
        type: "fill",
        source: "districts",
        paint: {
          "fill-color": colourExpression(breaks),
          "fill-opacity": 0.77,
        },
      });
      map.addLayer({
        id: "district-lines",
        type: "line",
        source: "districts",
        paint: { "line-color": "#ffffff", "line-width": 1.1, "line-opacity": 0.95 },
      });
      map.addLayer({
        id: "district-selected",
        type: "line",
        source: "districts",
        filter: ["==", ["get", "district"], selectedDistrict],
        paint: { "line-color": "#e84d2f", "line-width": 3.2 },
      });

      map.on("click", "district-fill", (event) => {
        const district = String(event.features?.[0]?.properties?.district ?? "");
        if (district) onDistrictChangeRef.current(district);
      });
      map.on("mousemove", "district-fill", (event) => {
        map.getCanvas().style.cursor = "pointer";
        const properties = event.features?.[0]?.properties;
        if (!properties) return;
        const value = Number(properties.value);
        popupRef.current?.remove();
        popupRef.current = new maplibregl.Popup({ closeButton: false, offset: 12 })
          .setLngLat(event.lngLat)
          .setHTML(
            `<strong>${properties.district}</strong><span>${properties.areaName}</span><b>${Number.isFinite(value) ? metricByKey[metricRef.current].format(value) : "No data"}</b>`,
          )
          .addTo(map);
      });
      map.on("mouseleave", "district-fill", () => {
        map.getCanvas().style.cursor = "";
        popupRef.current?.remove();
      });
      setMapReady(true);
    });

    mapRef.current = map;
    return () => {
      popupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    (map.getSource("districts") as GeoJSONSource)?.setData(districtData);
    map.setPaintProperty("district-fill", "fill-color", colourExpression(breaks));
  }, [breaks, districtData, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    map.setFilter("district-selected", ["==", ["get", "district"], selectedDistrict]);
    const feature = boundaries.features.find(
      (item) => item.properties?.district === selectedDistrict,
    );
    const bounds = feature && getFeatureBounds(feature);
    if (bounds) map.fitBounds(bounds, { padding: 90, maxZoom: 11.1, duration: 700 });
  }, [boundaries, mapReady, selectedDistrict]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map || !lsoaData) return;
    const existing = map.getSource("lsoas") as GeoJSONSource | undefined;
    if (existing) {
      existing.setData(lsoaData);
    } else {
      map.addSource("lsoas", { type: "geojson", data: lsoaData });
      map.addLayer({
        id: "lsoa-fill",
        type: "fill",
        source: "lsoas",
        paint: { "fill-color": colourExpression(lsoaBreaks), "fill-opacity": 0.88 },
      }, "district-lines");
      map.addLayer({
        id: "lsoa-lines",
        type: "line",
        source: "lsoas",
        paint: { "line-color": "#ffffff", "line-width": 0.8, "line-opacity": 0.9 },
      }, "district-lines");
    }
    map.setPaintProperty("lsoa-fill", "fill-color", colourExpression(lsoaBreaks));
    map.setLayoutProperty("lsoa-fill", "visibility", lsoaEnabled ? "visible" : "none");
    map.setLayoutProperty("lsoa-lines", "visibility", lsoaEnabled ? "visible" : "none");
  }, [lsoaBreaks, lsoaData, lsoaEnabled, mapReady]);

  const legendMetric = lsoaEnabled ? metricByKey[lsoaMetric] : metricByKey[metric];
  const legendValues = lsoaEnabled && lsoaData
    ? lsoaData.features
        .map((feature) => feature.properties?.value)
        .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
    : values;
  const legendMinimum = legendValues.length > 0 ? Math.min(...legendValues) : undefined;
  const legendMaximum = legendValues.length > 0 ? Math.max(...legendValues) : undefined;

  return (
    <main className="map-region" aria-label="London postcode district map">
      <div ref={containerRef} className="map-canvas" />
      <div className="map-mode">
        <Layers3 size={15} aria-hidden="true" />
        {lsoaEnabled ? `${selectedDistrict} · LSOA detail` : "Postcode districts"}
      </div>
      <div className="map-legend" aria-label={`${legendMetric.label} legend`}>
        <strong>{legendMetric.label}</strong>
        <div className="legend-ramp">
          {COLOURS.map((colour) => <i key={colour} style={{ backgroundColor: colour }} />)}
        </div>
        <div className="legend-labels">
          <span>{legendMinimum === undefined ? "No data" : legendMetric.format(legendMinimum)}</span>
          <span>{legendMaximum === undefined ? "" : legendMetric.format(legendMaximum)}</span>
        </div>
      </div>
    </main>
  );
}
