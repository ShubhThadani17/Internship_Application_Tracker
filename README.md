# Internship Application Tracker with Deadline Intelligence

A backend-first internship application tracking system designed to replace spreadsheet-based tracking with an enforced application pipeline, automated deadline intelligence, secure authentication, analytics, and background job processing.

> **Project type:** API-only backend  
> **Target:** Software Development Engineer internship portfolio project  
> **Status:** Planned / In development

## Overview

The system tracks internship applications through a real finite state machine:

`Wishlist → Applied → OA → Interview → Offer → Accepted / Declined`

with terminal outcomes such as `Rejected` and `Withdrawn`.

A background processing layer continuously checks upcoming deadlines and generates reminders automatically, removing the need for users to manually monitor every application.

The project is deliberately designed to demonstrate backend engineering depth in:

- Asynchronous database access with SQLAlchemy
- FastAPI
- Pydantic validation and serialization
- PostgreSQL
- Redis caching and token management
- Celery workers and Celery Beat
- JWT authentication with refresh-token rotation
- Finite state machine design
- Automated testing
- Docker and Docker Compose
- Continuous Integration with GitHub Actions
- Production deployment

## Problem

Once a student is tracking 30–40 internship applications, a spreadsheet becomes difficult to maintain.

Typical problems include:

- Statuses can be changed to logically impossible values.
- Deadlines are easy to miss because they require manual checking.
- There is little visibility into where the application funnel is succeeding or failing.
- There is no reliable historical record of status changes.
- Authentication and access control are generally absent from spreadsheet-based workflows.

This project addresses these problems through an enforced backend pipeline and automated background processing.

## Core Features

### Application Lifecycle

- Create internship application records.
- Associate applications with companies and roles.
- Maintain exactly one current status per application.
- Validate status changes against a finite state machine.
- Reject invalid transitions.
- Record every status transition with a timestamp.
- Support multiple interview rounds without creating unlimited FSM states.

### Deadline Intelligence

- Store application or action deadlines.
- Periodically scan for upcoming deadlines.
- Generate reminders when deadlines enter the configured reminder window.
- Prevent duplicate reminders for the same application and threshold.
- Rank upcoming deadlines by urgency.
- Optionally identify stale applications that have remained in the `Applied` state for an extended period.

### Authentication & Security

- User registration with email and password.
- Password hashing using Argon2 or bcrypt.
- Short-lived JWT access tokens.
- Longer-lived refresh tokens.
- Refresh-token rotation on every refresh.
- Immediate invalidation of the previous refresh token.
- Redis-backed active refresh-token tracking.
- Logout invalidates the current refresh token.
- Users can access only their own applications.

### Dashboard & Analytics

- Application counts by status.
- Stage conversion rates.
- Upcoming deadline ranking.
- Redis caching for dashboard summaries.
- Cache invalidation after changes affecting dashboard counts.

### Company Management

Companies are represented as a separate entity rather than duplicated as free text.

This avoids duplicate or misspelled company names and allows future aggregate analytics such as response-time analysis.

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| Language | Python |
| Validation / Serialization | Pydantic |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Async DB Driver | asyncpg |
| Cache | Redis |
| Authentication | JWT |
| Password Hashing | Argon2 / bcrypt |
| Background Jobs | Celery |
| Scheduler | Celery Beat |
| Containerization | Docker / Docker Compose |
| Migrations | Alembic |
| Testing | pytest |
| Async API Testing | Async test client |
| CI | GitHub Actions |
| Deployment | Railway or Render |

## Architecture

The application is composed of five services:

```text
                         ┌─────────────────────┐
                         │       Client        │
                         │  API Documentation  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │       FastAPI       │
                         │   Async API Layer   │
                         └──────┬────────┬─────┘
                                │        │
                    ┌───────────┘        └───────────┐
                    ▼                                ▼
          ┌─────────────────┐              ┌─────────────────┐
          │   PostgreSQL    │              │      Redis      │
          │ Persistent Data │              │ Cache + Tokens  │
          └─────────────────┘              │ Celery Broker   │
                                           └────────┬────────┘
                                                    │
                                      ┌─────────────┴─────────────┐
                                      ▼                           ▼
                              ┌───────────────┐           ┌───────────────┐
                              │  Celery Beat  │           │ Celery Worker │
                              │   Scheduler   │           │ Task Executor │
                              └───────┬───────┘           └───────┬───────┘
                                      │                             │
                                      └──────────► Redis ◄──────────┘
                                                                    │
                                                                    ▼
                                                              PostgreSQL
```

### Request Flow

1. A client sends a request to FastAPI.
2. FastAPI validates the request through Pydantic.
3. Persistent data is read or written asynchronously through SQLAlchemy.
4. Redis handles caching and refresh-token validation where required.
5. The API returns the validated response.

### Background Flow

1. Celery Beat wakes on its configured schedule.
2. It places a task onto the Redis-backed queue.
3. A Celery Worker consumes the task.
4. The worker performs the required processing.
5. Results and notification records are written to PostgreSQL.

Celery Beat is used as the scheduler; APScheduler is intentionally not included because a second scheduler would be redundant for this queue-based architecture.

## Repository Structure

```text
.
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── company.py
│   │   ├── application.py
│   │   ├── status_history.py
│   │   └── notification.py
│   │
│   ├── schemas/
│   │   ├── user.py
│   │   ├── application.py
│   │   └── auth.py
│   │
│   ├── routers/
│   │   ├── auth.py
│   │   ├── applications.py
│   │   ├── companies.py
│   │   └── dashboard.py
│   │
│   ├── services/
│   │   ├── fsm.py
│   │   ├── auth_service.py
│   │   └── dashboard_service.py
│   │
│   ├── tasks/
│   │   ├── celery_app.py
│   │   └── deadline_tasks.py
│   │
│   └── db/
│       ├── session.py
│       └── base.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── alembic/
│   └── versions/
│
├── .github/
│   └── workflows/
│
├── compose.yaml
├── Dockerfile
├── .env.example
└── README.md
```

## Application State Machine

The application lifecycle is implemented as a finite state machine.

### States

```text
Wishlist
Applied
OA
Interview
Offer
Accepted
Declined
Rejected
Withdrawn
```

### Allowed Transitions

```text
Wishlist
 ├── Applied
 └── Withdrawn

Applied
 ├── OA
 ├── Interview
 ├── Rejected
 └── Withdrawn

OA
 ├── Interview
 ├── Rejected
 └── Withdrawn

Interview
 ├── Offer
 ├── Rejected
 └── Withdrawn

Offer
 ├── Accepted
 └── Declined

Accepted  → terminal
Declined  → terminal
Rejected  → terminal
Withdrawn → terminal
```

`Applied → Interview` is intentionally allowed because some companies do not have an online assessment stage.

Interview rounds are represented by an `interview_round` integer rather than separate FSM states such as `Interview Round 1`, `Interview Round 2`, etc.

## Data Model

### User

- `id`
- `email`
- `hashed_password`
- `full_name`
- `created_at`

### Company

- `id`
- `name`
- `tier`
- `website`

### Application

- `id`
- `user_id`
- `company_id`
- `role_title`
- `status`
- `application_deadline`
- `applied_date`
- `portal_url`
- `notes`
- `interview_round`
- `created_at`
- `updated_at`

### StatusHistory

- `id`
- `application_id`
- `from_status`
- `to_status`
- `changed_at`

This provides an auditable history of every status transition and supports conversion-rate analytics.

### Notification

- `id`
- `application_id`
- `type`
- `channel`
- `sent_at`

The notification record is also used to prevent duplicate reminders.

### Refresh Tokens

Refresh-token identifiers are stored in Redis rather than PostgreSQL.

Each Redis key has a TTL matching the token's expiry, allowing expired token state to disappear automatically without a cleanup job.

## API Endpoints

### Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Create a user account |
| POST | `/auth/login` | Return access + refresh tokens |
| POST | `/auth/refresh` | Rotate refresh token and issue a new token pair |
| POST | `/auth/logout` | Invalidate the current refresh token |

### Applications

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/applications` | Create an application |
| GET | `/applications` | List applications with filtering, sorting, and pagination |
| GET | `/applications/{id}` | Retrieve one application |
| PATCH | `/applications/{id}` | Update application details |
| PATCH | `/applications/{id}/status` | Perform a validated status transition |
| DELETE | `/applications/{id}` | Delete an application |

### Companies

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/companies` | List companies |
| POST | `/companies` | Create a company |

An application creation request can also automatically create a company when the referenced company does not already exist.

### Dashboard

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/dashboard/summary` | Status counts and conversion rates |
| GET | `/dashboard/upcoming` | Upcoming deadlines ranked by urgency |

## Redis Caching Strategy

The dashboard summary uses a **cache-aside strategy with a 60-second TTL fallback**.

### Read

```text
Request
   │
   ▼
Check Redis
   │
   ├── Cache hit ──► Return cached summary
   │
   └── Cache miss
          │
          ▼
     Query PostgreSQL
          │
          ▼
     Store in Redis
       TTL = 60s
          │
          ▼
      Return result
```

### Write

Changes that affect dashboard counts explicitly invalidate the user's cache after the database transaction commits.

Cache invalidation occurs after:

- Creating an application
- Deleting an application
- Changing application status

Updates such as notes or portal URLs do not invalidate the summary because they do not affect dashboard counts.

The TTL provides a safety net if a future code path accidentally misses explicit invalidation.

## Background Jobs

### `scan_upcoming_deadlines`

Scheduled by Celery Beat.

Responsibilities:

- Find applications whose deadlines fall inside the reminder window.
- Check whether the relevant reminder has already been generated.
- Enqueue reminder tasks for applications requiring notification.

### `send_deadline_reminder`

Executed by a Celery Worker.

Responsibilities:

- Send the configured reminder.
- Initially, this can be represented by an application notification record.
- Optionally send email through a transactional email provider.
- Create a `Notification` record to prevent duplicate reminders.

### `flag_stale_applications`

Optional background task.

Identifies applications that have remained in the `Applied` state for an extended period without movement and surfaces them as follow-up candidates.

## Authentication Security

The authentication system uses:

- Short-lived access tokens (~15 minutes).
- Longer-lived refresh tokens (~1 week).
- Refresh-token rotation.
- Redis-backed active refresh-token identifiers.
- Immediate invalidation of previously used refresh tokens.
- Password hashing with Argon2 or bcrypt.
- Environment-based secrets.

A rotated refresh token cannot be reused because its identifier has already been removed from Redis.

## Testing

The project is designed around unit and integration testing.

### Unit Tests

The FSM is tested independently of the database and API layer.

Tests cover:

- Every valid transition.
- Every invalid transition.
- Terminal states.
- Transition edge cases.

### Integration Tests

API endpoints are tested using an asynchronous test client and real asynchronous database behavior.

### Celery Tests

Celery tasks use eager execution during testing so jobs can execute synchronously inside the test process without requiring a live broker.

## Environment Variables

Create a `.env` file based on `.env.example`.

Example configuration:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/internship_tracker
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=replace_with_a_secure_secret
```

Secrets and connection strings should never be hardcoded or committed to the repository.

## Running Locally

### Prerequisites

- Python 3.12+
- Docker
- Docker Compose
- PostgreSQL
- Redis

### Install Dependencies

```bash
git clone <repository-url>
cd internship-application-tracker

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Configure Environment

```bash
cp .env.example .env
```

Update the environment variables for your local setup.

### Run Migrations

```bash
alembic upgrade head
```

### Start the API

```bash
uvicorn app.main:app --reload
```

The API will be available through the configured local host and port.

FastAPI's generated interactive API documentation can be used to test the API without a frontend.

### Run Tests

```bash
pytest
```

## Docker

The complete system is designed to run through Docker Compose with:

- FastAPI API
- PostgreSQL
- Redis
- Celery Worker
- Celery Beat

Start the stack with:

```bash
docker compose up --build
```

Stop it with:

```bash
docker compose down
```

## Continuous Integration

GitHub Actions runs the test suite on:

- Every push to `main`
- Every pull request targeting `main`

The CI environment provisions temporary:

- PostgreSQL 16
- Redis 7

The workflow then:

1. Checks out the repository.
2. Installs Python 3.12.
3. Installs dependencies.
4. Applies Alembic migrations.
5. Runs the complete pytest suite.

This ensures that tests run against a clean and reproducible environment rather than relying on local machine state.

## Deployment

The architecture requires multiple long-running processes:

- API
- Celery Worker
- Celery Beat

The PRD identifies two compatible deployment options:

### Railway

Can host multiple services from the same repository and provides managed PostgreSQL and Redis options.

### Render

Supports web services, background workers, and scheduled workloads suitable for this architecture.

The final hosting platform is to be selected during the deployment phase.

## Development Roadmap

### Phase 1 — Core

- User registration
- Access-token authentication
- Application records
- Company records
- Finite state machine
- Status history
- Full test suite
- GitHub Actions CI
- Initial deployment

### Phase 2 — Background Processing

- Refresh-token rotation
- Redis token management
- Deadline scanning
- Reminder jobs
- Redis dashboard caching
- Cache invalidation

### Phase 3 — Polish & Deployment

- Dashboard analytics
- Complete Docker Compose configuration
- Production configuration
- Final deployment
- Documentation and interview-focused polish

Estimated total development time: **3–4 weeks of consistent part-time work**.

## Success Criteria

The project is considered successful when:

- All invalid FSM transitions are rejected.
- All valid FSM transitions work correctly.
- Deadline reminders are generated automatically.
- Duplicate reminders are prevented.
- Rotated refresh tokens are rejected on reuse.
- Dashboard data is not more than 60 seconds stale under the defined caching strategy.
- The system is publicly deployed.
- The architecture can be clearly explained in a technical interview.

## Design Decisions

### Why a Finite State Machine?

A simple status string cannot enforce business rules. The FSM makes application lifecycle rules explicit and testable.

### Why Redis?

Redis serves three useful roles in the project:

1. Celery broker and result backend.
2. Dashboard cache.
3. Active refresh-token store.

This provides practical experience with Redis beyond using it as a basic cache.

### Why Celery Beat?

Celery Beat already provides periodic scheduling for a Celery-based background processing architecture. Adding another scheduler would introduce unnecessary complexity.

### Why Cache Invalidation + TTL?

Explicit invalidation provides immediate freshness, while TTL provides a safety mechanism if a future code path forgets to invalidate the cache.

### Why Separate Companies?

Normalizing companies prevents duplicated company names and creates a foundation for company-level analytics.

## Non-Goals

The project intentionally does not include:

- A frontend application.
- Automatic scraping of company application portals.
- Organization/team collaboration.
- Mobile or browser push notifications.

Deadlines are entered by the user, and notifications are initially limited to stored records and optionally email.

## Interview Talking Points

This project is intended to demonstrate more than CRUD API development.

Key discussion areas include:

- Designing and testing a finite state machine.
- Async SQLAlchemy architecture.
- Pydantic validation and serialization.
- JWT authentication.
- Refresh-token rotation and revocation.
- Redis token storage.
- Cache-aside architecture.
- Explicit cache invalidation with TTL fallback.
- Celery task queues.
- Celery Beat scheduling.
- Idempotent background jobs.
- Database normalization.
- Audit logging.
- Async integration testing.
- Dockerized multi-service architecture.
- CI with disposable PostgreSQL and Redis services.
- Production deployment of worker-based systems.

## Project Context

This project is part of a portfolio series focused on backend engineering for software development internship applications. Its scope intentionally emphasizes real backend architecture, security, asynchronous processing, caching, background jobs, testing, and deployment rather than frontend development.

## License

Add the project's chosen license here before public release.
