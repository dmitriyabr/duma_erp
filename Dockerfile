# Build stage for frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Backend runtime
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
RUN pip install uv

# Create non-root user early
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Change ownership of /app to appuser BEFORE switching users
RUN chown -R appuser:appuser /app

# Copy Python dependencies
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Switch to non-root user before installing deps
USER appuser

# Install Python dependencies as appuser
RUN uv sync --frozen --no-dev

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini ./

# Copy frontend build
COPY --from=frontend-build --chown=appuser:appuser /app/frontend/dist ./frontend/dist

# Expose port
EXPOSE 8000

# Run migrations and start server
# Note: PORT env var is provided by Railway
CMD sh -c "uv run alembic upgrade head && uv run uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"
