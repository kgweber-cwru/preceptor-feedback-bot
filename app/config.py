"""
Enhanced configuration for FastAPI Preceptor Feedback Bot.
Includes OAuth, Firestore, and JWT settings alongside existing Vertex AI config.
"""

import os
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file (local development only)
load_dotenv()


class Settings(BaseSettings):
    """Application settings with validation"""

    # Deployment Environment
    DEPLOYMENT_ENV: str = os.getenv("DEPLOYMENT_ENV", "local")  # local or cloud

    @property
    def IS_CLOUD(self) -> bool:
        return self.DEPLOYMENT_ENV == "cloud"

    # GCP Settings
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "meded-gcp-sandbox")
    GCP_REGION: str = os.getenv("GCP_REGION", "us-central1")

    # Credentials (local only)
    GCP_CREDENTIALS_PATH: str | None = os.getenv("GCP_CREDENTIALS_PATH", None)

    # Vertex AI Model Settings
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-2.5-flash")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_OUTPUT_TOKENS: int = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))

    # Conversation Settings
    MAX_TURNS: int = int(os.getenv("MAX_TURNS", "10"))
    MIN_COMPETENCY_COVERAGE: int = int(os.getenv("MIN_COMPETENCY_COVERAGE", "3"))

    # Cloud Run Settings
    CLOUD_RUN_TIMEOUT: int = int(os.getenv("CLOUD_RUN_TIMEOUT", "600"))

    # Logging Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() == "true"

    @property
    def LOG_BUCKET(self) -> str | None:
        if self.IS_CLOUD:
            return os.getenv("LOG_BUCKET", "meded-feedback-bot-logs")
        return None

    @property
    def LOG_DIRECTORY(self) -> str:
        if self.IS_CLOUD and self.LOG_BUCKET:
            return f"gs://{self.LOG_BUCKET}"
        return os.getenv("LOG_DIRECTORY", "./logs")

    # System Prompt Path
    SYSTEM_PROMPT_PATH: str = os.getenv(
        "SYSTEM_PROMPT_PATH", "./prompts/system_prompt.md"
    )

    # ===== NEW: OAuth 2.0 Settings =====
    OAUTH_CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "")
    OAUTH_CLIENT_SECRET: str = os.getenv("OAUTH_CLIENT_SECRET", "")
    OAUTH_REDIRECT_URI: str = os.getenv(
        "OAUTH_REDIRECT_URI", "http://localhost:8080/auth/callback"
    )

    # Domain Restriction (hybrid approach)
    OAUTH_DOMAIN_RESTRICTION: bool = (
        os.getenv("OAUTH_DOMAIN_RESTRICTION", "false").lower() == "true"
    )

    @property
    def OAUTH_ALLOWED_DOMAINS(self) -> List[str]:
        domains_str = os.getenv("OAUTH_ALLOWED_DOMAINS", "case.edu")
        return [d.strip() for d in domains_str.split(",") if d.strip()]

    # Google OAuth URLs
    GOOGLE_AUTH_URL: str = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL: str = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL: str = "https://www.googleapis.com/oauth2/v2/userinfo"

    # ===== NEW: JWT Settings =====
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "development-secret-key-change-in-production"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    # ===== NEW: Firestore Settings =====
    FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "(default)")

    # Collections
    USERS_COLLECTION: str = "users"
    CONVERSATIONS_COLLECTION: str = "conversations"
    FEEDBACK_COLLECTION: str = "feedback"
    SURVEYS_COLLECTION: str = "surveys"

    # ===== FastAPI Settings =====
    APP_NAME: str = "Preceptor Feedback Bot"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS Settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    # Session Settings
    SESSION_COOKIE_NAME: str = "access_token"
    SESSION_MAX_AGE: int = 86400  # 24 hours in seconds

    def validate_config(self) -> bool:
        """Validate required configuration"""
        if not self.GCP_PROJECT_ID:
            raise ValueError("GCP_PROJECT_ID must be set")
        if not self.GCP_REGION:
            raise ValueError("GCP_REGION must be set")

        # In cloud, must have LOG_BUCKET
        if self.IS_CLOUD and not self.LOG_BUCKET:
            raise ValueError("LOG_BUCKET must be set in cloud deployment")

        # OAuth validation (only if domain restriction enabled)
        if self.OAUTH_DOMAIN_RESTRICTION:
            if not self.OAUTH_CLIENT_ID or not self.OAUTH_CLIENT_SECRET:
                raise ValueError(
                    "OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set for OAuth"
                )
            if not self.OAUTH_ALLOWED_DOMAINS:
                raise ValueError("OAUTH_ALLOWED_DOMAINS must be set when domain restriction is enabled")

        # JWT validation
        if self.JWT_SECRET_KEY == "development-secret-key-change-in-production":
            if self.IS_CLOUD or not self.DEBUG:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure value in production"
                )

        return True

    def get_model_display_name(self) -> str:
        """Get human-readable model name"""
        model_map = {
            "gemini-2.5-flash": "Gemini 2.5 Flash",
            "gemini-1.5-pro": "Gemini 1.5 Pro",
            "gemini-1.5-flash": "Gemini 1.5 Flash",
            "gemini-2.0-flash-exp": "Gemini 2.0 Flash (Experimental)",
        }
        return model_map.get(self.MODEL_NAME, self.MODEL_NAME)

    def get_deployment_info(self) -> dict:
        """Get deployment environment info for debugging"""
        return {
            "environment": self.DEPLOYMENT_ENV,
            "is_cloud": self.IS_CLOUD,
            "project": self.GCP_PROJECT_ID,
            "region": self.GCP_REGION,
            "model": self.MODEL_NAME,
            "log_destination": self.LOG_DIRECTORY,
            "oauth_enabled": bool(self.OAUTH_CLIENT_ID),
            "domain_restriction": self.OAUTH_DOMAIN_RESTRICTION,
            "debug": self.DEBUG,
        }

    class Config:
        case_sensitive = True


# Global settings instance
settings = Settings()

# Validate on import
settings.validate_config()
