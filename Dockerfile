# OD-Prank-BE/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# TLS certs for outbound HTTPS/SSL (Supabase Postgres, Supabase REST, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy application code
COPY . .

EXPOSE 8000

# Migrate then serve; bind to Railway's dynamic port
CMD ["sh", "-c", "uv run gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:${PORT:-8000} --forwarded-allow-ips='*'"]