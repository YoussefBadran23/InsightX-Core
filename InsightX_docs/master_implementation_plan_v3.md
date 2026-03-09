# InsightX Full-Stack Master Execution Plan (v3.0)

## 1. Goal Description
To execute a flawless integration of the InsightX SaaS platform, moving beyond basic analytics into a fully automated, Cache-First AI Engine capable of running 22 advanced ML and data science modules on any uploaded CSV with zero manual mapping.

## 2. Master Architecture & Tech Stack
*   **Frontend:** `Next.js (App Router)`, `React`, `Tailwind CSS`, `Recharts`, `Zustand`.
*   **Backend & Gateway:** `Python 3.10+`, `FastAPI`.
*   **AI Engine & Pipeline:** `Celery` workers across 4 dedicated queues, utilizing `scikit-learn`, `prophet`, `lifetimes`, `transformers`, `rapidfuzz`.
*   **Messaging:** `Redis`.
*   **Database:** `PostgreSQL` (11 tables, JSONB caching, asyncpg).
*   **Infrastructure:** Docker, Docker-Compose, AWS RDS/S3 wrapper, GitHub Actions.

---

## 3. The "Perfect Execution" Step-by-Step Roadmap

### PHASE 1: Bedrock Infrastructure & DevOps Setup (✅ COMPLETED)
*   [x] **Step 1:** Initialize repository.
*   [x] **Step 2:** Define [docker-compose.yml](file:///c:/work/InsightX/InsightX-Core/docker-compose.yml) (PostgreSQL, Redis, FastAPI, Celery).
*   [x] **Step 3:** Setup Cloud Infrastructure (AWS RDS, S3).
*   [x] **Step 4:** Configure CI/CD Pipeline.

---

### PHASE 2: Database Schema & Backend Foundation (📍 WE ARE HERE)
*   [x] **Step 5 & 6: Database Topology & Alembic**
    *   Initialize 11 fully normalized tables with JSONB and UUIDs: `users`, `customers`, `products`, `orders`, `order_items`, `upload_jobs`, `csv_column_mappings`, `forecast_results`, `daily_kpi_snapshots`, `analysis_results_cache`, [insights](file:///c:/work/InsightX/InsightX-Core/worker/tasks/insights.py#6-11).
    *   Run Alembic migrations.
*   [x] **Step 7: JWT Authentication & Secret Admin Gateway**
    *   Implement standard `/auth/register` (hardcoded to default [user](file:///c:/work/InsightX/InsightX-Core/backend/app/dependencies.py#15-59) or `analyst` roles — admin signups blocked).
    *   Implement `/auth/login`, `/auth/me`, password resets.
    *   **Implement secret `/auth/admin/login` endpoint** protected by a [.env](file:///c:/work/InsightX/InsightX-Core/backend/.env) handshake key (`ADMIN_SECRET_KEY`).
*   [ ] **Step 8: Auto-Pipeline (Stage 1 & 2) — Ingestion & Mapping**
    *   `POST /upload/csv` → stream to S3 → create `upload_jobs` row → dispatch `csv_queue`.
    *   Worker uses `rapidfuzz` and semantic matching to auto-map CSV headers to the DB schema and stores them in `csv_column_mappings`.

---

### PHASE 3: The 7-Stage AI Auto-Pipeline Engine
*   [ ] **Step 9: Auto-Pipeline (Stage 3) — Validation & Coercion**
    *   Worker (`csv_queue`) types dates/numerics and flags failed rows.
*   [ ] **Step 10: Auto-Pipeline (Stage 4 & 5) — Entity & Dimension Upserts**
    *   Worker (`db_queue`) uses Postgres `ON CONFLICT DO UPDATE` to mass-upsert `customers` and `products`.
    *   Bulk insert `orders` and `order_items` via COPY protocol. Recalculate LTV and stock denormalizations.
*   [ ] **Step 11: Auto-Pipeline (Stage 6) — 22 Parallel Analytics Modules**
    *   Trigger a **Celery Chord** executing all modules concurrently across two queues:
        *   **`analytics_queue` (14 tasks):** Standard math/grouping (RFM scoring, Market Basket Apriori, Margin, Cohort Retention, GeoJSON).
        *   **`ml_queue` (6 tasks):** Heavy compute (Prophet Forecasting, Isolation Forest Anomalies, BG/NBD CLV, BERT Sentiment, K-Means Segmentation).
    *   All outputs are written instantly to `analysis_results_cache` as JSONB.
*   [ ] **Step 12: Auto-Pipeline (Stage 7) — Finalize & Push**
    *   After all 22 chord tasks finish, `tasks.finalize` flips job to `COMPLETED`.
    *   Snapshot `daily_kpi_snapshots`.
    *   Push WebSocket event to the Next.js frontend to instantly reload the dashboard.

---

### PHASE 4: Cache-First API Binding & Frontend Development
*   [ ] **Step 13: Core Dashboard & KPI APIs**
    *   Implement Cache-First endpoints (`GET /analytics/rfm`, `GET /analytics/{type}`). API simply serves the pre-calculated `result_json` from the cache table.
*   [ ] **Step 14: Next.js scaffolding & Landing/Auth Pages**
    *   Build standard `/login` and `/register`. 
    *   **Feature:** Implement the physical `ESC` keydown event listener on the login page that slides out the secret Admin Login Panel (hits `/auth/admin/login` with secret handshake).
*   [ ] **Step 15: The Dashboard UI Shell**
    *   Build the 256px sidebar, frosted navbar, and WebSocket listener.
*   [ ] **Step 16: Dynamic Recharts & Data Tables**
    *   Build `/customers/segmentation` (3D bubble chart), `/forecasting` (scenario sliders), and the main home KPI charts.
*   [ ] **Step 17: User Profile & Widget Grid**
    *   Implement `react-grid-layout` allowing users to save custom dashboard layout coordinates back to their `users.widget_config` JSONB column.

---

### PHASE 5: Polish, Scheduling & Deployment
*   [ ] **Step 18: Error Handling & Graceful Degradation**
    *   Celery failure states update DB and push WebSocket error alerts to frontend.
*   [ ] **Step 19: Celery Beat Nightly Cron**
    *   Setup a nightly task at 00:05 UTC to freeze `daily_kpi_snapshots` for historical tracking.
*   [ ] **Step 20: Production Launch**
    *   Configure live WebSocket proxying in Nginx.
    *   E2E stress test with a 50,000-row dataset to prove sub-3-second API response times via the `analysis_results_cache` design.
