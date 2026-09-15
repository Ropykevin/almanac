# Almanac Africa AI — production image

FROM node:22-alpine AS css
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm ci
COPY tailwind.config.js ./
COPY app/templates ./app/templates
COPY app/static/js ./app/static/js
COPY app/static/css/input.css ./app/static/css/input.css
RUN npm run build:css

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=wsgi.py \
    FLASK_CONFIG=production

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .
COPY --from=css /build/app/static/css/main.css ./app/static/css/main.css

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/logs /app/instance /app/app/static/uploads \
    && chmod +x /app/docker-entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
