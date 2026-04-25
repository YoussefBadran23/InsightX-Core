# InsightX Full-Stack Master Execution Plan (v4.0)

## 1. Goal Description
To execute a flawless integration of the InsightX SaaS platform — a fully automated, Cache-First AI Engine capable of running 22 advanced ML and data science modules on any uploaded CSV with zero manual mapping. Built as a graduation project by 7 Data Science & Cloud Computing graduates (Canadian International College, 2025).

## 2. Master Architecture & Tech Stack
*   **Frontend:** `Next.js 14 (App Router)`, `React 18`, `Tailwind CSS 3.4`, `Recharts`, `Zustand`.
*   **Backend & Gateway:** `Python 3.11`, `FastAPI 0.111` (with GZip, CORS & ORJSON optimizations).
*   **AI Engine & Pipeline:** `Celery 5.4` workers across 4 dedicated queues, utilizing `scikit-learn 1.4`, `prophet`, `lifetimes`, `pandas 2.2`, `rapidfuzz 3.9`, and **Local LLM via OpenAI SDK** (LM Studio / Ollama / Groq).
*   **Messaging:** `Redis 7`.
*   **Database:** `PostgreSQL 16` (11 tables, JSONB caching, UUID PKs, soft-delete mixins).
*   **Infrastructure:** Docker, Docker Compose, AWS RDS/S3, GitHub Actions CI/CD.

---

## 3. The "Perfect Execution" Step-by-Step Roadmap

### PHASE 1: Bedrock Infrastructure & DevOps Setup (✅ COMPLETED)
*   [x] **Step 1:** Initialize monorepo (`backend/`, `worker/`, `next-scaffold/`, `frontend/`, `infrastructure/`).
*   [x] **Step 2:** Define `docker-compose.yml` — 5 services (PostgreSQL 16-alpine, Redis 7-alpine, FastAPI, Celery worker, Next.js).
*   [x] **Step 3:** Setup Cloud Infrastructure (AWS RDS instance, S3 bucket `insightx-raw-data-lake-prod`).
*   [x] **Step 4:** Configure CI/CD Pipeline (GitHub Actions: Black + Flake8 lint on PR, SSH deploy to EC2 on master push).

---

### PHASE 2: Database Schema & Backend Foundation (✅ COMPLETED — with bugs to fix)
*   [x] **Step 5 & 6: Database Topology & Alembic**
    *   Initialized 11 tables with UUIDs, TimestampMixin, SoftDeleteMixin: `users`, `customers`, `products`, `orders`, `order_items`, `upload_jobs`, `csv_column_mappings`, `forecast_results`, `daily_kpi_snapshots`, `analysis_results_cache`, `insights`.
    *   Alembic migration `cd7f4376ca5f` creates full schema with indexes, unique constraints, and foreign keys.
    *   **Verified by:** `test_db_step5.py` (73 checks — schema, CRUD, constraints, computed fields).
*   [x] **Step 7: JWT Authentication & Secret Admin Gateway**
    *   `/auth/register` — roles restricted to `user` | `analyst` (admin signup blocked via Pydantic regex).
    *   `/auth/login`, `/auth/me`, `/auth/me` PATCH, `/auth/change-password`.
    *   `/auth/forgot-password` and `/auth/reset-password` with SHA256 token hashing.
    *   Secret `/auth/admin/login` endpoint (hidden from Swagger, requires `ADMIN_SECRET_KEY` handshake).
    *   **Verified by:** `test_auth_step7.py` (50+ checks), `test_final.py` (73 checks), `test_comprehensive.py` (12 edge cases incl. SQL injection defense).
*   [x] **Step 8: Auto-Pipeline (Stage 1 & 2) — Ingestion & Mapping**
    *   `POST /upload/csv` — saves file locally with UUID prefix, creates `upload_jobs` row, dispatches Celery task.
    *   Worker `tasks.csv.process_csv` uses `rapidfuzz.fuzz.WRatio` to auto-map CSV headers against 7 standard columns. Score >= 0.85 auto-confirmed; 0.60–0.84 low confidence.
    *   Results stored in `csv_column_mappings` with match_score and match_method.
    *   LLM insight generation (`tasks.insights.run_insights`) implemented via OpenAI SDK with `base_url` override for local LLM.

---

### PHASE 2.5: Security Hardening & Bug Fixes (🔴 CRITICAL — DO FIRST)

> **Rationale:** Deep code analysis revealed critical security vulnerabilities and bugs that must be resolved before building further. Shipping Phase 3+ on a broken foundation compounds technical debt.

*   [ ] **Step 8A: Credential Rotation & Secrets Cleanup**
    *   Rotate all exposed AWS credentials (`AKIA55U6VQSUG6CT6B75`) — they are in committed `.env` files.
    *   Rotate RDS password (`InsightX2025!`) — exposed in `backend/.env` and `worker/.env`.
    *   Delete `pass db.txt` and `insightx-key.pem` from repo root.
    *   Purge credentials from git history (`git filter-branch` or `BFG Repo-Cleaner`).
    *   Replace hardcoded defaults: `SECRET_KEY="insecure-change-me-in-production"` and `ADMIN_SECRET_KEY="insightx-admin-secret-change-me"` with strong generated values.
    *   Ensure all `.env` files are in `.gitignore` and never committed again.

*   [ ] **Step 8B: Backend Bug Fixes**
    *   **Upload router:** Replace per-request Celery instance creation (line 60 of `upload.py`) with imported singleton from `celery_app`.
    *   **Upload router:** Add file size validation (max 50MB), MIME type check (`text/csv`), and CSV structure validation (must have headers).
    *   **Upload router:** Wrap `UploadJob` creation + Celery dispatch in a DB transaction (rollback if dispatch fails).
    *   **Auth router:** Remove dev shortcut that returns raw reset token in `/forgot-password` response (line 212 of `auth.py`).
    *   **Auth router:** Invalidate existing JWTs on password change (add `token_version` to users table or use a token blacklist).
    *   **CORS:** Restrict `allow_methods` and `allow_headers` to specific values instead of `["*"]`.
    *   **Config:** Add production validation — error if `SECRET_KEY` or `ADMIN_SECRET_KEY` still contain default values when `APP_ENV=production`.

*   [ ] **Step 8C: Worker Bug Fixes**
    *   **csv.py:** Fix session leak — wrap initial `SessionLocal()` + query in `try/finally`.
    *   **csv.py:** Add CSV encoding detection (`chardet` or explicit `utf-8-sig` fallback).
    *   **csv.py:** Handle malformed CSV with `try/except` around `pd.read_csv()`.
    *   **csv.py:** Log unmapped columns (score < 0.60) as warnings instead of silent skip.
    *   **csv.py:** Make fuzzy match threshold configurable via env var `FUZZY_MATCH_THRESHOLD` (default 0.85).
    *   **insights.py:** Add timeout to LLM call (`httpx` timeout or `openai` client timeout param).
    *   **insights.py:** Fix env var mismatch — standardize on `LOCAL_LLM_URL` + `LOCAL_LLM_API_KEY` across `.env` and `.env.example`.
    *   **insights.py:** Update job status on failure (currently only logs, doesn't write to DB).
    *   **insights.py:** Replace hardcoded placeholder text `"Statistical variance observed in dataset."` with explicit `[No insight generated]` marker.
    *   **celery_app.py:** Add `task_soft_time_limit=300`, `task_time_limit=600`, `task_acks_late=True`.
    *   **celery_app.py:** Configure dead letter queue for permanently failed tasks.
    *   Fix duplicate `pandas` entry in `worker/requirements.txt`.

*   [ ] **Step 8D: Repo Cleanup**
    *   Remove `node_modules/` from git tracking (add to `.gitignore`, `git rm -r --cached`).
    *   Remove dead code: `rebrand.py` (no-op script — replaces strings with themselves).
    *   Consolidate duplicate test files (`test_upload_flow.py` exists in both root and `backend/`).
    *   Remove installer executables from repo root (Chrome, Claude, Cursor `.exe` files).
    *   Rename all "Velin" references to "InsightX" in docs, CI/CD pipeline name, and docker image names.
    *   Create missing `docker-compose.prod.yml` (referenced in `deploy.yml` but doesn't exist — deployment is broken).

*   [ ] **Step 8E: Add Rate Limiting & Input Validation**
    *   Add `slowapi` rate limiter to auth endpoints (5 login attempts / minute per IP).
    *   Add request logging middleware (structured JSON with request ID).
    *   Add input sanitization for string fields (strip whitespace, validate URL formats for `avatar_url`).

---

### PHASE 3: The 7-Stage AI Auto-Pipeline Engine (📍 START HERE AFTER 2.5)

*   [ ] **Step 9: Auto-Pipeline (Stage 3) — Validation & Coercion**
    *   Implement `tasks.preprocess.run_preprocessing` (currently raises `NotImplementedError`).
    *   Pull CSV from local storage (S3 in production) using the column mappings from Stage 2.
    *   Type-cast columns: parse dates (`pd.to_datetime`), cast numerics (`pd.to_numeric`), normalize strings.
    *   Flag invalid rows → increment `upload_jobs.rows_failed`, log errors to `upload_jobs.error_message`.
    *   Update `upload_jobs.status` to `"validating"` → `"validated"`.
    *   Add `chardet` encoding detection for non-UTF-8 files.

*   [ ] **Step 10: Auto-Pipeline (Stage 4 & 5) — Entity & Dimension Upserts**
    *   Implement `tasks.upsert.run_upserts` (new task file needed).
    *   Upsert `customers` via `ON CONFLICT (external_id) DO UPDATE` — merge demographics, preserve `first_purchase_date`.
    *   Upsert `products` via `ON CONFLICT (sku) DO UPDATE` — update pricing, preserve stock.
    *   Bulk insert `orders` and `order_items` via `psycopg2.extras.execute_values` or COPY protocol.
    *   Recalculate denormalized counters: `customers.total_orders`, `customers.lifetime_value`, `products.total_revenue`, `products.total_units_sold`.
    *   Update `upload_jobs.rows_processed` incrementally for frontend progress bars.
    *   Wrap all inserts in a single DB transaction (rollback entire batch on failure).
    *   Update `upload_jobs.status` to `"inserting"` → `"insert_complete"`.

*   [ ] **Step 11: Auto-Pipeline (Stage 6) — 22 Parallel Analytics Modules**
    *   Trigger a **Celery Chord** executing all modules concurrently across two queues:
        *   **`analytics_queue` (14 tasks):**
            *   A01: Revenue Summary (total, by region, by period)
            *   A02: RFM Scoring (Recency, Frequency, Monetary → 5-5-5 scoring → segment labels)
            *   A03: Market Basket / Apriori (association rules from `order_items`)
            *   A04: Gross Margin Analysis (per product, per category)
            *   A05: Cohort Retention (monthly cohorts, retention heatmap)
            *   A06: Geographic Revenue (GeoJSON aggregation by region/country)
            *   A07: ABC Tier Classification (Pareto 80/20 on product revenue)
            *   A08: Average Order Value trends
            *   A09: Top N Products / Categories
            *   A10: Customer Lifetime summary statistics
            *   A11: Order Status Distribution
            *   A12: Discount Impact Analysis
            *   A13: Period-over-Period Growth Rates
            *   A14: Customer Acquisition by Channel
        *   **`ml_queue` (6 tasks):**
            *   A15: Prophet Revenue Forecasting (30/60/90 day, confidence intervals → `forecast_results`)
            *   A16: Isolation Forest Anomaly Detection (outlier orders)
            *   A17: BG/NBD + Gamma-Gamma CLV Prediction (→ `customers.clv_predicted`)
            *   A18: Local LLM Sentiment Analysis (order comments → `orders.sentiment_label/score`)
            *   A19: K-Means Customer Segmentation (→ `customers.ai_segment`)
            *   A20: Churn Risk Logistic Regression (→ `customers.churn_risk_score`)
        *   **Post-chord tasks (2):**
            *   A21: Return Rate Analysis (per product, per category)
            *   A22: Fulfillment SLA Analysis (delivery_days distribution)
    *   All outputs written to `analysis_results_cache` as JSONB with `duration_ms` for performance tracking.
    *   Mark previous cache entries as `is_stale=True` before recompute; flip to `False` after.

*   [ ] **Step 12: Auto-Pipeline (Stage 7) — Finalize & Push**
    *   Implement `tasks.finalize.run_finalize` callback (fires after chord completion).
    *   Flip `upload_jobs.status` to `"completed"`, set `completed_at`.
    *   Snapshot `daily_kpi_snapshots` for today (aggregate from orders).
    *   Generate 3 LLM insight bullets per analysis type via `tasks.insights.run_insights`.
    *   Push WebSocket event (`job_complete`) to Next.js frontend for instant dashboard reload.

---

### PHASE 4: Cache-First API Binding & Frontend Development

*   [ ] **Step 13: Core Dashboard & KPI APIs**
    *   Implement `routers/analytics.py`:
        *   `GET /api/v1/analytics/{type}` — serves pre-calculated `result_json` from `analysis_results_cache`. Cache-First: zero recomputation.
        *   `GET /api/v1/analytics/kpi/summary` — latest `daily_kpi_snapshots` row + period-over-period deltas.
        *   `GET /api/v1/analytics/kpi/history?days=30` — time-series of daily snapshots.
    *   Implement `routers/customers.py`:
        *   `GET /api/v1/customers` — paginated list with filters (segment, region, LTV range).
        *   `GET /api/v1/customers/{id}` — full profile with order history.
    *   Implement `routers/products.py`:
        *   `GET /api/v1/products` — paginated list with filters (category, ABC tier, stock status).
    *   Implement `routers/forecasts.py`:
        *   `GET /api/v1/forecasts/latest` — most recent Prophet run.
        *   `POST /api/v1/forecasts/scenario` — trigger new forecast with scenario params.
    *   Implement `routers/jobs.py`:
        *   `GET /api/v1/jobs/{id}/status` — poll upload pipeline progress.
    *   All list endpoints must support pagination (`?page=1&per_page=20`), sorting, and filtering.
    *   Add `Cache-Control` and `ETag` headers for HTTP-level caching.

*   [ ] **Step 14: Frontend Foundation — Install Dependencies & Create Structure**
    *   Install missing packages: `recharts`, `zustand`, `axios` (or `swr`), `react-hook-form`, `lucide-react`, `posthog-js`, `react-grid-layout`.
    *   Create directory structure under `next-scaffold/src/`:
        ```
        src/
        ├── app/           # App Router pages (layout, page, loading, error)
        ├── components/    # Reusable UI (Button, Card, Input, Modal, Table, Chart wrappers)
        ├── lib/           # API client (axios instance), auth helpers, constants
        ├── stores/        # Zustand stores (authStore, dashboardStore, uploadStore)
        ├── hooks/         # Custom hooks (useAuth, useAnalytics, useUpload)
        └── types/         # TypeScript interfaces matching backend Pydantic schemas
        ```
    *   Update `layout.tsx` metadata: title → "InsightX — AI Analytics Platform".
    *   Create `lib/api.ts` — Axios instance with `NEXT_PUBLIC_API_URL` base, JWT interceptor, error handler.
    *   Create `stores/authStore.ts` — Zustand store for JWT token, user profile, login/logout actions.

*   [ ] **Step 15: Landing Page & Auth Pages**
    *   Build `/` landing page from `stitch_insightx/insightx_landing_page_1` mockup — hero section, feature cards, glassmorphism nav, CTA buttons.
    *   Build `/login` from `stitch_insightx/insightx_login_page_1` mockup — dark card, email + password with visibility toggle.
    *   Build `/signup` from `stitch_insightx/insightx_sign_up_page_1` mockup — 4 fields (email, password, confirm, company).
    *   **Secret Feature:** Implement `ESC` keydown listener on `/login` that slides out the secret Admin Login Panel (calls `/auth/admin/login` with `admin_key` handshake).
    *   Implement protected route middleware — redirect unauthenticated users to `/login`.

*   [ ] **Step 16: The Dashboard UI Shell**
    *   Build authenticated layout from `stitch_insightx/insightx_dashboard_home_1` mockup:
        *   256px sidebar with navigation links (Home, Product, Customer, Analytics, Forecasting, Segmentation, Settings).
        *   Frosted glass top navbar with notification bell + user avatar.
        *   Mobile-responsive: collapsible sidebar on `< md` breakpoints.
    *   Build `/dashboard` home page — 3 KPI cards (Revenue, Active Customers, Churn Rate) + Sales Trend line chart + Revenue by Region bar chart.
    *   Implement WebSocket listener for real-time `job_complete` events → auto-refresh dashboard data.

*   [ ] **Step 17: Data Pages — Products, Customers, Analytics**
    *   Build `/dashboard/products` from `stitch_insightx/insightx_product_inventory_1` mockup — data table with search, filters (category, status), ABC tier badges, pagination.
    *   Build `/dashboard/customers` from `stitch_insightx/insightx_customer_profiles_1` mockup — sortable table with LTV, AI segment badges (VIP Champion, Loyalist, At-Risk, New Potential, Undetermined), import/export buttons.
    *   Build `/dashboard/customers/segmentation` from `stitch_insightx/insightx_customer_segmentation_1` mockup — 3D bubble chart (Champions/Loyal/At-Risk clusters), ARR metrics sidebar, date/metric/region filters.

*   [ ] **Step 18: Forecasting & Analytics Editor**
    *   Build `/dashboard/forecasting` from `stitch_insightx/insightx_forecasting_module_1` mockup:
        *   SVG line chart: historical (solid blue) + forecast (dashed purple) + 95% confidence band.
        *   "Today" vertical marker separating actual vs predicted.
        *   Bottom panel: 3 scenario sliders — Marketing Spend (+0% to +50%), Price Shift (-10% to +20%), Seasonal Adjustment (Low/Medium/High).
        *   Sliders trigger `POST /forecasts/scenario` and re-render chart.
    *   Build `/dashboard/analytics/edit` from `stitch_insightx/insightx_analytics_edit_mode_1` mockup:
        *   Widget library sidebar with search + accordion categories (Sales, Profit, Inventory, Customer).
        *   12-column grid canvas with drag-and-drop widgets.
        *   Widget controls: drag handle, edit, close, resize.
        *   Save/Cancel/Reset toolbar.

*   [ ] **Step 19: User Profile & Widget Grid**
    *   Implement `react-grid-layout` on the dashboard home page.
    *   Allow users to drag, resize, and reorder dashboard widgets.
    *   Save layout coordinates to `users.widget_config` JSONB column via `PATCH /auth/me`.
    *   Load saved layout on login; fall back to default grid if no config.

*   [ ] **Step 20: CSV Upload UI & Progress**
    *   Build upload modal/page — drag-and-drop CSV file zone, file validation (`.csv`, < 50MB).
    *   Show real-time pipeline progress: poll `GET /jobs/{id}/status` every 2 seconds.
    *   Display progress bar with stage labels: Uploading → Mapping → Validating → Inserting → Analyzing → Complete.
    *   Show column mapping preview table (csv_header → mapped_column, match_score, confidence badge).
    *   On completion, auto-navigate to dashboard with refreshed data.

---

### PHASE 5: Polish, Scheduling & Deployment

*   [ ] **Step 21: Error Handling & Graceful Degradation**
    *   Celery failure states update `upload_jobs.status` to `"failed"` with `error_message`.
    *   Push WebSocket error events to frontend → show toast notification with failure reason.
    *   Add React error boundaries on all dashboard pages — show friendly fallback UI.
    *   Add loading skeletons for all data-fetching components.
    *   Handle API 401 responses globally — clear auth store, redirect to `/login`.

*   [ ] **Step 22: Testing & Quality**
    *   Migrate existing test scripts to `pytest` framework with fixtures and proper assertions.
    *   Add unit tests for all 22 analytics modules (mock data in, expected JSONB out).
    *   Add frontend tests: Jest + React Testing Library for key components.
    *   Add E2E test: upload CSV → verify all 22 analytics cached → verify dashboard renders.
    *   Configure CI/CD to run `pytest` and block merge on failure.

*   [ ] **Step 23: Celery Beat Nightly Cron**
    *   Setup a nightly task at 00:05 UTC to freeze `daily_kpi_snapshots` from orders table.
    *   Add stale cache detection: mark `analysis_results_cache.is_stale = True` for entries older than 24 hours.

*   [ ] **Step 24: Production Launch**
    *   Create `docker-compose.prod.yml` with production configs:
        *   Remove `--reload` from uvicorn CMD.
        *   Set `APP_ENV=production`, disable SQL echo.
        *   Add `USER` directives to all Dockerfiles (don't run as root).
        *   Add `HEALTHCHECK` instructions to all containers.
        *   Configure Nginx reverse proxy with HTTPS (Let's Encrypt) and WebSocket proxying.
    *   Deploy to target platforms:
        *   Frontend → Vercel (or Nginx).
        *   Backend + Worker → Render / Railway (or EC2).
        *   Database → Neon.tech / Supabase (free PostgreSQL).
        *   Cache → Upstash Redis.
    *   E2E stress test with 50,000-row dataset — target sub-3-second API responses via `analysis_results_cache` design.
    *   Verify all `.env` secrets are injected via platform env vars (never committed).

---

## 4. Known Technical Debt (Post-Launch)

| Item | Priority | Notes |
|------|----------|-------|
| Migrate file storage from local disk to S3 | High | `boto3` installed but unused; `s3_key` stores local filename |
| Add refresh token rotation | Medium | Currently access tokens only (60 min expiry, no refresh) |
| Replace string enums with Python Enum types | Low | Role, status, segment fields are all strings |
| Add Sentry / structured logging | Medium | No error aggregation or request tracing |
| Add PostHog analytics to frontend | Low | `NEXT_PUBLIC_POSTHOG_KEY` configured but unused |
| Async SQLAlchemy (`asyncpg`) | Low | Currently sync engine; async would improve throughput |
| Add email service for password resets | High | Currently returns token in response (dev shortcut) |
| Compute `net_amount` / `line_total` as generated columns | Low | Currently stored redundantly, can drift |

---

## 5. UI Mockup Reference (9 Screens in `stitch_insightx/`)

| Screen | Mockup Path | Target Route |
|--------|------------|-------------|
| Landing Page | `insightx_landing_page_1/code.html` | `/` |
| Login | `insightx_login_page_1/code.html` | `/login` |
| Sign Up | `insightx_sign_up_page_1/code.html` | `/signup` |
| Dashboard Home | `insightx_dashboard_home_1/code.html` | `/dashboard` |
| Product Inventory | `insightx_product_inventory_1/code.html` | `/dashboard/products` |
| Customer Profiles | `insightx_customer_profiles_1/code.html` | `/dashboard/customers` |
| Customer Segmentation | `insightx_customer_segmentation_1/code.html` | `/dashboard/customers/segmentation` |
| Analytics Edit Mode | `insightx_analytics_edit_mode_1/code.html` | `/dashboard/analytics/edit` |
| Forecasting Module | `insightx_forecasting_module_1/code.html` | `/dashboard/forecasting` |

**Design System:** Dark-first, Inter font, Material Symbols icons, glassmorphism panels, blue primary (`#137fec`), emerald/amber/red semantic colors.
