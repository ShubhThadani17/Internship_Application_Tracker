from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.db.sync_session import SyncSessionLocal
from app.db.models import AnalyticsSnapshot
from app.services.analytics_service import compute_analytics


@celery_app.task(name="app.tasks.analytics_tasks.recompute_analytics")
def recompute_analytics(session=None):
    owns_session = session is None
    if owns_session:
        session = SyncSessionLocal()

    try:
        data = compute_analytics(session)

        snapshot = session.get(AnalyticsSnapshot, 1)
        if snapshot is None:
            snapshot = AnalyticsSnapshot(id=1, data=data, computed_at=datetime.now(timezone.utc))
            session.add(snapshot)
        else:
            snapshot.data = data
            snapshot.computed_at = datetime.now(timezone.utc)

        session.commit()
    finally:
        if owns_session:
            session.close()