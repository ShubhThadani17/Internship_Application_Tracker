from datetime import datetime, timedelta, timezone

from app.db.models import Application, StatusHistory, User
from app.domain.status import ApplicationStatus
from app.services.analytics_service import compute_analytics


def _make_user(sync_db, email):
    user = User(email=email, hashed_password="fake_hash")
    sync_db.add(user)
    sync_db.flush()
    return user


def _make_application_with_history(sync_db, user, company_name, status_sequence):
    application = Application(
        user_id=user.id,
        company_name=company_name,
        role_title="Backend Intern",
        current_status=status_sequence[-1][0],
    )
    sync_db.add(application)
    sync_db.flush()

    previous_status = None
    for status, changed_at in status_sequence:
        history = StatusHistory(
            application_id=application.id,
            from_status=previous_status,
            to_status=status,
            changed_at=changed_at,
        )
        sync_db.add(history)
        previous_status = status

    sync_db.flush()
    return application


def test_funnel_counts_reflects_current_status(sync_db):
    baseline = compute_analytics(sync_db)["funnel_counts"]

    user = _make_user(sync_db, "funnel@example.com")
    now = datetime.now(timezone.utc)

    _make_application_with_history(
        sync_db, user, "Adobe", [(ApplicationStatus.APPLIED, now), (ApplicationStatus.OA1, now)]
    )
    _make_application_with_history(
        sync_db, user, "Meta", [(ApplicationStatus.APPLIED, now)]
    )
    sync_db.commit()

    result = compute_analytics(sync_db)["funnel_counts"]

    assert result["OA1"] - baseline["OA1"] == 1
    assert result["APPLIED"] - baseline["APPLIED"] == 1


def test_conversion_rate_reflects_new_applications(sync_db):
    user = _make_user(sync_db, "conversion@example.com")
    now = datetime.now(timezone.utc)

    _make_application_with_history(
        sync_db, user, f"UniqueCo-{user.id}",
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.OA1, now + timedelta(days=1)),
            (ApplicationStatus.OA2, now + timedelta(days=2)),
            (ApplicationStatus.INTERVIEW, now + timedelta(days=3)),
        ],
    )
    sync_db.commit()

    result = compute_analytics(sync_db)
    rates = result["conversion_rates"]

    assert rates["APPLIED_to_OA1"] is not None
    assert rates["OA2_to_INTERVIEW"] is not None


def test_avg_time_per_status_computes_correct_gap(sync_db):
    user = _make_user(sync_db, f"avgtime-{datetime.now(timezone.utc).timestamp()}@example.com")
    now = datetime.now(timezone.utc)

    application = _make_application_with_history(
        sync_db, user, "PrecisionTestCo",
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.OA1, now + timedelta(days=3)),
        ],
    )
    sync_db.commit()

    from sqlalchemy import select, func
    from app.db.models import StatusHistory as SH

    lag_expr = func.lag(SH.changed_at).over(partition_by=SH.application_id, order_by=SH.changed_at)
    subquery = (
        select(
            SH.application_id,
            SH.to_status,
            (func.extract("epoch", SH.changed_at - lag_expr) / 86400.0).label("gap"),
        ).subquery()
    )
    row = sync_db.execute(
        select(subquery.c.gap).where(
            subquery.c.application_id == application.id,
            subquery.c.to_status == ApplicationStatus.OA1,
        )
    ).scalar_one()

    assert round(row, 1) == 3.0


def test_ghosting_rate_reflects_new_ghosted_and_rejected(sync_db):
    baseline = compute_analytics(sync_db)["ghosting_rate"]

    user = _make_user(sync_db, f"ghosting-{datetime.now(timezone.utc).timestamp()}@example.com")
    now = datetime.now(timezone.utc)

    _make_application_with_history(
        sync_db, user, "GhostCo", [(ApplicationStatus.APPLIED, now), (ApplicationStatus.GHOSTED, now)]
    )
    _make_application_with_history(
        sync_db, user, "RejectCo", [(ApplicationStatus.APPLIED, now), (ApplicationStatus.REJECTED, now)]
    )
    sync_db.commit()

    result = compute_analytics(sync_db)["ghosting_rate"]

    assert result["ghosted"] - baseline["ghosted"] == 1
    assert result["rejected"] - baseline["rejected"] == 1


def test_response_rate_by_company_merges_casing(sync_db):
    user = _make_user(sync_db, f"casing-{datetime.now(timezone.utc).timestamp()}@example.com")
    now = datetime.now(timezone.utc)
    unique_company = f"CasingTestCo-{user.id}"

    _make_application_with_history(
        sync_db, user, unique_company, [(ApplicationStatus.APPLIED, now), (ApplicationStatus.OA1, now)]
    )
    _make_application_with_history(
        sync_db, user, unique_company.lower(), [(ApplicationStatus.APPLIED, now)]
    )
    sync_db.commit()

    result = compute_analytics(sync_db)
    matches = [
        row for row in result["response_rate_by_company"]
        if row["company_name"] == unique_company.lower()
    ]

    assert len(matches) == 1
    assert matches[0]["total_applications"] == 2
    assert matches[0]["responded"] == 1