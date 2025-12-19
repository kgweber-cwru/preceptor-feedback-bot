"""
In-memory session store for OAuth state and PKCE verifiers.
Used to work around Safari's aggressive cookie blocking in OAuth flows.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass


@dataclass
class OAuthSession:
    """OAuth session data"""
    state: str
    code_verifier: str
    created_at: datetime


class OAuthSessionStore:
    """
    In-memory store for OAuth sessions.

    Safari's Intelligent Tracking Prevention blocks cookies with samesite=none,
    even when secure=True. This breaks traditional cookie-based OAuth flows.

    Solution: Store state and code_verifier server-side, use state as lookup key.
    """

    def __init__(self, ttl_seconds: int = 600):
        """
        Initialize session store.

        Args:
            ttl_seconds: Time-to-live for sessions (default 10 minutes)
        """
        self._sessions: dict[str, OAuthSession] = {}
        self._ttl_seconds = ttl_seconds

    def create_session(self, state: str, code_verifier: str) -> str:
        """
        Create a new OAuth session.

        Args:
            state: CSRF state token (used as session key)
            code_verifier: PKCE code verifier

        Returns:
            state: The state token (for consistency with old API)
        """
        # Clean up expired sessions
        self._cleanup_expired()

        # Store session using state as key
        self._sessions[state] = OAuthSession(
            state=state,
            code_verifier=code_verifier,
            created_at=datetime.utcnow(),
        )

        return state

    def get_session(self, state: str) -> Optional[OAuthSession]:
        """
        Retrieve OAuth session data.

        Args:
            state: State token used as session key

        Returns:
            OAuthSession if found and not expired, None otherwise
        """
        session = self._sessions.get(state)

        if not session:
            return None

        # Check if expired
        age = datetime.utcnow() - session.created_at
        if age.total_seconds() > self._ttl_seconds:
            # Remove expired session
            self._sessions.pop(state, None)
            return None

        return session

    def delete_session(self, state: str):
        """
        Delete a session (called after successful OAuth callback).

        Args:
            state: State token used as session key
        """
        self._sessions.pop(state, None)

    def _cleanup_expired(self):
        """Remove expired sessions to prevent memory leaks."""
        now = datetime.utcnow()
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if (now - session.created_at).total_seconds() > self._ttl_seconds
        ]
        for sid in expired_ids:
            self._sessions.pop(sid, None)


# Global singleton instance
_oauth_store = OAuthSessionStore()


def get_oauth_store() -> OAuthSessionStore:
    """Get the global OAuth session store instance."""
    return _oauth_store
