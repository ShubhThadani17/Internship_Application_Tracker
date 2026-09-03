from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "internship_tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.deadline_tasks",
        "app.tasks.notification_tasks",
    ],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True

celery_app.conf.beat_schedule = {
    "scan-deadlines-every-12h": {
        "task": "app.tasks.deadline_tasks.scan_deadlines",
        "schedule": crontab(minute=0, hour="0,12"),
    },
}