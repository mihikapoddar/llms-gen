FROM python:3.9-slim

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system .

ENV LLMS_GEN_DATABASE_URL=sqlite+aiosqlite:///./data/llms_gen.db
RUN mkdir -p /app/data

# Render sets PORT (default 10000 per https://render.com/docs/web-services#port-binding ).
# If PORT were ever unset, binding 8000 while Render probes 10000 causes "no open ports" deploy failures.
# Local: set PORT=8000 in docker-compose (see docker-compose.yml).
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn llms_gen.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
