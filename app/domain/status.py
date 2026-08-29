from enum import Enum

#used str instead of Enum for better serialization and deserialization
class ApplicationStatus(str, Enum):
    APPLIED = "APPLIED"
    OA1 = "OA1"
    OA2 = "OA2"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    GHOSTED = "GHOSTED"