# Internship Application Tracker

A backend-only internship application tracking system that replaces spreadsheet-based tracking with an enforced application pipeline, deadline reminders, secure authentication, analytics, and background processing.

## Features

- **Application lifecycle:** Wishlist → Applied → OA → Interview → Offer → Accepted / Declined
- **Finite State Machine:** Prevents invalid status transitions.
- **Status history:** Audits every application status change.
- **Deadline intelligence:** Automatically detects upcoming deadlines and generates reminders.
- **Authentication:** JWT access/refresh tokens with refresh-token rotation.
- **User isolation:** Users can only access their own applications.
- **Dashboard:** Application counts, conversion rates, and upcoming deadlines.
- **Redis caching:** Cache-aside dashboard caching with TTL fallback.
- **Background jobs:** Celery + Celery Beat for deadline processing.
- **Testing & CI:** pytest, async integration tests, and GitHub Actions.
- **Deployment:** Docker Compose; designed for Railway or Render.

## Tech Stack

**FastAPI · Python · PostgreSQL · SQLAlchemy · Pydantic · Redis · Celery · JWT · Alembic · pytest · Docker · GitHub Actions**

## Architecture

```text
Client
  │
  ▼
FastAPI ───────► PostgreSQL
  │
  └────────────► Redis
                   │
              ┌────┴────┐
              ▼         ▼
         Celery Beat  Celery Worker
```

## Project Structure

```text
app/
├── core/          # Configuration & security
├── models/        # Database models
├── schemas/       # Pydantic schemas
├── routers/       # API endpoints
├── services/      # Business logic & FSM
├── tasks/         # Celery tasks
└── db/            # Database configuration

tests/
alembic/
.github/workflows/
compose.yaml
Dockerfile
.env.example
```

## API

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`

### Applications
- `POST /applications`
- `GET /applications`
- `GET /applications/{id}`
- `PATCH /applications/{id}`
- `PATCH /applications/{id}/status`
- `DELETE /applications/{id}`

### Dashboard
- `GET /dashboard/summary`
- `GET /dashboard/upcoming`

### Companies
- `GET /companies`
- `POST /companies`

## Run Locally

```bash
git clone <repository-url>
cd internship-application-tracker

python -m venv .venv
pip install -r requirements.txt

cp .env.example .env
alembic upgrade head

uvicorn app.main:app --reload
```

Or run the complete stack with Docker:

```bash
docker compose up --build
```

Run tests:

```bash
pytest
```

## Why This Project?

The goal is to demonstrate backend engineering beyond CRUD through **state-machine design, asynchronous database access, caching, background jobs, authentication security, testing, CI, and deployment**.

> API-only project — no frontend planned.
