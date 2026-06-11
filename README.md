# Cragent
>
> An Autonomous Website Testing Agent

A CLI tool that crawls a target URL, generates test plans via LLM, executes them with headless browsers, and produces a severity-classified Markdown report.
It uses a recursive LangGraph architecture to orchestrate planners and parallel executors.

## About

This tool is designed to automate quality assurance testing by simulating human-like browser interactions. It allows users to:

- Automatically analyze a page and generate a structured `TestPlan` using multimodal LLMs (analyzing screenshots, no browser agent spawned for planning).

- Execute test cases in parallel using `browser-use` headless browser agents bounded by a semaphore.

- Recursively discover sub-pages and queue them for testing.

- Use a "Human-in-the-loop" (`interrupt()`) gate to manually approve or decline testing on discovered sub-pages.

- Generate a final, severity-classified Markdown report (`report.md`) via an LLM summarizer.

- Easily switch between LLM providers (Gemini, Ollama, OpenRouter, Groq, NVIDIA, OpenAI) for different roles (Planner, Executor, Summarizer).

## Tech Stack

#### Core & Orchestration

- Python ≥ 3.11

- LangGraph

- browser-use ≥ v0.12.1

- Playwright (for screenshot capture during planning)

#### Data & CLI

- Pydantic v2

- Rich

#### Supported LLMs

- Gemini (via google-genai SDK for multimodal planning)

- Ollama (Local)

- OpenRouter, Groq, NVIDIA NIM, OpenAI
  
## Pre-requisites

- Install [uv](https://docs.astral.sh/uv/) for Python dependency management.

- Initialize a `.env` file with your required API keys (e.g., `GOOGLE_API_KEY`, `OPENAI_API_KEY`).

- Configure your `config.yaml` file to set the `target_url` and your preferred LLMs.

## Installation

Install the dependencies and install the Playwright browser binaries:

```Bash
make develop
uv run playwright install chromium
```

## Setup

1. **Create your env file:**

   ```bash
   cp .env.example .env
   ```

   Add your API keys here (e.g. `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, etc.).

2. **Create / edit `config.yaml`:**

   ```yaml
   target_url: https://example.com

   extra_urls:
     - /login
     - /products

   llm:
     planner:
       provider: gemini
       model: gemini-2.0-flash
     executor:
       provider: ollama
       model: qwen2.5:7b
     summarizer:
       provider: ollama
       model: qwen2.5:7b
     fallback:
       provider: ollama
       model: qwen2.5:7b

   concurrency:
     max_executors: 4

   depth:
     max_depth: 2

   approval:
     mode: auto_approve

   browser:
     headless: true
     allowed_domains_extra: []
   ```

## Local Development

To run the agent (using `approval.mode` from `config.yaml`):

```Bash
make run
```

To run the agent and automatically approve all sub-pages (overrides `approval.mode`):

```Bash
make run-auto
```

To run in interactive mode (prompts for each discovered sub-page), set `approval.mode: interrupt` in `config.yaml` and then run `make run`.

Advanced CLI execution (override target URL, add seed URLs, and provide custom instructions):

```Bash
uv run python -m src.main --config config.yaml \
  --url https://example.com \
  --urls /products /login /cart \
  -i "Test navigation, forms, and interactive elements" \
  --auto-approve -v
```

### CLI Flags

| Flag | Description |
|---|---|
| `--config PATH` | Path to config file (default: `config.yaml`) |
| `--url URL` | Override `target_url` from config |
| `--urls PATH...` | Additional pages to test |
| `--instructions / -i TEXT` | Testing instructions (skips the interactive prompt) |
| `--auto-approve` | Skip approval prompts for sub-pages |
| `--verbose / -v` | Enable debug logging |

## Configuration Reference

| Setting | Default | Description |
|---|---|---|
| `target_url` | — | Root URL to test |
| `extra_urls` | `[]` | Additional paths or full URLs to include |
| `llm.planner` | — | LLM used to generate test plans |
| `llm.executor` | — | LLM used to drive the browser |
| `llm.summarizer` | — | LLM used to write the final report |
| `llm.fallback` | `null` | Optional fallback LLM if the planner fails |
| `concurrency.max_executors` | `4` | Number of parallel browser instances |
| `concurrency.stagger_delay_seconds` | `2.0` | Delay (seconds) between starting each parallel browser executor |
| `concurrency.step_timeout` | `180` | Per-step timeout (seconds) for browser agents |
| `depth.max_depth` | `2` | How many levels deep to follow sub-pages (0 = root only) |
| `approval.mode` | `auto_approve` | `auto_approve`, `interrupt` (manual), or `auto_decline` |
| `approval.timeout_seconds` | `120` | Seconds to wait for human approval before timing out |
| `browser.headless` | `true` | Set to `false` to watch the browser in real time |
| `browser.proxy` | `null` | Optional proxy URL for browser sessions |
| `browser.use_cloud` | `false` | Use cloud browser instances instead of local |
| `browser.allowed_domains_extra` | `[]` | Extra domains the executor may navigate to (e.g., auth providers like `accounts.google.com`) |
| `cost.max_total_cost` | `null` | Optional budget cap for total LLM costs (USD) |
| `cost.calculate_cost` | `true` | Whether to track and log LLM token costs |
| `report.output_path` | `report.md` | Where to save the report |

## Supported LLMs

> **Provider availability by role:**
>
> - **Planner**: all providers (`gemini` is the only one with multimodal/screenshot support; others fall back to text-only planning)
> - **Executor**: `openrouter`, `groq`, `ollama`, `nvidia`, `openai`
> - **Summarizer**: `gemini` or `ollama` only
> - **Fallback**: `openrouter`, `groq`, `ollama`, `nvidia`, `openai`

| Provider | Config value | Requirements |
|---|---|---|
| Google Gemini | `gemini` | `GOOGLE_API_KEY` in `.env` |
| Ollama | `ollama` | Local Ollama instance running |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` in `.env` |
| Groq | `groq` | `GROQ_API_KEY` in `.env` |
| NVIDIA NIM | `nvidia` | `NVIDIA_API_KEY` in `.env` |
| OpenAI | `openai` | `OPENAI_API_KEY` in `.env` |

### Provider config format

Each LLM entry in `config.yaml` takes:

```yaml
provider: gemini          # One of the providers above
model: gemini-2.0-flash   # Model identifier
base_url: null            # Optional: custom endpoint URL
api_key_env: null         # Optional: override env var name for the API key
```

## Development

```bash
make check          # Lint + test
make lint           # Linting only
make format         # Auto-format code
make test           # Run tests
make clean          # Remove caches
```

### Output

The agent produces a `report.md` file with test results classified by severity.

## Notes

> - You need to configure config.yaml to define your llm's planner, executor, and summarizer preferences.<br>
> - The default recursion depth for sub-pages is 2. You can adjust depth.max_depth in the config.<br>
> - If you want to watch the agent interact with the website, set browser.headless = false in your config.<br>
> - Developer commands available: make check (lint + test), make format (ruff fix), and make clean.<br>
