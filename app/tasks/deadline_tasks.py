from datetime import datetime, timedelta, timezone

from app.core.celery_app import celery_app
from app.db.sync_session import SyncSessionLocal
from app.db.models import Application
from app.tasks.notification_tasks import send_notification


@celery_app.task(name="app.tasks.deadline_tasks.scan_deadlines")
def scan_deadlines(session=None):
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=48)

    owns_session = session is None
    if owns_session:
        session = SyncSessionLocal()

    try:
        applications = (
            session.query(Application)
            .filter(
                Application.deadline.isnot(None),
                Application.deadline_notified.is_(False),
                Application.deadline <= window_end,
                Application.deadline >= now,
            )
            .all()
        )

        for application in applications:
            send_notification.delay(
                application_id=str(application.id),
                company_name=application.company_name,
                role_title=application.role_title,
                deadline_iso=application.deadline.isoformat(),
            )
            application.deadline_notified = True

        session.commit()
    finally:
        if owns_session:
            session.close()