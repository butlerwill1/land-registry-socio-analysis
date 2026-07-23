from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.data_repository import DataAccessError, DataRepository


def test_free_district_is_physically_sanitised(repository: DataRepository) -> None:
    district = repository.get_district("sw11", "free")
    assert [item.year for item in district.history] == [2021, 2022, 2023, 2024, 2025]
    assert district.overall == 20
    assert district.income is None
    assert district.population is None
    assert district.populationDensity is None
    assert district.percentiles is None


def test_pro_district_has_full_history_and_server_percentiles(
    repository: DataRepository,
) -> None:
    district = repository.get_district("SW11", "pro")
    assert [item.year for item in district.history] == list(range(2020, 2027))
    assert district.income == 0.2
    assert district.populationDensity == 2_000
    assert district.percentiles is not None
    assert district.percentiles["overall"] == 0


def test_free_map_allows_core_metric_in_free_year(repository: DataRepository) -> None:
    response = repository.map_values("medianPrice", 2025, "free")
    assert response.plan == "free"
    assert len(response.values) == 2
    assert response.values[0].value is not None


def test_free_map_rejects_premium_metric(repository: DataRepository) -> None:
    with pytest.raises(PermissionError, match="requires the Pro"):
        repository.map_values("income", 2025, "free")


def test_free_map_rejects_old_and_partial_years(repository: DataRepository) -> None:
    with pytest.raises(DataAccessError, match="not available"):
        repository.map_values("medianPrice", 2020, "free")
    with pytest.raises(DataAccessError, match="not available"):
        repository.map_values("medianPrice", 2026, "free")


def test_pro_map_allows_full_history_and_premium_metric(
    repository: DataRepository,
) -> None:
    old_history = repository.map_values("transactions", 2020, "pro")
    premium = repository.map_values("income", 2026, "pro")
    assert len(old_history.values) == 2
    assert [item.value for item in premium.values] == [0.2, 0.3]


def test_lsoa_response_is_scoped_and_strips_other_metrics(
    repository: DataRepository,
) -> None:
    response = repository.lsoa_values("sw11", "income")
    assert response.district == "SW11"
    assert len(response.features) == 1
    assert response.features[0].properties.value == 0.1
    dumped = response.model_dump()
    assert "environment" not in dumped["features"][0]["properties"]


def test_lsoa_rejects_price_and_population_density(repository: DataRepository) -> None:
    with pytest.raises(DataAccessError, match="not available at LSOA"):
        repository.lsoa_values("SW11", "medianPrice")
    with pytest.raises(DataAccessError, match="not available at LSOA"):
        repository.lsoa_values("SW11", "populationDensity")


def test_repository_detects_metadata_count_mismatch(data_dir: Path) -> None:
    metadata_path = data_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["districtCount"] = 99
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(RuntimeError, match="count does not match"):
        DataRepository(data_dir).load()
