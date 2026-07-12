# Verity Web UI — Usage Guide

## Prerequisites

- Python 3.12 or 3.13
- The Verity environment prepared with `make develop`
- A valid `.env` file with your provider API key (see `.env.example`)
- A valid `config.yaml` (the default one ships with the repo)

## Install Dependencies

```bash
make develop
uv run playwright install chromium
```

The project dependencies, including FastAPI, Uvicorn, and SSE-Starlette, are declared in `pyproject.toml` and installed by `make develop`.

## Start the Server

From the repo root:

```bash
python server.py
```

The server starts on `http://localhost:8000`.

## Using the Web UI

1. Open `http://localhost:8000` in your browser.
2. Enter a **Target URL** (e.g., `https://automationexercise.com/`).
3. Optionally enter **Test Instructions** describing what to test.
4. Click **Run**.
5. Watch the **live log panel** — it streams all agent output in real time: node transitions, LLM calls, browser actions, errors, and tracebacks.
6. When the run completes, a **Test Results** table appears showing pass/fail for each test case.
7. If a final markdown report was generated, it appears in the **Full Report** section.

## How It Works

- `server.py` is a thin FastAPI wrapper around the existing CLI pipeline (`src/main.py:run_agent`).
- It calls the exact same LangGraph graph, LLM providers, and browser-use agents as the CLI.
- All output is streamed via Server-Sent Events (SSE) to the browser.
- The approval mode is forced to `auto_approve` so no interactive prompts are needed.
- Runs use the OpenRouter Auto Router configuration from `config.yaml` by default.

## Troubleshooting

- **Blank log panel / no output**: Open browser DevTools (F12) → Console tab. Every SSE message is logged to `console.log`. Check for connection errors.
- **"SSE connection closed unexpectedly"**: The server may have crashed. Check the terminal where `python server.py` is running for tracebacks.
- **Config errors**: Make sure `config.yaml` exists in the repo root and is valid. API keys must be set in `.env`.
- **Module not found errors**: Run `make develop` and `uv run playwright install chromium`.
- **Authentication errors**: Configure `VERITY_API_TOKEN` and `VERITY_REQUIRE_API_TOKEN=true` when protecting a deployed server.

## CLI Usage

The CLI is available as `verity`:

```bash
uv run verity --config config.yaml --url https://example.com -i "test the login"
```

Use `make run ARGS=--gemini` for a one-off Gemini run; OpenRouter Auto Router remains the fallback.
