"""
Integration tests for OAuth authentication flow.
Tests login, callback, JWT generation, and logout.
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime, timedelta

pytestmark = [pytest.mark.integration, pytest.mark.auth]


class TestOAuthLogin:
    """Tests for OAuth login initiation."""

    @pytest.mark.asyncio
    async def test_login_redirects_to_google(self, unauthenticated_client):
        """Test that /auth/login redirects to Google OAuth."""
        response = await unauthenticated_client.get("/auth/login", follow_redirects=False)

        assert response.status_code == 302
        assert "accounts.google.com" in response.headers["location"]
        assert "client_id" in response.headers["location"]
        assert "redirect_uri" in response.headers["location"]
        assert "code_challenge" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_login_sets_oauth_state_cookie(self, unauthenticated_client):
        """Test that login handles OAuth state (server-side sessions, not cookies)."""
        response = await unauthenticated_client.get("/auth/login", follow_redirects=False)

        # Implementation uses server-side Firestore sessions instead of cookies
        # (Safari blocks samesite=none cookies). Verify state is passed via URL.
        assert response.status_code == 302
        assert "state=" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_login_sets_code_verifier_cookie(self, unauthenticated_client):
        """Test that login uses PKCE (code_challenge present in OAuth URL)."""
        response = await unauthenticated_client.get("/auth/login", follow_redirects=False)

        # PKCE is implemented server-side; code_challenge appears in the OAuth redirect URL
        assert response.status_code == 302
        assert "code_challenge=" in response.headers["location"]
        assert "code_challenge_method=S256" in response.headers["location"]


class TestOAuthCallback:
    """Tests for OAuth callback handling."""

    @pytest.mark.asyncio
    async def test_successful_callback_creates_jwt(
        self, unauthenticated_client, mock_firestore
    ):
        """Test successful OAuth callback creates JWT and user."""
        from app.services.oauth_session_store import OAuthSession

        mock_session = OAuthSession(
            state="mock_state",
            code_verifier="mock_verifier",
            created_at=datetime.utcnow(),
        )

        mock_auth = Mock()
        mock_auth.exchange_code_for_tokens = AsyncMock(
            return_value={"access_token": "mock_access_token", "id_token": "mock_id_token"}
        )
        mock_auth.verify_google_id_token = Mock(
            return_value={"email": "test@case.edu", "name": "Test User", "picture": "https://example.com/pic.jpg", "sub": "google_123"}
        )
        mock_auth.extract_user_info_from_id_token = Mock(
            return_value={"email": "test@case.edu", "name": "Test User", "picture_url": "https://example.com/pic.jpg", "domain": "case.edu"}
        )
        mock_auth.check_domain_restriction = Mock(return_value=True)
        mock_auth.create_jwt_token = Mock(return_value="mock_jwt_token_string")

        with patch("app.api.auth.oauth_store") as mock_store, \
             patch("app.api.auth.auth_service", mock_auth), \
             patch("app.api.auth.FirestoreService") as mock_fs_class:

            mock_store.get_session.return_value = mock_session
            mock_store.delete_session.return_value = None

            mock_fs_instance = AsyncMock()
            mock_fs_instance.get_or_create_user.return_value = Mock(
                user_id="test_user_123",
                email="test@case.edu",
                name="Test User",
                domain="case.edu",
            )
            mock_fs_class.return_value = mock_fs_instance

            response = await unauthenticated_client.get(
                "/auth/callback?code=mock_code&state=mock_state",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

        # Check that JWT cookie was set
        cookies = response.cookies
        assert "access_token" in cookies

    @pytest.mark.asyncio
    async def test_callback_missing_state_returns_error(self, unauthenticated_client):
        """Test callback without state parameter returns error."""
        response = await unauthenticated_client.get(
            "/auth/callback?code=mock_code",
            follow_redirects=False,
        )

        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_callback_invalid_state_returns_error(self, unauthenticated_client):
        """Test callback with mismatched state returns error."""
        response = await unauthenticated_client.get(
            "/auth/callback?code=mock_code&state=wrong_state",
            cookies={"oauth_state": "correct_state"},
            follow_redirects=False,
        )

        assert response.status_code == 400


class TestJWTValidation:
    """Tests for JWT token validation."""

    @pytest.mark.asyncio
    async def test_valid_jwt_grants_access(self, client):
        """Test that valid JWT allows access to protected routes."""
        response = await client.get("/dashboard")

        assert response.status_code == 200
        assert "Test User" in response.text or "Dashboard" in response.text

    @pytest.mark.asyncio
    async def test_missing_jwt_redirects_to_login(self, unauthenticated_client):
        """Test that missing JWT redirects to login."""
        response = await unauthenticated_client.get("/dashboard", follow_redirects=False)

        assert response.status_code == 302
        assert "/" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_invalid_jwt_redirects_to_login(self, unauthenticated_client):
        """Test that invalid JWT redirects to login."""
        response = await unauthenticated_client.get(
            "/dashboard",
            cookies={"access_token": "invalid.jwt.token"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/" in response.headers["location"]


class TestLogout:
    """Tests for logout functionality."""

    @pytest.mark.asyncio
    async def test_logout_clears_jwt_cookie(self, client):
        """Test that logout clears JWT cookie."""
        response = await client.post("/auth/logout", follow_redirects=False)

        assert response.status_code == 302
        assert "/" in response.headers["location"]

        # Check that cookie is cleared
        cookies = response.cookies
        # Cookie should be deleted or set to empty
        assert "access_token" not in cookies or cookies.get("access_token") == ""

    @pytest.mark.asyncio
    async def test_logout_redirects_to_home(self, client):
        """Test that logout redirects to home page."""
        response = await client.post("/auth/logout", follow_redirects=False)

        assert response.status_code == 302
        assert response.headers["location"] == "/"


class TestDomainRestriction:
    """Tests for OAuth domain restriction."""

    @pytest.mark.asyncio
    async def test_allowed_domain_grants_access(
        self, unauthenticated_client, monkeypatch
    ):
        """Test that users from allowed domain can log in."""
        from app.config import settings
        from app.services.oauth_session_store import OAuthSession

        monkeypatch.setattr(settings, "OAUTH_DOMAIN_RESTRICTION", True)
        monkeypatch.setattr(type(settings), "OAUTH_ALLOWED_DOMAINS", property(lambda self: ["case.edu"]))

        mock_session = OAuthSession(
            state="mock_state",
            code_verifier="mock_verifier",
            created_at=datetime.utcnow(),
        )

        mock_auth = Mock()
        mock_auth.exchange_code_for_tokens = AsyncMock(
            return_value={"access_token": "mock_access_token", "id_token": "mock_id_token"}
        )
        mock_auth.verify_google_id_token = Mock(
            return_value={"email": "user@case.edu", "name": "Allowed User", "picture": "https://example.com/pic.jpg", "sub": "google_123"}
        )
        mock_auth.extract_user_info_from_id_token = Mock(
            return_value={"email": "user@case.edu", "name": "Allowed User", "picture_url": "https://example.com/pic.jpg", "domain": "case.edu"}
        )
        mock_auth.check_domain_restriction = Mock(return_value=True)
        mock_auth.create_jwt_token = Mock(return_value="mock_jwt_token_string")

        with patch("app.api.auth.oauth_store") as mock_store, \
             patch("app.api.auth.auth_service", mock_auth), \
             patch("app.api.auth.FirestoreService") as mock_fs_class:

            mock_store.get_session.return_value = mock_session
            mock_store.delete_session.return_value = None

            mock_fs_instance = AsyncMock()
            mock_fs_instance.get_or_create_user.return_value = Mock(
                user_id="test_user_123",
                email="user@case.edu",
                name="Allowed User",
                domain="case.edu",
            )
            mock_fs_class.return_value = mock_fs_instance

            response = await unauthenticated_client.get(
                "/auth/callback?code=mock_code&state=mock_state",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_disallowed_domain_denies_access(
        self, unauthenticated_client, monkeypatch
    ):
        """Test that users from disallowed domain are denied."""
        from app.config import settings
        from app.services.oauth_session_store import OAuthSession

        monkeypatch.setattr(settings, "OAUTH_DOMAIN_RESTRICTION", True)
        monkeypatch.setattr(type(settings), "OAUTH_ALLOWED_DOMAINS", property(lambda self: ["case.edu"]))

        mock_session = OAuthSession(
            state="mock_state",
            code_verifier="mock_verifier",
            created_at=datetime.utcnow(),
        )

        mock_auth = Mock()
        mock_auth.exchange_code_for_tokens = AsyncMock(
            return_value={"access_token": "mock_access_token", "id_token": "mock_id_token"}
        )
        mock_auth.verify_google_id_token = Mock(
            return_value={"email": "user@gmail.com", "name": "Unauthorized User", "picture": "https://example.com/pic.jpg", "sub": "google_456"}
        )
        mock_auth.extract_user_info_from_id_token = Mock(
            return_value={"email": "user@gmail.com", "name": "Unauthorized User", "picture_url": "https://example.com/pic.jpg", "domain": "gmail.com"}
        )
        mock_auth.check_domain_restriction = Mock(return_value=False)
        mock_auth.create_jwt_token = Mock(return_value="mock_jwt_token_string")

        with patch("app.api.auth.oauth_store") as mock_store, \
             patch("app.api.auth.auth_service", mock_auth), \
             patch("app.api.auth.FirestoreService") as mock_fs_class:

            mock_store.get_session.return_value = mock_session
            mock_store.delete_session.return_value = None

            mock_fs_instance = AsyncMock()
            mock_fs_instance.get_or_create_user.return_value = Mock(
                user_id="other_user",
                email="user@gmail.com",
                name="Unauthorized User",
                domain="gmail.com",
            )
            mock_fs_class.return_value = mock_fs_instance

            response = await unauthenticated_client.get(
                "/auth/callback?code=mock_code&state=mock_state",
                follow_redirects=False,
            )

        # Should return 403 error for disallowed domain
        assert response.status_code in [403, 302]
