# ===========================================================================
# Dash - Self-learning Data Agent
# ===========================================================================

FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

# ---------------------------------------------------------------------------
# Install dockerize (used by entrypoint.sh to wait for DB)
# ---------------------------------------------------------------------------
ARG DOCKERIZE_VERSION=v0.11.0
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl nodejs npm \
    libjpeg-dev libpng-dev zlib1g-dev libfreetype6-dev \
    libffi-dev libssl-dev libxml2-dev libxslt-dev \
    tesseract-ocr \
    && curl -sSfL "https://github.com/jwilder/dockerize/releases/download/${DOCKERIZE_VERSION}/dockerize-linux-${TARGETARCH}-${DOCKERIZE_VERSION}.tar.gz" \
       | tar -xz -C /usr/local/bin \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
WORKDIR /app
COPY requirements.txt ./
RUN uv pip sync requirements.txt --system
COPY . .
ENV PYTHONPATH=/app

# ---------------------------------------------------------------------------
# Build frontend (Brutalist Chat UI)
# ---------------------------------------------------------------------------
# Use pre-built frontend (run `cd frontend && npm run build` locally before docker build)
# Fallback: build inside Docker if no pre-built output exists
RUN if [ -d "frontend/build" ] && [ -f "frontend/build/index.html" ]; then \
      echo "Using pre-built frontend"; \
    else \
      echo "Building frontend inside Docker..." && \
      cd frontend && rm -rf .svelte-kit build node_modules && npm install && npm run build; \
    fi

# ---------------------------------------------------------------------------
# Create non-root user
# ---------------------------------------------------------------------------
RUN groupadd -r dash && useradd -r -g dash -d /app -s /sbin/nologin dash \
    && chown -R dash:dash /app
USER dash

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
RUN chmod +x /app/scripts/entrypoint.sh 2>/dev/null || true
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -f http://localhost:8000/health || exit 1

# ---------------------------------------------------------------------------
# Default command
# ---------------------------------------------------------------------------
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
