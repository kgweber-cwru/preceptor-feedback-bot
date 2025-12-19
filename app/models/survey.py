from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel


class ToolRating(str, Enum):
    """Rating options for tool usefulness survey."""
    GREAT_FIRST_TRY = "Was great on the first try"
    HELPFUL_WITH_EDITS = "Gave me something helpful I can edit"
    NOT_HELPFUL = "Not especially helpful"


class SurveyBase(BaseModel):
    """Base survey fields."""
    preceptor_name: Optional[str] = None
    tool_rating: ToolRating
    comments: Optional[str] = None


class SurveyCreate(SurveyBase):
    """Survey creation request."""
    pass


class Survey(SurveyBase):
    """Complete survey record stored in Firestore."""
    survey_id: str
    conversation_id: str
    user_id: str
    student_name: str
    submitted_at: datetime
    skipped: bool = False

    class Config:
        from_attributes = True
