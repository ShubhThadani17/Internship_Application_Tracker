from app.domain.status_resolver import resolve_status
from app.domain.status import ApplicationStatus


def test_resolve_oa_with_no_prior_status_returns_oa1():
    assert resolve_status("OA", None) == ApplicationStatus.OA1


def test_resolve_oa_with_current_oa1_returns_oa2():
    assert resolve_status("OA", ApplicationStatus.OA1) == ApplicationStatus.OA2


def test_resolve_online_assessment_phrase_returns_oa1():
    assert resolve_status("Online Assessment", None) == ApplicationStatus.OA1


def test_resolve_interview_returns_interview():
    assert resolve_status("Technical Interview", ApplicationStatus.OA2) == ApplicationStatus.INTERVIEW


def test_resolve_offer_returns_offer():
    assert resolve_status("We are happy to offer you", ApplicationStatus.INTERVIEW) == ApplicationStatus.OFFER


def test_resolve_rejected_returns_rejected():
    assert resolve_status("Unfortunately you were rejected", ApplicationStatus.OA1) == ApplicationStatus.REJECTED


def test_resolve_none_stage_returns_none():
    assert resolve_status(None, ApplicationStatus.OA1) is None


def test_resolve_unrecognized_stage_returns_none():
    assert resolve_status("some random gibberish text", ApplicationStatus.OA1) is None