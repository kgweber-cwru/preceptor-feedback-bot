"""
Authentication API routes for Google OAuth 2.0 login flow.
Handles login redirect, OAuth callback, logout, and token verification.
"""

from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import RedirectResponse, HTMLResponse

from app.config import settings
from app.dependencies import templates
from app.services.auth_service import AuthService
from app.services.firestore_service import FirestoreService
from app.services.oauth_session_store import get_oauth_store
from app.models.user import UserCreate

router = APIRouter()
auth_service = AuthService()
oauth_store = get_oauth_store()


@router.get("/login")
async def login(request: Request):
    """
    Initiate OAuth login flow.
    Generates PKCE parameters and redirects to Google OAuth.

    NOTE: Uses server-side session storage instead of cookies to work around
    Safari's Intelligent Tracking Prevention blocking samesite=none cookies.
    """
    # Generate PKCE pair
    code_verifier, code_challenge = auth_service.generate_pkce_pair()

    # Generate CSRF state token
    state = auth_service.generate_state_token()

    # Store state and code_verifier server-side (Safari blocks cookies)
    session_id = oauth_store.create_session(state, code_verifier)

    # Build OAuth URL
    oauth_url = auth_service.build_oauth_url(code_challenge, state)

    # Diagnostic logging
    print(f"[OAuth Debug] Login initiated")
    print(f"[OAuth Debug] Created server-side session: {session_id[:20]}...")
    print(f"[OAuth Debug] State token: {state[:20]}...")
    print(f"[OAuth Debug] Redirecting to: {oauth_url[:100]}...")

    # No cookies needed - state stored server-side
    response = RedirectResponse(url=oauth_url, status_code=302)
    return response


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
):
    """
    Handle OAuth callback from Google.
    Exchanges authorization code for tokens, creates/updates user, and issues JWT.

    NOTE: Retrieves state and code_verifier from server-side session storage
    instead of cookies (Safari compatibility).
    """
    # Check for OAuth error
    if error:
        return HTMLResponse(
            f'<h1>Authentication Error</h1><p>{error}</p><a href="/">Return to login</a>',
            status_code=400,
        )

    # Diagnostic logging
    print(f"[OAuth Debug] Callback received")
    print(f"[OAuth Debug] State from URL: {state[:20] if state else 'None'}...")
    print(f"[OAuth Debug] User-Agent: {request.headers.get('user-agent', 'Unknown')}")

    if not state:
        print(f"[OAuth Debug] No state parameter in callback")
        raise HTTPException(status_code=400, detail="Missing state parameter")

    # Retrieve session from server-side store using state
    session = oauth_store.get_session(state)

    if not session:
        print(f"[OAuth Debug] No session found for state (expired or invalid)")
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired session. Please try logging in again."
        )

    print(f"[OAuth Debug] Session found - validating state match")

    # Validate state matches (CSRF protection)
    if state != session.state:
        print(f"[OAuth Debug] State mismatch!")
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Get code_verifier from session
    code_verifier = session.code_verifier
    print(f"[OAuth Debug] Retrieved code_verifier from session")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        # Exchange code for tokens
        tokens = await auth_service.exchange_code_for_tokens(code, code_verifier)
        id_token_str = tokens.get("id_token")

        if not id_token_str:
            raise HTTPException(status_code=400, detail="No ID token received")

        # Verify ID token
        idinfo = auth_service.verify_google_id_token(id_token_str)

        # Extract user info
        user_info = auth_service.extract_user_info_from_id_token(idinfo)

        # Check domain restriction
        if not auth_service.check_domain_restriction(user_info["email"]):
            denied_response = HTMLResponse(
                f'''
                <h1>Access Denied</h1>
                <p>Your email domain ({user_info["domain"]}) is not authorized to access this application.</p>
                <p>Allowed domains: {", ".join(settings.OAUTH_ALLOWED_DOMAINS)}</p>
                <a href="/">Return to login</a>
                ''',
                status_code=403,
            )
            # Clear any existing session cookie so a stale session from a
            # previously-authenticated user doesn't remain active in the browser.
            denied_response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
            return denied_response

        # Create/update user in Firestore
        firestore_service = FirestoreService()
        user_create = UserCreate(**user_info)
        user = await firestore_service.get_or_create_user(user_create)

        # Generate JWT
        jwt_token = auth_service.create_jwt_token(
            user_id=user.user_id,
            email=user.email,
            name=user.name,
            domain=user.domain,
        )

        # Clean up server-side OAuth session
        oauth_store.delete_session(state)
        print(f"[OAuth Debug] Session cleaned up")

        # Redirect to dashboard with JWT cookie
        response = RedirectResponse(url="/dashboard", status_code=302)

        # Set JWT cookie (httpOnly, secure)
        # NOTE: Session cookie uses samesite="lax" which works fine for same-site requests
        # Only the temporary OAuth cookies needed samesite="none" (now server-side)
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=jwt_token,
            max_age=settings.SESSION_MAX_AGE,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            path="/",
        )

        print(f"[OAuth Debug] Login successful! Redirecting to dashboard")
        return response

    except ValueError as e:
        # Token verification failed
        return HTMLResponse(
            f'<h1>Authentication Error</h1><p>{str(e)}</p><a href="/">Return to login</a>',
            status_code=400,
        )
    except Exception as e:
        # Other errors
        print(f"OAuth callback error: {e}")
        return HTMLResponse(
            f'<h1>Authentication Error</h1><p>An unexpected error occurred.</p><a href="/">Return to login</a>',
            status_code=500,
        )


@router.post("/logout")
async def logout(response: Response):
    """
    Log out user by clearing JWT cookie.
    """
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/verify")
async def verify_token(request: Request):
    """
    Verify current user's JWT token and return user info.
    Useful for client-side auth state checks.
    """
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = auth_service.verify_jwt_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "authenticated": True,
        "user": {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "domain": payload.get("domain"),
        },
    }
