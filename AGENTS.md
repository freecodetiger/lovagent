# Repository Guidelines

## Project Structure & Module Organization
- `app/`: FastAPI backend. Key areas: `routers/` (HTTP routes), `services/` (business logic), `models/` (DB entities), `schemas/` (request/response models), `prompts/` (LLM prompt templates), `utils/` (helpers).
- `admin-ui/`: React + TypeScript admin frontend (`src/components`, `src/lib`, `src/api.ts`). Build output is `admin-ui/dist` and is served by backend routes (`/admin`, `/setup`).
- `tests/`: Python test suite for API and services (`test_*.py`).
- `scripts/`: cross-platform bootstrap/run/stop scripts (`*.sh`, `*.ps1`, `stop.bat`).

## Build, Test, and Development Commands
- Windows quick start:
  - `./scripts/check-env.ps1 -Mode Bootstrap` checks required tools.
  - `./scripts/bootstrap.ps1` creates `.venv`, installs Python deps, installs/builds frontend.
  - `./scripts/dev-up.ps1` starts backend on `:8000`.
  - `./scripts/dev-up.ps1 -DevUI` also starts Vite dev server on `:5173`.
  - `./scripts/stop.ps1` stops started processes.
- Frontend only (from repo root):
  - `npm --prefix admin-ui run dev` for UI development.
  - `npm --prefix admin-ui run build` for production build.
- Tests:
  - `python -m pytest tests -q` runs backend tests.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes, explicit type hints on new/changed public functions.
- TypeScript/React: follow existing style (2-space indentation, double quotes, trailing commas). Components use `PascalCase` file names (for example `SetupWizard.tsx`); utilities use lower camel/snake consistent with existing files.
- Keep routers thin; put logic in `app/services/`.

## Testing Guidelines
- Add tests in `tests/` with names `test_<feature>.py` and functions `test_<behavior>()`.
- Prefer deterministic service/unit tests; mock external HTTP/LLM calls.
- For route changes, include FastAPI `TestClient` coverage for success and error paths.

## Commit & Pull Request Guidelines
- Current history mixes plain summaries and Conventional Commit prefixes (for example `feat: ...`, `fix: ...`). Prefer Conventional Commits for new work: `feat(scope): ...`, `fix(scope): ...`, `chore: ...`.
- Keep commits focused and runnable.
- PRs should include:
  - purpose and scope
  - test evidence (commands run + results)
  - screenshots/GIFs for `admin-ui` changes
  - config/env changes (update `.env.example` when needed)

## Security & Configuration Tips
- Never commit real secrets. Use `.env` locally and keep `.env.example` in sync with required keys.
- Validate callback/public URL settings via the setup flow before enabling external integrations.
