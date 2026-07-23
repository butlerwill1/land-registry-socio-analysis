from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


PlanId = Literal["free", "pro"]
BillingInterval = Literal["month", "year"]
MetricKey = Literal[
    "medianPrice",
    "averagePrice",
    "transactions",
    "overall",
    "income",
    "employment",
    "education",
    "health",
    "crime",
    "housingBarriers",
    "environment",
    "populationDensity",
]

PRICE_METRICS = frozenset({"medianPrice", "averagePrice", "transactions"})
FREE_METRICS = PRICE_METRICS | {"overall"}
PREMIUM_METRICS = frozenset(
    {
        "income",
        "employment",
        "education",
        "health",
        "crime",
        "housingBarriers",
        "environment",
        "populationDensity",
    }
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TransactionYear(ApiModel):
    year: int = Field(ge=1995, le=2100)
    transactions: int = Field(ge=0)
    averagePrice: float | None = Field(default=None, ge=0)
    medianPrice: float | None = Field(default=None, ge=0)


class DistrictRecord(ApiModel):
    district: str = Field(min_length=2, max_length=5, pattern=r"^[A-Z]{1,2}\d[A-Z\d]?$")
    areaName: str = Field(min_length=1)
    hasSocioeconomicSummary: bool
    lsoaCount: int = Field(ge=0)
    excludedLsoaCount: int = Field(ge=0)
    meanOverlapShare: float | None = Field(default=None, ge=0, le=1)
    areaKm2: float = Field(gt=0)
    population: int | None = Field(default=None, ge=0)
    populationDensity: float | None = Field(default=None, ge=0)
    overall: float | None = None
    income: float | None = None
    employment: float | None = None
    education: float | None = None
    health: float | None = None
    crime: float | None = None
    housingBarriers: float | None = None
    environment: float | None = None
    history: list[TransactionYear]
    percentiles: dict[MetricKey, int] | None = None

    @field_validator("history")
    @classmethod
    def validate_history(cls, history: list[TransactionYear]) -> list[TransactionYear]:
        years = [record.year for record in history]
        if years != sorted(years) or len(years) != len(set(years)):
            raise ValueError("District history years must be unique and sorted")
        return history


class BoundarySource(ApiModel):
    name: str
    role: str
    url: str
    licence: str
    attribution: str | None = None


class AppMetadata(ApiModel):
    generatedFrom: dict[str, str] | None = None
    dataAsOf: str
    boundarySource: str
    boundarySources: list[BoundarySource]
    boundaryMethod: str
    boundarySourceRetrievedOn: str
    centralBoundaryCoverageShare: float = Field(ge=0, le=1)
    centralBoundaryDistrictMatchShare: float = Field(ge=0, le=1)
    districtCount: int = Field(gt=0)
    lsoaCount: int = Field(gt=0)
    years: list[int]
    latestCompleteYear: int
    latestYear: int
    latestYearIsPartial: bool
    transactionCount: int = Field(ge=0)

    @field_validator("years")
    @classmethod
    def validate_years(cls, years: list[int]) -> list[int]:
        if years != sorted(years) or len(years) != len(set(years)):
            raise ValueError("Metadata years must be unique and sorted")
        return years


class LsoaProperties(ApiModel):
    lsoaCode: str
    lsoaName: str
    district: str
    overlapShare: float = Field(ge=0, le=1)
    assignmentConfidence: str
    includedInDistrictSummary: bool
    overall: float | None = None
    income: float | None = None
    employment: float | None = None
    education: float | None = None
    health: float | None = None
    crime: float | None = None
    housingBarriers: float | None = None
    environment: float | None = None
    population: int | None = Field(default=None, ge=0)


class GeoJsonFeature(ApiModel):
    type: Literal["Feature"]
    properties: LsoaProperties
    geometry: dict[str, Any]
    id: str | None = None


class LsoaFeatureCollection(ApiModel):
    type: Literal["FeatureCollection"]
    features: list[GeoJsonFeature]


class MapValue(ApiModel):
    district: str
    value: float | None


class MapMetricResponse(ApiModel):
    metric: MetricKey
    year: int
    plan: PlanId
    values: list[MapValue]


class LsoaMapProperties(ApiModel):
    lsoaCode: str
    lsoaName: str
    district: str
    overlapShare: float
    assignmentConfidence: str
    includedInDistrictSummary: Literal[True]
    value: float | None


class LsoaMapFeature(ApiModel):
    type: Literal["Feature"] = "Feature"
    properties: LsoaMapProperties
    geometry: dict[str, Any]
    id: str


class LsoaMapResponse(ApiModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    metric: MetricKey
    district: str
    features: list[LsoaMapFeature]


class EntitlementResponse(ApiModel):
    plan: PlanId
    authenticated: bool
    features: list[str]


class CheckoutRequest(ApiModel):
    plan: Literal["pro"]
    interval: BillingInterval


class RedirectResponse(ApiModel):
    url: HttpUrl


class WebhookResponse(ApiModel):
    received: Literal[True] = True
    duplicate: bool = False


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    dataLoaded: bool
    database: Literal["ok"]


class ErrorResponse(ApiModel):
    error: str


class Principal(ApiModel):
    subject: str | None = None
    email: str | None = None
    authenticated: bool = False
    devPlan: PlanId | None = None


class SubscriptionProjection(ApiModel):
    stripeSubscriptionId: str
    stripeCustomerId: str
    stripePriceId: str | None = None
    status: str
    currentPeriodEnd: datetime | None = None
    cancelAtPeriodEnd: bool = False
