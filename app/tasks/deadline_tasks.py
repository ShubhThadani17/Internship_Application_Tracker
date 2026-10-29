import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, or_, update
from sqlalchemy.orm import joinedload

from app.core.celery_app import celery_app
from app.db.models import Application
from app.db.sync_session import SyncSessionLocal
from app.repositories.application_repository import TERMINAL_STATUSES
from app.tasks.notification_tasks import send_notification


logger = logging.getLogger(__name__)

STALE_QUEUE_AFTER = timedelta(minutes=15)
REMINDER_WINDOW = timedelta(hours=48)


@celery_app.task(name="app.tasks.deadline_tasks.scan_deadlines")
def scan_deadlines(session=None, direct_send=False):
    now = datetime.now(timezone.utc)
    window_end = now + REMINDER_WINDOW
    stale_before = now - STALE_QUEUE_AFTER

    owns_session = session is None

    if owns_session:
        session = SyncSessionLocal()

    try:
        # Cancel pending reminders whose applications are no longer eligible.
        session.execute(
            update(Application)
            .where(
                Application.deadline_notification_status.in_(
                    ["pending", "failed"]
                ),
                or_(
                    Application.deadline.is_(None),
                    Application.deadline < now,
                    Application.current_status.in_(
                        list(TERMINAL_STATUSES)
                    ),
                ),
            )
            .values(
                deadline_notification_status="cancelled",
                deadline_notification_queued_at=None,
                deadline_notified=False,
            )
            .execution_options(synchronize_session=False)
        )
        session.commit()

        # Recover stale queued reminders.
        session.execute(
            update(Application)
            .where(
                Application.deadline_notification_status == "queued",
                or_(
                    Application.deadline_notification_queued_at.is_(None),
                    Application.deadline_notification_queued_at
                    <= stale_before,
                ),
            )
            .values(
                deadline_notification_status=case(
                    (
                        or_(
                            Application.deadline.is_(None),
                            Application.deadline < now,
                            Application.current_status.in_(
                                list(TERMINAL_STATUSES)
                            ),
                        ),
                        "cancelled",
                    ),
                    else_="failed",
                ),
                deadline_notification_queued_at=None,
                deadline_notified=False,
            )
            .execution_options(synchronize_session=False)
        )
        session.commit()
        session.expire_all()

        # Find eligible reminders for the next 48 hours.
        applications = (
            session.query(Application)
            .options(joinedload(Application.user))
            .filter(
                Application.deadline.isnot(None),
                Application.deadline_notification_status.in_(
                    ["pending", "failed"]
                ),
                Application.current_status.notin_(
                    list(TERMINAL_STATUSES)
                ),
                Application.deadline >= now,
                Application.deadline <= window_end,
            )
            .all()
        )

        candidates = []

        for application in applications:
            if application.user is None:
                continue

            candidates.append(
                {
                    "application_id": str(application.id),
                    "company_name": application.company_name,
                    "role_title": application.role_title,
                    "deadline_iso": application.deadline.isoformat(),
                    "recipient_email": application.user.email,
                }
            )

        for candidate in candidates:
            application_uuid = uuid.UUID(candidate["application_id"])
            candidate_deadline = datetime.fromisoformat(
                candidate["deadline_iso"]
            )

            # Atomically claim only reminders that are still eligible.
            result = session.execute(
                update(Application)
                .where(
                    Application.id == application_uuid,
                    Application.deadline_notification_status.in_(
                        ["pending", "failed"]
                    ),
                    Application.deadline == candidate_deadline,
                    Application.deadline >= now,
                    Application.deadline <= window_end,
                    Application.current_status.notin_(
                        list(TERMINAL_STATUSES)
                    ),
                )
                .values(
                    deadline_notification_status="queued",
                    deadline_notification_queued_at=now,
                    deadline_notified=False,
                )
                .execution_options(synchronize_session=False)
            )

            claimed = result.rowcount == 1
            session.commit()
            session.expire_all()

            if not claimed:
                continue

            if direct_send:
                # The scheduled runner delivers the email in this process.
                # No Celery broker or worker is required.
                try:
                    send_notification.run(
                        **candidate,
                        session=session,
                        direct_mode=True,
                    )
                except Exception:
                    # The delivery task records failure for HTTP delivery
                    # errors. Other failures remain recoverable through
                    # stale-queue handling.
                    logger.exception(
                        "Direct reminder delivery failed for application %s",
                        candidate["application_id"],
                    )

            else:
                # Preserve the existing worker-based development mode.
                try:
                    send_notification.delay(**candidate)

                except Exception:
                    session.execute(
                        update(Application)
                        .where(
                            Application.id == application_uuid,
                            Application.deadline_notification_status
                            == "queued",
                            Application.deadline == candidate_deadline,
                        )
                        .values(
                            deadline_notification_status="failed",
                            deadline_notification_queued_at=None,
                            deadline_notified=False,
                        )
                        .execution_options(synchronize_session=False)
                    )
                    session.commit()

                    logger.exception(
                        "Could not queue reminder for application %s",
                        candidate["application_id"],
                    )

    finally:
        if owns_session:
            session.close()