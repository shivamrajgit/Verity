.PHONY: develop check test lint format clean run

# ── Setup ──
develop:
	uv sync --all-extras
	@echo "✓ Environment ready"

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
