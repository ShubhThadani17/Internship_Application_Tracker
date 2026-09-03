from datetime import datetime, timezone, timedelta

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings

IST = timezone(timedelta(hours=5, minutes=30))


@celery_app.task(
    name="app.tasks.notification_tasks.send_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_notification(self, application_id: str, company_name: str, role_title: str, deadline_iso: str):
    deadline_utc = datetime.fromisoformat(deadline_iso)
    deadline_ist = deadline_utc.astimezone(IST)
    formatted_deadline = deadline_ist.strftime("%d %b %Y, %I:%M %p IST")

    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.brevo_api_key,
                "Content-Type": "application/json",
            },
            json={
                "sender": {"email": settings.from_email, "name": "Internship Tracker"},
                "to": [{"email": settings.notify_email}],
                "subject": f"Deadline approaching: {company_name} - {role_title}",
                "htmlContent": (
                    f"<p>Your deadline for <b>{role_title}</b> at <b>{company_name}</b> "
                    f"is on <b>{formatted_deadline}</b>.</p>"
                ),
            },
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise self.retry(exc=exc)