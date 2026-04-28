# ── Worker Dockerfile ───────────────────────────────────────────────────────
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
# gcc/g++ are required for Prophet; libpq-dev for Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install requirements
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the worker source code
COPY . .

# Ensure backend models are discoverable if backend is mounted/copied to /app/backend
ENV PYTHONPATH=/app:/app/backend

# Start Celery worker with concurrency optimized for HP Z440
CMD ["celery", "-A celery_app", "worker", "--loglevel=info", "--concurrency=4", "--pool=prefork"]