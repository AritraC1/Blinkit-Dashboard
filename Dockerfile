# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build stage: resolve dependencies with uv (matches pyproject.toml / uv.lock)
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_PYTHON=3.12 \
    UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Cache dependencies: only pyproject.toml/uv.lock are needed for the venv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# Run as an unprivileged user
RUN useradd --create-home --uid 1000 appuser

# Virtualenv built in the previous stage (system Python, no uv needed at runtime)
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Application code (see .dockerignore for what stays out of the image)
COPY --chown=appuser:appuser . .

# Collect WhiteNoise static files at build time (prod uses the manifest storage,
# so this must happen once with a throwaway SECRET_KEY).
# chart.umd.js references a source map that is not vendored, so WhiteNoise
# would fail post-processing it - strip the sourceMappingURL comment first.
RUN chmod +x entrypoint.sh \
    && sed -i '/sourceMappingURL=/d' static/vendor/chart.umd.js \
    && SECRET_KEY=docker-build-only-key python manage.py collectstatic --noinput

USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
