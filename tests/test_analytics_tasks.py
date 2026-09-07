from app.db.models import AnalyticsSnapshot
from app.tasks.analytics_tasks import recompute_analytics


def test_recompute_analytics_creates_snapshot_when_none_exists(sync_db):
    recompute_analytics(session=sync_db)

    snapshot = sync_db.get(AnalyticsSnapshot, 1)
    assert snapshot is not None
    assert "funnel_counts" in snapshot.data


def test_recompute_analytics_updates_existing_snapshot(sync_db):
    recompute_analytics(session=sync_db)
    first_computed_at = sync_db.get(AnalyticsSnapshot, 1).computed_at

    recompute_analytics(session=sync_db)
    snapshot = sync_db.get(AnalyticsSnapshot, 1)

    assert snapshot.computed_at >= first_computed_at
    count = sync_db.query(AnalyticsSnapshot).count()
    assert count == 1