from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class AnalysisMetadata(BaseModel):
    decision_date_from: date
    decision_date_to: date
    delivery_date_from: date
    delivery_date_to: date
    decision_cutoff_local: str
    timezone: str = "Europe/London"
    forecast_resolution: str = "1 hour"
    actual_source_resolution: str = "30 minutes"
    actual_alignment: str = "Mean of two complete adjacent half-hour MW values"
    error_definition: str = "forecast - actual; positive bias means overforecasting"
    latest_eligible_publish_time: datetime | None
    source: str = "Elexon BMRS FUELHH and WINDFOR"


class AccuracyMetrics(BaseModel):
    mae_mw: float | None
    rmse_mw: float | None
    mbe_mw: float | None
    matched_intervals: int


class IntervalRecord(BaseModel):
    decision_date: date
    delivery_start: datetime
    decision_cutoff: datetime
    forecast_publish_time: datetime | None
    forecast_mw: float | None
    actual_mw: float | None
    signed_error_mw: float | None
    absolute_error_mw: float | None
    status: Literal["matched", "missing_forecast", "missing_actual", "missing_both"]


class DataQuality(BaseModel):
    actual_records_received: int
    forecast_records_received: int
    invalid_actual_values: int
    invalid_forecast_values: int
    duplicate_actual_records: int
    conflicting_actual_intervals: int
    duplicate_forecast_records: int
    conflicting_forecast_versions: int
    missing_eligible_forecasts: int
    missing_actual_intervals: int


class AccuracyResponse(BaseModel):
    metadata: AnalysisMetadata
    metrics: AccuracyMetrics
    data_quality: DataQuality
    records: list[IntervalRecord]


class ForecastItem(BaseModel):
    decision_date: date
    delivery_start: datetime
    decision_cutoff: datetime
    publish_time: datetime | None
    generation_mw: float | None


class ForecastsResponse(BaseModel):
    metadata: AnalysisMetadata
    data_quality: DataQuality
    forecasts: list[ForecastItem]


class ActualItem(BaseModel):
    delivery_start: datetime
    generation_mw: float | None


class ActualsResponse(BaseModel):
    delivery_date_from: date
    delivery_date_to: date
    resolution: str
    data_quality: DataQuality
    actuals: list[ActualItem]
