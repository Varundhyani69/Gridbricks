# Requirements and Traceability

## Scope

Build a public, demonstrable MVP for UK electricity procurement users to inspect
Elexon national wind generation forecasts and compare eligible forecasts with
actual wind generation for decisions made in January 2026. Elexon FUELHH and
WINDFOR are the only product data sources.

The source assignment is `REint Full Stack SWE challenge v4 Shared.docx`. This
document records the product requirements; technical choices and unresolved
interpretations are identified separately rather than presented as client
requirements.

## Requirement classification

### Mandatory

| ID | Requirement |
|---|---|
| M-01 | Show national wind forecasts and actual wind generation from Elexon only; filter FUELHH to `fuelType=WIND`. |
| M-02 | Limit the analysis to day-ahead purchase decisions made in January 2026. |
| M-03 | Show when a forecast was published and which delivery interval it predicts. |
| M-04 | Quantitatively compare forecasts with actuals and explain forecast error. |
| M-05 | Build the frontend with React and the backend with Python. |
| M-06 | Use Docker. |
| M-07 | Deploy a sample application to Vercel or Heroku, subject to verified platform compatibility. |
| M-08 | Create a public GitHub repository with an anonymous/random repository name. |
| M-09 | Include a README with repository layout, startup instructions, and deployment link. |
| M-10 | Prepare a public-accessible, unlisted YouTube demo of no more than 10 minutes: customer overview (max 5 min) and technical review (max 5 min). |
| M-11 | Use only the Elexon national-level wind data in this challenge; do not broaden the product into trading or add unrelated datasets. |
| M-12 | Disclose use of AI tools in the README. |

### Recommended engineering choices

These are recommended by the planning prompt, not mandatory assignment
constraints; select only those that fit the implementation:

- React + Vite + TypeScript.
- Tailwind CSS and Recharts.
- FastAPI, Pydantic, Pandas, and NumPy.
- pytest and HTTPX; Vitest and React Testing Library; Playwright when available.
- FastAPI OpenAPI documentation and Docker Compose.
- Pin dependencies and keep the deployment architecture compatible with the
  selected platform.

### Optional

- Additional accuracy metrics, provided they are justified and do not mislead.
- Playwright end-to-end coverage where tooling and environment permit.
- In-memory caching only if measured API behavior makes it worthwhile.

### Unspecified; explicit decisions required

| ID | Unspecified area | Proposed treatment |
|---|---|---|
| U-01 | Exact day-ahead decision cutoff and whether a forecast published exactly at the cutoff is eligible. | Make the cutoff configurable. Provisional default: 10:00 Europe/London on the day before delivery; include publication timestamps equal to the cutoff. Treat both as assumptions pending client confirmation. |
| U-02 | Whether “purchase decisions made in January” means decision dates or delivery dates in January. | Interpret as decision dates 1–31 January 2026, with next-day delivery dates 2 January–1 February 2026. Confirm before final analysis. |
| U-03 | How to compare one-hour WINDFOR intervals with half-hour FUELHH intervals. | Aggregate two complete half-hour actual MW averages into an hourly arithmetic mean and match on UTC interval start. Do not interpolate or compare unmatched half-hours. Confirm this interpretation. |
| U-04 | Whether published historical WINDFOR versions returned by the API are complete and immutable. | Preserve every returned `publishTime`, test coverage and duplicates, and report the selection and coverage limitations. Do not claim a completeness guarantee beyond observed API results. |
| U-05 | Hosting split, platform account, and any deployment charges. | Verify current Vercel/Heroku Python and container support in the deployment stage. Do not create paid resources or incur charges without authorization. |
| U-06 | YouTube account and video publication permissions. | Prepare a recording script; recording, upload, and access verification require an account and user action if no authorized account is available. |
| U-07 | Public repository name and GitHub remote. | Use a random anonymous name. Repository creation requires an authenticated GitHub account or user-created remote. |

## Traceability matrix

| Requirement | Planned implementation | Verification |
|---|---|---|
| M-01, M-02, M-03, U-01, U-02 | `backend/app/services/elexon.py`, `backend/app/services/forecast_selection.py`, `backend/app/api/forecasts.py`; cutoff and interpretation documented in README and assumptions docs | Backend tests for API parameter bounds, wind filtering, forecast publication eligibility, selected publication time, and January decision/delivery bounds |
| M-01, U-03, U-04 | `backend/app/services/normalization.py`; hourly actual aggregation and exact interval join | Unit tests for interval aggregation, UTC alignment, missing half-hours, duplicates, and no interpolation; integration test with captured API-shaped fixtures |
| M-04 | `backend/app/analytics/metrics.py` and `/api/accuracy` response | Hand-calculated MAE, RMSE, MBE tests; matched-sample count and missing-data tests |
| M-05, M-06 | `backend/`, `frontend/`, `Dockerfile` files, and `docker-compose.yml` | pytest and frontend test/build commands; Docker build and compose health smoke tests |
| M-07, U-05 | deployment configuration and README deployment links, selected only after platform verification | Public frontend/API health checks and one end-to-end workflow; deployment status reported accurately |
| M-08, M-09 | repository root, `README.md`, and GitHub remote | Inspect public visibility, repository contents, README links, and remote commit |
| M-10, U-06 | `docs/demo-script.md` and actual unlisted video link when produced | Keep video under 10 minutes; check both segments and verify link access in a private/incognito session |
| M-11 | Elexon-only data clients and documented scope | Review configured upstream hosts and test that no non-Elexon dataset enters analysis |
| M-12 | `README.md` AI disclosure | Final README checklist |

## Product output

The dashboard should provide:

- Analysis/decision period and data availability.
- Latest eligible forecast publication time and delivery interval.
- Forecast and actual series with clearly labeled MW units.
- MAE, RMSE, MBE, and matched interval count, calculated only from matched,
  valid records.
- Inspectable interval rows with publication time, delivery time, forecast,
  actual, signed error, and absolute error.
- Explicit missing-data, loading, empty, and recoverable error states.
