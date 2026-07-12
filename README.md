# Verity

Verity is an autonomous website testing agent for quick QA checks.
Give it a target URL and it will plan tests, run them in a browser, and create a final report.
It can discover useful sub-pages, test them in parallel, and summarize issues in simple Markdown output.

This project supports both:
- CLI runs for terminal-based workflows
- A frontend web UI for live logs and controls while the run is in progress

## Tech Stack

Built with Python, LangGraph, browser-use, Playwright, and FastAPI.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- A `.env` file with required API keys

## Installation

```bash
make develop
uv run playwright install chromium
```

## Setup

1. Create your env file:

```bash
cp .env.example .env
```

2. Edit `config.yaml`:

- Set your `target_url`
- Choose planner, executor, and summarizer models
- Adjust `depth`, `concurrency`, and `browser.headless` if needed

## Run (CLI)

Use your config settings:

```bash
make run
```

Force auto-approve mode:

```bash
make run-auto
```

The default provider is OpenRouter's Auto Router. To use Gemini for the
planner, executor, and summarizer for one run, pass:

```bash
uv run python -m src.main --config config.yaml --gemini
```

(`--Gemini` is accepted as an alias.) Gemini runs keep OpenRouter Auto Router
as their fallback provider.

With Make, use `make run ARGS=--gemini`.

A final report is written to the configured report path (default: `report.md`).

## Provider Config Format

Each LLM entry in `config.yaml` uses this shape:

```yaml
provider: openrouter
model: openrouter/auto
base_url: null
api_key_env: OPENROUTER_API_KEY
```

`provider` and `model` are required. `base_url` and `api_key_env` are optional.

## Frontend Setup

Install frontend server dependencies:

```bash
pip install -r requirements.txt
```

## Run (Frontend)

Start the web server:

```bash
python server.py
```

Then open:

```text
http://localhost:8000
```

For a deployed server, keep the application bound to localhost behind an
authenticated reverse proxy, or set `VERITY_API_TOKEN` and
`VERITY_REQUIRE_API_TOKEN=true`. Target URLs are checked against private-IP
and domain policies before a browser is launched.

From the UI you can:
- Enter target URL and optional instructions
- Stream planner/executor/system logs live
- Submit planner clarification answers
- View test results and the final report

## Development

```bash
make check
make lint
make format
make test
make clean
```

## Output

Verity generates a Markdown report with pass/fail/error results and findings summary.
By default, it is written to `report.md` (or the path set in your config).
