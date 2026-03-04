# ── Worker Dockerfile ───────────────────────────────────────────────────────
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# System deps: gcc for Prophet/numpy compilation, libpq for DB access
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (heavy AI stack — cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Default: start Celery worker (overridden by docker-compose)
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=2"]
