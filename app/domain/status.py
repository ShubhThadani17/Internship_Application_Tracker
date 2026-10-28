from enum import Enum

#used str instead of Enum for better serialization and deserialization
class ApplicationStatus(str, Enum):   #enum- to define a set of named constant values
    APPLIED = "APPLIED"               #makes code more readable and prevents the use of arbitrary values.
    OA1 = "OA1"
    OA2 = "OA2"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    GHOSTED = "GHOSTED"