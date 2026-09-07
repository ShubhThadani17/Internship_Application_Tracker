from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.db.models import Application, User
from app.domain.status import ApplicationStatus
from app.tasks.deadline_tasks import scan_deadlines


def _make_user_and_application(sync_db, deadline, deadline_notified, status=ApplicationStatus.OA1):
    user = User(email=f"test-{deadline}@example.com", hashed_password="fake_hash")
    sync_db.add(user)
    sync_db.flush()

    application = Application(
        user_id=user.id,
        company_name="TestCo",
        role_title="Backend Intern",
        current_status=status,
        deadline=deadline,
        deadline_notified=deadline_notified,
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
        deadline_notified=False,
    )

    scan_deadlines(session=sync_db)

    called_ids = [call.kwargs["application_id"] for call in mock_delay.call_args_list]
    assert str(application.id) in called_ids

    sync_db.refresh(application)
    assert application.deadline_notified is True


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_skips_already_notified(mock_delay, sync_db):
    now = datetime.now(timezone.utc)
    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=24),
        deadline_notified=True,
    )

    scan_deadlines(session=sync_db)

    called_ids = [call.kwargs["application_id"] for call in mock_delay.call_args_list]
    assert str(application.id) not in called_ids


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_skips_deadline_outside_window(mock_delay, sync_db):
    now = datetime.now(timezone.utc)
    application = _make_user_and_application(
        sync_db,
        deadline=now + timedelta(hours=72),
        deadline_notified=False,
    )

    scan_deadlines(session=sync_db)

    called_ids = [call.kwargs["application_id"] for call in mock_delay.call_args_list]
    assert str(application.id) not in called_ids


@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_skips_past_deadline(mock_delay, sync_db):
    now = datetime.now(timezone.utc)
    application = _make_user_and_application(
        sync_db,
        deadline=now - timedelta(hours=5),
        deadline_notified=False,
    )

    scan_deadlines(session=sync_db)

    called_ids = [call.kwargs["application_id"] for call in mock_delay.call_args_list]
    assert str(application.id) not in called_ids



@patch("app.tasks.deadline_tasks.send_notification.delay")
def test_scan_skips_null_deadline(mock_delay, sync_db):
    now = datetime.now(timezone.utc)
    application = _make_user_and_application(
        sync_db,
        deadline=None,
        deadline_notified=False,
    )

    scan_deadlines(session=sync_db)

    called_ids = [call.kwargs["application_id"] for call in mock_delay.call_args_list]
    assert str(application.id) not in called_ids
