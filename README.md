# InsightX-Core

> AI-powered SaaS analytics platform — Graduation Project 2025

## 🏗️ Monorepo Structure

```
InsightX-Core/
├── frontend/        # Next.js (App Router) + Tailwind CSS
├── backend/         # Python FastAPI — REST API Gateway
├── worker/          # Celery async workers — AI Engine Room
├── infrastructure/  # Docker, Docker Compose, GitHub Actions CI/CD
└── README.md
```

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, Tailwind CSS, Recharts, Zustand |
| Backend | Python 3.10+, FastAPI, SQLAlchemy, Alembic |
| AI Engine | Prophet, Multilingual BERT, Groq API (LLaMA 3) |
| Async | Celery + Redis |
| Database | PostgreSQL (Supabase / Neon.tech free tier) |
| DevOps | Docker, Docker Compose, GitHub Actions |
| Hosting | Vercel (frontend), Render / Railway (backend) |

## 🚀 Quick Start (Local Dev)

```bash
# 1. Clone the repo
git clone https://github.com/<your-org>/InsightX-Core.git
cd InsightX-Core

# 2. Copy environment templates
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# 3. Spin up all services
docker compose up --build
```

Services will be available at:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## 📋 Roadmap

See [implementation_plan.md](../docs/implementation_plan.md) for the full 5-phase execution plan.

## 📄 License

MIT — Graduation Project Use Only
