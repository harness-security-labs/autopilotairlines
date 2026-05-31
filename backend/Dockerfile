FROM ghcr.io/astral-sh/uv:python3.12-trixie

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY bin/autoreport /usr/local/bin/autoreport
RUN chmod +x /usr/local/bin/autoreport

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
