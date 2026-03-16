"""
User models for authentication and profile management.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """User profile model"""

    user_id: str = Field(..., description="Firestore document ID")
    email: EmailStr = Field(..., description="User email from OAuth")
    name: str = Field(..., description="User display name")
    domain: str = Field(..., description="Email domain (e.g., case.edu)")
    picture_url: Optional[str] = Field(None, description="Profile picture URL from OAuth")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "abc123",
                "email": "faculty@case.edu",
                "name": "Dr. Jane Smith",
                "domain": "case.edu",
                "picture_url": "https://lh3.googleusercontent.com/...",
                "created_at": "2025-01-15T10:30:00Z",
                "last_login": "2025-01-20T14:45:00Z",
            }
        }


class UserCreate(BaseModel):
    """Model for creating a new user"""

    email: EmailStr
    name: str
    domain: str
    picture_url: Optional[str] = None


class UserInDB(User):
    """User model as stored in Firestore (includes internal fields)"""

    pass


class UserPublic(BaseModel):
    """Public user info (for API responses)"""

    user_id: str
    email: EmailStr
    name: str
    picture_url: Optional[str] = None
    last_login: datetime
