from app.domain.status import ApplicationStatus

# Creating your own custom exception.
class InvalidTransitionError(Exception):
    def __init__(self, current: ApplicationStatus, target: ApplicationStatus):
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current.value} to {target.value}") #constructor
        #super() - lets your child class access functionality from its parent class.
        
#creating a dictionary to define valid transitions.
#used set instead of list for faster lookup times 
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.APPLIED: {
        ApplicationStatus.OA1,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.GHOSTED,
    },
    ApplicationStatus.OA1: {
        ApplicationStatus.OA2,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.GHOSTED,
    },
    ApplicationStatus.OA2: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.GHOSTED,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.OFFER: {
        ApplicationStatus.WITHDRAWN,
    },
    #terminal states
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.WITHDRAWN: set(),
    ApplicationStatus.GHOSTED: set(),
}


def transition(current: ApplicationStatus, target: ApplicationStatus) -> ApplicationStatus: #return an ApplicationStatus
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError(current, target)
    return target