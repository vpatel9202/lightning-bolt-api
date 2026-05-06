FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    LB_DEFAULT_TZ=America/Chicago

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["/app/.venv/bin/lb-api-mcp", "http", "--host", "0.0.0.0", "--port", "8000"]
