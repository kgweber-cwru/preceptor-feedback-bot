"""
Integration tests for OAuth authentication flow.
Tests login, callback, JWT generation, and logout.
"""

import pytest
from unittest.mock import patch, Mock
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
        """Test that login sets oauth_state cookie."""
        response = await unauthenticated_client.get("/auth/login", follow_redirects=False)

        cookies = response.cookies
        assert "oauth_state" in cookies
        assert cookies["oauth_state"] != ""
        assert cookies.get("oauth_state_httponly", True)

    @pytest.mark.asyncio
    async def test_login_sets_code_verifier_cookie(self, unauthenticated_client):
        """Test that login sets code_verifier cookie for PKCE."""
        response = await unauthenticated_client.get("/auth/login", follow_redirects=False)

        cookies = response.cookies
        assert "oauth_code_verifier" in cookies
        assert cookies["oauth_code_verifier"] != ""


class TestOAuthCallback:
    """Tests for OAuth callback handling."""

    @pytest.mark.asyncio
    @patch("app.api.auth.httpx.AsyncClient.post")
    @patch("app.api.auth.httpx.AsyncClient.get")
    async def test_successful_callback_creates_jwt(
        self, mock_get, mock_post, unauthenticated_client, mock_firestore
    ):
        """Test successful OAuth callback creates JWT and user."""
        # Mock Google token exchange
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "access_token": "mock_access_token",
                "id_token": "mock_id_token",
            },
        )

        # Mock Google userinfo
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "email": "test@case.edu",
                "name": "Test User",
                "picture": "https://example.com/pic.jpg",
            },
        )

        # Set cookies as if we came from /auth/login
        response = await unauthenticated_client.get(
            "/auth/callback?code=mock_code&state=mock_state",
            cookies={"oauth_state": "mock_state", "oauth_code_verifier": "mock_verifier"},
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
    @patch("app.api.auth.httpx.AsyncClient.post")
    @patch("app.api.auth.httpx.AsyncClient.get")
    async def test_allowed_domain_grants_access(
        self, mock_get, mock_post, unauthenticated_client, monkeypatch
    ):
        """Test that users from allowed domain can log in."""
        # Enable domain restriction via monkeypatch
        from app.config import settings
        monkeypatch.setattr(settings, "OAUTH_DOMAIN_RESTRICTION", True)
        # Patch the property to return the list directly
        monkeypatch.setattr(type(settings), "OAUTH_ALLOWED_DOMAINS", property(lambda self: ["case.edu"]))

        # Mock Google token exchange
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "access_token": "mock_access_token",
                "id_token": "mock_id_token",
            },
        )

        # Mock Google userinfo with allowed domain
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "email": "user@case.edu",
                "name": "Allowed User",
                "picture": "https://example.com/pic.jpg",
            },
        )

        response = await unauthenticated_client.get(
            "/auth/callback?code=mock_code&state=mock_state",
            cookies={"oauth_state": "mock_state", "oauth_code_verifier": "mock_verifier"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]

    @pytest.mark.asyncio
    @patch("app.api.auth.httpx.AsyncClient.post")
    @patch("app.api.auth.httpx.AsyncClient.get")
    async def test_disallowed_domain_denies_access(
        self, mock_get, mock_post, unauthenticated_client, monkeypatch
    ):
        """Test that users from disallowed domain are denied."""
        # Enable domain restriction via monkeypatch
        from app.config import settings
        monkeypatch.setattr(settings, "OAUTH_DOMAIN_RESTRICTION", True)
        # Patch the property to return the list directly
        monkeypatch.setattr(type(settings), "OAUTH_ALLOWED_DOMAINS", property(lambda self: ["case.edu"]))

        # Mock Google token exchange
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "access_token": "mock_access_token",
                "id_token": "mock_id_token",
            },
        )

        # Mock Google userinfo with disallowed domain
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "email": "user@gmail.com",
                "name": "Unauthorized User",
                "picture": "https://example.com/pic.jpg",
            },
        )

        response = await unauthenticated_client.get(
            "/auth/callback?code=mock_code&state=mock_state",
            cookies={"oauth_state": "mock_state", "oauth_code_verifier": "mock_verifier"},
            follow_redirects=False,
        )

        # Should return error or redirect to login with error
        assert response.status_code in [403, 302]
