# =============================================================================
# 1024 Multi-Agent Deep Research Oracle
# AI-Powered Decentralized Oracle for Prediction Markets
# =============================================================================

# Use official Python 3.12 slim image (smaller footprint)
FROM python:3.12-slim

# Labels for container registry
LABEL org.opencontainers.image.source="https://github.com/1024chain/1024-multi-deep-research-agent-oracle"
LABEL org.opencontainers.image.description="AI-Powered Decentralized Oracle for Prediction Markets"
LABEL org.opencontainers.image.licenses="MIT"

# Set working directory
WORKDIR /app

# Install system dependencies
# - curl: for health checks
# - build-essential: for compiling some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Sync dependencies (frozen to ensure reproducibility)
RUN uv sync --frozen --no-dev

# Copy source code
COPY oracle/ ./oracle/
COPY README.md LICENSE ./

# Expose port (default: 8989, matching .env.example)
EXPOSE 8989

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    API_HOST=0.0.0.0 \
    API_PORT=8989 \
    LOG_LEVEL=INFO \
    DEBUG=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${API_PORT:-8989}/health || exit 1

# Run the Oracle API server
# Production: no --reload, single worker (AI research is CPU/network bound)
CMD ["uv", "run", "uvicorn", "oracle.api.server:app", "--host", "0.0.0.0", "--port", "8989", "--workers", "1"]

