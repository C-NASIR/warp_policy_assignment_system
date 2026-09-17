# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.9 AS uv

FROM python:3.12.12-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12.12-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system --gid 10001 policyos \
    && useradd --system --uid 10001 --gid policyos --home-dir /app --shell /usr/sbin/nologin policyos

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=policyos:policyos alembic ./alembic
COPY --chown=policyos:policyos app ./app
COPY --chown=policyos:policyos scripts ./scripts
COPY --chown=policyos:policyos alembic.ini main.py ./

USER policyos
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3).read()"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
