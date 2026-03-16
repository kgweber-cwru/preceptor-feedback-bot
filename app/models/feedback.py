"""
Feedback models for storing generated feedback and refinements.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class FeedbackVersionType(str, Enum):
    """Type of feedback version"""

    INITIAL = "initial"
    REFINEMENT = "refinement"


class FeedbackVersion(BaseModel):
    """A version of feedback (initial or refined)"""

    version: int = Field(..., description="Version number (1-indexed)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    type: FeedbackVersionType = Field(..., description="Version type")
    content: str = Field(..., description="Feedback content")
    request: Optional[str] = Field(None, description="Refinement request (if type=refinement)")

    class Config:
        json_schema_extra = {
            "example": {
                "version": 1,
                "timestamp": "2025-01-20T14:15:00Z",
                "type": "initial",
                "content": "**Structured Summary**\n\n...",
                "request": None,
            }
        }


class Feedback(BaseModel):
    """Complete feedback model with version history"""

    feedback_id: str = Field(..., description="Firestore document ID")
    conversation_id: str = Field(..., description="Reference to conversation")
    user_id: str = Field(..., description="Reference to user who generated this")
    student_name: str = Field(..., description="Student being evaluated")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    versions: List[FeedbackVersion] = Field(default_factory=list)
    current_version: int = Field(default=1, description="Current active version number")

    class Config:
        json_schema_extra = {
            "example": {
                "feedback_id": "feedback_abc123",
                "conversation_id": "conv_xyz789",
                "user_id": "user_abc123",
                "student_name": "Sarah Chen",
                "generated_at": "2025-01-20T14:15:00Z",
                "updated_at": "2025-01-20T14:18:00Z",
                "versions": [
                    {
                        "version": 1,
                        "timestamp": "2025-01-20T14:15:00Z",
                        "type": "initial",
                        "content": "**Structured Summary**\n\n...",
                        "request": None,
                    }
                ],
                "current_version": 1,
            }
        }

    def get_current_content(self) -> Optional[str]:
        """Get content of current version"""
        for version in self.versions:
            if version.version == self.current_version:
                return version.content
        return None


class FeedbackRefinementRequest(BaseModel):
    """Model for requesting feedback refinement"""

    refinement_request: str = Field(..., min_length=1, max_length=1000)


class FeedbackPublic(BaseModel):
    """Public feedback info (for API responses)"""

    feedback_id: str
    conversation_id: str
    student_name: str
    content: str
    version: int
    generated_at: datetime
    updated_at: datetime
