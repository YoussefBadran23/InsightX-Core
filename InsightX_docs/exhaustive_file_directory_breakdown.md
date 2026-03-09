# InsightX Exhaustive File & Directory Breakdown

This document provides a highly granular, file-by-file explanation of every component residing in the `c:\work\InsightX` directory.

---

## 📁 `c:\work\InsightX` (Root Directory)
This is the main workspace directory. 

*   📄 **`master_implementation_plan_v3.md.resolved`**: The project's ultimate roadmap and source of truth outlining the 5-phase execution plan.
*   📄 **`database_schema_review.md.resolved`**: Detailed DB architecture document mapping out the 9-table schema, indexing, and business rules.
*   📄 **`InsightX_Graduation_Project_Documentation_2025_v2.pdf`** & **`InsightX_v3_Schema_Analytics_Pipeline.pdf`**: Original project requirements and documentation.
*   📄 **`pass db.txt`** & **`insightx-key.pem`**: Local development credentials and SSH keys for the AWS infrastructure.
*   📁 **`stitch_insightx/`**: Contains the raw HTML/CSS/Asset exports of the 9 UI screens (Login, Dashboard, Profiles, Forecasting, etc.). These are the static templates used as reference to build the dynamic Next.js React components.
*   📁 **`InsightX-Core/`**: The actual living codebase where all active development happens.

---

## 📁 `InsightX-Core/` (The Application Monorepo)

### ⚙️ Root Configuration Files
*   📄 **`docker-compose.yml`**: The orchestrator. Defines the 5 containers (PostgreSQL, Redis, FastAPI Backend, Celery Worker, Next.js Frontend) and connects them via a virtual Docker network.
*   📄 **`README.md`**: High-level developer setup guide.
*   📄 **`.gitignore`**: Tells Git to ignore sensitive files (like `.env`) and heavy dependencies (`node_modules`, `__pycache__`).
*   📄 **`test_phase_1.ps1`** & **`test_phase_1.sh`**: Automation scripts to verify that Docker containers are healthy and communicating (for Windows and Linux).

---

### 🌐 1. `backend/` (FastAPI Server)
This is the synchronous API engine. It handles HTTP requests, authentication, and database queries. 

*   📄 **`Dockerfile` & `.dockerignore`**: Instructions to build the Python 3.10+ image and ignore clutter during the build.
*   📄 **`requirements.txt`**: Lists Python dependencies (`fastapi`, `sqlalchemy`, `alembic`, `psycopg2`, `passlib`, `jose`).
*   📄 **`.env` & `.env.example`**: Environment variables holding secrets (e.g., `DATABASE_URL`, JWT `SECRET_KEY`, `ADMIN_SECRET_KEY`).
*   📄 **`alembic.ini`**: Main configuration file for Alembic, pointing it to the PostgreSQL database URL.
*   📄 **`test_db_step5.py`, `test_auth_step7.py`, `test_final.py`**: Automated test scripts used to verify that the database connection and authentication endpoints work perfectly.
*   📄 **`verify_aws.py`**: Script to verify connection payloads against the AWS RDS instance.

#### 📂 `backend/alembic/` (Database Migrations)
Manages database schema changes over time without destroying existing data.
*   📄 **`env.py`**: Tells Alembic how to connect to the database and where to find our Python SQLAlchemy models to auto-generate SQL diffs.

#### 📂 `backend/app/` (The Core Backend Logic)
*   📄 **`main.py`**: The entry point. Initializes the FastAPI app, configures CORS (so the frontend can talk to it), and mounts the routers.
*   📄 **`database.py`**: Creates the `SessionLocal` class and SQLAlchemy `engine`. Manages the physical connection pool to PostgreSQL.
*   📄 **`dependencies.py`**: Contains reusable functions injected into endpoints. E.g., `get_current_user(...)` intercepts the JWT token in requests, validates it, and fetches the User from the DB.

**📂 `backend/app/core/` (Security & config)**
*   📄 **`config.py`**: Uses Pydantic to read `.env` variables and make them accessible safely throughout the app (`settings.DATABASE_URL`).
*   📄 **`security.py`**: Contains the cryptographic functions: `hash_password()`, `verify_password()`, and `create_access_token()` using `python-jose` for JWTs.

**📂 `backend/app/models/` (SQLAlchemy DB Schemas)**
Translates Python classes into the 9 physical PostgreSQL tables.
*   📄 **`base.py`**: The `Base` class that all models inherit from.
*   📄 **`user.py`**: The `users` table (auth, roles, workspace layouts).
*   📄 **`customer.py`**: The `customers` table (LTV, engagement scores, regional data).
*   📄 **`product.py`**: The `products` table (inventory, pricing, ABC tiers).
*   📄 **`order.py`**: The `orders` fact table (revenue, sentiment labels).
*   📄 **`order_item.py`**: Junction table linking orders to multiple products.
*   📄 **`upload_job.py`**: Tracks CSV upload progress (`rows_processed`, `status`).
*   📄 **`forecast_result.py`**: Stores Prophet ML predictions (`yhat`, confidence bands, scenario parameters).
*   📄 **`daily_kpi_snapshot.py`**: Pre-aggregated nightly metrics (+12% revenue) for instant dashboard loading.
*   📄 **`insight.py`**: Stores the LLM-generated NLP summary bullets.
*   📄 **`csv_column_mapping.py`**: Tracks which raw CSV headers map to which DB columns.
*   📄 **`analysis_results_cache.py`**: Rapid JSONB storage for complex query outputs.

**📂 `backend/app/routers/` (API Endpoints)**
*   📄 **`auth.py`**: Contains `POST /auth/register`, `POST /auth/login`, `POST /auth/admin/login`, and `/me`.

**📂 `backend/app/schemas/` (Pydantic Validators)**
*   📄 **`auth.py`**: Defines strict incoming data structures. e.g., `LoginRequest` forces the client to send a valid `email` and `password` string. Prevents bad data from hitting the database.

---

### 🧠 2. `worker/` (Celery Async AI Engine)
Handles CPU-heavy tasks asynchronously so the FastAPI backend never freezes.

*   📄 **`Dockerfile` & `.dockerignore`**: Builds the heavy worker image containing ML libraries.
*   📄 **`requirements.txt`**: Includes `celery`, `redis`, `pandas`, `scikit-learn`, `prophet`.
*   📄 **`celery_app.py`**: Initializes the Celery worker and connects it to the Redis message broker (`CELERY_BROKER_URL`).

#### 📂 `worker/tasks/` (The AI Jobs)
These scripts listen for messages on Redis queues and execute autonomously.
*   📄 **`preprocess.py`**: Downloads CSVs from AWS S3, cleans the data using `pandas`, coerces types, and bulk-inserts rows into PostgreSQL while updating `upload_jobs`.
*   📄 **`ml.py`**: Contains compute-heavy machine learning workflows (e.g., Prophet Forecasting, K-Means clustering for customer segmentation).
*   📄 **`sentiment.py`**: Takes raw customer comments from new orders and runs them through a BERT model to output POSITIVE/NEGATIVE labels.
*   📄 **`insights.py`**: Takes the mathematical outputs of other tasks and sends them to Groq LLaMA 3 to generate 3 plain-English business insights.

---

### 💻 3. `next-scaffold/` (Next.js Application)
This is the actual user interface the client interacts with, built using React and Next.js (App Router).

*   📄 **`package.json`**: Lists Node.js dependencies (`react`, `next`, `tailwindcss`, `lucide-react`, `recharts`, `zustand`).
*   📄 **`tailwind.config.ts` & `postcss.config.mjs`**: Configuration for the Tailwind CSS styling framework to ensure brand colors and layout utilities work.
*   📄 **`tsconfig.json` & `next-env.d.ts`**: Typescript configuration enforcing strict type safety across the frontend.
*   📄 **`next.config.mjs`**: Next.js build and routing configuration.

#### 📂 `next-scaffold/src/` (UI Source Code)
*   **📂 `app/`**: Uses App Router for actual web pages.
    *   📄 **`layout.tsx`**: The global HTML shell. Wraps all pages in necessary context providers.
    *   📄 **`page.tsx`**: The root landing page.
    *   📄 **`globals.css`**: Global CSS injections and Tailwind base layers.
    *   📂 **`fonts/`**: Local typography files.

*(Note: In Phase 4, we will populate `src/components` with reusable UI buttons/charts, and `src/lib` with API fetching functions).*

---

### 🐳 4. `frontend/` (Docker Wrapper)
A lightweight wrapper used alongside Docker-Compose to containerize the `next-scaffold` code.

*   📄 **`Dockerfile`**: Triggers `npm install` and `npm run dev` for the Next.js app inside a secure container.
*   📄 **`.env.local`**: Holds the `NEXT_PUBLIC_API_URL` pointing the UI to our FastAPI backend (`localhost:8000`).

---

### ☁️ 5. `infrastructure/` 
Reserved for IaC (Infrastructure as Code) scripts. Currently contains Terraform or script stubs used to automatically provision our AWS resources (like the RDS database and S3 buckets).
