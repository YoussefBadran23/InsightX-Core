FROM python:3.11-slim

# System dependencies for scientific packages and fontconfig
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r celery && useradd -r -g celery celery

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create cache directories for matplotlib and fontconfig and set permissions
RUN mkdir -p /app/.config/matplotlib \
    && mkdir -p /app/.cache/fontconfig \
    && chown -R celery:celery /app/.config \
    && chown -R celery:celery /app/.cache

# Set environment variables for writable cache directories
ENV MPLCONFIGDIR=/app/.config/matplotlib
ENV FONTCONFIG_PATH=/app/.cache/fontconfig

COPY . .
RUN chown -R celery:celery /app

USER celery

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=2", "-Q", "celery,analytics,ml"]
