# InsightX

**InsightX** is a data-analytics platform that turns raw business data (CSV / Excel / JSON / Parquet) into actionable insights. Upload a dataset and a background engine runs a multi-stage pipeline — preprocessing, database upsert, 18+ analytics & ML modules (forecasting, segmentation, sentiment, CLV, …), and an optional LLM enrichment pass — then surfaces the results on an interactive dashboard.

---

## Architecture

InsightX is a set of cooperating services:

| Service       | Tech                         | Port   | Role                                                            |
| ------------- | ---------------------------- | ------ | -------------------------------------------------------------- |
| **frontend**  | Next.js 14 (React 18)        | `3000` | Dashboard UI — upload data, view charts & reports              |
| **backend**   | FastAPI (Python 3.11)        | `8000` | REST API gateway, auth, uploads, dispatches analytics jobs     |
| **worker**    | Celery (Python 3.11)         | —      | Runs the analytics/ML pipeline asynchronously                  |
| **db**        | PostgreSQL 16                | `5432` | Single source of truth (relational store)                      |
| **redis**     | Redis 7                      | `6379` | Celery broker + result backend                                 |
| **nginx**     | Nginx (production only)      | `80/443` | Reverse proxy in front of frontend + backend                 |

```
            ┌────────────┐      HTTP       ┌────────────┐
  Browser ─▶│  frontend  │ ──────────────▶ │  backend   │
            │ Next.js    │   /api/v1/...    │  FastAPI   │
            └────────────┘                 └─────┬──────┘
                                                 │ enqueue job (Redis)
                                  ┌──────────────┼───────────────┐
                                  ▼              ▼               ▼
                            ┌─────────┐    ┌──────────┐    ┌──────────┐
                            │  redis  │◀──▶│  worker  │    │  db      │
                            │ broker  │    │  Celery  │───▶│ Postgres │
                            └─────────┘    └──────────┘    └──────────┘
```

The backend and worker **share the same database** and the **same uploads folder** (the worker reads the files the backend saved).

---

## Repository layout

```
InsightX-Core/
├── backend/            # FastAPI gateway (API, auth, uploads, Alembic migrations)
│   ├── app/            #   main.py, routers/, models/, schemas/, services/, core/
│   ├── alembic/        #   database migrations
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── worker/             # Celery analytics & ML engine
│   ├── celery_app.py   #   Celery app + queue routing
│   ├── tasks/          #   pipeline stages + analytics modules
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/           # Next.js dashboard
│   ├── src/
│   ├── package.json
│   ├── Dockerfile
│   └── .env.example
├── infrastructure/     # nginx.conf, redis.conf (DevOps config)
├── docker-compose.yml        # local development stack
├── docker-compose.prod.yml   # production stack (nginx + Datadog + resource limits)
└── README.md
```

---

## Prerequisites

Pick **one** of the two paths below.

* **Docker path (recommended):** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine) with Docker Compose v2. Nothing else needed.
* **Local / no-Docker path:** Python **3.11**, Node.js **20+**, PostgreSQL **16**, and Redis **7**.

> **Default dev credentials** (used everywhere below): database `insightx_db`, user `insightx_user`, password `insightx_pass`.

---

## Option A — Run with Docker (recommended)

This builds and starts **all** services (Postgres, Redis, backend, worker, frontend) with one command. Database migrations run automatically on backend start.

### 1. Clone

```bash
git clone <YOUR_REPO_URL> InsightX-Core
cd InsightX-Core
```

### 2. Create the env files

The compose file reads three env files that are **not** committed (they hold secrets). Create them from the templates:

```bash
cp backend/.env.example   backend/.env
cp worker/.env.example    worker/.env
cp frontend/.env.example  frontend/.env.local
```

> On Windows PowerShell, `cp` works as an alias; or use `Copy-Item backend/.env.example backend/.env`.

### 3. Set real secrets

Open `backend/.env` and replace the placeholder keys with strong values:

```bash
# generate a secret (run twice — one for SECRET_KEY, one for ADMIN_SECRET_KEY)
python -c "import secrets; print(secrets.token_hex(32))"
```

> For Docker you can leave the `DATABASE_URL` / `REDIS_URL` values as-is — compose overrides them with the internal service hostnames (`db`, `redis`). Optional integrations (Gemini AI, SMTP email, Sentry, Datadog) can stay blank for local use.

### 4. Build & start

```bash
docker compose up --build
```

First build takes a few minutes (the worker image installs pandas/scikit-learn/prophet). Subsequent starts are fast.

### 5. Open the app

| URL                                  | What                         |
| ------------------------------------ | ---------------------------- |
| http://localhost:3000                | Frontend dashboard           |
| http://localhost:8000/docs           | Backend API docs (Swagger)   |
| http://localhost:8000/health         | Backend health check         |

### Everyday Docker commands

```bash
docker compose up -d          # start in the background
docker compose logs -f worker # follow one service's logs
docker compose ps             # list running services
docker compose down           # stop & remove containers (keeps data)
docker compose down -v        # stop & WIPE the database/redis volumes (fresh start)
docker compose up --build backend   # rebuild a single service
```

Code is bind-mounted, so the backend (uvicorn `--reload`) and frontend (`next dev`) **hot-reload** on file changes. Restart the `worker` container after editing worker code.

---

## Option B — Run locally without Docker

You will run **five** processes: PostgreSQL, Redis, the backend, the worker, and the frontend. Open a separate terminal for each long-running process.

> **Windows note:** Redis has no official native Windows build. Use [WSL2](https://learn.microsoft.com/windows/wsl/install), [Memurai](https://www.memurai.com/), or just run Redis (and/or Postgres) via Docker while running the app code natively.

### 0. Start PostgreSQL & Redis, then create the database

Make sure both services are running, then create the role and database (using `psql` as a superuser):

```sql
CREATE USER insightx_user WITH PASSWORD 'insightx_pass';
CREATE DATABASE insightx_db OWNER insightx_user;
GRANT ALL PRIVILEGES ON DATABASE insightx_db TO insightx_user;
```

Confirm Redis responds:

```bash
redis-cli ping     # -> PONG
```

### 1. Backend (terminal 1)

```bash
cd backend
python -m venv venv

# activate the virtualenv:
venv\Scripts\Activate.ps1     # Windows PowerShell
# source venv/bin/activate    # macOS / Linux

pip install -r requirements.txt

cp .env.example .env          # then edit .env — see below
```

Edit `backend/.env` so the hosts point at **localhost** (the template uses Docker hostnames) and set real secret keys:

```ini
DATABASE_URL=postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
SECRET_KEY=<paste output of: python -c "import secrets; print(secrets.token_hex(32))">
ADMIN_SECRET_KEY=<another generated value>
```

Apply migrations and start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Backend is now live at http://localhost:8000 (docs at `/docs`).

### 2. Worker (terminal 2)

The worker imports the backend's ORM models (`app.models.*`) and reads the files the backend saved, so it needs two extra environment variables: `PYTHONPATH` (pointing at `backend/`) and `UPLOAD_DIR` (pointing at `backend/uploads`). The worker reads config **from the shell environment** (it does not auto-load a `.env` file), and its code defaults to Docker hostnames — so you must export these for local runs.

```bash
cd worker
python -m venv venv
venv\Scripts\Activate.ps1          # Windows PowerShell  (or: source venv/bin/activate)
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
$env:PYTHONPATH            = "..\backend"
$env:UPLOAD_DIR            = (Resolve-Path ..\backend\uploads).Path
$env:DATABASE_URL          = "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db"
$env:REDIS_URL             = "redis://localhost:6379/0"
$env:CELERY_BROKER_URL     = "redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

# -P solo: the default prefork pool is not supported on Windows
celery -A celery_app worker --loglevel=info --concurrency=2 -Q celery,analytics,ml -P solo
```

**macOS / Linux:**

```bash
export PYTHONPATH=../backend
export UPLOAD_DIR="$(cd ../backend/uploads && pwd)"
export DATABASE_URL="postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db"
export REDIS_URL="redis://localhost:6379/0"
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"

celery -A celery_app worker --loglevel=info --concurrency=2 -Q celery,analytics,ml
```

> Some ML dependencies (e.g. `prophet`) need C/C++ build tools. If installation is troublesome on Windows, the code falls back to `statsmodels`, or simply run the worker via Docker.

### 3. Frontend (terminal 3)

```bash
cd frontend
npm install
cp .env.example .env.local     # default API URL is http://localhost:8000 — fine for local
npm run dev
```

Open http://localhost:3000.

---

## Environment variables

Each service has its own template; copy it and fill in values.

| File                  | Used by   | Key settings                                                              |
| --------------------- | --------- | ------------------------------------------------------------------------- |
| `backend/.env`        | backend   | `SECRET_KEY`, `ADMIN_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, SMTP, `GOOGLE_AI_API_KEY` |
| `worker/.env`         | worker    | `DATABASE_URL`, `REDIS_URL`, `UPLOAD_DIR`, `GOOGLE_AI_API_KEY`            |
| `frontend/.env.local` | frontend  | `NEXT_PUBLIC_API_URL` (baked into the bundle at build time)               |

> ⚠️ **`NEXT_PUBLIC_API_URL` is read at build time**, not runtime. For a production frontend build, set it to your public backend URL before building (see `frontend/Dockerfile` and `docker-compose.prod.yml`).

---

## Production

`docker-compose.prod.yml` adds an **nginx** reverse proxy and a **Datadog** agent, runs uvicorn with multiple workers, and applies per-service memory limits.

```bash
cp backend/.env.example  backend/.env     # fill in real production secrets
cp worker/.env.example   worker/.env
cp frontend/.env.example frontend/.env.local

docker compose -f docker-compose.prod.yml build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.your-domain.com
docker compose -f docker-compose.prod.yml up -d
```

See [`infrastructure/README.md`](infrastructure/README.md) for the hosting/observability toolchain.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `docker compose up` fails: *env file not found* | You skipped step 2 — create `backend/.env`, `worker/.env`, `frontend/.env.local` from the `.example` files. |
| Backend can't reach the DB locally | Postgres isn't running, or `DATABASE_URL` still points at `db` instead of `localhost`. |
| Worker: `ModuleNotFoundError: No module named 'app'` | `PYTHONPATH` isn't set to the `backend/` folder. |
| Worker runs but never picks up jobs | It's pointing at the wrong Redis, or files aren't found — check `REDIS_URL` and `UPLOAD_DIR`. |
| Worker error on Windows about the pool | Add `-P solo` (or `--pool=threads`) to the Celery command. |
| Frontend calls the wrong API | `NEXT_PUBLIC_API_URL` is baked at build time — rebuild after changing it. |

---

## Security

* **Never commit real secrets.** `.env` files are git-ignored; only `*.env.example` templates are tracked.
* Generate strong `SECRET_KEY` / `ADMIN_SECRET_KEY` values before any non-local use.
* If a credential (SMTP password, API key, etc.) has ever been committed or shared, **rotate it.**

---

## License

_No license specified yet — add one (e.g. `LICENSE` file) before publishing if you intend others to use it._
