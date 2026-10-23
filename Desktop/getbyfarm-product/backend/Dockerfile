FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# libpq runtime only (psycopg2-binary bundles what it needs); curl for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
# Robust to how the repo was zipped/committed: Windows tools can drop the executable bit and add CRLF line endings,
# either of which makes the container die at start with no output. Fix both here and run via `sh` below.
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh
# Collect static files at build time (needs a dummy key; the real one is injected at runtime).
RUN DJANGO_DEBUG=true DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

# Run as an unprivileged user.
RUN useradd --system --uid 10001 --no-create-home app && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD curl -fsS -H "Host: ${HEALTHCHECK_HOST:-localhost}" http://127.0.0.1:${PORT:-8000}/api/health/ || exit 1
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
# PORT is injected by platforms like Render (default 10000); WEB_CONCURRENCY likewise. Locally: 8000 and 3 workers.
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-3} --timeout 60 --access-logfile -"]
