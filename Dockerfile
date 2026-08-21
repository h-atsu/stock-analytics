FROM ghcr.io/astral-sh/uv:0.11.19 AS uv

FROM python:3.12.13-slim-bookworm

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY dbt ./dbt
RUN uv sync --frozen --no-dev

ENTRYPOINT ["stock-analytics"]
CMD ["--help"]
