# syntax=docker/dockerfile:1.4
# ============================================================================
# Multi-stage Production-grade Dockerfile for DMarket Telegram Bot
# Size reduction: ~70% vs single-stage | Security: non-root user | Health checks included
# Last updated: January 2026
# BuildKit optimizations: cache mounts, inline cache
# ============================================================================

# ============================================================================
# STAGE 1: Builder - Install dependencies and create wheels
# ============================================================================
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better layer caching
COPY requirements.txt .

# Create wheels for all dependencies with BuildKit cache mount
# This caches pip downloads between builds, significantly speeding up rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels -r requirements.txt && \
    cp requirements.txt /wheels/

# ============================================================================
# STAGE 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.13-slim AS runtime

# OCI Image Spec labels (https://github.com/opencontainers/image-spec/blob/main/annotations.md)
LABEL org.opencontainers.image.title="DMarket Telegram Bot"
LABEL org.opencontainers.image.description="Production-ready Telegram bot for DMarket trading and arbitrage"
LABEL org.opencontainers.image.version="1.1.0"
LABEL org.opencontainers.image.authors="DMarket Bot Team"
LABEL org.opencontainers.image.source="https://github.com/Dykij/DMarket-Telegram-Bot"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.base.name="python:3.13-slim"
# Legacy labels for compatibility
LABEL maintainer="https://github.com/Dykij/DMarket-Telegram-Bot"
LABEL python.version="3.13"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH=/home/botuser/.local/bin:$PATH \
    LOG_LEVEL=INFO \
    DMARKET_API_URL=https://api.dmarket.com

# Install runtime dependencies only (PostgreSQL client libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/logs /app/data && \
    chown -R botuser:botuser /app

# Switch to non-root user BEFORE copying files
USER botuser
WORKDIR /app

# Copy wheels from builder stage
COPY --from=builder --chown=botuser:botuser /wheels /wheels

# Install dependencies from wheels (much faster than pip install)
RUN pip install --no-cache-dir --user --no-index --find-links=/wheels -r /wheels/requirements.txt && \
    rm -rf /wheels/*

# Copy application code (only needed files, not entire repo)
COPY --chown=botuser:botuser src/ ./src/
COPY --chown=botuser:botuser config/ ./config/
COPY --chown=botuser:botuser alembic/ ./alembic/
COPY --chown=botuser:botuser alembic.ini ./

# Expose metrics port for Prometheus (optional)
EXPOSE 8001

# Expose health check port (Roadmap Task #5)
EXPOSE 8080

# Health check endpoint using aiohttp health check server
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health').read()" || exit 1

# Use SIGTERM for graceful shutdown (Roadmap Task #4)
STOPSIGNAL SIGTERM

# Run bot (src/__main__.py must be entrypoint)
CMD ["python", "-m", "src"]
