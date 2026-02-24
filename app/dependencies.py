"""
Dependency injection functions for FastAPI routes.
Provides common dependencies like current user, Firestore client, etc.
"""

from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.firestore_service import FirestoreService
from app.utils.markdown import markdown_to_html
from app.utils.time_formatting import timeago

# Shared Jinja2Templates instance — globals and filters are registered once here
# so all routes see the same values regardless of which router handles the request.
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["app_name"] = settings.APP_NAME
templates.env.globals["version"] = settings.APP_VERSION
templates.env.filters["markdown"] = markdown_to_html
templates.env.filters["timeago"] = timeago


def get_current_user(request: Request) -> dict:
    """
    Dependency: Get current authenticated user from request state.
    Raises 401 if not authenticated (unless OAuth is disabled for testing).

    Args:
        request: FastAPI request with auth middleware applied

    Returns:
        dict: User info from JWT or mock user if OAuth disabled

    Raises:
        HTTPException: 401 if not authenticated
    """
    from app.config import settings

    # If OAuth is completely disabled, use a mock user for testing
    if not settings.OAUTH_CLIENT_ID or not settings.OAUTH_DOMAIN_RESTRICTION:
        # Return a mock user for testing when OAuth is disabled
        return {
            "user_id": "test-user-001",
            "email": "test@example.com",
            "name": "Test User (OAuth Disabled)",
            "domain": "example.com",
        }

    if not request.state.authenticated or not request.state.user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return request.state.user


def get_current_user_optional(request: Request) -> Optional[dict]:
    """
    Dependency: Get current user if authenticated, None otherwise.
    Does not raise exception for unauthenticated requests.

    Args:
        request: FastAPI request

    Returns:
        dict: User info if authenticated, None otherwise
    """
    if request.state.authenticated and request.state.user:
        return request.state.user
    return None


def get_firestore() -> FirestoreService:
    """
    Dependency: Get Firestore service instance.

    Returns:
        FirestoreService: Initialized Firestore client
    """
    return FirestoreService()


def get_current_user_id(current_user: dict = Depends(get_current_user)) -> str:
    """
    Dependency: Get current user's ID.

    Args:
        current_user: User dict from get_current_user dependency

    Returns:
        str: User ID
    """
    return current_user["user_id"]
