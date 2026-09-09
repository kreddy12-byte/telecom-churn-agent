Tests live next to each package:

- `frontend/` — Vitest (`npm test`)
- `backend/tests/` — API, auth, persistence
- `ml/tests/` — data, training, prediction, SHAP
- `agent/tests/` — strategy engine, recommendation, what-if

This folder is reserved for optional cross-cutting smoke tests. It is not required to run the suites above.
