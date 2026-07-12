# Verity

Verity is an autonomous website QA agent. Give it a target URL and it plans browser tests, executes them, discovers useful sub-pages, and writes a deterministic Markdown report with optional LLM narrative findings.

It supports both a terminal CLI and a FastAPI/SSE web UI for live run status, logs, results, and reports.

## Tech Stack

Python 3.12–3.13, LangGraph, browser-use, Playwright, Pydantic, FastAPI, SSE-Starlette, and configurable LLM providers.

## Prerequisites

- Python 3.12 or 3.13
- [uv](https://docs.astral.sh/uv/)
- A `.env` file with the API key for the provider you use

## Installation

```bash
make develop
uv run playwright install chromium
```

Create local environment configuration:

```bash
copy .env.example .env       # PowerShell
# cp .env.example .env       # macOS/Linux
```

The default configuration uses OpenRouter Auto Router for the planner, executor, summarizer, and fallback. Set:

```text
OPENROUTER_API_KEY=sk-or-...
```

The optional `--gemini` override uses `GOOGLE_API_KEY` instead and keeps OpenRouter Auto Router as fallback.

## Configuration

Edit `config.yaml` to change:

- `target_url` and `extra_urls`
- LLM providers and models
- concurrency, browser step limits, and timeouts
- approval mode and recursion depth
- report output path
- private-target and allowed-domain security policies

The normal provider configuration is:

```yaml
provider: openrouter
model: openrouter/auto
api_key_env: OPENROUTER_API_KEY
```

OpenRouter planner calls request structured `TestPlan` output. The planner also repairs safe formatting/schema variations from routed models and rejects plans without actionable test steps. The executor and summarizer have bounded retries and provider fallbacks.

## CLI Usage

Run with the repository configuration:

```bash
make run
```

Run with automatic approvals:

```bash
make run-auto
```

Use Gemini for one run:

```bash
make run ARGS=--gemini
```

Direct CLI usage:

```bash
uv run verity --config config.yaml --url https://example.com \
  --instructions "Test the main navigation" --auto-approve
```

Available overrides include `--config`, `--url`, `--urls`, `--instructions`/`-i`, `--auto-approve`, `--verbose`/`-v`, and `--gemini` (with `--Gemini` accepted as an alias).

A run returns a nonzero exit code when the pipeline fails, no reports are generated, or any test has `fail` or `error` status.

## Web UI

Start the server:

```bash
python server.py
```

Open <http://localhost:8000>. The UI can:

- accept a target URL and optional instructions
- stream planner, executor, and system logs through SSE
- submit planner clarification answers
- cancel active runs
- display structured results and the final Markdown report

For deployment, keep the server behind an authenticated reverse proxy or configure:

```text
VERITY_API_TOKEN=replace-with-a-long-random-token
VERITY_REQUIRE_API_TOKEN=true
VERITY_HOST=127.0.0.1
VERITY_PORT=8000
VERITY_REPORT_DIR=reports
VERITY_SESSION_TTL_SECONDS=3600
VERITY_MAX_ACTIVE_RUNS=2
```

The server rejects private or loopback targets by default. Configure `security.allow_private_targets` only for trusted local development, and use `security.allowed_target_domains` to restrict target scope.

## Reports and Outputs

CLI reports default to `report.md`. Server runs write isolated reports under `reports/`. Reports include deterministic totals for pass, fail, error, skipped, and observed provider cost, plus an optional `LLM Narrative` section.

Generated reports, `.env`, caches, bytecode, and build artifacts are ignored by Git.

## Development

```bash
make check
make lint
make format
make test
make test-slow
make clean
```

The test suite covers configuration validation, target security, planner schema repair, provider fallbacks, graph behavior, deterministic reports, and server controls without making live API or browser calls.
