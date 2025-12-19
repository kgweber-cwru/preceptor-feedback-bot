"""
Authentication API routes for Google OAuth 2.0 login flow.
Handles login redirect, OAuth callback, logout, and token verification.
"""

from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.auth_service import AuthService
from app.services.firestore_service import FirestoreService
from app.models.user import UserCreate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
auth_service = AuthService()


@router.get("/login")
async def login(request: Request):
    """
    Initiate OAuth login flow.
    Generates PKCE parameters and redirects to Google OAuth.
    """
    # Generate PKCE pair
    code_verifier, code_challenge = auth_service.generate_pkce_pair()

    # Generate CSRF state token
    state = auth_service.generate_state_token()

    # Build OAuth URL
    oauth_url = auth_service.build_oauth_url(code_challenge, state)

    # Create response with redirect
    response = RedirectResponse(url=oauth_url, status_code=302)

    # Store code_verifier and state in secure cookies (temporary, httpOnly)
    # NOTE: samesite="none" required for OAuth redirect flow to work in Safari
    # (Google OAuth redirects back to app = cross-site context)
    response.set_cookie(
        key="oauth_code_verifier",
        value=code_verifier,
        max_age=600,  # 10 minutes
        httponly=True,
        secure=True,  # Required when samesite="none"
        samesite="none",
        path="/",  # Ensure cookie is sent to all paths
    )

    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,  # 10 minutes
        httponly=True,
        secure=True,  # Required when samesite="none"
        samesite="none",
        path="/",  # Ensure cookie is sent to all paths
    )

    # Diagnostic logging
    print(f"[OAuth Debug] Login initiated")
    print(f"[OAuth Debug] Setting oauth_state cookie: {state[:20]}...")
    print(f"[OAuth Debug] Cookie attributes: secure=True, samesite=none, httponly=True, path=/")
    print(f"[OAuth Debug] Redirecting to: {oauth_url[:100]}...")

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
    """
    # Check for OAuth error
    if error:
        return HTMLResponse(
            f'<h1>Authentication Error</h1><p>{error}</p><a href="/">Return to login</a>',
            status_code=400,
        )

    # Validate state (CSRF protection)
    stored_state = request.cookies.get("oauth_state")

    # Diagnostic logging
    print(f"[OAuth Debug] Callback received")
    print(f"[OAuth Debug] State from URL: {state[:20] if state else 'None'}...")
    print(f"[OAuth Debug] Stored state cookie: {stored_state[:20] if stored_state else 'None'}...")
    print(f"[OAuth Debug] All cookies: {list(request.cookies.keys())}")
    print(f"[OAuth Debug] User-Agent: {request.headers.get('user-agent', 'Unknown')}")

    if not state or not stored_state or state != stored_state:
        print(f"[OAuth Debug] State validation FAILED - state={bool(state)}, stored={bool(stored_state)}, match={state == stored_state if state and stored_state else False}")
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Get code_verifier from cookie
    code_verifier = request.cookies.get("oauth_code_verifier")
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Missing code verifier")

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
            return HTMLResponse(
                f'''
                <h1>Access Denied</h1>
                <p>Your email domain ({user_info["domain"]}) is not authorized to access this application.</p>
                <p>Allowed domains: {", ".join(settings.OAUTH_ALLOWED_DOMAINS)}</p>
                <a href="/">Return to login</a>
                ''',
                status_code=403,
            )

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

        # Redirect to dashboard with JWT cookie
        response = RedirectResponse(url="/dashboard", status_code=302)

        # Set JWT cookie (httpOnly, secure)
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=jwt_token,
            max_age=settings.SESSION_MAX_AGE,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            path="/",
        )

        # Clear temporary OAuth cookies
        response.delete_cookie("oauth_code_verifier", path="/")
        response.delete_cookie("oauth_state", path="/")

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
