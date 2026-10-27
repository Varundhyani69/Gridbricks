# Elexon API Exploration Findings

Verified on 2026-10-28 using the official OpenAPI specification and bounded
requests to `https://data.elexon.co.uk/bmrs/api/v1`.

## Reproduce the check

Run from the repository root with Python 3.10+ and no third-party packages:

```bash
python3 scripts/probe_elexon.py
```

By default, the script requests WIND actuals for settlement dates
2026-01-01 through 2026-01-31 and forecasts with publication timestamps from
2026-01-01T00:00:00Z to 2026-02-01T00:00:00Z. Ranges are bounded to at most 32
calendar dates for actuals and 32 elapsed days for forecasts. Each request has
a 30-second timeout (maximum configurable timeout: 60 seconds). The script
checks response shapes and reports coverage summaries; failures and non-200
HTTP responses are explicit. Optional
`--actual-from`, `--actual-to`, `--forecast-from`, `--forecast-to`, and
`--timeout` arguments permit other bounded probes.

## Observed January 2026 results

- FUELHH returned 1,488 WIND records across all 31 January settlement dates
  (48 per date). The following 1 February settlement date returned a further
  48 actual records, useful if “January purchase decisions” means January
  decision dates with next-day delivery.
- WINDFOR returned 18,104 records over the January publication window, including
  248 distinct publication timestamps on 31 dates. The observed response
  included 73 target records per publication; target starts ranged from
  2025-12-31T21:00:00Z to 2026-02-02T21:00:00Z.
- The observed forecast target timestamps were one hour apart. FUELHH actuals
  are half-hourly average MW records. The API does not perform the product's
  desired forecast-to-actual aggregation or pairing.
- The stream endpoints expose bounded time/date filters and return JSON arrays.
  The inspected OpenAPI definitions show no pagination parameter. FUELHH
  settlement dates cannot be combined with publication-time filters. Requests
  must therefore be segmented by supported filters and remain bounded.
- The `generation` schema is an integer and nullable. Treat nulls and missing
  records as unavailable; do not silently replace them with zero.
- WINDFOR publication-time filters retrieve multiple historical versions in
  the observed response. This supports implementing point-in-time selection,
  but does not establish a completeness or indefinite retention guarantee for
  all historical versions.

A first exploratory request using guessed `from`/`to` parameter names did not
apply the intended January forecast publication filter and returned current
records. The verified request uses the documented
`publishDateTimeFrom`/`publishDateTimeTo` names.

## Fixture

[`tests/fixtures/elexon_api_samples.json`](../tests/fixtures/elexon_api_samples.json)
contains a few observed records to preserve the external field shape. It is
explicitly a small fixture, not a complete or representative dataset and not
the basis for claiming application analytics.

## Limits and next step

The bounded check establishes that historical data and multiple January
forecast publications are retrievable now. It does not prove that Elexon
retains every publication version, that every interval is present, or that a
specific market cutoff is appropriate. Stage 4 must preserve each publication
timestamp, select no later than the explicitly configured decision cutoff,
report unmatched intervals, and use only a documented actual aggregation
rule. Recheck API behavior if the schema or service changes.
