# Infrastructure

This folder contains all DevOps and infrastructure configuration.

## Contents

```
infrastructure/
├── docker/           # Per-service Dockerfiles (if not co-located)
├── nginx/            # Nginx reverse proxy config for production
└── README.md
```

The root `docker-compose.yml` (one level up) is the primary local dev entrypoint.

## Production Hosting

| Service | Platform |
|---|---|
| Frontend | Vercel |
| Backend / Worker | Render or Railway (free tier) |
| Database | Neon.tech or Supabase (PostgreSQL free tier) |
| Cache | Upstash Redis (free tier) |
| Object Storage | AWS S3 |
