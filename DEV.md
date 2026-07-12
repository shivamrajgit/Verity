# Verity — Development & Deployment

Developer-facing guide: the frontend workflow, server hardening, deployment, and
quality commands. End-user usage is in [README.md](README.md); repository
conventions are in [AGENTS.md](AGENTS.md).

## Frontend (React)

The web UI is a **React + Vite + TypeScript** app (Tailwind CSS) in `frontend/`.
The backend serves the compiled assets from `static/`, so **no Node runtime is
required in production**.

Make targets wrap the whole workflow (npm is installed automatically on first use):

```bash
make setup             # Python env + frontend dependencies
make frontend-dev      # Vite dev server at http://localhost:5173 (proxies /api to :8000)
make frontend-build    # compile the UI into static/ (commit the result)
make serve             # run the backend (python server.py)
make web               # build the UI, then serve it
```

For development, run `make frontend-dev` and `make serve` in two terminals. The
raw npm equivalents also work:

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
npm run build          # → ../static/
```

`static/` is a committed build artifact so the server (and deploys) need no Node;
`frontend/node_modules/` stays uncommitted.

## Server Hardening & Configuration

The server binds to localhost by default. For deployment, keep it behind an
authenticated reverse proxy or configure:

```text
VERITY_API_TOKEN=replace-with-a-long-random-token
VERITY_REQUIRE_API_TOKEN=true
VERITY_ALLOW_UNAUTHENTICATED=true   # bind publicly without a token (rate-limited personal deploy)
VERITY_HOST=127.0.0.1
VERITY_PORT=8000                    # $PORT is honored as a fallback (Render/Railway)
VERITY_REPORT_DIR=reports
VERITY_SESSION_TTL_SECONDS=3600
VERITY_MAX_ACTIVE_RUNS=2
VERITY_RATE_LIMIT_RUNS=20           # per-IP runs per window; 0 disables
VERITY_RATE_LIMIT_WINDOW_SECONDS=3600
```

Binding beyond localhost requires either `VERITY_API_TOKEN` or
`VERITY_ALLOW_UNAUTHENTICATED=true`. Every `/api/run` request is rate limited per
IP so a bot or accidental loop cannot exhaust provider credits or memory.

The server rejects private or loopback targets by default. Configure
`security.allow_private_targets` only for trusted local development, and use
`security.allowed_target_domains` to restrict target scope.

LLM provider requests default to a 4,096-token completion cap through
`llm.*.max_output_tokens`. This prevents OpenRouter Auto Router from requesting
its full context limit and helps keep provider credit usage bounded; lower the
value further in `config.yaml` if needed.

## Deploy (Docker · Render · Railway)

A single `Dockerfile` produces a self-contained image (Playwright Chromium plus
the committed `static/` build) that runs on either Render or Railway:

1. Ensure `static/` holds a fresh `make frontend-build`, then push the repo to GitHub.
2. For Render, choose **New → Blueprint**, select the repo, and keep the root
   `render.yaml`. It configures the Docker runtime, `/api/health` check, and
   rate-limited unauthenticated access for a personal deployment (5 runs per IP
   per day). Enter your `OPENROUTER_API_KEY` when Render prompts for it.
   Alternatively, create a Web Service and select **Docker**.
3. For Railway or a manual Render Web Service, set environment variables:
   - `OPENROUTER_API_KEY` — your provider key (the server pays for runs).
   - Either `VERITY_API_TOKEN` (require a token) **or** `VERITY_ALLOW_UNAUTHENTICATED=true` for an open, rate-limited personal deploy.
   - Optionally tune `VERITY_RATE_LIMIT_RUNS` / `VERITY_RATE_LIMIT_WINDOW_SECONDS` and `VERITY_MAX_ACTIVE_RUNS`.

`VERITY_HOST=0.0.0.0` is baked into the image and the server binds the platform's
`$PORT` automatically.

**Free-tier note:** a full Chromium needs more than the 512 MB a free instance
provides. On free tiers, set `browser.use_cloud: true` in `config.yaml` to run the
browser off-box (you can then drop the `playwright install` line from the
`Dockerfile`); otherwise use a ~2 GB instance.

## Quality & Tests

```bash
make check
make lint
make format
make test
make test-slow
make clean
```

The test suite covers configuration validation, target security, planner schema
repair, provider fallbacks, graph behavior, deterministic reports, and server
controls without making live API or browser calls.
