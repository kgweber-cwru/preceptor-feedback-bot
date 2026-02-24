"""
FastAPI Main Application - Preceptor Feedback Bot
Entry point for the FastAPI application with OAuth authentication and Firestore persistence.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.middleware.auth_middleware import AuthMiddleware
from app.api import auth, conversations, feedback, user, survey, dev


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup: Initialize services
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Environment: {settings.DEPLOYMENT_ENV}")
    print(f"Model: {settings.get_model_display_name()}")
    print(f"OAuth enabled: {bool(settings.OAUTH_CLIENT_ID)}")

    # Validate configuration
    try:
        settings.validate_config()
        print("Configuration validated successfully")
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise

    yield

    # Shutdown: Cleanup
    print("Shutting down application")


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered feedback tool for medical education",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# Add middleware
app.add_middleware(AuthMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Shared templates instance (globals and filters configured in app.dependencies)
from app.dependencies import templates


# Include API routers
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
app.include_router(feedback.router, tags=["feedback"])
app.include_router(user.router, tags=["user"])
app.include_router(survey.router, tags=["survey"])
if settings.DEBUG:
    app.include_router(dev.router)


# ===== Root Routes =====


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Root endpoint - redirects to dashboard if authenticated, otherwise shows login page.
    """
    # Check if user is authenticated (via middleware)
    if request.state.authenticated and request.state.user:
        # Redirect to dashboard
        return RedirectResponse(url="/dashboard", status_code=302)

    # Show login page
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Dashboard - start new conversations or view history.
    """
    # Check if authenticated
    if not request.state.authenticated:
        return RedirectResponse(url="/", status_code=302)

    user = request.state.user

    # Render dashboard template
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "debug": settings.DEBUG,
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.DEPLOYMENT_ENV,
    }


@app.get("/config")
async def config_info():
    """Configuration info endpoint (for debugging)"""
    return settings.get_deployment_info()


# ===== Error Handlers =====


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    # Check if it's an HTMX request
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<div class="text-red-600 p-4">Page not found</div>', status_code=404
        )

    return templates.TemplateResponse(
        "base.html",
        {
            "request": request,
            "error_message": "Page not found",
            "status_code": 404,
        },
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<div class="text-red-600 p-4">Internal server error</div>',
            status_code=500,
        )

    return templates.TemplateResponse(
        "base.html",
        {
            "request": request,
            "error_message": "Internal server error",
            "status_code": 500,
        },
        status_code=500,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.DEBUG,
    )
