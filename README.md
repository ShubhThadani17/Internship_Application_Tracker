# Internship Application Tracker with Deadline Intelligence

A backend-focused internship application tracker built to go beyond a plain CRUD tracker: a finite-state-machine-driven status pipeline, automated deadline reminders, LLM-assisted email parsing with human confirmation, and precomputed analytics.

## Why this project exists

Most "application tracker" projects are a database table with a form in front of it. This project intentionally goes further in a few specific directions:

- A real finite-state machine governs status transitions, so an application cannot jump from `APPLIED` straight to `OFFER`.
- A background job pipeline (Celery) handles time-based work — deadline reminders — that has no natural place inside a request/response cycle.
- An LLM (Google Gemini, free tier) is used narrowly: to extract structured data from unstructured email text, with a human confirmation step before anything is written to the database, never as an autonomous writer.
- Analytics are precomputed and event-triggered rather than calculated live on every request, using SQL window functions rather than in-Python loops.

## Tech stack

- **Language / Framework:** Python, FastAPI (async)
- **Database:** PostgreSQL, SQLAlchemy (async ORM for the API, sync ORM for background tasks), Alembic for migrations
- **Auth:** JWT access tokens + Redis-backed refresh tokens, bcrypt password hashing
- **Background jobs:** Celery (worker + Beat), Redis as broker
- **Email:** Brevo HTTPS API (not SMTP — see Design Decisions)
- **LLM:** Google Gemini (Flash), free tier, structured JSON output mode
- **Testing:** Pytest, pytest-asyncio, transaction-rollback test isolation
- **Containerization:** Docker Compose (local development)

## Architecture overview

```
                     ┌────────────────────┐
                     │   FastAPI (async)   │
                     │  — CRUD, auth,      │
                     │  status FSM,        │
                     │  parse/confirm,     │
                     │  analytics read     │
                     └─────────┬───────────┘
                               │
                 ┌─────────────┼─────────────┐
                 ▼                           ▼
          PostgreSQL (async)           Redis (refresh tokens,
                                          Celery broker)
                 ▲                           │
                 │                           ▼
          PostgreSQL (sync) ◄──── Celery worker + Beat (combined)
                                   — deadline scan (every 12h)
                                   — email notifications (Brevo)
                                   — analytics recompute (event-triggered)
```

FastAPI and Celery each maintain their **own** database engine — async for the API, sync for background tasks — because Celery's execution model has no event loop, and reusing an async engine across Celery's process model causes event-loop-binding errors with asyncpg. This is a deliberate architectural boundary, not an oversight.

## Core domain model

- **User** — auth identity.
- **Application** — company, role, current status, deadline, deadline_notified flag.
- **StatusHistory** — an append-only log of every status transition, used both as an audit trail and as the source data for analytics (average time per status, conversion rates).

### Status FSM

Applications move through a finite state machine (`APPLIED → OA1 → OA2 → INTERVIEW → OFFER`, with `REJECTED`, `WITHDRAWN`, and `GHOSTED` reachable as terminal branches from most stages). Invalid transitions are rejected at the repository layer, not just the API layer, so no code path can force an invalid state.

## What's been built

**Authentication and core tracking**
User registration and login with JWT access tokens and Redis-backed refresh tokens, bcrypt password hashing. Full CRUD for applications, scoped so a user can only ever see or modify their own data. Status changes are validated through the FSM and every transition is recorded in an append-only `StatusHistory` log, which later becomes the raw data analytics is computed from.

**Deadline reminders**
Each application can carry a `deadline` and a `deadline_notified` flag. A Celery Beat job runs every 12 hours, finds applications with a deadline in the next 48 hours that haven't been notified yet, and sends a reminder email through Brevo's HTTPS API, with automatic retry (up to 3 attempts) on transient failures. Moving an application to a terminal status (`REJECTED` / `WITHDRAWN` / `GHOSTED`) automatically clears its deadline, since it's no longer relevant.

**LLM-assisted email parsing**
`POST /parse-email` accepts raw email text and calls Gemini with a structured JSON schema to extract company name, role, stage, and deadline — read-only, nothing is written to the database at this step. If a matching application already exists (case-insensitive company match), the extracted stage is disambiguated against that application's current status (for example, "OA" appearing a second time is inferred to mean OA2, not OA1). If no match exists, the response is a "new application" suggestion instead, since a cold interview invite may be the first record of a company you ever get. `POST /confirm-parsed-application` takes the (optionally user-edited) suggestion and performs the actual write, reusing the same FSM-validated code path as the manual API rather than a shortcut. The deadline is never auto-converted from the LLM's raw text into a real datetime — a human must supply an explicit, unambiguous datetime at confirmation time.

**Analytics**
Five metrics are computed: funnel counts per status, conversion rate between consecutive stages, average time spent per status, ghosting rate, and response rate by company — all computed with SQL aggregates and window functions (`LAG` for time-per-status) rather than Python loops. The result is stored as a single overwritten JSON snapshot and recomputed automatically via a Celery task fired right after any status change, so the numbers are always fresh without being recalculated on every read.

## Key design decisions (and why)

- **Sync SQLAlchemy session for Celery tasks, kept separate from the async engine.** Celery's prefork worker model and asyncpg's event-loop-bound connection pooling don't mix safely; a sync engine avoids the entire bug class rather than working around it.
- **Combined worker + Beat process (`celery worker -B`) instead of two separate processes.** A deliberate simplification for lightweight, single-worker deployment. The known tradeoff (a crash loses both scheduling and execution at once) is accepted given the low task volume here.
- **Deadline notification uses "mark-then-send," not "send-then-mark."** `deadline_notified` is set to `True` the moment a notification is queued, before the email actually sends. A notification that fails all its retries is never automatically retried on the next scan — a known, accepted gap, chosen because the alternative is more fragile against connection drops and cold starts.
- **Brevo's HTTPS API instead of SMTP.** Many hosting platforms block outbound SMTP on port 587; an HTTPS API sidesteps the restriction entirely.
- **LLM output is a suggestion, never a direct write.** Every LLM-derived field, especially the deadline, requires explicit human confirmation before touching the database. The backend does not rely on a frontend to enforce this — the confirm endpoint independently re-validates ownership and re-runs the FSM transition check, exactly as the manual PATCH endpoint does, so it stays safe even if called directly.
- **Conversion rate = "ever reached this stage," not "resolved outcome from this stage."** Given the FSM allows branching (e.g. `OA1 → REJECTED` directly), conversion rate is defined as the simpler, more standard funnel metric: of all applications that ever reached stage X, what percentage also reached stage Y — regardless of what happened afterward.
- **Analytics stored as a single overwritten JSON row, not a time-series table.** No historical analytics-of-analytics is needed for a personal tracker; simplicity won over generality here.

## Known limitations (deliberate, not oversights)

- Single-user by design. The notification path sends to one fixed configured email address rather than looking up a per-user recipient; multi-user support was consciously deferred since retrofitting it later is cheaper than half-supporting it now.
- A notification that exhausts all retries is not automatically retried on a later scan, per the mark-then-send tradeoff above.
- Company name matching is exact-match-after-lowercasing, not fuzzy. "Google" and "google" merge correctly; "Google" and "Google Inc." do not.
- The test suite shares its database with the local development database rather than a fully isolated test database. Tests that aggregate across an entire table (analytics, deadline scanning) are written to assert deltas or the presence/absence of a specific known row, not absolute counts, to remain correct regardless of leftover manual-testing data.

## Local development setup

```bash
git clone <repo-url>
cd Internship_Tracker

# start Postgres and Redis
docker compose up -d

# create and activate a virtual environment, then
pip install -r requirements.txt

# copy and fill in environment variables (see below)
cp .env.example .env

# run migrations
alembic upgrade head

# run the API
uvicorn app.main:app --reload

# run the background worker + scheduler (Linux/macOS)
celery -A app.core.celery_app worker -B --loglevel=info

# on Windows, -B is unsupported; run as two processes instead:
celery -A app.core.celery_app worker --loglevel=info --pool=solo
celery -A app.core.celery_app beat --loglevel=info
```

Run tests with:
```bash
pytest tests/
```

## Required environment variables

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/internship_tracker
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=
REFRESH_TOKEN_EXPIRE_DAYS=
BREVO_API_KEY=
FROM_EMAIL=          # must be a verified sender in your Brevo account
NOTIFY_EMAIL=        # recipient for deadline reminder emails
GEMINI_API_KEY=
```

## API surface (high level)

- `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`
- `POST /applications`, `GET /applications`, `GET /applications/{id}`, `PATCH /applications/{id}`, `PATCH /applications/{id}/status`
- `POST /parse-email`, `POST /confirm-parsed-application`
- `GET /analytics`