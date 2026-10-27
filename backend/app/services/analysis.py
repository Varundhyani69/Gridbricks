from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import isfinite

from app.analytics.metrics import calculate_metrics
from app.core.config import LONDON, get_decision_cutoff
from app.models import (
    AccuracyResponse,
    ActualItem,
    ActualsResponse,
    AnalysisMetadata,
    DataQuality,
    ForecastItem,
    ForecastsResponse,
    IntervalRecord,
)
from app.services.elexon import (
    ElexonClient,
    ElexonUpstreamError,
    FuelRecord,
    WindForecastRecord,
)

ANALYSIS_FROM = date(2026, 1, 1)
ANALYSIS_TO = date(2026, 1, 31)


class InvalidAnalysisRange(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedRecord:
    start_time: datetime
    publish_time: datetime
    generation: float


def validate_decision_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise InvalidAnalysisRange("decision_date_to must not be earlier than decision_date_from")
    if date_from < ANALYSIS_FROM or date_to > ANALYSIS_TO:
        raise InvalidAnalysisRange("decision dates must be within January 2026")


def _require_utc_timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid Elexon {label} timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"Elexon {label} timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _normalize(
    rows: list[FuelRecord] | list[WindForecastRecord],
) -> tuple[list[NormalizedRecord], int]:
    records: list[NormalizedRecord] = []
    invalid_values = 0
    for row in rows:
        if row.generation is None or not isfinite(row.generation) or row.generation < 0:
            invalid_values += 1
            continue
        try:
            records.append(
                NormalizedRecord(
                    start_time=_require_utc_timestamp(row.start_time, "startTime"),
                    publish_time=_require_utc_timestamp(row.publish_time, "publishTime"),
                    generation=float(row.generation),
                )
            )
        except ValueError as exc:
            raise ElexonUpstreamError("Elexon record contains an invalid timestamp") from exc
    return records, invalid_values


def _decision_date(delivery_start: datetime) -> date:
    return delivery_start.astimezone(LONDON).date() - timedelta(days=1)


def _cutoff(delivery_start: datetime, cutoff_time: time) -> datetime:
    local_decision_date = _decision_date(delivery_start)
    local_cutoff = datetime.combine(local_decision_date, cutoff_time, tzinfo=LONDON)
    return local_cutoff.astimezone(UTC)


def _delivery_starts(date_from: date, date_to: date) -> list[datetime]:
    starts: list[datetime] = []
    decision_day = date_from
    while decision_day <= date_to:
        delivery_date = decision_day + timedelta(days=1)
        local_start = datetime.combine(delivery_date, time.min, tzinfo=LONDON)
        local_end = datetime.combine(delivery_date + timedelta(days=1), time.min, tzinfo=LONDON)
        current = local_start.astimezone(UTC)
        end = local_end.astimezone(UTC)
        while current < end:
            starts.append(current)
            current += timedelta(hours=1)
        decision_day += timedelta(days=1)
    return starts


def _select_forecasts(
    rows: list[NormalizedRecord],
    delivery_starts: list[datetime],
    cutoff_time: time,
) -> tuple[dict[datetime, NormalizedRecord], int, int]:
    expected = set(delivery_starts)
    by_version: dict[tuple[datetime, datetime], set[float]] = defaultdict(set)
    version_counts: dict[tuple[datetime, datetime], int] = defaultdict(int)
    for row in rows:
        if row.start_time in expected:
            version_key = (row.start_time, row.publish_time)
            version_counts[version_key] += 1
            if row.publish_time <= _cutoff(row.start_time, cutoff_time):
                by_version[version_key].add(row.generation)

    duplicate_count = sum(count - 1 for count in version_counts.values())
    conflicts = 0
    by_delivery: dict[datetime, list[NormalizedRecord]] = defaultdict(list)
    for (delivery_start, publish_time), generations in by_version.items():
        if len(generations) > 1:
            conflicts += 1
            continue
        if not generations:
            continue
        by_delivery[delivery_start].append(
            NormalizedRecord(delivery_start, publish_time, next(iter(generations)))
        )

    selected: dict[datetime, NormalizedRecord] = {}
    for delivery_start, candidates in by_delivery.items():
        if candidates:
            selected[delivery_start] = max(candidates, key=lambda row: row.publish_time)
    return selected, duplicate_count, conflicts


def _aggregate_actuals(
    rows: list[NormalizedRecord],
    delivery_starts: list[datetime],
) -> tuple[dict[datetime, float], int, int, int]:
    expected = set(delivery_starts)
    grouped: dict[datetime, list[NormalizedRecord]] = defaultdict(list)
    for row in rows:
        hour_start = row.start_time.replace(minute=0, second=0, microsecond=0)
        if hour_start in expected and row.start_time in {
            hour_start,
            hour_start + timedelta(minutes=30),
        }:
            grouped[row.start_time].append(row)

    selected_halves: dict[datetime, float] = {}
    duplicates = 0
    conflicts = 0
    for start_time, candidates in grouped.items():
        by_publication: dict[datetime, set[float]] = defaultdict(set)
        for row in candidates:
            by_publication[row.publish_time].add(row.generation)
        latest_publication = max(by_publication)
        latest_values = by_publication[latest_publication]
        duplicates += len(candidates) - 1
        if len(latest_values) != 1:
            conflicts += 1
            continue
        selected_halves[start_time] = next(iter(latest_values))

    hourly: dict[datetime, float] = {}
    for hour_start in delivery_starts:
        first = selected_halves.get(hour_start)
        second = selected_halves.get(hour_start + timedelta(minutes=30))
        if first is not None and second is not None:
            hourly[hour_start] = (first + second) / 2
    return hourly, duplicates, conflicts, len(delivery_starts) - len(hourly)


def _validate_fuel_types(rows: list[FuelRecord]) -> list[FuelRecord]:
    return [row for row in rows if row.fuel_type == "WIND"]


def _request_bounds(date_from: date, date_to: date) -> tuple[str, str, str, str]:
    delivery_from = date_from + timedelta(days=1)
    delivery_to = date_to + timedelta(days=1)
    forecast_from = datetime.combine(date_from, time.min, tzinfo=LONDON).astimezone(UTC)
    forecast_to = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=LONDON).astimezone(
        UTC
    )
    return (
        delivery_from.isoformat(),
        delivery_to.isoformat(),
        forecast_from.isoformat().replace("+00:00", "Z"),
        forecast_to.isoformat().replace("+00:00", "Z"),
    )


def analyze(
    date_from: date,
    date_to: date,
    client: ElexonClient,
) -> AccuracyResponse:
    validate_decision_range(date_from, date_to)
    cutoff_time = get_decision_cutoff()
    actual_from, actual_to, forecast_from, forecast_to = _request_bounds(date_from, date_to)
    raw_actuals = _validate_fuel_types(client.get_fuelhh(actual_from, actual_to))
    raw_forecasts = client.get_windfor(forecast_from, forecast_to)
    actuals, invalid_actuals = _normalize(raw_actuals)
    forecasts, invalid_forecasts = _normalize(raw_forecasts)
    starts = _delivery_starts(date_from, date_to)
    selected, duplicate_forecasts, conflicting_forecasts = _select_forecasts(
        forecasts, starts, cutoff_time
    )
    hourly_actuals, duplicate_actuals, conflicting_actuals, missing_actuals = _aggregate_actuals(
        actuals, starts
    )

    records: list[IntervalRecord] = []
    pairs: list[tuple[float, float]] = []
    for delivery_start in starts:
        decision_date = _decision_date(delivery_start)
        decision_cutoff = _cutoff(delivery_start, cutoff_time)
        forecast = selected.get(delivery_start)
        actual = hourly_actuals.get(delivery_start)
        matched = forecast is not None and actual is not None
        error = forecast.generation - actual if matched and forecast is not None else None
        if matched and forecast is not None and actual is not None:
            pairs.append((forecast.generation, actual))
        status = (
            "matched"
            if matched
            else "missing_both"
            if forecast is None and actual is None
            else "missing_forecast"
            if forecast is None
            else "missing_actual"
        )
        records.append(
            IntervalRecord(
                decision_date=decision_date,
                delivery_start=delivery_start,
                decision_cutoff=decision_cutoff,
                forecast_publish_time=forecast.publish_time if forecast else None,
                forecast_mw=forecast.generation if forecast else None,
                actual_mw=actual,
                signed_error_mw=error,
                absolute_error_mw=abs(error) if error is not None else None,
                status=status,
            )
        )

    eligible_publications = [row.publish_time for row in selected.values()]
    delivery_from = date_from + timedelta(days=1)
    delivery_to = date_to + timedelta(days=1)
    return AccuracyResponse(
        metadata=AnalysisMetadata(
            decision_date_from=date_from,
            decision_date_to=date_to,
            delivery_date_from=delivery_from,
            delivery_date_to=delivery_to,
            decision_cutoff_local=cutoff_time.isoformat(timespec="minutes"),
            latest_eligible_publish_time=max(eligible_publications, default=None),
        ),
        metrics=calculate_metrics(pairs),
        data_quality=DataQuality(
            actual_records_received=len(raw_actuals),
            forecast_records_received=len(raw_forecasts),
            invalid_actual_values=invalid_actuals,
            invalid_forecast_values=invalid_forecasts,
            duplicate_actual_records=duplicate_actuals,
            conflicting_actual_intervals=conflicting_actuals,
            duplicate_forecast_records=duplicate_forecasts,
            conflicting_forecast_versions=conflicting_forecasts,
            missing_eligible_forecasts=sum(row.forecast_mw is None for row in records),
            missing_actual_intervals=missing_actuals,
        ),
        records=records,
    )


def get_forecasts(
    date_from: date,
    date_to: date,
    client: ElexonClient,
) -> ForecastsResponse:
    validate_decision_range(date_from, date_to)
    cutoff_time = get_decision_cutoff()
    _, _, forecast_from, forecast_to = _request_bounds(date_from, date_to)
    raw_forecasts = client.get_windfor(forecast_from, forecast_to)
    forecasts, invalid_forecasts = _normalize(raw_forecasts)
    starts = _delivery_starts(date_from, date_to)
    selected, duplicate_forecasts, conflicting_forecasts = _select_forecasts(
        forecasts, starts, cutoff_time
    )
    latest_publication = max(
        (row.publish_time for row in selected.values()),
        default=None,
    )
    delivery_from = date_from + timedelta(days=1)
    delivery_to = date_to + timedelta(days=1)
    return ForecastsResponse(
        metadata=AnalysisMetadata(
            decision_date_from=date_from,
            decision_date_to=date_to,
            delivery_date_from=delivery_from,
            delivery_date_to=delivery_to,
            decision_cutoff_local=cutoff_time.isoformat(timespec="minutes"),
            latest_eligible_publish_time=latest_publication,
        ),
        data_quality=DataQuality(
            actual_records_received=0,
            forecast_records_received=len(raw_forecasts),
            invalid_actual_values=0,
            invalid_forecast_values=invalid_forecasts,
            duplicate_actual_records=0,
            conflicting_actual_intervals=0,
            duplicate_forecast_records=duplicate_forecasts,
            conflicting_forecast_versions=conflicting_forecasts,
            missing_eligible_forecasts=len(starts) - len(selected),
            missing_actual_intervals=0,
        ),
        forecasts=[
            ForecastItem(
                decision_date=_decision_date(start),
                delivery_start=start,
                decision_cutoff=_cutoff(start, cutoff_time),
                publish_time=selected[start].publish_time if start in selected else None,
                generation_mw=selected[start].generation if start in selected else None,
            )
            for start in starts
        ],
    )


def get_actuals(
    delivery_date_from: date,
    delivery_date_to: date,
    client: ElexonClient,
) -> ActualsResponse:
    if delivery_date_to < delivery_date_from:
        raise InvalidAnalysisRange("delivery_date_to must not be earlier than delivery_date_from")
    if delivery_date_from < ANALYSIS_FROM or delivery_date_to > ANALYSIS_TO + timedelta(days=1):
        raise InvalidAnalysisRange("delivery dates must be within January 2026 and 2026-02-01")
    rows = _validate_fuel_types(
        client.get_fuelhh(delivery_date_from.isoformat(), delivery_date_to.isoformat())
    )
    normalized, invalid_values = _normalize(rows)
    starts = _delivery_starts(
        delivery_date_from - timedelta(days=1),
        delivery_date_to - timedelta(days=1),
    )
    hourly, duplicates, conflicts, missing = _aggregate_actuals(normalized, starts)
    data_quality = DataQuality(
        actual_records_received=len(rows),
        forecast_records_received=0,
        invalid_actual_values=invalid_values,
        invalid_forecast_values=0,
        duplicate_actual_records=duplicates,
        conflicting_actual_intervals=conflicts,
        duplicate_forecast_records=0,
        conflicting_forecast_versions=0,
        missing_eligible_forecasts=0,
        missing_actual_intervals=missing,
    )
    return ActualsResponse(
        delivery_date_from=delivery_date_from,
        delivery_date_to=delivery_date_to,
        resolution="1 hour; mean of two complete adjacent half-hour values",
        data_quality=data_quality,
        actuals=[
            ActualItem(delivery_start=start, generation_mw=hourly.get(start)) for start in starts
        ],
    )
