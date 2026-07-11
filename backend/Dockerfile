# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Dev target: deps installed into the image; source is bind-mounted by compose.
FROM base AS dev
COPY . .
RUN pip install --no-cache-dir ".[dev]"
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]

# Production target: slim, non-root.
FROM base AS prod
COPY . .
RUN pip install --no-cache-dir .
RUN useradd -m appuser
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
