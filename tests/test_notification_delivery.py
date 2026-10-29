from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

from app.db.models import Application, User
from app.domain.status import ApplicationStatus
from app.tasks.notification_tasks import send_notification


def _make_queued_application(
    sync_db,
    deadline=None,
    status=ApplicationStatus.OA1,
):
    if deadline is None:
        deadline = datetime.now(timezone.utc) + timedelta(hours=24)

    user = User(
        email=f"delivery-{uuid4()}@example.com",
        hashed_password="fake_hash",
    )
    sync_db.add(user)
    sync_db.flush()

    application = Application(
        user_id=user.id,
        company_name="Example Company",
        role_title="Backend Intern",
        current_status=status,
        deadline=deadline,
        deadline_notified=False,
        deadline_notification_status="queued",
        deadline_notification_queued_at=datetime.now(timezone.utc),
    )

    sync_db.add(application)
    sync_db.flush()

    return application, user


def _task_arguments(application, user, expected_deadline=None):
    if expected_deadline is None:
        expected_deadline = application.deadline

    return {
        "application_id": str(application.id),
        "company_name": application.company_name,
        "role_title": application.role_title,
        "deadline_iso": expected_deadline.isoformat(),
        "recipient_email": user.email,
    }


def test_successful_delivery_marks_notification_sent(sync_db):
    application, user = _make_queued_application(sync_db)
    arguments = _task_arguments(application, user)

    with patch(
        "app.tasks.notification_tasks.httpx.post"
    ) as mock_post:
        mock_post.return_value.raise_for_status.return_value = None

        send_notification.run(**arguments, session=sync_db)

        mock_post.assert_called_once()

        request_payload = mock_post.call_args.kwargs["json"]
        assert request_payload["to"] == [{"email": user.email}]

    sync_db.refresh(application)

    assert application.deadline_notification_status == "sent"
    assert application.deadline_notification_queued_at is None
    assert application.deadline_notified is True


def test_final_delivery_failure_marks_notification_failed(sync_db):
    application, user = _make_queued_application(sync_db)
    arguments = _task_arguments(application, user)

    with patch(
        "app.tasks.notification_tasks.httpx.post",
        side_effect=httpx.TimeoutException("Simulated timeout"),
    ):
        # Simulate the last retry attempt.
        send_notification.push_request(
            retries=send_notification.max_retries
        )

        try:
            with pytest.raises(httpx.TimeoutException):
                send_notification.run(
                    **arguments,
                    session=sync_db,
                )
        finally:
            send_notification.pop_request()

    sync_db.refresh(application)

    assert application.deadline_notification_status == "failed"
    assert application.deadline_notification_queued_at is None
    assert application.deadline_notified is False


def test_obsolete_task_does_not_send_for_changed_deadline(sync_db):
    now = datetime.now(timezone.utc)

    current_deadline = now + timedelta(hours=48)
    old_deadline = now + timedelta(hours=24)

    application, user = _make_queued_application(
        sync_db,
        deadline=current_deadline,
    )

    arguments = _task_arguments(
        application,
        user,
        expected_deadline=old_deadline,
    )

    with patch(
        "app.tasks.notification_tasks.httpx.post"
    ) as mock_post:
        send_notification.run(**arguments, session=sync_db)
        mock_post.assert_not_called()

    sync_db.refresh(application)

    assert application.deadline_notification_status == "pending"
    assert application.deadline_notification_queued_at is None
    assert application.deadline_notified is False


def test_terminal_application_cannot_send_queued_reminder(sync_db):
    application, user = _make_queued_application(
        sync_db,
        status=ApplicationStatus.REJECTED,
    )
    arguments = _task_arguments(application, user)

    with patch(
        "app.tasks.notification_tasks.httpx.post"
    ) as mock_post:
        send_notification.run(**arguments, session=sync_db)
        mock_post.assert_not_called()

    sync_db.refresh(application)

    assert application.deadline is None
    assert application.deadline_notification_status == "cancelled"
    assert application.deadline_notification_queued_at is None
    assert application.deadline_notified is False