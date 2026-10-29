import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.models import Application
from app.db.sync_session import SyncSessionLocal
from app.repositories.application_repository import TERMINAL_STATUSES


IST = timezone(timedelta(hours=5, minutes=30))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _load_valid_notification_context(
    application_id: str,
    expected_deadline_iso: str,
    session=None,
) -> dict | None:
    owns_session = session is None

    if owns_session:
        session = SyncSessionLocal()

    try:
        try:
            application_uuid = uuid.UUID(application_id)
            expected_deadline = _as_utc(
                datetime.fromisoformat(expected_deadline_iso)
            )
        except (TypeError, ValueError):
            return None

        application = session.get(Application, application_uuid)

        if application is None:
            return None

        # Do not send a task that has been cancelled or replaced.
        if application.deadline_notification_status != "queued":
            return None

        deadline = application.deadline
        terminal = application.current_status in TERMINAL_STATUSES

        if (
            deadline is None
            or terminal
            or _as_utc(deadline) <= datetime.now(timezone.utc)
        ):
            if terminal:
                application.deadline = None

            application.deadline_notification_status = "cancelled"
            application.deadline_notification_queued_at = None
            application.deadline_notified = False
            session.commit()
            return None

        # The user may have replaced the deadline while this task was queued.
        if _as_utc(deadline) != expected_deadline:
            application.deadline_notification_status = "pending"
            application.deadline_notification_queued_at = None
            application.deadline_notified = False
            session.commit()
            return None

        if application.user is None:
            application.deadline_notification_status = "failed"
            application.deadline_notification_queued_at = None
            application.deadline_notified = False
            session.commit()
            return None

        # Always use current database values and the current owner.
        return {
            "company_name": application.company_name,
            "role_title": application.role_title,
            "deadline": _as_utc(deadline),
            "recipient_email": application.user.email,
        }

    finally:
        if owns_session:
            session.close()


def _update_notification_status(
    application_id: str,
    new_status: str,
    expected_deadline_iso: str,
    session=None,
) -> None:
    if new_status not in {"sent", "failed"}:
        raise ValueError(f"Unsupported delivery status: {new_status}")

    owns_session = session is None

    if owns_session:
        session = SyncSessionLocal()

    try:
        application = session.get(
            Application,
            uuid.UUID(application_id),
        )

        if application is None:
            return

        # A newer user action may already have changed the state.
        if application.deadline_notification_status != "queued":
            return

        try:
            expected_deadline = _as_utc(
                datetime.fromisoformat(expected_deadline_iso)
            )
        except (TypeError, ValueError):
            return

        deadline = application.deadline

        if (
            deadline is None
            or application.current_status in TERMINAL_STATUSES
            or _as_utc(deadline) <= datetime.now(timezone.utc)
        ):
            final_status = "cancelled"

        elif _as_utc(deadline) != expected_deadline:
            final_status = "pending"

        else:
            final_status = new_status

        application.deadline_notification_status = final_status
        application.deadline_notification_queued_at = None
        application.deadline_notified = final_status == "sent"

        session.commit()

    finally:
        if owns_session:
            session.close()


@celery_app.task(
    name="app.tasks.notification_tasks.send_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_notification(
    self,
    application_id: str,
    company_name: str,
    role_title: str,
    deadline_iso: str,
    recipient_email: str,
    session=None,
    direct_mode: bool = False,
):
    context = _load_valid_notification_context(
        application_id=application_id,
        expected_deadline_iso=deadline_iso,
        session=session,
    )

    if context is None:
        return

    formatted_deadline = context["deadline"].astimezone(IST).strftime(
        "%d %b %Y, %I:%M %p IST"
    )

    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.brevo_api_key,
                "Content-Type": "application/json",
            },
            json={
                "sender": {
                    "email": settings.from_email,
                    "name": "Internship Tracker",
                },
                "to": [
                    {"email": context["recipient_email"]}
                ],
                "subject": (
                    f"Deadline approaching: "
                    f"{context['company_name']} - "
                    f"{context['role_title']}"
                ),
                "htmlContent": (
                    f"<p>Your deadline for "
                    f"<b>{context['role_title']}</b> at "
                    f"<b>{context['company_name']}</b> is on "
                    f"<b>{formatted_deadline}</b>.</p>"
                ),
            },
            timeout=10.0,
        )
        response.raise_for_status()

    except httpx.HTTPError as exc:
        if direct_mode or self.request.retries >= self.max_retries:
            _update_notification_status(
                application_id,
                "failed",
                deadline_iso,
                session=session,
            )
            raise

        raise self.retry(exc=exc)

    _update_notification_status(
        application_id,
        "sent",
        deadline_iso,
        session=session,
    )   