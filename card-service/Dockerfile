FROM ghcr.io/astral-sh/uv:python3.12-trixie

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY src/ ./src/

EXPOSE 8002

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
