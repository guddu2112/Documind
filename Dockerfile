# ── Stage 1: Python builder ────────────────────────────────────
FROM python:3.11-slim AS python-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Virtual-env for clean copy to runtime
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install deps first (layer cache)
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# ── Stage 2: Frontend build ───────────────────────────────────
FROM node:20-slim AS frontend

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --ignore-scripts
COPY web/ ./
RUN npm run build

# ── Stage 3: Runtime ──────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user
RUN groupadd -r documind && useradd -r -g documind -d /app -s /sbin/nologin documind

WORKDIR /app

# Copy virtualenv from builder
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code and config
COPY src/ ./src/
COPY config/ ./config/

# Copy frontend build output
COPY --from=frontend /web/dist ./static/

RUN chown -R documind:documind /app

USER documind

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "documind.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
