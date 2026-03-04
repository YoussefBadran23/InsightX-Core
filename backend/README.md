# Backend — FastAPI Gateway

This package contains the InsightX REST API built with **FastAPI**.

## Structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app entrypoint
│   ├── api/             # Route handlers (v1)
│   ├── core/            # Config, security, DB session
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic request/response schemas
│   └── services/        # Business logic services
├── alembic/             # Database migrations
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Local Dev

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
