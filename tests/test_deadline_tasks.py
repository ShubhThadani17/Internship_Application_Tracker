from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from app.db.models import Application, User
from app.domain.status import ApplicationStatus
from app.tasks.deadline_tasks import scan_deadlines


def _make_user_and_application(
    sync_db,
    deadline,
    deadline_notified=False,
    status=ApplicationStatus.OA1,
    deadline_notification_status=None,
    deadline_notification_queued_at=None,
    company_name="TestCo",
):
    user = User(
        email=f"test-{uuid4()}@example.com",
        hashed_password="fake_hash",
    )
    sync_db.add(user)
    sync_db.flush()

    if deadline_notification_status is None:
        deadline_notification_status = (
            "sent" if deadline_notified else "pending"
        )

    application = Application(
        user_id=user.id,
        company_name=company_name,
        role_title="Backend Intern",
        current_status=status,
        deadline=deadline,
        deadline_notified=deadline_notified,
        deadline_notification_status=deadline_notification_status,
        deadline_notification_queued_at=(
            deadline_notification_queued_at
        ),
    )

    sync_db.add(application)
    sync_db.flush()
    return application


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_finds_application_within_window(mock_delay, sync_db):
    now = datetime.now(timezone.utc)

    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=24),
    )

    sync_db.commit()

    scan_deadlines(session=sync_db)

    called_ids = [
        call.kwargs["application_id"]
        for call in mock_delay.call_args_list
    ]

    assert str(application.id) in called_ids

    sync_db.refresh(application)

    assert application.deadline_notification_status == "queued"
    assert application.deadline_notification_queued_at is not None
    assert application.deadline_notified is False


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_skips_already_sent_notification(mock_delay, sync_db):
    now = datetime.now(timezone.utc)

    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=24),
        deadline_notified=True,
        deadline_notification_status="sent",
    )

    sync_db.commit()
    scan_deadlines(session=sync_db)

    called_ids = [
        call.kwargs["application_id"]
        for call in mock_delay.call_args_list
    ]

    assert str(application.id) not in called_ids


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_skips_deadline_outside_window(mock_delay, sync_db):
    now = datetime.now(timezone.utc)

    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=72),
    )

    sync_db.commit()
    scan_deadlines(session=sync_db)

    called_ids = [
        call.kwargs["application_id"]
        for call in mock_delay.call_args_list
    ]

    assert str(application.id) not in called_ids


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_skips_past_deadline(mock_delay, sync_db):
    now = datetime.now(timezone.utc)

    application = _make_user_and_application(
        sync_db,
        deadline=now - timedelta(hours=5),
    )

    sync_db.commit()
    scan_deadlines(session=sync_db)

    called_ids = [
        call.kwargs["application_id"]
        for call in mock_delay.call_args_list
    ]

    assert str(application.id) not in called_ids


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_skips_null_deadline(mock_delay, sync_db):
    application = _make_user_and_application(
        sync_db,
        deadline=None,
    )

    sync_db.commit()
    scan_deadlines(session=sync_db)

    called_ids = [
        call.kwargs["application_id"]
        for call in mock_delay.call_args_list
    ]

    assert str(application.id) not in called_ids


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_sends_reminders_to_correct_user(
    mock_delay,
    sync_db,
):
    now = datetime.now(timezone.utc)

    application_a = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=24),
        company_name="CompanyA",
    )

    application_b = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=30),
        company_name="CompanyB",
    )

    # Capture the owners' addresses before running the scanner.
    sync_db.flush()
    email_a = application_a.user.email
    email_b = application_b.user.email

    sync_db.commit()
    scan_deadlines(session=sync_db)

    queued_recipients = {
        call.kwargs["application_id"]: call.kwargs["recipient_email"]
        for call in mock_delay.call_args_list
    }

    assert queued_recipients[str(application_a.id)] == email_a
    assert queued_recipients[str(application_b.id)] == email_b
    assert email_a != email_b


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_retries_failed_notification_only_once(
    mock_delay,
    sync_db,
):
    now = datetime.now(timezone.utc)

    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=24),
        deadline_notification_status="failed",
    )

    sync_db.commit()

    scan_deadlines(session=sync_db)
    sync_db.refresh(application)

    assert application.deadline_notification_status == "queued"
    assert mock_delay.call_count == 1

    # It is queued already, so another scan must not queue it again.
    scan_deadlines(session=sync_db)

    assert mock_delay.call_count == 1


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_recovers_stale_queued_notification(
    mock_delay,
    sync_db,
):
    now = datetime.now(timezone.utc)
    old_queued_at = now - timedelta(minutes=30)

    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=24),
        deadline_notification_status="queued",
        deadline_notification_queued_at=old_queued_at,
    )

    sync_db.commit()

    scan_deadlines(session=sync_db)
    sync_db.refresh(application)

    # The stale attempt was recovered and queued again.
    assert application.deadline_notification_status == "queued"
    assert application.deadline_notification_queued_at is not None
    assert application.deadline_notification_queued_at > old_queued_at
    assert mock_delay.call_count == 1


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_does_not_queue_terminal_application(
    mock_delay,
    sync_db,
):
    now = datetime.now(timezone.utc)

    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=24),
        status=ApplicationStatus.REJECTED,
        deadline_notification_status="pending",
    )

    sync_db.commit()
    scan_deadlines(session=sync_db)

    called_ids = [
        call.kwargs["application_id"]
        for call in mock_delay.call_args_list
    ]

    assert str(application.id) not in called_ids

@patch("app.tasks.deadline_tasks.send_notification.delay")
@patch("app.tasks.deadline_tasks.send_notification.run")
def test_direct_send_mode_bypasses_celery(
    mock_run,
    mock_delay,
    sync_db,
):
    now = datetime.now(timezone.utc)

    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=12),
        deadline_notification_status="pending",
    )

    sync_db.commit()

    scan_deadlines(
        session=sync_db,
        direct_send=True,
    )

    mock_delay.assert_not_called()
    mock_run.assert_called_once()

    task_kwargs = mock_run.call_args.kwargs

    assert task_kwargs["direct_mode"] is True
    assert task_kwargs["session"] is sync_db
    assert task_kwargs["application_id"] == str(application.id)