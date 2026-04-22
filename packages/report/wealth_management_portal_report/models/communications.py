# Communications data contract
from datetime import date

from pydantic import BaseModel


class Meeting(BaseModel):
    """
    Record of a client meeting.
    Contains date, format, and advisor notes from the interaction.
    """

    date: date
    meeting_type: str  # e.g., "In-Person", "Video", "Phone"
    subject: str
    notes: str


class Email(BaseModel):
    """
    Email communication with the client.
    Captures key correspondence for context and follow-up tracking.
    """

    date: date
    subject: str
    body: str


class Task(BaseModel):
    """
    Action item related to the client.
    Tracks commitments, follow-ups, and their completion status.
    """

    due_date: date
    subject: str
    summary: str
    status: str  # e.g., "Pending", "Completed", "Overdue"


class Communications(BaseModel):
    """
    Complete communication history with a client.
    Aggregates meetings, emails, and tasks for relationship context.
    """

    meetings: list[Meeting]
    emails: list[Email]
    tasks: list[Task]
