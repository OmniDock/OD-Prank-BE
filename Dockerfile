# OD-Prank-BE/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# TLS certs for outbound HTTPS/SSL (Supabase Postgres, Supabase REST, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y ffmpeg

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
# CMD ["sh", "-c", ""]