import os
from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_decision_cutoff
from app.models import AccuracyResponse, ActualsResponse, ForecastsResponse
from app.services.analysis import (
    InvalidAnalysisRange,
    analyze,
    get_actuals,
    get_forecasts,
)
from app.services.elexon import ElexonClient, ElexonUpstreamError

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app = FastAPI(title="Wind Forecast Analytics API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_elexon_client() -> Iterator[ElexonClient]:
    with ElexonClient() as client:
        yield client


@app.exception_handler(ElexonUpstreamError)
def handle_elexon_error(_: Request, exc: ElexonUpstreamError) -> JSONResponse:
    status_code = 503 if exc.upstream_status == 429 else 502
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": {
                "message": str(exc),
                "upstream_status": exc.upstream_status,
            }
        },
        headers={"Retry-After": "30"} if exc.upstream_status == 429 else None,
    )


@app.exception_handler(InvalidAnalysisRange)
def handle_invalid_range(_: Request, exc: InvalidAnalysisRange) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metadata")
def metadata() -> dict[str, object]:
    return {
        "analysis_period": {"from": "2026-01-01", "to": "2026-01-31"},
        "decision_cutoff_local": get_decision_cutoff().isoformat(timespec="minutes"),
        "timezone": "Europe/London",
        "source": "Elexon BMRS FUELHH and WINDFOR",
        "forecast_resolution": "1 hour",
        "actual_source_resolution": "30 minutes",
    }


@app.get("/api/forecasts", response_model=ForecastsResponse)
def forecasts(
    decision_date_from: date,
    decision_date_to: date,
    client: Annotated[ElexonClient, Depends(get_elexon_client)],
) -> ForecastsResponse:
    return get_forecasts(decision_date_from, decision_date_to, client)


@app.get("/api/actuals", response_model=ActualsResponse)
def actuals(
    delivery_date_from: date,
    delivery_date_to: date,
    client: Annotated[ElexonClient, Depends(get_elexon_client)],
) -> ActualsResponse:
    return get_actuals(delivery_date_from, delivery_date_to, client)


@app.get("/api/accuracy", response_model=AccuracyResponse)
def accuracy(
    decision_date_from: date,
    decision_date_to: date,
    client: Annotated[ElexonClient, Depends(get_elexon_client)],
) -> AccuracyResponse:
    return analyze(decision_date_from, decision_date_to, client)
