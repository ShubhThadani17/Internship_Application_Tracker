from app.domain.status import ApplicationStatus

STAGE_KEYWORDS = {
    "oa": ApplicationStatus.OA1,
    "online assessment": ApplicationStatus.OA1,
    "interview": ApplicationStatus.INTERVIEW,
    "offer": ApplicationStatus.OFFER,
    "rejected": ApplicationStatus.REJECTED,
    "reject": ApplicationStatus.REJECTED,
}


def resolve_status(extracted_stage: str | None, current_status: ApplicationStatus | None) -> ApplicationStatus | None:
    if not extracted_stage:
        return None

    stage_lower = extracted_stage.lower()

    matched_status = None
    for keyword, status in STAGE_KEYWORDS.items():
        if keyword in stage_lower:
            matched_status = status
            break

    if matched_status is None:
        return None

    if matched_status == ApplicationStatus.OA1 and current_status == ApplicationStatus.OA1:
        return ApplicationStatus.OA2

    return matched_status