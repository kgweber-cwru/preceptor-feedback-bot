"""
Authentication service for Google OAuth 2.0 with PKCE and JWT token management.
Handles OAuth flow, token exchange, JWT generation/validation, and domain restriction.
"""

import hashlib
import secrets
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings


class AuthService:
    """Service for handling OAuth and JWT authentication"""

    @staticmethod
    def generate_pkce_pair() -> tuple[str, str]:
        """
        Generate PKCE code_verifier and code_challenge pair.

        Returns:
            tuple: (code_verifier, code_challenge)
        """
        # Generate random code_verifier (43-128 characters)
        code_verifier = urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")

        # Generate code_challenge using SHA256
        challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")

        return code_verifier, code_challenge

    @staticmethod
    def generate_state_token() -> str:
        """
        Generate CSRF state token for OAuth flow.

        Returns:
            str: Random state token
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def build_oauth_url(code_challenge: str, state: str) -> str:
        """
        Build Google OAuth authorization URL with PKCE parameters.

        Args:
            code_challenge: PKCE code challenge
            state: CSRF state token

        Returns:
            str: Complete OAuth authorization URL
        """
        params = {
            "client_id": settings.OAUTH_CLIENT_ID,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",  # Request refresh token
            "prompt": "select_account",  # Always show account selector
        }

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{settings.GOOGLE_AUTH_URL}?{query_string}"

    @staticmethod
    async def exchange_code_for_tokens(
        authorization_code: str, code_verifier: str
    ) -> dict:
        """
        Exchange authorization code for access and ID tokens.

        Args:
            authorization_code: Authorization code from OAuth callback
            code_verifier: PKCE code verifier

        Returns:
            dict: Token response containing id_token, access_token, etc.

        Raises:
            Exception: If token exchange fails
        """
        import httpx

        token_data = {
            "client_id": settings.OAUTH_CLIENT_ID,
            "client_secret": settings.OAUTH_CLIENT_SECRET,
            "code": authorization_code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.GOOGLE_TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise Exception(f"Token exchange failed: {response.text}")

            return response.json()

    @staticmethod
    def verify_google_id_token(id_token_str: str) -> dict:
        """
        Verify and decode Google ID token.

        Args:
            id_token_str: Google ID token JWT

        Returns:
            dict: Decoded token payload with user info

        Raises:
            ValueError: If token verification fails
        """
        try:
            # Verify token with Google's public keys
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.OAUTH_CLIENT_ID,
            )

            # Verify issuer
            if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
                raise ValueError("Wrong issuer")

            return idinfo
        except Exception as e:
            raise ValueError(f"Invalid ID token: {e}")

    @staticmethod
    def check_domain_restriction(email: str) -> bool:
        """
        Check if user's email domain is allowed.

        Args:
            email: User email address

        Returns:
            bool: True if allowed, False if restricted
        """
        if not settings.OAUTH_DOMAIN_RESTRICTION:
            return True

        domain = email.split("@")[1] if "@" in email else ""
        return domain in settings.OAUTH_ALLOWED_DOMAINS

    @staticmethod
    def create_jwt_token(user_id: str, email: str, name: str, domain: str) -> str:
        """
        Create JWT access token for authenticated user.

        Args:
            user_id: Firestore user document ID
            email: User email
            name: User display name
            domain: Email domain

        Returns:
            str: JWT token
        """
        now = datetime.utcnow()
        expiration = now + timedelta(hours=settings.JWT_EXPIRATION_HOURS)

        payload = {
            "sub": user_id,
            "email": email,
            "name": name,
            "domain": domain,
            "iat": now,
            "exp": expiration,
        }

        token = jwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        return token

    @staticmethod
    def verify_jwt_token(token: str) -> Optional[dict]:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            dict: Decoded payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return payload
        except JWTError:
            return None

    @staticmethod
    def extract_user_info_from_id_token(idinfo: dict) -> dict:
        """
        Extract user information from verified Google ID token.

        Args:
            idinfo: Decoded ID token payload

        Returns:
            dict: User info with email, name, picture, domain
        """
        email = idinfo.get("email", "")
        domain = email.split("@")[1] if "@" in email else ""

        return {
            "email": email,
            "name": idinfo.get("name", ""),
            "picture_url": idinfo.get("picture"),
            "domain": domain,
        }
