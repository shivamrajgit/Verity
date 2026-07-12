# Verity Repository Guidelines

## Project Structure

- `src/main.py` is the CLI entry point; the installed command is `verity`.
- `src/graph/` contains the LangGraph planning, execution, approval, queue, compile, and summarization nodes.
- `src/llm/` contains provider integrations, retry handling, direct chat, and the LLM factory.
- `src/models/` contains Pydantic state, test-plan, executor-result, and report schemas.
- `src/utils/` contains URL normalization, target security validation, and safe fallback helpers.
- `server.py` provides the FastAPI/SSE backend; frontend assets are in `static/`.
- `tests/` contains pytest coverage for configuration, security, routing, provider fallbacks, planner repair, reports, and server behavior.
- `config.yaml` and `.env.example` document runtime configuration. Generated `report.md` and `reports/` output must remain uncommitted.

## Runtime and Setup

The project requires Python 3.12 or 3.13, `uv`, and Playwright Chromium:

```bash
make develop
uv run playwright install chromium
```

Copy `.env.example` to `.env` and add only the provider keys needed for the selected configuration. The default provider is OpenRouter Auto Router:

- `OPENROUTER_API_KEY` powers the default planner, executor, summarizer, and fallback.
- `GOOGLE_API_KEY` is needed only when using the `--gemini` CLI override.
- Optional providers are documented in `.env.example` and validated by `src/config.py`.

## Build, Test, and Run Commands

Run commands from the repository root:

```bash
make develop
uv run playwright install chromium
make check                         # Ruff plus the full pytest suite
make format                        # Format and auto-fix Ruff findings
make test                          # Verbose pytest run
make test-slow                     # Extended-timeout pytest run
make run                           # CLI with config.yaml and Auto Router
make run ARGS=--gemini             # One run with Gemini, Auto Router fallback
make run-auto                      # CLI with automatic approvals
make run-auto ARGS=--gemini        # Auto-approve plus Gemini override
uv run verity --help               # Installed CLI entry point
python server.py                   # Web UI at http://localhost:8000
make clean                         # Remove local caches and bytecode
```

The CLI also supports `--config`, `--url`, `--urls`, `--instructions`,
`--auto-approve`, `--verbose`, and the case-insensitive alias `--Gemini`.

## LLM and Planner Behavior

- `config.yaml` uses `openrouter/auto` for all default LLM roles.
- OpenRouter planner calls request a structured Pydantic `TestPlan` response.
- The planner repairs safe shape errors such as code fences, string sub-pages, missing defaults, and invalid priorities, then rejects plans without actionable steps.
- Provider failures use bounded retries and configured failover. Gemini runs use OpenRouter Auto Router as their fallback.
- The executor uses bounded browser steps, conservative action prompts, and does not invent credentials or irreversible data.
- Reports retain deterministic pass/fail/error counts even when narrative summarization fails.

## Coding Style

Use four-space indentation, type hints, and small focused functions. Ruff is the formatter and linter with a 100-character line limit. Use `snake_case` for functions, variables, and modules; `PascalCase` for classes and Pydantic models; and descriptive names for graph nodes and provider roles.

## Testing Guidelines

Tests use pytest with `pytest-asyncio` in auto mode. Name files `test_*.py` and functions `test_*`. Keep unit tests deterministic and avoid live API or browser calls in the test suite. When changing planner schemas, provider routing, security validation, or server controls, add regression coverage in `tests/`.

## Server and Security Configuration

The server binds to localhost by default. For deployment, use an authenticated reverse proxy or configure:

- `VERITY_API_TOKEN` and `VERITY_REQUIRE_API_TOKEN=true` to protect run/control endpoints.
- `VERITY_HOST` and `VERITY_PORT` to control the bind address and port.
- `VERITY_REPORT_DIR` for generated server reports.
- `VERITY_SESSION_TTL_SECONDS` and `VERITY_MAX_ACTIVE_RUNS` for session retention and concurrency limits.

Keep `allow_private_targets: false` unless trusted local development requires private targets. Use `allowed_target_domains` to restrict scope, keep API keys out of Git, and never commit `.env`, reports, or personal test data.

## Commits and Pull Requests

Existing history uses concise version-style subjects such as `1.0`, `1.0.1`, and `1.0.2`. Match that style for release/version commits; otherwise use a short imperative subject. Pull requests should explain behavior changes, list validation commands, link relevant issues, and include UI notes or screenshots when changing `static/` or `server.py`.
