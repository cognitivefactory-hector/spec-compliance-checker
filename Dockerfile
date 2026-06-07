FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Install dependencies first so the layer caches across code changes.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY . .

# Collect static assets (whitenoise serves them in production).
RUN DJANGO_SECRET_KEY=build-time-only python manage.py collectstatic --noinput

EXPOSE 8000

# Render provides $PORT; default to 8000 locally.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3"]
