import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application


@pytest.mark.asyncio
async def test_changing_deadline_after_sent_resets_notification(
    client: AsyncClient,
    auth_headers: dict,
    db: AsyncSession,
):
    create_response = await client.post(
        "/applications",
        json={
            "company_name": "DeadlineStateTestCo",
            "role_title": "Backend Intern",
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201

    application_id = uuid.UUID(create_response.json()["id"])

    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one()

    previous_deadline = datetime.now(timezone.utc) + timedelta(days=2)

    application.deadline = previous_deadline
    application.deadline_notification_status = "sent"
    application.deadline_notification_queued_at = None
    application.deadline_notified = True

    await db.flush()

    new_deadline = datetime.now(timezone.utc) + timedelta(days=5)

    response = await client.patch(
        f"/applications/{application_id}",
        json={"deadline": new_deadline.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 200

    await db.refresh(application)

    assert application.deadline is not None
    assert application.deadline_notification_status == "pending"
    assert application.deadline_notification_queued_at is None
    assert application.deadline_notified is False


@pytest.mark.asyncio
async def test_clearing_deadline_cancels_queued_notification(
    client: AsyncClient,
    auth_headers: dict,
    db: AsyncSession,
):
    create_response = await client.post(
        "/applications",
        json={
            "company_name": "DeadlineClearTestCo",
            "role_title": "Backend Intern",
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201

    application_id = uuid.UUID(create_response.json()["id"])

    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one()

    application.deadline = datetime.now(timezone.utc) + timedelta(days=2)
    application.deadline_notification_status = "queued"
    application.deadline_notification_queued_at = datetime.now(timezone.utc)

    await db.flush()

    response = await client.patch(
        f"/applications/{application_id}",
        json={"deadline": None},
        headers=auth_headers,
    )

    assert response.status_code == 200

    await db.refresh(application)

    assert application.deadline is None
    assert application.deadline_notification_status == "cancelled"
    assert application.deadline_notification_queued_at is None
    assert application.deadline_notified is False


@pytest.mark.asyncio
async def test_terminal_status_cancels_queued_notification(
    client: AsyncClient,
    auth_headers: dict,
    db: AsyncSession,
):
    create_response = await client.post(
        "/applications",
        json={
            "company_name": "TerminalStateTestCo",
            "role_title": "Backend Intern",
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201

    application_id = uuid.UUID(create_response.json()["id"])

    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one()

    application.deadline = datetime.now(timezone.utc) + timedelta(days=2)
    application.deadline_notification_status = "queued"
    application.deadline_notification_queued_at = datetime.now(timezone.utc)

    await db.flush()

    response = await client.patch(
        f"/applications/{application_id}/status",
        json={"target_status": "REJECTED"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    await db.refresh(application)

    assert application.current_status.value == "REJECTED"
    assert application.deadline is None
    assert application.deadline_notification_status == "cancelled"
    assert application.deadline_notification_queued_at is None
    assert application.deadline_notified is False