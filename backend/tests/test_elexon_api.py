import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_elexon_client
from app.services.elexon import ElexonClient, ElexonUpstreamError

FIXTURE_PATH = Path(__file__).parents[2] / "tests" / "fixtures" / "elexon_api_samples.json"
DECISION_PARAMS = {
    "decision_date_from": "2026-01-01",
    "decision_date_to": "2026-01-01",
}


def _daily_actuals() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    start = datetime(2026, 1, 2, tzinfo=UTC)
    for period in range(48):
        delivery_start = start + timedelta(minutes=30 * period)
        rows.append(
            {
                "dataset": "FUELHH",
                "publishTime": (delivery_start + timedelta(minutes=30))
                .isoformat()
                .replace("+00:00", "Z"),
                "startTime": delivery_start.isoformat().replace("+00:00", "Z"),
                "settlementDate": "2026-01-02",
                "settlementPeriod": period + 1,
                "fuelType": "WIND",
                "generation": 100 + period,
            }
        )
    return rows


def _daily_forecasts() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    start = datetime(2026, 1, 2, tzinfo=UTC)
    for hour in range(24):
        delivery_start = start + timedelta(hours=hour)
        rows.append(
            {
                "dataset": "WINDFOR",
                "publishTime": "2026-01-01T09:30:00Z",
                "startTime": delivery_start.isoformat().replace("+00:00", "Z"),
                "generation": 130 + 2 * hour,
            }
        )
    rows.append(
        {
            "dataset": "WINDFOR",
            "publishTime": "2026-01-01T10:01:00Z",
            "startTime": "2026-01-02T00:00:00Z",
            "generation": 99999,
        }
    )
    return rows


def _mock_api_client(
    monkeypatch: pytest.MonkeyPatch,
    transport: httpx.BaseTransport,
) -> None:
    def override_client():
        with ElexonClient(transport=transport) as client:
            yield client

    monkeypatch.setitem(app.dependency_overrides, get_elexon_client, override_client)


def test_observed_fixture_matches_expected_dataset_fields() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text())

    assert "observed" in fixture["_fixture_note"].lower()
    assert fixture["FUELHH"][0]["fuelType"] == "WIND"
    assert {"startTime", "publishTime", "generation"} <= fixture["WINDFOR"][0].keys()


def test_client_uses_documented_stream_query_parameters() -> None:
    requests: list[httpx.Request] = []
    fixture = json.loads(FIXTURE_PATH.read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        rows = (
            fixture["FUELHH"] if request.url.path.endswith("FUELHH/stream") else fixture["WINDFOR"]
        )
        return httpx.Response(200, json=rows)

    with ElexonClient(transport=httpx.MockTransport(handler)) as client:
        actuals = client.get_fuelhh("2026-01-01", "2026-01-31")
        forecasts = client.get_windfor("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z")

    actual_query = parse_qs(urlparse(str(requests[0].url)).query)
    forecast_query = parse_qs(urlparse(str(requests[1].url)).query)
    assert actual_query == {
        "settlementDateFrom": ["2026-01-01"],
        "settlementDateTo": ["2026-01-31"],
        "fuelType": ["WIND"],
    }
    assert forecast_query == {
        "publishDateTimeFrom": ["2026-01-01T00:00:00Z"],
        "publishDateTimeTo": ["2026-02-01T00:00:00Z"],
    }
    assert len(actuals) == 1
    assert len(forecasts) == 2


@pytest.mark.parametrize(
    ("status_code", "expected_api_status"),
    [(429, 503), (500, 502)],
)
def test_upstream_http_failures_are_reported_by_api(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_api_status: int,
) -> None:
    _mock_api_client(
        monkeypatch,
        httpx.MockTransport(lambda _: httpx.Response(status_code, json={"error": "upstream"})),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/accuracy", params=DECISION_PARAMS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == expected_api_status
    assert "Elexon" in response.json()["detail"]["message"]
    if status_code == 429:
        assert response.headers["retry-after"] == "30"


def test_upstream_invalid_json_is_an_explicit_error() -> None:
    with ElexonClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content="not json", headers={"content-type": "application/json"}
            )
        )
    ) as client:
        with pytest.raises(ElexonUpstreamError, match="invalid JSON"):
            client.get_fuelhh("2026-01-01", "2026-01-01")


def test_upstream_schema_mismatch_is_an_explicit_error() -> None:
    with ElexonClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=[{"startTime": "2026-01-01"}])
        )
    ) as client:
        with pytest.raises(ElexonUpstreamError, match="schema was invalid"):
            client.get_fuelhh("2026-01-01", "2026-01-01")


def test_client_timeout_is_an_explicit_error() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with ElexonClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(ElexonUpstreamError, match="timed out"):
            client.get_windfor("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")


def test_valid_accuracy_request_matches_only_cutoff_eligible_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actuals = _daily_actuals()
    forecasts = _daily_forecasts()
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        rows = actuals if request.url.path.endswith("FUELHH/stream") else forecasts
        return httpx.Response(200, json=rows)

    _mock_api_client(monkeypatch, httpx.MockTransport(handler))
    try:
        with TestClient(app) as client:
            response = client.get("/api/accuracy", params=DECISION_PARAMS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()
    first = result["records"][0]
    assert first["forecast_mw"] == 130
    assert first["forecast_publish_time"] == "2026-01-01T09:30:00Z"
    assert first["actual_mw"] == 100.5
    assert first["signed_error_mw"] == 29.5
    assert result["metrics"] == {
        "mae_mw": 29.5,
        "rmse_mw": 29.5,
        "mbe_mw": 29.5,
        "matched_intervals": 24,
    }
    assert len(calls) == 2
    assert result["metadata"]["decision_cutoff_local"] == "10:00"


def test_empty_period_is_explicit_and_health_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_api_client(
        monkeypatch,
        httpx.MockTransport(lambda _: httpx.Response(200, json=[])),
    )
    try:
        with TestClient(app) as client:
            health = client.get("/api/health")
            response = client.get("/api/accuracy", params=DECISION_PARAMS)
    finally:
        app.dependency_overrides.clear()

    assert health.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"] == {
        "mae_mw": None,
        "rmse_mw": None,
        "mbe_mw": None,
        "matched_intervals": 0,
    }
    assert len(body["records"]) == 24
    assert all(row["status"] == "missing_both" for row in body["records"])


def test_missing_actual_remains_unmatched_without_zero_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actuals = _daily_actuals()[1:]
    forecasts = _daily_forecasts()

    def handler(request: httpx.Request) -> httpx.Response:
        rows = actuals if request.url.path.endswith("FUELHH/stream") else forecasts
        return httpx.Response(200, json=rows)

    _mock_api_client(monkeypatch, httpx.MockTransport(handler))
    try:
        with TestClient(app) as client:
            response = client.get("/api/accuracy", params=DECISION_PARAMS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()
    first = result["records"][0]
    assert first["forecast_mw"] == 130
    assert first["actual_mw"] is None
    assert first["signed_error_mw"] is None
    assert first["status"] == "missing_actual"
    assert result["metrics"]["matched_intervals"] == 23


def test_actuals_endpoint_returns_hourly_aligned_wind_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actuals = _daily_actuals()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=actuals)

    _mock_api_client(monkeypatch, httpx.MockTransport(handler))
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/actuals",
                params={"delivery_date_from": "2026-01-02", "delivery_date_to": "2026-01-02"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body["actuals"]) == 24
    assert body["actuals"][0]["generation_mw"] == 100.5
    assert body["data_quality"]["missing_actual_intervals"] == 0
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [
        ("2025-12-31", "2026-01-01"),
        ("2026-01-02", "2026-01-01"),
        ("2026-01-01", "2026-02-01"),
    ],
)
def test_invalid_decision_ranges_return_client_error(
    date_from: str,
    date_to: str,
) -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/accuracy",
            params={"decision_date_from": date_from, "decision_date_to": date_to},
        )

    assert response.status_code == 422


def test_cors_allows_configured_frontend_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
