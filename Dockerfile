# syntax=docker/dockerfile:1
# AI Company OS — FastAPI backend.
# Uses Python 3.12 (broad dependency support) and runs as a non-root user.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python dependencies (requirements.txt contains lower-bound pins).
# asyncpg/pydantic-core/greenlet all ship manylinux wheels, so no compiler
# or system libraries are required.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (see .dockerignore for exclusions).
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY pyproject.toml .

# Create a non-root user and owned directory.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Configurable port, default 8000.
ENV PORT=8000

# Bind to all interfaces (0.0.0.0) inside the container.
EXPOSE ${PORT}

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]