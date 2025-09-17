FROM python:3.12-slim

# Set up a minimal working dir
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# copy project files
COPY . /app

# create virtualenv-like environment using pip
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Collect static if needed (no-op safe)
ENV DJANGO_SETTINGS_MODULE=settings.prod
RUN python blog_manager/manage.py collectstatic --noinput || true

# run gunicorn by default
CMD ["gunicorn", "blog_manager.wsgi:application", "-b", "0.0.0.0:8000", "--workers", "3"]
