# Proposed Architecture

## Design goals

- Keep the implementation small enough for a 16-hour assignment.
- Preserve the historical publication time needed for point-in-time forecast
  selection.
- Make UTC delivery-time alignment, the day-ahead cutoff, and unmatched data
  visible and testable.
- Avoid a database, queue, authentication, extra data sources, and unrelated
  infrastructure.

## Runtime shape

```text
Browser (React + Vite + TypeScript)
        |
        | JSON over HTTP; configurable API base URL
        v
Python API (FastAPI + Pydantic)
        |
        +-- Elexon FUELHH client: bounded settlement-date query, WIND only
        +-- Elexon WINDFOR client: bounded publication-time query
        |
        +-- normalization and validation
        +-- forecast selection at configured decision cutoff
        +-- hourly actual aggregation and interval matching
        +-- MAE / RMSE / MBE analytics
        |
        v
Elexon BMRS API
```

For local development, Docker Compose will run frontend and backend services.
The deployment topology will be selected only after verifying the current
Vercel/Heroku Python runtime, container, timeout, and cost constraints. No
database is proposed: the January analysis is bounded and the Elexon API is the
source of record.

## Backend responsibilities

1. **API routes and validation** — health, metadata, forecast/actual analysis,
   and accuracy routes; validate date ranges and return meaningful upstream
   errors.
2. **Elexon clients** — call the official `data.elexon.co.uk/bmrs/api/v1`
   endpoints with finite timeouts and bounded requests; handle non-success
   responses, rate limits, and malformed payloads explicitly.
3. **Normalization** — validate required fields and numeric values; parse
   timestamps as timezone-aware UTC; filter actuals to `WIND`; record duplicates
   and missing intervals.
4. **Selection** — per hourly delivery start, choose the latest forecast with
   `publishTime <= cutoff`; retain both timestamps and indicate intervals with
   no eligible forecast.
5. **Actual alignment** — combine exactly two complete, adjacent half-hour
   FUELHH average-MW observations for each forecast hour; do not interpolate.
6. **Analytics** — compute error only over matched, valid pairs. Define error as
   `forecast - actual`, so positive MBE means overforecasting.
7. **Response schemas** — return units, interval and publication timestamps,
   missing-data/coverage information, metric sample size, and source/assumption
   metadata.

Suggested API surface:

- `GET /api/health`
- `GET /api/metadata`
- `GET /api/forecasts?decision_date_from=...&decision_date_to=...`
- `GET /api/actuals?delivery_date_from=...&delivery_date_to=...`
- `GET /api/accuracy?decision_date_from=...&decision_date_to=...`

The precise schema should be stabilized and documented before full frontend
implementation. Do not return an empty success response after an upstream
failure.

## Frontend responsibilities

- Typed API client isolated from presentation components.
- Procurement-oriented overview, period selector, forecast/actual chart,
  metric cards, and detailed interval table.
- Display publication time as distinct from delivery time.
- Show an explicit hourly resolution and actual aggregation explanation.
- Render loading, error/retry, empty, missing, and partial-coverage states.
- Keep date and number formatting consistent and labels keyboard accessible.
- No client-side duplicate forecast-selection or metric calculations.

## Data contracts and temporal conventions

- Treat Elexon `startTime` and `publishTime` as UTC instants; keep the `Z`/UTC
  offset when parsing and serializing.
- FUELHH is filtered using settlement dates and `fuelType=WIND`; its `generation`
  is an average MW value over a 30-minute settlement period according to the
  official API description.
- WINDFOR forecasts have hourly `startTime` targets and a separate `publishTime`.
- The requested decision-date window and resulting delivery-date window must
  be explicit in API metadata and user interface.
- Use `Europe/London` only for the configured business cutoff and human display;
  convert cutoff instants to UTC for comparisons.
- The default cutoff and hourly aggregation are provisional business/data
  assumptions, not Elexon-defined behavior.

## Reliability and security

- Keep upstream base URLs and CORS origins in backend configuration; expose no
  credentials to the browser. The documented endpoints currently require no
  credentials in the tested bounded requests.
- Use explicit HTTP timeouts, validate upstream records, and return diagnosable
  4xx/5xx responses.
- Use no broad catch-and-empty fallback. Log useful error context without
  credentials or unnecessary personal information.
- Consider only bounded, short-lived in-memory caching after tests confirm the
  cache key includes the full requested period and retains forecast publication
  history. It is not required for the initial version.
- Pin dependencies, exclude secrets and build artifacts from Docker images, and
  expose only necessary ports.

## Deployment decision gate

The preferred deployment shape is a public React client plus a Python API on
the permitted platform(s). Choose between a Vercel Python deployment and a
Heroku container only after a small compatibility check covering routing,
timeouts, CORS, health checks, and cost. The plan does not authorize paid
resources. If a single-platform deployment cannot meet these needs without
material compromise, document the blocker and request account/cost approval
before provisioning.
