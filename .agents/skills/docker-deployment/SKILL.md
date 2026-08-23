---
name: docker-deployment
description: 'Use when creating Dockerfiles, Docker Compose configs, or deploying containers. Trigger keywords: "Docker", "container", "deploy", "Dockerfile", "docker-compose", "multi-stage build", "health check", "volume". Essential for DMarket bot production deployment.'
---

# Docker Deployment

Docker Compose, container services, deployment best practices.

## When to Use

- Creating or updating Dockerfiles
- Setting up Docker Compose for multi-service deployment
- Configuring health checks and volumes
- Optimizing container images
- Debugging container issues

## Core Patterns

### 1. Multi-Stage Dockerfile (Python)

```dockerfile
# Stage 1: Build
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

ENTRYPOINT ["python", "-m", "src.main"]
```

### 2. Docker Compose

```yaml
version: '3.8'

services:
  bot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: dmarket-bot
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./memory:/app/memory
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  redis:
    image: redis:7-alpine
    container_name: dmarket-redis
    restart: unless-stopped
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  redis-data:
```

### 3. ARM64 Compatibility

```dockerfile
# Multi-platform build
FROM --platform=$BUILDPLATFORM python:3.11-slim as builder

# For ARM64 (Apple Silicon, Raspberry Pi)
FROM python:3.11-slim as runtime-arm64
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# For x86_64
FROM python:3.11-slim as runtime-amd64

# Final stage - select based on architecture
FROM runtime-${TARGETARCH} as runtime
```

### 4. Environment Variables

```yaml
# docker-compose.yml
services:
  bot:
    environment:
      - DMARKET_API_KEY=${DMARKET_API_KEY}
      - DMARKET_API_SECRET=${DMARKET_API_SECRET}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - DRY_RUN=${DRY_RUN:-true}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    env_file:
      - .env
```

### 5. Volume Mounts

```yaml
services:
  bot:
    volumes:
      # Persistent data (SQLite, price history)
      - ./data:/app/data
      # Logs (rotate with Docker logging driver)
      - ./logs:/app/logs
      # Memory files (MEMORY.md, daily notes)
      - ./memory:/app/memory
      # Configuration
      - ./config:/app/config:ro
```

## Deployment Checklist

- [ ] Multi-stage build (smaller image)
- [ ] Non-root user in container
- [ ] Health checks configured
- [ ] Resource limits set
- [ ] Logging driver configured
- [ ] Volumes for persistent data
- [ ] Environment variables for secrets
- [ ] Restart policy set
- [ ] Network isolation configured

## Anti-patterns

### Running as root
**Symptom:** Security vulnerability
**Fix:** Create and use non-root user in Dockerfile

### No health checks
**Symptom:** Container appears running but bot is hung
**Fix:** Add HEALTHCHECK instruction

### Storing secrets in image
**Symptom:** Secrets in git history, image layers
**Fix:** Use environment variables or Docker secrets

### No resource limits
**Symptom:** Container consumes all host resources
**Fix:** Set `deploy.resources.limits`

### Using `latest` tag
**Symptom:** Non-reproducible builds
**Fix:** Pin specific versions in Dockerfile
