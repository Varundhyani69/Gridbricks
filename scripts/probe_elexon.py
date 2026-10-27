#!/usr/bin/env python3
"""Run bounded, read-only checks against the official Elexon dataset streams."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

API_BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
MAX_RANGE_DAYS = 32


class ProbeError(Exception):
    """An expected API or response-validation failure."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual-from", default="2026-01-01", help="FUELHH settlement date, inclusive")
    parser.add_argument("--actual-to", default="2026-01-31", help="FUELHH settlement date, inclusive")
    parser.add_argument(
        "--forecast-from",
        default="2026-01-01T00:00:00Z",
        help="WINDFOR publication timestamp lower bound",
    )
    parser.add_argument(
        "--forecast-to",
        default="2026-02-01T00:00:00Z",
        help="WINDFOR publication timestamp upper bound",
    )
    parser.add_argument("--timeout", type=float, default=30, help="Request timeout in seconds (maximum 60)")
    return parser.parse_args()


def validate_bounds(args: argparse.Namespace) -> None:
    try:
        actual_from = date.fromisoformat(args.actual_from)
        actual_to = date.fromisoformat(args.actual_to)
        forecast_from = datetime.fromisoformat(args.forecast_from.replace("Z", "+00:00"))
        forecast_to = datetime.fromisoformat(args.forecast_to.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProbeError(f"Invalid date or timestamp: {exc}") from exc

    if actual_to < actual_from or (actual_to - actual_from).days >= MAX_RANGE_DAYS:
        raise ProbeError(f"FUELHH range must be ordered and cover no more than {MAX_RANGE_DAYS} calendar dates")
    if forecast_to <= forecast_from or forecast_to - forecast_from > timedelta(days=MAX_RANGE_DAYS):
        raise ProbeError(f"WINDFOR range must be ordered and no longer than {MAX_RANGE_DAYS} days")
    if forecast_from.utcoffset() is None or forecast_to.utcoffset() is None:
        raise ProbeError("WINDFOR timestamps must include a timezone")
    if not 0 < args.timeout <= 60:
        raise ProbeError("Timeout must be greater than 0 and no more than 60 seconds")


def fetch_rows(path: str, params: dict[str, str], timeout: float) -> list[dict[str, object]]:
    url = f"{API_BASE}/{path}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise ProbeError(f"{path} returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProbeError(f"Could not retrieve valid JSON from {path}: {exc}") from exc

    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ProbeError(f"{path} response must be a JSON array of records")
    if not payload:
        raise ProbeError(f"{path} returned no records for the requested period")
    return payload


def require_fields(rows: list[dict[str, object]], fields: set[str], dataset: str) -> None:
    for index, row in enumerate(rows):
        missing = fields.difference(row)
        if missing:
            names = ", ".join(sorted(missing))
            raise ProbeError(f"{dataset} record {index} is missing required fields: {names}")


def summarize_actuals(rows: list[dict[str, object]]) -> dict[str, object]:
    require_fields(rows, {"startTime", "publishTime", "settlementDate", "fuelType", "generation"}, "FUELHH")
    wrong_fuels = sorted({str(row["fuelType"]) for row in rows if row["fuelType"] != "WIND"})
    if wrong_fuels:
        raise ProbeError(f"FUELHH returned unexpected fuel types: {', '.join(wrong_fuels)}")
    dates = sorted({str(row["settlementDate"]) for row in rows})
    return {
        "records": len(rows),
        "settlement_dates": dates,
        "fuel_types": ["WIND"],
        "null_generations": sum(row["generation"] is None for row in rows),
    }


def summarize_forecasts(rows: list[dict[str, object]]) -> dict[str, object]:
    require_fields(rows, {"startTime", "publishTime", "generation"}, "WINDFOR")
    publish_counts = Counter(str(row["publishTime"]) for row in rows)
    targets = sorted({str(row["startTime"]) for row in rows})
    publications = sorted(publish_counts)
    return {
        "records": len(rows),
        "publication_versions": len(publications),
        "publication_range": [publications[0], publications[-1]],
        "target_range": [targets[0], targets[-1]],
        "records_per_publication_min": min(publish_counts.values()),
        "records_per_publication_max": max(publish_counts.values()),
        "null_generations": sum(row["generation"] is None for row in rows),
    }


def main() -> int:
    args = parse_args()
    try:
        validate_bounds(args)
        actuals = fetch_rows(
            "FUELHH/stream",
            {
                "settlementDateFrom": args.actual_from,
                "settlementDateTo": args.actual_to,
                "fuelType": "WIND",
            },
            args.timeout,
        )
        forecasts = fetch_rows(
            "WINDFOR/stream",
            {
                "publishDateTimeFrom": args.forecast_from,
                "publishDateTimeTo": args.forecast_to,
            },
            args.timeout,
        )
        print(
            json.dumps(
                {
                    "api_base": API_BASE,
                    "actuals": summarize_actuals(actuals),
                    "forecasts": summarize_forecasts(forecasts),
                    "note": "Response coverage is observed, not a guarantee of complete historical publication retention.",
                },
                indent=2,
            )
        )
    except ProbeError as exc:
        print(f"Elexon probe failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
