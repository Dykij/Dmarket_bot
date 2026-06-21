# ============================================================================
# DMarket Quantitative Engine — Production Dockerfile (v14.4)
# Multi-stage build: compiles Rust module, keeps final image ~250 MB.
# Works on x86_64, aarch64 (Raspberry Pi 4/5), and ARM64 mini-PCs.
# ============================================================================

# ── Stage 1: Builder ───────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: build tools for Python C-extensions + Rust
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain (required for dmarket_parser_rs)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# Copy and install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# Copy Rust crate source and build, then clean up build artifacts
COPY src/rust_core/ src/rust_core/
WORKDIR /app/src/rust_core
RUN maturin build --release \
    && pip install target/wheels/*.whl \
    && rm -rf target/ \
    && rm -rf ~/.cargo/registry/ ~/.cargo/git/

WORKDIR /app
COPY src/ src/
COPY pyproject.toml .

# ── Stage 2: Runtime ───────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal runtime deps (curl for health check, tini for signal handling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire Python environment from builder (includes compiled Rust .so)
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application source (skip rust_core — .so already in site-packages)
WORKDIR /app
COPY --from=builder /app/src/ /app/src/
COPY --from=builder /app/pyproject.toml /app/
# Clean up Rust build artifacts if they leaked through
RUN rm -rf /app/src/rust_core/target/ 2>/dev/null || true

# Create non-root user
RUN groupadd --gid 1000 bot \
    && useradd --uid 1000 --gid 1000 -m bot \
    && mkdir -p /app/data /app/logs \
    && chown -R bot:bot /app

USER bot

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://127.0.0.1:9091/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "src"]
