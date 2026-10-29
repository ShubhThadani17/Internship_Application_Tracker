import uuid
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.db.models import Application, StatusHistory
from app.domain.status import ApplicationStatus

FUNNEL_ORDER = [
    ApplicationStatus.APPLIED,
    ApplicationStatus.OA1,
    ApplicationStatus.OA2,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
]


def compute_analytics(db: Session, user_id: uuid.UUID) -> dict:
    funnel_counts = _compute_funnel_counts(db, user_id)
    reach_counts = _compute_reach_counts(db, user_id)
    conversion_rates = _compute_conversion_rates(reach_counts)
    avg_time = _compute_avg_time_per_status(db, user_id)
    ghosting_rate = _compute_ghosting_rate(db, user_id)
    response_rate = _compute_response_rate_by_company(db, user_id)

    return {
        "funnel_counts": funnel_counts,
        "conversion_rates": conversion_rates,
        "avg_time_per_status_days": avg_time,
        "ghosting_rate": ghosting_rate,
        "response_rate_by_company": response_rate,
    }


def _compute_funnel_counts(db: Session,user_id: uuid.UUID,) -> dict:
    result = db.execute(
        select(Application.current_status,func.count(Application.id),)
        .where(Application.user_id == user_id)
        .group_by(Application.current_status)
    )
    counts = {status.value: 0 for status in ApplicationStatus}
    for status, count in result.all():
        counts[status.value] = count
    return counts


def _compute_reach_counts(db: Session,user_id: uuid.UUID,) -> dict:
    result = db.execute(
        select(StatusHistory.to_status,func.count(func.distinct(StatusHistory.application_id)),)
        .join(Application,Application.id == StatusHistory.application_id,)
        .where(Application.user_id == user_id)
        .group_by(StatusHistory.to_status)
    )
    return {status.value: count
        for status, count in result.all()
    }


def _compute_conversion_rates(reach_counts: dict) -> dict:
    rates = {}
    for i in range(len(FUNNEL_ORDER) - 1):
        from_stage = FUNNEL_ORDER[i].value
        to_stage = FUNNEL_ORDER[i + 1].value
        from_count = reach_counts.get(from_stage, 0)
        to_count = reach_counts.get(to_stage, 0)
        rates[f"{from_stage}_to_{to_stage}"] = (
            round(to_count / from_count * 100, 1) if from_count > 0 else None
        )
    return rates


def _compute_avg_time_per_status(
    db: Session,
    user_id: uuid.UUID,
) -> dict:
    lag_expr = func.lag(StatusHistory.changed_at).over(
        partition_by=StatusHistory.application_id,
        order_by=StatusHistory.changed_at,
    )

    subquery = (
        select(
            StatusHistory.from_status.label("status"),
            (
                func.extract(
                    "epoch",
                    StatusHistory.changed_at - lag_expr,
                ) / 86400.0
            ).label("days_in_status"),
        )
        .join(
            Application,
            Application.id == StatusHistory.application_id,
        )
        .where(Application.user_id == user_id)
        .subquery()
    )

    result = db.execute(
        select(
            subquery.c.status,
            func.avg(subquery.c.days_in_status),
        )
        .where(subquery.c.days_in_status.isnot(None))
        .where(subquery.c.status.isnot(None))
        .group_by(subquery.c.status)
    )

    return {
        status.value: round(float(avg_days), 1)
        for status, avg_days in result.all()
    }

def _compute_ghosting_rate(db: Session,user_id: uuid.UUID,) -> dict:
    result = db.execute(
        select(func.count(case((Application.current_status== ApplicationStatus.GHOSTED,1,))),
            func.count(
                case((Application.current_status== ApplicationStatus.REJECTED,1,))),
        )
        .where(Application.user_id == user_id)
    )
    ghosted, rejected = result.one()
    total = ghosted + rejected
    return {
        "ghosted": ghosted,
        "rejected": rejected,
        "ghosting_rate_percent": (round(ghosted / total * 100, 1)
            if total > 0
            else None
        ),
    }


def _compute_response_rate_by_company(db: Session,user_id: uuid.UUID,) -> list[dict]:
    result = db.execute(
        select(
            func.lower(Application.company_name).label("company_name"),
            func.count(Application.id),
            func.count(case((Application.current_status!= ApplicationStatus.APPLIED,1,))
            ),
        )
        .where(Application.user_id == user_id)
        .group_by(func.lower(Application.company_name))
    )

    return [
        {
            "company_name": company,
            "total_applications": total,
            "responded": responded,
            "response_rate_percent": (
                round(responded / total * 100, 1)
                if total > 0
                else None
            ),
        }
        for company, total, responded in result.all()
    ]