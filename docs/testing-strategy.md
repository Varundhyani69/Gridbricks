# Testing Strategy

## Principles

- Tests are deterministic and never require the live Elexon service.
- Keep a small, clearly labeled fixture captured from observed Elexon response
  shapes; remove or minimize records and do not treat fixture values as
  production analysis output.
- Test boundary conditions and actual output requirements, especially temporal
  cutoff selection, time zones, missing intervals, and metric sample size.
- Exercise the live API only through a separately run, bounded exploration
  script with finite timeouts and documented parameters.

## Backend test matrix

| Area | Cases and expected result |
|---|---|
| API client | Correct FUELHH settlement-date and `fuelType=WIND` filters; WINDFOR publication-time bounds; timeout, 429, 4xx/5xx, invalid JSON, and malformed record errors remain explicit |
| Normalization | UTC-aware timestamps; required fields; invalid/null generation policy; WIND filtering; deterministic duplicate handling; no synthetic zero values |
| Forecast selection | Latest publication at or before cutoff; publication exactly at cutoff is included per provisional rule; after-cutoff forecasts excluded; per-interval independence; no eligible record represented explicitly; deterministic ties |
| Interval alignment | Two consecutive half-hour actuals aggregate to the correct hourly average; missing half-hour leaves that hour unmatched; exact UTC target match; no interpolation or accidental adjacent-hour joins |
| Metrics | Perfect forecast gives zero MAE/RMSE/MBE; hand-calculated MAE and RMSE; positive/negative MBE sign; only valid matched pairs count; empty sample returns no misleading numeric metric |
| API integration | Health and metadata; valid schema; invalid/reversed/oversized date ranges; empty period; upstream errors; CORS allowlist; correct matched count and publication timestamp |

Run with `pytest` from `backend/`. Mock HTTPX transport/client responses; do
not make the test suite call Elexon.

## Frontend test matrix

- Render analysis period, MW units, selected publication timestamp, metrics,
  sample count, chart data, and detailed rows from a typed fixture.
- Ensure missing actuals/forecasts remain visibly missing.
- Cover loading, retryable error, and empty-data states.
- Assert period controls produce the expected backend query parameters.
- Verify API request cancellation/replacement on period changes where applicable.
- Check keyboard-accessible labels and reasonable narrow-screen layout.
- Use Vitest and React Testing Library. Playwright is a separate end-to-end
  layer, not a requirement for unit test success.

## End-to-end and integration gate

The E2E workflow must open the dashboard, load a deterministic decision-date
period, inspect forecast/actual series, metrics, and an interval record, and
assert that the displayed publication timestamp equals the backend-selected
timestamp. Run against a controlled backend fixture, not a live historical
request, so results remain reproducible.

## Build, container, and deployment checks

- Run backend formatter/linter and tests.
- Run frontend lint/tests and production build.
- Build both Docker images and run Compose health checks.
- Verify backend API health through the container network and frontend-to-API
  configuration.
- After deployment only, verify public frontend, API health, CORS, and one
  end-to-end request against the public URLs.
- Report each command and actual result in the final QA report; distinguish
  unavailable checks from passes.

## Acceptance thresholds

- No test may silently substitute zero, fabricated live values, or a later
  forecast version for missing data.
- The exact cutoff equality behavior is asserted.
- Metrics are computed from the exact records reported as matched.
- No deployment or video status is marked complete without externally
  accessible verification.
