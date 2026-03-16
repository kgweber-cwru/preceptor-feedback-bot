from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel


class HelpfulnessRating(str, Enum):
    """Rating options for chatbot helpfulness."""
    NOT_AT_ALL_HELPFUL = "Not at all helpful"
    SLIGHTLY_HELPFUL = "Slightly helpful"
    MODERATELY_HELPFUL = "Moderately helpful"
    VERY_HELPFUL = "Very helpful"
    EXTREMELY_HELPFUL = "Extremely helpful"


class LikelihoodRating(str, Enum):
    """Rating options for likelihood to use tool again."""
    VERY_UNLIKELY = "Very unlikely"
    UNLIKELY = "Unlikely"
    NEUTRAL = "Neutral"
    LIKELY = "Likely"
    VERY_LIKELY = "Very likely"


class SurveyBase(BaseModel):
    """Base survey fields."""
    helpfulness_rating: Optional[HelpfulnessRating] = None
    likelihood_rating: Optional[LikelihoodRating] = None
    comments: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None


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
