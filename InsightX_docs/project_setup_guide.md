# InsightX Local Setup & Deployment Guide

This guide provides step-by-step instructions on how to clone the InsightX repository from GitHub and get the entire system running on a brand-new PC or laptop.

## 1. Prerequisites (Technologies to Install)

Before cloning the repository, ensure the following software is installed on your machine. The local development environment strictly relies on Docker to minimize native dependencies.

1.  **Git:**
    *   Required for cloning the repository.
    *   [Download Git](https://git-scm.com/downloads)
2.  **Docker Desktop:**
    *   **CRUCIAL:** The entire application (PostgreSQL, Redis, FastAPI backend, Next.js frontend) runs inside Docker containers.
    *   [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
    *   *Note for Windows users:* Ensure WSL2 (Windows Subsystem for Linux) integration is enabled in Docker settings for optimal performance.
3.  **Python 3.10+ (Optional but Recommended):**
    *   Used for running local verification scripts (like [test_phase_1.ps1](file:///c:/work/InsightX/InsightX-Core/test_phase_1.ps1), [test_db_step5.py](file:///c:/work/InsightX/InsightX-Core/backend/test_db_step5.py), etc.) without needing to jump into the container.
    *   [Download Python](https://www.python.org/downloads/)
    *   If installed, also install `pip install requests` and `pip install pytest`.

## 2. Cloning the Repository

Open a terminal (Command Prompt, PowerShell, or Git Bash) and execute the following commands:

```bash
# 1. Clone the repository (replace with your actual GitHub repo URL)
git clone https://github.com/YoussefBadran/InsightX.git

# 2. Navigate into the core project directory
cd InsightX/InsightX-Core
```

## 3. Environment Variables Configuration

The [.env](file:///c:/work/InsightX/InsightX-Core/worker/.env) files are already included in the repository for local development convenience (normally they would be [.env.example](file:///c:/work/InsightX/InsightX-Core/worker/.env.example)).

Verify the primary backend [.env](file:///c:/work/InsightX/InsightX-Core/worker/.env) file exists at [InsightX-Core/backend/.env](file:///c:/work/InsightX/InsightX-Core/backend/.env). It should contain the database credentials and the JWT secret:

```env
DATABASE_URL=postgresql://insightx_user:insightx_pass@db:5432/insightx_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=youssef_insightx_super_secret_jwt_key_2026_dev
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ADMIN_SECRET_KEY=98b4461-secret-admin-handshake
```

## 4. Starting the Application (Docker Compose)

InsightX uses Docker Compose to orchestrate all microservices simultaneously.

```bash
# Make sure Docker Desktop is currently running on your PC.

# Build and start all services in detached mode
docker-compose up --build -d
```

**What this command does:**
1.  Pulls the official `postgres:16-alpine` and `redis:7-alpine` images.
2.  Builds the `insightx_backend` image using [backend/Dockerfile](file:///c:/work/InsightX/InsightX-Core/backend/Dockerfile) and installs all AI/ML Python requirements.
3.  Builds the `insightx_frontend` Next.js image (Note: The frontend code lives in `next-scaffold/`).
4.  Starts all containers and wires them together via an internal bridge network.

## 5. Running Database Migrations (One-Time Setup)

Once the containers are spinning, you must tell the backend to construct the 11 database tables via Alembic migrations.

```bash
# Execute the Alembic upgrade command inside the backend container
docker exec insightx_backend alembic upgrade head
```

You should see output indicating that all revisions (up to the current head, `cd7f4376ca5f`) have been successfully applied.

## 6. Accessing the Application

With everything running, you can now access the system locally:

1.  **Backend API Documentation (Swagger UI):**
    *   URL: [http://localhost:8000/docs](http://localhost:8000/docs)
    *   Use this to test the `/api/v1/auth/register` and `/api/v1/auth/login` endpoints directly from your browser.
2.  **Frontend Dashboard:**
    *   URL: [http://localhost:3000](http://localhost:3000)
    *   *(Note: The frontend UI components are slated for Phase 4, but the Next.js server handles requests right now).*
3.  **Database Access (if needed):**
    *   Host: `localhost`
    *   Port: `5432`
    *   Username: `insightx_user`
    *   Password: `insightx_pass`
    *   Database: `insightx_db`

## 7. Verifying the Installation

To prove the system is fully operational on your new PC, run the automated verification suites:

```bash
# 1. Test Database Integrity
docker exec insightx_backend python test_db_step5.py

# 2. Test the Authentication Flow
docker exec insightx_backend python test_auth_step7.py

# 3. Test Full Backend Architecture
docker exec insightx_backend python test_final.py
```

If all three scripts output `ALL PASS`, the clone was 100% successful!

## 8. Stopping the Application

To shut down the application without losing your database data:

```bash
docker-compose stop
```

To completely destroy the containers and wipe the database volumes clean (starting fresh):

```bash
docker-compose down -v
```
