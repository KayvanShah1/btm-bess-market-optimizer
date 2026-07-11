# syntax=docker/dockerfile:1

FROM python:3.12.13-slim-trixie AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip uv

# .dockerignore prevents local environments and caches from entering the image.
COPY . .

# Install the complete workspace without development dependencies.
RUN uv sync \
    --frozen \
    --all-packages \
    --no-dev


FROM python:3.12.13-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BESS_PROJECT_ROOT=/app \
    PORT=10000 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN groupadd --system app \
    && useradd \
    --system \
    --gid app \
    --create-home \
    app

# Python environment created in the builder stage.
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Editable workspace packages point to these source directories.
COPY --from=builder --chown=app:app /app/apps /app/apps
COPY --from=builder --chown=app:app /app/bess_optimizer /app/bess_optimizer

# The dashboard reads committed processed data and model outputs.
COPY --from=builder --chown=app:app /app/data /app/data

USER app

EXPOSE 10000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '10000') + '/_stcore/health', timeout=4)"

CMD ["sh", "-c", "exec streamlit run apps/dashboard/src/bess_dashboard/app.py --server.address=0.0.0.0 --server.port=${PORT:-10000} --server.headless=true --browser.gatherUsageStats=false"]