from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from app.core.config import ELEXON_API_BASE_URL, ELEXON_TIMEOUT_SECONDS


class ElexonUpstreamError(Exception):
    def __init__(self, message: str, *, upstream_status: int | None = None) -> None:
        super().__init__(message)
        self.upstream_status = upstream_status


class ElexonRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start_time: str = Field(alias="startTime")
    publish_time: str = Field(alias="publishTime")
    generation: float | None


class FuelRecord(ElexonRecord):
    settlement_date: str | None = Field(default=None, alias="settlementDate")
    settlement_period: int | None = Field(default=None, alias="settlementPeriod")
    fuel_type: str | None = Field(default=None, alias="fuelType")


class WindForecastRecord(ElexonRecord):
    pass


class ElexonClient:
    def __init__(
        self,
        *,
        base_url: str = ELEXON_API_BASE_URL,
        timeout: float = ELEXON_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "ElexonClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_fuelhh(self, settlement_date_from: str, settlement_date_to: str) -> list[FuelRecord]:
        payload = self._get(
            "/datasets/FUELHH/stream",
            {
                "settlementDateFrom": settlement_date_from,
                "settlementDateTo": settlement_date_to,
                "fuelType": "WIND",
            },
        )
        return self._validate_rows(payload, FuelRecord, "FUELHH")

    def get_windfor(self, publish_time_from: str, publish_time_to: str) -> list[WindForecastRecord]:
        payload = self._get(
            "/datasets/WINDFOR/stream",
            {
                "publishDateTimeFrom": publish_time_from,
                "publishDateTimeTo": publish_time_to,
            },
        )
        return self._validate_rows(payload, WindForecastRecord, "WINDFOR")

    def _get(self, path: str, params: Mapping[str, str]) -> Any:
        try:
            response = self._http.get(f"{self.base_url}{path}", params=params)
        except httpx.TimeoutException as exc:
            raise ElexonUpstreamError("Elexon request timed out") from exc
        except httpx.RequestError as exc:
            raise ElexonUpstreamError("Could not connect to Elexon") from exc

        if response.status_code == 429:
            raise ElexonUpstreamError("Elexon rate limit reached", upstream_status=429)
        if response.is_error:
            raise ElexonUpstreamError(
                f"Elexon returned HTTP {response.status_code}",
                upstream_status=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ElexonUpstreamError("Elexon returned invalid JSON") from exc
        if not isinstance(payload, list):
            raise ElexonUpstreamError("Elexon response must be an array of records")
        if any(not isinstance(row, dict) for row in payload):
            raise ElexonUpstreamError("Elexon response contains a non-object record")
        return payload

    @staticmethod
    def _validate_rows(
        payload: list[dict[str, Any]],
        model: type[FuelRecord] | type[WindForecastRecord],
        dataset: str,
    ) -> list[FuelRecord] | list[WindForecastRecord]:
        try:
            return TypeAdapter(list[model]).validate_python(payload)
        except ValidationError as exc:
            raise ElexonUpstreamError(f"Elexon {dataset} record schema was invalid") from exc
