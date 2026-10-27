# Staged Implementation Plan

## Schedule

Target effort: **14.5 hours of engineering and preparation**, plus a **1.5-hour
contingency reserve**; total planned effort is 16 hours. External account
approval, hosting queues, and recording/upload wait time are not engineering
effort and may delay calendar completion. Re-estimate if a critical platform or
data limitation invalidates an acceptance criterion.

| Stage | Objective and deliverables | Depends on | Estimate | Gate and commit checkpoint |
|---|---|---:|---:|---|
| 1. Requirements and plan | Requirements, architecture, implementation plan, testing strategy, assumptions/risks | None | 0.75 h | Review all five docs; commit `docs: add requirements analysis and implementation plan` |
| 2. Elexon verification | Reproducible bounded API probes, observed fixture(s), API behavior and history notes | 1 | 0.75 h | Validate response shape, Jan range, forecast versions, timestamps, units; commit `docs: verify Elexon historical data availability` |
| 3. Repository scaffold | Initialize anonymous repo structure, Python/React configuration, env example, ignores, basic Docker Compose, smoke skeleton | 2 | 0.75 h | Frontend/backend start checks; commit `chore: scaffold dashboard application` |
| 4. Backend implementation | Elexon clients, normalization, cutoff selection, interval alignment, metrics, API schemas/routes | 2, 3 | 2.5 h | API starts and OpenAPI is available; commit `feat(backend): implement wind forecast analytics API` |
| 5. Backend verification | Unit/integration tests with deterministic fixtures; upstream errors and invalid ranges | 4 | 1.0 h | All backend tests pass without live API dependence; commit `test(backend): cover selection and metrics` |
| 6. React dashboard | Typed API client, overview, charts, metrics, detail table, loading/error/empty states | 5 | 3.0 h | Production build and component checks pass; commit `feat(frontend): build wind analytics dashboard` |
| 7. Integration and E2E | Frontend tests, API integration, complete user-flow test where available | 6 | 1.25 h | Verify displayed publication time and metrics match backend response; commit `test: verify dashboard workflow` |
| 8. Containerization | Production Dockerfiles, Compose, health checks, `.dockerignore`, tested run commands | 3, 5, 6 | 0.75 h | Build images and smoke-test both services; commit `chore(docker): containerize application` |
| 9. Deployment | Verify platform compatibility, configure deployment, deploy and test public workflow | 8 | 1.25 h | Public app and API health/workflow verified; commit `chore(deploy): configure verified hosting` |
| 10. QA and README | Full relevant checks, final repository review, README, QA report and limitation disclosure | 7, 8, 9 | 1.0 h | Clean tests/build and accurate links/status; commit `docs: complete setup and quality report` |
| 11. Demo preparation | Timed two-part script, record/upload if authorized, verify access | 10 | 1.5 h | Video <=10 min and link verified, or blocker explicitly reported; commit `docs: prepare product demo script` |
| Contingency | Resolve one bounded integration/data/deployment issue | As needed | 1.5 h | Spend only against a diagnosed blocker; include in 16-hour cap |

The listed stages total 14.5 hours; with 1.5 hours contingency, the plan is
exactly 16 hours. Do not use the reserve to expand product scope.

## Dependencies and sequencing

- API exploration precedes contract and analytics implementation.
- Backend tests and contract stabilization precede the full dashboard.
- Docker verification follows working backend and frontend services.
- Deployment selection is gated on current platform compatibility and cost.
- Final README and demo content must reflect the actual verified build/deployment;
  never claim an uncompleted deployment or video.

## Git and GitHub workflow

- Use one `main` branch unless a concrete reason requires another branch.
- Start from the empty `Gridbricks` directory; do not alter sibling projects.
- Check `git status`, diff, generated files, and secret exposure before every
  commit.
- Commit each completed stage only after its gate passes; use descriptive
  conventional commit messages.
- Push each completed commit and verify remote head before starting the next
  stage. Never force-push or rewrite shared history.
- Do not commit credentials, `.env`, virtual environments, `node_modules`,
  generated builds, or large/unnecessary data captures.
- If GitHub authentication or an author identity/remote is unavailable, stop at
  the local checkpoint and request only the missing setup; do not use or ask for
  credentials in chat.

## External approvals and likely blockers

- Confirm the decision cutoff, date-window interpretation, and actual/forecast
  interval aggregation before calling the analysis business-validated.
- Provide or authorize access to an anonymous public GitHub repository. The
  workspace currently has no repository, configured identity, or GitHub CLI.
- Approve any paid hosting resource before provisioning.
- Provide access to an authorized YouTube account or upload the finished video
  if no authorized account is available.
