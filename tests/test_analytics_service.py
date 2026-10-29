from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db.models import Application, StatusHistory, User
from app.domain.status import ApplicationStatus
from app.services.analytics_service import compute_analytics


def _make_user(sync_db, email):
    user = User(email=email, hashed_password="fake_hash")
    sync_db.add(user)
    sync_db.flush()
    return user


def _make_application_with_history(
    sync_db,
    user,
    company_name,
    status_sequence,
):
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
    user = _make_user(sync_db, "funnel@example.com")
    now = datetime.now(timezone.utc)

    baseline = compute_analytics(
        sync_db, user.id
    )["funnel_counts"]

    _make_application_with_history(
        sync_db,
        user,
        "Adobe",
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.OA1, now + timedelta(days=1)),
        ],
    )

    _make_application_with_history(
        sync_db,
        user,
        "Meta",
        [
            (ApplicationStatus.APPLIED, now),
        ],
    )

    sync_db.commit()

    result = compute_analytics(
        sync_db, user.id
    )["funnel_counts"]

    assert result["OA1"] - baseline["OA1"] == 1
    assert result["APPLIED"] - baseline["APPLIED"] == 1


def test_conversion_rate_reflects_new_applications(sync_db):
    user = _make_user(sync_db, "conversion@example.com")
    now = datetime.now(timezone.utc)

    _make_application_with_history(
        sync_db,
        user,
        f"UniqueCo-{user.id}",
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.OA1, now + timedelta(days=1)),
            (ApplicationStatus.OA2, now + timedelta(days=2)),
            (ApplicationStatus.INTERVIEW, now + timedelta(days=3)),
        ],
    )

    sync_db.commit()

    result = compute_analytics(sync_db, user.id)
    rates = result["conversion_rates"]

    assert rates["APPLIED_to_OA1"] is not None
    assert rates["OA2_to_INTERVIEW"] is not None


def test_avg_time_per_status_attributes_time_to_previous_status(sync_db):
    user = _make_user(
        sync_db,
        f"avgtime-{datetime.now(timezone.utc).timestamp()}@example.com",
    )
    now = datetime.now(timezone.utc)

    _make_application_with_history(
        sync_db,
        user,
        "PrecisionTestCo",
        [
            (ApplicationStatus.APPLIED, now),
            (
                ApplicationStatus.OA1,
                now + timedelta(days=3),
            ),
        ],
    )

    sync_db.commit()

    result = compute_analytics(sync_db, user.id)
    averages = result["avg_time_per_status_days"]

    # The application spent three days in APPLIED.
    assert averages["APPLIED"] == 3.0

    # There is no completed interval for OA1 yet.
    assert "OA1" not in averages


def test_ghosting_rate_reflects_new_ghosted_and_rejected(sync_db):
    email = (
        f"ghosting-{datetime.now(timezone.utc).timestamp()}@example.com"
    )
    user = _make_user(sync_db, email)

    baseline = compute_analytics(
        sync_db, user.id
    )["ghosting_rate"]

    now = datetime.now(timezone.utc)

    _make_application_with_history(
        sync_db,
        user,
        "GhostCo",
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.GHOSTED, now + timedelta(days=1)),
        ],
    )

    _make_application_with_history(
        sync_db,
        user,
        "RejectCo",
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.REJECTED, now + timedelta(days=1)),
        ],
    )

    sync_db.commit()

    result = compute_analytics(
        sync_db, user.id
    )["ghosting_rate"]

    assert result["ghosted"] - baseline["ghosted"] == 1
    assert result["rejected"] - baseline["rejected"] == 1


def test_response_rate_by_company_merges_casing(sync_db):
    email = (
        f"casing-{datetime.now(timezone.utc).timestamp()}@example.com"
    )
    user = _make_user(sync_db, email)
    now = datetime.now(timezone.utc)
    unique_company = f"CasingTestCo-{user.id}"

    _make_application_with_history(
        sync_db,
        user,
        unique_company,
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.OA1, now + timedelta(days=1)),
        ],
    )

    _make_application_with_history(
        sync_db,
        user,
        unique_company.lower(),
        [
            (ApplicationStatus.APPLIED, now),
        ],
    )

    sync_db.commit()

    result = compute_analytics(sync_db, user.id)

    matches = [
        row
        for row in result["response_rate_by_company"]
        if row["company_name"] == unique_company.lower()
    ]

    assert len(matches) == 1
    assert matches[0]["total_applications"] == 2
    assert matches[0]["responded"] == 1


def test_analytics_are_isolated_between_users(sync_db):
    now = datetime.now(timezone.utc)

    user_a = _make_user(
        sync_db,
        "user-a-isolation@example.com",
    )
    user_b = _make_user(
        sync_db,
        "user-b-isolation@example.com",
    )

    _make_application_with_history(
        sync_db,
        user_a,
        "CompanyA",
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.OA1, now + timedelta(days=1)),
        ],
    )

    _make_application_with_history(
        sync_db,
        user_b,
        "CompanyB",
        [
            (ApplicationStatus.APPLIED, now),
            (ApplicationStatus.GHOSTED, now + timedelta(days=2)),
        ],
    )

    sync_db.commit()

    analytics_a = compute_analytics(sync_db, user_a.id)
    analytics_b = compute_analytics(sync_db, user_b.id)

    # Current status counts must be specific to each user.
    assert analytics_a["funnel_counts"]["OA1"] == 1
    assert analytics_a["funnel_counts"]["GHOSTED"] == 0

    assert analytics_b["funnel_counts"]["OA1"] == 0
    assert analytics_b["funnel_counts"]["GHOSTED"] == 1

    # Ghosting metrics must not include another user's applications.
    assert analytics_a["ghosting_rate"]["ghosted"] == 0
    assert analytics_a["ghosting_rate"]["rejected"] == 0

    assert analytics_b["ghosting_rate"]["ghosted"] == 1
    assert analytics_b["ghosting_rate"]["rejected"] == 0

    # Company-level analytics must not expose another user's companies.
    companies_a = {
        row["company_name"]
        for row in analytics_a["response_rate_by_company"]
    }

    companies_b = {
        row["company_name"]
        for row in analytics_b["response_rate_by_company"]
    }

    assert "companya" in companies_a
    assert "companyb" not in companies_a

    assert "companyb" in companies_b
    assert "companya" not in companies_b