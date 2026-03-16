"""
Authentication middleware for validating JWT tokens.
Injects current_user into request state for authenticated routes.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.services.auth_service import AuthService


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JWT tokens and inject user info into request state.
    Does not block unauthenticated requests - use dependencies for that.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and inject user if authenticated.

        Args:
            request: FastAPI request
            call_next: Next middleware/route handler

        Returns:
            Response from next handler
        """
        # Get JWT from cookie
        token = request.cookies.get(settings.SESSION_COOKIE_NAME)

        # Initialize request state
        request.state.user = None
        request.state.authenticated = False

        if token:
            # Verify token
            auth_service = AuthService()
            payload = auth_service.verify_jwt_token(token)

            if payload:
                # Valid token - inject user info
                request.state.user = {
                    "user_id": payload.get("sub"),
                    "email": payload.get("email"),
                    "name": payload.get("name"),
                    "domain": payload.get("domain"),
                }
                request.state.authenticated = True

        # Continue to next handler
        response = await call_next(request)
        return response
