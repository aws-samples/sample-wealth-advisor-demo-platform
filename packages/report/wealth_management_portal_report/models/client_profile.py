# Client profile data contract
from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class RiskProfile(StrEnum):
    """Investment risk tolerance level assigned to the client."""

    CONSERVATIVE = "Conservative"
    MODERATE = "Moderate"
    AGGRESSIVE = "Aggressive"


class ServiceModel(StrEnum):
    """How the advisor manages the client's portfolio."""

    DISCRETIONARY = "Discretionary"
    ADVISORY = "Advisory"
    SELF_DIRECTED = "Self-Directed"


class ActivityLevel(StrEnum):
    """Frequency of client trading activity."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Sophistication(StrEnum):
    """Client's financial literacy and investment knowledge."""

    BASIC = "Basic"
    INTERMEDIATE = "Intermediate"
    SOPHISTICATED = "Sophisticated"


class DocumentLink(BaseModel):
    """Reference to a client-related document."""

    label: str
    url: str


class AssociatedAccount(BaseModel):
    """
    Linked account or business relationship.
    Represents additional accounts, trusts, or business entities connected to the client.
    """

    account_type: str
    value: float
    description: str | None = None
    currency: str = "USD"  # reference currency
    risk_profile: str | None = None  # account-level risk profile
    inception_date: date | None = None  # when the account was opened


class ClientProfile(BaseModel):
    """
    Core client identity and preferences.
    Contains demographic info, service configuration, and investment constraints.
    """

    client_id: str
    names: list[str]
    dates_of_birth: list[date]
    client_since: date
    aum: float
    risk_profile: RiskProfile
    service_model: ServiceModel
    activity_level: ActivityLevel
    sophistication: Sophistication
    qualified_investor: bool
    domicile: str  # e.g., "US", "CH"
    tax_jurisdiction: str  # e.g., "US - Florida", "CH - Zurich"
    restrictions: list[str]  # e.g., ["ESG only", "No EUR assets"]
    document_links: list[DocumentLink] = []  # investor profile, guidelines, brochure
    associated_accounts: list[AssociatedAccount]
