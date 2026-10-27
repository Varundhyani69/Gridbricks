from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.services.analysis import (
    NormalizedRecord,
    _aggregate_actuals,
    _delivery_starts,
    _normalize,
    _select_forecasts,
    _validate_fuel_types,
)
from app.services.elexon import ElexonUpstreamError, FuelRecord, WindForecastRecord


def record(start: str, published: str, generation: float) -> NormalizedRecord:
    return NormalizedRecord(
        datetime.fromisoformat(start.replace("Z", "+00:00")),
        datetime.fromisoformat(published.replace("Z", "+00:00")),
        generation,
    )


def test_latest_forecast_at_or_before_cutoff_is_selected_per_interval() -> None:
    first = datetime(2026, 1, 2, 0, tzinfo=UTC)
    second = first + timedelta(hours=1)
    starts = [first, second]
    forecasts = [
        record("2026-01-02T00:00:00Z", "2026-01-01T08:00:00Z", 100),
        record("2026-01-02T00:00:00Z", "2026-01-01T09:30:00Z", 110),
        record("2026-01-02T00:00:00Z", "2026-01-01T10:00:00Z", 120),
        record("2026-01-02T00:00:00Z", "2026-01-01T10:00:01Z", 999),
        record("2026-01-02T01:00:00Z", "2026-01-01T09:00:00Z", 200),
    ]

    selected, duplicates, conflicts = _select_forecasts(forecasts, starts, time(10, 0))

    assert selected[first].generation == 120
    assert selected[first].publish_time == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert selected[second].generation == 200
    assert duplicates == 0
    assert conflicts == 0


def test_forecast_selection_reports_intervals_without_eligible_version() -> None:
    first = datetime(2026, 1, 2, 0, tzinfo=UTC)
    second = first + timedelta(hours=1)
    forecasts = [record("2026-01-02T01:00:00Z", "2026-01-01T11:00:00Z", 200)]

    selected, _, _ = _select_forecasts(forecasts, [first, second], time(10, 0))

    assert first not in selected
    assert second not in selected


def test_identical_forecast_duplicates_are_deduplicated_and_counted() -> None:
    first = datetime(2026, 1, 2, 0, tzinfo=UTC)
    duplicate_rows = [
        record("2026-01-02T00:00:00Z", "2026-01-01T09:30:00Z", 110),
        record("2026-01-02T00:00:00Z", "2026-01-01T09:30:00Z", 110),
    ]

    selected, duplicates, conflicts = _select_forecasts(duplicate_rows, [first], time(10, 0))

    assert selected[first].generation == 110
    assert duplicates == 1
    assert conflicts == 0


def test_conflicting_same_publication_forecasts_are_not_selected() -> None:
    first = datetime(2026, 1, 2, 0, tzinfo=UTC)
    conflicting_rows = [
        record("2026-01-02T00:00:00Z", "2026-01-01T09:30:00Z", 110),
        record("2026-01-02T00:00:00Z", "2026-01-01T09:30:00Z", 111),
    ]

    selected, duplicates, conflicts = _select_forecasts(conflicting_rows, [first], time(10, 0))

    assert first not in selected
    assert duplicates == 1
    assert conflicts == 1


def test_two_complete_half_hours_are_averaged_to_hourly_mw() -> None:
    start = datetime(2026, 1, 2, 0, tzinfo=UTC)
    half_hours = [
        record("2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z", 100),
        record("2026-01-02T00:30:00Z", "2026-01-02T01:00:00Z", 120),
    ]

    hourly, duplicates, conflicts, missing = _aggregate_actuals(half_hours, [start])

    assert hourly == {start: 110}
    assert duplicates == 0
    assert conflicts == 0
    assert missing == 0


def test_missing_half_hour_is_not_interpolated_or_treated_as_zero() -> None:
    start = datetime(2026, 1, 2, 0, tzinfo=UTC)
    half_hours = [record("2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z", 100)]

    hourly, _, _, missing = _aggregate_actuals(half_hours, [start])

    assert hourly == {}
    assert missing == 1


def test_latest_published_actual_value_wins_for_duplicate_delivery_interval() -> None:
    start = datetime(2026, 1, 2, 0, tzinfo=UTC)
    rows = [
        record("2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z", 100),
        record("2026-01-02T00:00:00Z", "2026-01-02T01:00:00Z", 110),
        record("2026-01-02T00:30:00Z", "2026-01-02T01:00:00Z", 120),
    ]

    hourly, duplicates, conflicts, missing = _aggregate_actuals(rows, [start])

    assert hourly == {start: 115}
    assert duplicates == 1
    assert conflicts == 0
    assert missing == 0


def test_same_publication_actual_conflict_leaves_hour_unmatched() -> None:
    start = datetime(2026, 1, 2, 0, tzinfo=UTC)
    rows = [
        record("2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z", 100),
        record("2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z", 101),
        record("2026-01-02T00:30:00Z", "2026-01-02T01:00:00Z", 120),
    ]

    hourly, _, conflicts, missing = _aggregate_actuals(rows, [start])

    assert hourly == {}
    assert conflicts == 1
    assert missing == 1


def test_delivery_generation_accounts_for_daylight_saving_hour_counts() -> None:
    spring_forward = _delivery_starts(date(2026, 3, 28), date(2026, 3, 28))
    fall_back = _delivery_starts(date(2026, 10, 24), date(2026, 10, 24))

    assert len(spring_forward) == 23
    assert len(fall_back) == 25


def test_normalization_counts_null_generation_and_requires_utc_offsets() -> None:
    rows = [
        FuelRecord.model_validate(
            {
                "startTime": "2026-01-02T00:00:00Z",
                "publishTime": "2026-01-02T00:30:00Z",
                "generation": 100,
                "fuelType": "WIND",
            }
        ),
        FuelRecord.model_validate(
            {
                "startTime": "2026-01-02T00:30:00Z",
                "publishTime": "2026-01-02T01:00:00Z",
                "generation": None,
                "fuelType": "WIND",
            }
        ),
        FuelRecord.model_validate(
            {
                "startTime": "2026-01-02T01:00:00Z",
                "publishTime": "2026-01-02T01:30:00Z",
                "generation": -1,
                "fuelType": "WIND",
            }
        ),
    ]

    normalized, invalid_values = _normalize(rows)

    assert len(normalized) == 1
    assert normalized[0].start_time.tzinfo == UTC
    assert invalid_values == 2


def test_actual_filter_keeps_only_wind_records() -> None:
    rows = [
        FuelRecord.model_validate(
            {
                "startTime": "2026-01-02T00:00:00Z",
                "publishTime": "2026-01-02T00:30:00Z",
                "generation": 100,
                "fuelType": "WIND",
            }
        ),
        FuelRecord.model_validate(
            {
                "startTime": "2026-01-02T00:30:00Z",
                "publishTime": "2026-01-02T01:00:00Z",
                "generation": 500,
                "fuelType": "NUCLEAR",
            }
        ),
    ]

    filtered = _validate_fuel_types(rows)

    assert len(filtered) == 1
    assert filtered[0].fuel_type == "WIND"


def test_malformed_timestamp_is_an_upstream_contract_error() -> None:
    row = WindForecastRecord.model_validate(
        {"startTime": "not-a-time", "publishTime": "2026-01-01T09:30:00Z", "generation": 1}
    )

    with pytest.raises(ElexonUpstreamError, match="invalid timestamp"):
        _normalize([row])
