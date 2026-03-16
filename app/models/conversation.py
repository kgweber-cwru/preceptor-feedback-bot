"""
Conversation and message models for storing chat interactions.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role enumeration"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ConversationStatus(str, Enum):
    """Conversation status enumeration"""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Message(BaseModel):
    """Individual message in a conversation"""

    message_id: str = Field(..., description="Unique message identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    turn: int | str = Field(..., description="Turn number or special marker (feedback_generation, etc.)")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    response_time_ms: Optional[float] = Field(None, description="Response time for assistant messages")

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_abc123",
                "timestamp": "2025-01-20T14:00:15Z",
                "turn": 1,
                "role": "user",
                "content": "The student demonstrated excellent clinical reasoning.",
                "response_time_ms": None,
            }
        }


class ConversationMetadata(BaseModel):
    """Metadata about the conversation"""

    model: str = Field(..., description="AI model used")
    total_turns: int = Field(default=0, description="Number of conversation turns")
    project_id: str = Field(..., description="GCP project ID")
    environment: str = Field(..., description="Deployment environment")


class Conversation(BaseModel):
    """Complete conversation model"""

    conversation_id: str = Field(..., description="Firestore document ID")
    user_id: str = Field(..., description="Reference to user who created this")
    student_name: str = Field(..., description="Student being evaluated")
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: ConversationMetadata
    messages: List[Message] = Field(default_factory=list)
    has_feedback: bool = Field(default=False, description="Whether feedback has been generated")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_xyz789",
                "user_id": "user_abc123",
                "student_name": "Sarah Chen",
                "status": "active",
                "created_at": "2025-01-20T14:00:00Z",
                "updated_at": "2025-01-20T14:15:00Z",
                "metadata": {
                    "model": "gemini-2.5-flash",
                    "total_turns": 5,
                    "project_id": "meded-gcp-sandbox",
                    "environment": "cloud",
                },
                "messages": [],
            }
        }


class ConversationCreate(BaseModel):
    """Model for creating a new conversation"""

    student_name: str = Field(..., min_length=1, max_length=200)


class ConversationSummary(BaseModel):
    """Summary of a conversation for list views"""

    conversation_id: str
    student_name: str
    status: ConversationStatus
    total_turns: int
    last_message_preview: Optional[str] = Field(None, description="Preview of last message")
    created_at: datetime
    updated_at: datetime
    has_feedback: bool = Field(default=False, description="Whether feedback has been generated")
    feedback_preview: Optional[str] = Field(None, description="Short preview of feedback content")


class MessageCreate(BaseModel):
    """Model for creating a new message"""

    content: str = Field(..., min_length=1, max_length=10000)
