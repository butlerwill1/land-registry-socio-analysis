from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .schemas import (
    AppMetadata,
    DistrictRecord,
    FREE_METRICS,
    LsoaFeatureCollection,
    LsoaMapFeature,
    LsoaMapProperties,
    LsoaMapResponse,
    MapMetricResponse,
    MapValue,
    MetricKey,
    PlanId,
    PRICE_METRICS,
)


class DataAccessError(ValueError):
    pass


class DataRepository:
    def __init__(self, data_dir: Path, free_transaction_years: int = 5) -> None:
        self._data_dir = data_dir
        self._free_transaction_years = free_transaction_years
        self._metadata: AppMetadata | None = None
        self._districts: dict[str, DistrictRecord] = {}
        self._lsoas: LsoaFeatureCollection | None = None

    @property
    def loaded(self) -> bool:
        return self._metadata is not None and bool(self._districts) and self._lsoas is not None

    @property
    def metadata(self) -> AppMetadata:
        if self._metadata is None:
            raise RuntimeError("Data repository has not been loaded")
        return self._metadata

    @property
    def free_years(self) -> list[int]:
        return [
            year
            for year in self.metadata.years
            if year <= self.metadata.latestCompleteYear
        ][-self._free_transaction_years :]

    def load(self) -> None:
        try:
            metadata = AppMetadata.model_validate_json(
                (self._data_dir / "metadata.json").read_text(encoding="utf-8")
            )
            records = TypeAdapter(list[DistrictRecord]).validate_json(
                (self._data_dir / "districts.private.json").read_text(encoding="utf-8")
            )
            lsoas = LsoaFeatureCollection.model_validate_json(
                (self._data_dir / "lsoa.private.geojson").read_text(encoding="utf-8")
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"Required API data file is missing: {exc.filename}") from exc
        except ValidationError as exc:
            raise RuntimeError(f"API data validation failed: {exc}") from exc

        if len(records) != metadata.districtCount:
            raise RuntimeError("District data count does not match metadata")
        if len(lsoas.features) != metadata.lsoaCount:
            raise RuntimeError("LSOA data count does not match metadata")
        district_codes = [record.district for record in records]
        if len(district_codes) != len(set(district_codes)):
            raise RuntimeError("District data contains duplicate codes")
        self._metadata = metadata
        self._districts = {record.district: record for record in records}
        self._lsoas = lsoas

    def get_district(self, district: str, plan: PlanId) -> DistrictRecord:
        try:
            record = self._districts[district.upper()]
        except KeyError as exc:
            raise KeyError(f"Unknown postcode district: {district}") from exc
        if plan == "pro":
            return record.model_copy(update={"percentiles": self._percentiles(record)})
        return record.model_copy(
            update={
                "population": None,
                "populationDensity": None,
                "income": None,
                "employment": None,
                "education": None,
                "health": None,
                "crime": None,
                "housingBarriers": None,
                "environment": None,
                "percentiles": None,
                "history": [
                    item for item in record.history if item.year in set(self.free_years)
                ],
            }
        )

    def map_values(self, metric: MetricKey, year: int, plan: PlanId) -> MapMetricResponse:
        allowed_years = self.metadata.years if plan == "pro" else self.free_years
        if year not in allowed_years:
            raise DataAccessError(f"Year {year} is not available on the {plan} plan")
        if plan == "free" and metric not in FREE_METRICS:
            raise PermissionError(f"Metric {metric} requires the Pro plan")

        values = [
            MapValue(
                district=record.district,
                value=self._metric_value(record, metric, year),
            )
            for record in self._districts.values()
        ]
        return MapMetricResponse(metric=metric, year=year, plan=plan, values=values)

    def lsoa_values(self, district: str, metric: MetricKey) -> LsoaMapResponse:
        if metric in PRICE_METRICS or metric == "populationDensity":
            raise DataAccessError(f"Metric {metric} is not available at LSOA level")
        code = district.upper()
        if code not in self._districts:
            raise KeyError(f"Unknown postcode district: {district}")
        if self._lsoas is None:
            raise RuntimeError("Data repository has not been loaded")

        features = []
        for feature in self._lsoas.features:
            properties = feature.properties
            if properties.district != code or not properties.includedInDistrictSummary:
                continue
            features.append(
                LsoaMapFeature(
                    properties=LsoaMapProperties(
                        lsoaCode=properties.lsoaCode,
                        lsoaName=properties.lsoaName,
                        district=properties.district,
                        overlapShare=properties.overlapShare,
                        assignmentConfidence=properties.assignmentConfidence,
                        includedInDistrictSummary=True,
                        value=getattr(properties, metric),
                    ),
                    geometry=feature.geometry,
                    id=feature.id or properties.lsoaCode,
                )
            )
        return LsoaMapResponse(metric=metric, district=code, features=features)

    def _percentiles(self, selected: DistrictRecord) -> dict[MetricKey, int]:
        metrics: tuple[MetricKey, ...] = (
            "overall",
            "income",
            "employment",
            "education",
            "health",
            "crime",
            "housingBarriers",
            "environment",
            "populationDensity",
        )
        result: dict[MetricKey, int] = {}
        for metric in metrics:
            value = getattr(selected, metric)
            if value is None:
                continue
            values = sorted(
                candidate
                for record in self._districts.values()
                if (candidate := getattr(record, metric)) is not None
            )
            if len(values) < 2:
                result[metric] = 50
                continue
            below_or_equal = sum(candidate <= value for candidate in values)
            result[metric] = round(((below_or_equal - 1) / (len(values) - 1)) * 100)
        return result

    @staticmethod
    def _metric_value(
        record: DistrictRecord, metric: MetricKey, year: int
    ) -> float | None:
        if metric in PRICE_METRICS:
            year_record = next((item for item in record.history if item.year == year), None)
            return None if year_record is None else getattr(year_record, metric)
        return getattr(record, metric)
