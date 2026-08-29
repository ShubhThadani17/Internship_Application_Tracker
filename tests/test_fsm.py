import pytest

from app.domain.status import ApplicationStatus
from app.domain.fsm import (
    InvalidTransitionError,
    transition,
)


# ---------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "current,target",
    [
        # APPLIED
        (ApplicationStatus.APPLIED, ApplicationStatus.OA1),
        (ApplicationStatus.APPLIED, ApplicationStatus.REJECTED),
        (ApplicationStatus.APPLIED, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.APPLIED, ApplicationStatus.GHOSTED),

        # OA1
        (ApplicationStatus.OA1, ApplicationStatus.OA2),
        (ApplicationStatus.OA1, ApplicationStatus.REJECTED),
        (ApplicationStatus.OA1, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.OA1, ApplicationStatus.GHOSTED),

        # OA2
        (ApplicationStatus.OA2, ApplicationStatus.INTERVIEW),
        (ApplicationStatus.OA2, ApplicationStatus.REJECTED),
        (ApplicationStatus.OA2, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.OA2, ApplicationStatus.GHOSTED),

        # INTERVIEW
        (ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER),
        (ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED),
        (ApplicationStatus.INTERVIEW, ApplicationStatus.WITHDRAWN),

        # OFFER
        (ApplicationStatus.OFFER, ApplicationStatus.WITHDRAWN),
    ],
)
def test_valid_transitions(current, target):
    result = transition(current, target)

    assert result == target


# ---------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "current,target",
    [
        # APPLIED cannot skip directly to OA2, INTERVIEW, or OFFER
        (ApplicationStatus.APPLIED, ApplicationStatus.OA2),
        (ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW),
        (ApplicationStatus.APPLIED, ApplicationStatus.OFFER),

        # OA1 cannot skip OA2
        (ApplicationStatus.OA1, ApplicationStatus.INTERVIEW),
        (ApplicationStatus.OA1, ApplicationStatus.OFFER),

        # OA2 cannot skip directly to OFFER
        (ApplicationStatus.OA2, ApplicationStatus.OFFER),

        # INTERVIEW cannot go backwards
        (ApplicationStatus.INTERVIEW, ApplicationStatus.APPLIED),
        (ApplicationStatus.INTERVIEW, ApplicationStatus.OA1),
        (ApplicationStatus.INTERVIEW, ApplicationStatus.OA2),

        # OFFER cannot go backwards
        (ApplicationStatus.OFFER, ApplicationStatus.APPLIED),
        (ApplicationStatus.OFFER, ApplicationStatus.INTERVIEW),

        # Terminal states cannot transition anywhere
        (ApplicationStatus.REJECTED, ApplicationStatus.APPLIED),
        (ApplicationStatus.REJECTED, ApplicationStatus.OFFER),

        (ApplicationStatus.WITHDRAWN, ApplicationStatus.APPLIED),
        (ApplicationStatus.WITHDRAWN, ApplicationStatus.INTERVIEW),

        (ApplicationStatus.GHOSTED, ApplicationStatus.APPLIED),
        (ApplicationStatus.GHOSTED, ApplicationStatus.OFFER),
    ],
)
def test_invalid_transitions(current, target):
    with pytest.raises(InvalidTransitionError):
        transition(current, target)

@pytest.mark.parametrize(
    "status",
    list(ApplicationStatus),
)
def test_self_transition_is_invalid(status):
    with pytest.raises(InvalidTransitionError):
        transition(status, status)
# ---------------------------------------------------------
# Exception details
# ---------------------------------------------------------

def test_invalid_transition_error_contains_current_and_target():
    current = ApplicationStatus.APPLIED
    target = ApplicationStatus.OFFER

    with pytest.raises(InvalidTransitionError) as exc_info:
        transition(current, target)

    error = exc_info.value

    assert error.current == current
    assert error.target == target


def test_invalid_transition_error_message():
    with pytest.raises(InvalidTransitionError) as exc_info:
        transition(
            ApplicationStatus.APPLIED,
            ApplicationStatus.OFFER,
        )

    assert str(exc_info.value) == (
        "Cannot transition from APPLIED to OFFER"
    )