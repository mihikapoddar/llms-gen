FROM python:3.9-slim

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system .

ENV LLMS_GEN_DATABASE_URL=sqlite+aiosqlite:///./data/llms_gen.db
RUN mkdir -p /app/data

# Render (and some hosts) set PORT at runtime; default 8000 for local docker compose.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn llms_gen.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
