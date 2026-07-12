# Verity Web UI — Usage Guide

## Prerequisites

- Python 3.11+
- The base Verity project installed (`pip install -e .` from the repo root)
- A valid `.env` file with your API keys (see `.env.example`)
- A valid `config.yaml` (the default one ships with the repo)

## Install Frontend Dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, and SSE-Starlette on top of the existing project dependencies.

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
- No existing agent code is modified.

## Troubleshooting

- **Blank log panel / no output**: Open browser DevTools (F12) → Console tab. Every SSE message is logged to `console.log`. Check for connection errors.
- **"SSE connection closed unexpectedly"**: The server may have crashed. Check the terminal where `python server.py` is running for tracebacks.
- **Config errors**: Make sure `config.yaml` exists in the repo root and is valid. API keys must be set in `.env`.
- **Module not found errors**: Run `pip install -e .` to install the base project, then `pip install -r requirements.txt` for server dependencies.

## CLI Still Works

The original CLI is unchanged. You can still run:

```bash
python -m src.main --config config.yaml --url https://example.com -i "test the login"
```
