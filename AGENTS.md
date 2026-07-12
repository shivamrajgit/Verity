# Repository Guidelines

## Project Structure & Module Organization

- `src/` contains the Python application. `src/main.py` is the CLI entry point; `src/graph/` builds the LangGraph workflow and its planning, execution, approval, queue, and summarization nodes.
- `src/llm/` contains provider integrations and the LLM factory. `src/models/` contains Pydantic state and result schemas; `src/utils/` contains URL and fallback helpers.
- `server.py` provides the FastAPI/SSE web UI backend, with frontend assets in `static/`.
- `tests/` is the pytest location. Add new tests there; keep reusable application code under `src/`.
- `config.yaml` and `.env.example` document runtime configuration. Generated reports such as `report.md` should remain uncommitted.

## Build, Test, and Development Commands

Run these from the repository root:

```bash
make develop       # Create/sync the uv environment and dev dependencies
uv run playwright install chromium
make check         # Run lint and tests
make format        # Format and auto-fix Ruff findings
make run           # Run the CLI with config.yaml
make run-auto      # Run the CLI with automatic approvals
python server.py   # Start the web UI at http://localhost:8000
```

Use `make test` for verbose pytest runs, `make test-slow` for the extended timeout, and `make clean` to remove caches.

## Coding Style & Naming Conventions

Use Python 3.11+, four-space indentation, type hints, and small focused functions. Ruff is the formatter and linter (`line-length = 100`); run `make format` before submitting. Use `snake_case` for functions, variables, and modules; `PascalCase` for classes and Pydantic models; and descriptive names for graph nodes and provider roles.

## Testing Guidelines

Tests use pytest with `pytest-asyncio` in auto mode. Name files `test_*.py` and test functions `test_*`; cover URL/config helpers, model validation, graph routing, and provider fallbacks without making live API or browser calls. Run `make test` locally and `make check` before opening a PR.

## Commit & Pull Request Guidelines

Existing history uses concise version-style subjects such as `1.0` and `1.0.1`. Match that style for release/version commits; otherwise use a short imperative subject, for example `Fix planner fallback`. PRs should explain the behavior change, list validation commands, link any relevant issue, and include a screenshot or short UI notes when changing `static/` or `server.py`.

## Security & Configuration Tips

Copy `.env.example` to `.env` and keep API keys out of Git. Update `config.yaml` for target URLs, model providers, concurrency, approval mode, and browser visibility; use a safe test target and avoid committing personal or generated reports.
