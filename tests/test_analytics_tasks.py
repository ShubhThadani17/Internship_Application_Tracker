from uuid import uuid4

from app.db.models import AnalyticsSnapshot, User
from app.tasks.analytics_tasks import recompute_analytics


def _make_user(sync_db):
    user = User(
        email=f"analytics-{uuid4()}@example.com",
        hashed_password="fake_hash",
    )
    sync_db.add(user)
    sync_db.flush()
    return user


def test_recompute_analytics_creates_snapshot_when_none_exists(sync_db):
    user = _make_user(sync_db)

    recompute_analytics(
        user_id=str(user.id),
        session=sync_db,
    )

    snapshot = sync_db.get(AnalyticsSnapshot, user.id)

    assert snapshot is not None
    assert snapshot.user_id == user.id
    assert "funnel_counts" in snapshot.data


def test_recompute_analytics_updates_existing_snapshot(sync_db):
    user = _make_user(sync_db)

    recompute_analytics(
        user_id=str(user.id),
        session=sync_db,
    )

    first_snapshot = sync_db.get(AnalyticsSnapshot, user.id)
    assert first_snapshot is not None

    first_computed_at = first_snapshot.computed_at

    recompute_analytics(
        user_id=str(user.id),
        session=sync_db,
    )

    snapshot = sync_db.get(AnalyticsSnapshot, user.id)

    assert snapshot is not None
    assert snapshot.user_id == user.id
    assert snapshot.computed_at >= first_computed_at

    count = (
        sync_db.query(AnalyticsSnapshot)
        .filter(AnalyticsSnapshot.user_id == user.id)
        .count()
    )

    assert count == 1


def test_recompute_analytics_creates_separate_snapshots_for_users(sync_db):
    user_a = _make_user(sync_db)
    user_b = _make_user(sync_db)

    recompute_analytics(
        user_id=str(user_a.id),
        session=sync_db,
    )

    recompute_analytics(
        user_id=str(user_b.id),
        session=sync_db,
    )

    snapshot_a = sync_db.get(AnalyticsSnapshot, user_a.id)
    snapshot_b = sync_db.get(AnalyticsSnapshot, user_b.id)

    assert snapshot_a is not None
    assert snapshot_b is not None

    assert snapshot_a.user_id == user_a.id
    assert snapshot_b.user_id == user_b.id

    assert snapshot_a.user_id != snapshot_b.user_id

    assert (
        sync_db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.user_id.in_(
                [user_a.id, user_b.id]
            )
        )
        .count()
        == 2
    )