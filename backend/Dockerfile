# syntax=docker/dockerfile:1.7
# One image for api, worker, scheduler and the migrate job (different commands).
FROM ghcr.io/astral-sh/uv:0.6.17@sha256:4a6c9444b126bd325fba904bff796bf91fb777bf6148d60109c4cb1de2ffc497 AS uv

FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PRICETRACKER_DATA_DIR=/data \
    PRICETRACKER_WORKER_HEARTBEAT_FILE=/tmp/worker.alive
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /data/uploads /data/cache && chown -R app:app /data
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --from=build --chown=app:app /app/alembic.ini /app/alembic.ini
COPY --from=build --chown=app:app /app/migrations /app/migrations
USER app
VOLUME ["/data"]
EXPOSE 8000
ENTRYPOINT ["pricetracker"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
