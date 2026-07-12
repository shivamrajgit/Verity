# Verity — single portable image for Render or Railway.
#
# Serves the committed React build in static/ (no Node needed at runtime) and
# includes Playwright Chromium so local-browser runs work out of the box.
# If you deploy on a memory-constrained free tier, set `browser.use_cloud: true`
# in config.yaml and you can drop the `playwright install` line to slim the image.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    VERITY_HOST=0.0.0.0

WORKDIR /app

# uv for fast, locked dependency installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies first (cached until the lockfile changes).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Playwright Chromium plus its OS libraries (cached layer).
RUN uv run playwright install --with-deps chromium

# Application code, including the prebuilt static/ frontend.
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

# The server honors the platform's $PORT and refuses to bind publicly without
# either VERITY_API_TOKEN or VERITY_ALLOW_UNAUTHENTICATED=true (see README).
CMD ["uv", "run", "python", "server.py"]
