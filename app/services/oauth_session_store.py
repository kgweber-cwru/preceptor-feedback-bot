"""
Firestore-backed session store for OAuth state and PKCE verifiers.
Used to work around Safari's aggressive cookie blocking in OAuth flows.

IMPORTANT: Uses Firestore instead of in-memory storage to support
multiple Cloud Run instances (sessions must be shared across instances).
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass
from google.cloud import firestore


@dataclass
class OAuthSession:
    """OAuth session data"""
    state: str
    code_verifier: str
    created_at: datetime


class OAuthSessionStore:
    """
    Firestore-backed store for OAuth sessions.

    Safari's Intelligent Tracking Prevention blocks cookies with samesite=none,
    even when secure=True. This breaks traditional cookie-based OAuth flows.

    Solution: Store state and code_verifier in Firestore, use state as lookup key.
    Firestore ensures sessions are available across all Cloud Run instances.
    """

    def __init__(self, ttl_seconds: int = 600):
        """
        Initialize session store.

        Args:
            ttl_seconds: Time-to-live for sessions (default 10 minutes)
        """
        self._db = firestore.Client()
        self._collection = self._db.collection("oauth_sessions")
        self._ttl_seconds = ttl_seconds

    def create_session(self, state: str, code_verifier: str) -> str:
        """
        Create a new OAuth session in Firestore.

        Args:
            state: CSRF state token (used as document ID)
            code_verifier: PKCE code verifier

        Returns:
            state: The state token (for consistency with old API)
        """
        # Store session in Firestore using state as document ID
        session_data = {
            "state": state,
            "code_verifier": code_verifier,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        self._collection.document(state).set(session_data)

        print(f"[OAuth Session] Created Firestore session: {state[:20]}...")
        return state

    def get_session(self, state: str) -> Optional[OAuthSession]:
        """
        Retrieve OAuth session data from Firestore.

        Args:
            state: State token used as document ID

        Returns:
            OAuthSession if found and not expired, None otherwise
        """
        doc_ref = self._collection.document(state)
        doc = doc_ref.get()

        if not doc.exists:
            print(f"[OAuth Session] Session not found in Firestore: {state[:20]}...")
            return None

        data = doc.to_dict()
        created_at = data.get("created_at")

        # Check if expired (use timezone-aware datetime to match Firestore timestamps)
        if created_at:
            age = datetime.now(timezone.utc) - created_at
            if age.total_seconds() > self._ttl_seconds:
                # Remove expired session
                print(f"[OAuth Session] Session expired, deleting: {state[:20]}...")
                doc_ref.delete()
                return None

        print(f"[OAuth Session] Session found in Firestore: {state[:20]}...")
        return OAuthSession(
            state=data.get("state"),
            code_verifier=data.get("code_verifier"),
            created_at=created_at or datetime.now(timezone.utc),
        )

    def delete_session(self, state: str):
        """
        Delete a session from Firestore (called after successful OAuth callback).

        Args:
            state: State token used as document ID
        """
        self._collection.document(state).delete()
        print(f"[OAuth Session] Deleted session: {state[:20]}...")

    def cleanup_expired_sessions(self):
        """
        Remove expired sessions from Firestore to prevent storage bloat.
        Should be called periodically (e.g., via Cloud Scheduler).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._ttl_seconds)

        # Query expired sessions
        expired_query = self._collection.where("created_at", "<", cutoff).stream()

        count = 0
        for doc in expired_query:
            doc.reference.delete()
            count += 1

        if count > 0:
            print(f"[OAuth Session] Cleaned up {count} expired sessions")


# Global singleton instance
_oauth_store = None


def get_oauth_store() -> OAuthSessionStore:
    """Get the global OAuth session store instance."""
    global _oauth_store
    if _oauth_store is None:
        _oauth_store = OAuthSessionStore()
    return _oauth_store
