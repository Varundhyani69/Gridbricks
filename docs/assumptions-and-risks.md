# Assumptions, API Evidence, and Risks

## Official API references

- [FUELHH stream documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream)
- [WINDFOR stream documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream)
- [Elexon OpenAPI specification](https://data.elexon.co.uk/swagger/v1/swagger.json)
- API base observed in the specification and request probes:
  `https://data.elexon.co.uk/bmrs/api/v1`

The documentation pages are JavaScript-rendered; the official OpenAPI document
and bounded requests to the documented endpoints were used to inspect and
verify the contract. These observations were made on 2026-10-28 and must be
rechecked in Stage 2.

## Historical-data feasibility check

Bounded HTTPS GET requests to the official endpoints succeeded with HTTP 200
and JSON responses:

| Request | Observed result |
|---|---|
| `GET /datasets/FUELHH/stream?settlementDateFrom=2026-01-01&settlementDateTo=2026-01-31&fuelType=WIND` | 1,488 rows, 31 settlement dates, 48 records per date; all returned rows were `WIND`. |
| `GET /datasets/FUELHH/stream?settlementDateFrom=2026-02-01&settlementDateTo=2026-02-01&fuelType=WIND` | 48 rows; confirms actuals are available for the final delivery date if January means decision dates. |
| `GET /datasets/WINDFOR/stream?publishDateTimeFrom=2026-01-01T00:00:00Z&publishDateTimeTo=2026-02-01T00:00:00Z` | 18,104 rows, 248 distinct publication timestamps on 31 dates, 73 forecast target rows per publication in this response; target starts ranged from 2025-12-31T21:00:00Z to 2026-02-02T21:00:00Z. |

This verifies that the observed API currently returns historical FUELHH data and
multiple historical WINDFOR publication versions over the requested period.
It is evidence of feasibility, **not an Elexon guarantee that every forecast
version is permanently retained or that every target interval is complete**.
Stage 2 must repeat the bounded checks, inspect coverage and duplicates, and
keep the observed payload format in a minimal fixture. No full-month dataset
has been saved in the project.

## API contract observations

- The OpenAPI spec identifies `GET /datasets/FUELHH/stream` parameters
  `settlementDateFrom`, `settlementDateTo`, `fuelType`, optional
  `settlementPeriod`, and publication-time filters. Settlement dates use
  `yyyy-MM-dd`; the endpoint description says FUELHH values are average MW
  over 30-minute periods. Settlement-date filters cannot be set with
  publication-date filters.
- The OpenAPI spec identifies `GET /datasets/WINDFOR/stream` filters
  `publishDateTimeFrom` and `publishDateTimeTo`. Its description says that
  without publication-time filters, the latest published forecast is returned.
- Both stream operations return JSON arrays with fields including
  `publishTime`, `startTime`, and `generation`; FUELHH additionally has
  `settlementDate`, `settlementPeriod`, and `fuelType`. Schema generation is
  integer and nullable in the spec; client code must still validate nulls.
- In the observed historical WINDFOR response, forecast starts were one hour
  apart; FUELHH has 30-minute settlement records. This is a material mismatch:
  compare only after a documented aggregation of two complete actual intervals
  per forecast hour, or report the intervals as unmatched.
- The stream routes returned arrays and the inspected OpenAPI contract exposed
  no pagination parameter. Keep date ranges bounded and handle 429 responses.
- The first exploratory WINDFOR request used unsupported `from`/`to` parameter
  names and returned current records; switching to the documented
  `publishDateTimeFrom`/`publishDateTimeTo` filters retrieved the requested
  historical publication window. Use only the documented names.

## Assumptions requiring validation

1. **Decision window:** Treat “purchase decisions made in January 2026” as
   decision local dates 2026-01-01 through 2026-01-31. With next-day delivery,
   actual delivery dates run 2026-01-02 through 2026-02-01. The assignment
   could instead mean delivery dates in January.
2. **Cutoff:** No cutoff time is supplied. The provisional default is
   10:00 Europe/London on the day before delivery. Forecasts published at the
   cutoff are included (`publishTime <= cutoff`). This is a configurable
   analysis rule, not a claim about an official market gate closure. The client
   must validate the cutoff before results are presented as operationally
   representative.
3. **Aggregation:** Forecasts are hourly while actuals are half-hourly.
   Aggregate two complete, adjacent half-hour actual average-MW rows to hourly
   average MW. If either row is absent or invalid, mark that hour unmatched.
   Confirm this with the client and the meaning of the WINDFOR value before
   production analysis.
4. **Time handling:** Parse source timestamps as UTC instants. Use the Elexon
   settlement date for actual-date bounds and `Europe/London` for decision-date
   rules and user display. Verify DST edge cases in tests.
5. **Metric policy:** Error is forecast minus actual; positive MBE means
   overforecasting. Compute MAE/RMSE/MBE only from complete matched intervals.
   Empty matched samples have null metrics and an explicit explanation.
6. **No fabricated results:** If any required historical version or actual is
   unavailable, show missing coverage; do not substitute a current forecast,
   interpolate, or claim synthetic data is real Elexon output.

## Risks and mitigations

| Risk | Impact | Mitigation / decision gate |
|---|---|---|
| Decision cutoff/window interpretation is wrong | Backtest may not represent the buyer’s actual decision information set | Make it explicit/configurable; confirm with the client before final interpretation |
| API history changes or omits versions/intervals | Backtest completeness and reproducibility may be limited | Re-query bounded dates, inspect distinct publish times and coverage, preserve minimal provenance/fixtures, clearly report gaps |
| Hourly forecast and half-hour actual definitions differ | Misleading metrics if paired or resampled incorrectly | Confirm units/interval meaning; aggregate only complete adjacent observations; expose resolution and matched count |
| API rate limiting, outage, or changed schema | Dashboard data requests may fail | Bounded requests, finite timeout, explicit 429/upstream error handling, schema validation and retryable UI state |
| DST and settlement-period changes | Duplicate/missing interval or wrong local cutoff | Store UTC instants, use `Europe/London` conversion at business boundary, test transition dates |
| Vercel/Heroku runtime, request timeout, or charges | Incompatible or unexpectedly costly deployment | Verify current platform constraints and cost before resource creation; report blocked deployment honestly |
| GitHub/YouTube authorization unavailable | Public repository/video deliverables cannot be completed | Request only the missing repository/account access action; never ask for passwords or tokens in chat |

## Actions needing user authorization or confirmation

- Confirm decision-date versus delivery-date interpretation and the exact cutoff
  rule before labeling forecast choices business-validated.
- Supply an anonymous public repository URL or authorize an authenticated
  GitHub flow. At inspection time, the workspace has no Git repository, no
  configured Git author identity, and no `gh` executable/authentication.
- Explicitly approve any paid hosting plan or resource before provisioning.
- Provide an authorized YouTube account/upload route if the video is to be
  uploaded on the user's behalf.
