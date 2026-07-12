.PHONY: develop setup check test lint format clean run run-auto \
        serve web frontend-install frontend-dev frontend-build

# ── Setup ──
develop:
	uv sync --all-extras
	@echo "✓ Environment ready"

# Full setup: Python environment plus frontend dependencies.
setup: develop frontend-install
	@echo "✓ Python and frontend dependencies installed"

# ── Frontend (React + Vite → static/) ──
# Installs only when node_modules is missing, so builds stay fast.
frontend/node_modules:
	cd frontend && npm install

frontend-install: frontend/node_modules

frontend-dev: frontend/node_modules
	cd frontend && npm run dev

frontend-build: frontend/node_modules
	cd frontend && npm run build
	@echo "✓ Frontend built into static/"

# ── Web server (serves the built UI + SSE API) ──
serve:
	uv run python server.py

# Build the UI, then start the server that serves it.
web: frontend-build serve

# ── Quality ──
check: lint test
	@echo "✓ All checks passed"

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

test:
	uv run pytest tests/ -v

test-slow:
	uv run pytest tests/ -v --timeout=300

# ── Run ──
run:
	uv run python -m src.main --config config.yaml $(ARGS)

run-auto:
	uv run python -m src.main --config config.yaml --auto-approve $(ARGS)

# ── Clean ──
clean:
	rm -rf .ruff_cache __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
