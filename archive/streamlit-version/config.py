"""
Configuration management for Preceptor Feedback Bot.
Loads settings from environment variables with sensible defaults.
Handles both local and cloud deployment environments.
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file (local development only)
load_dotenv()


class Config:
    """Application configuration"""

    # Deployment Environment
    DEPLOYMENT_ENV = os.getenv("DEPLOYMENT_ENV", "local")  # local or cloud
    IS_CLOUD = DEPLOYMENT_ENV == "cloud"

    # GCP Settings
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "meded-gcp-sandbox")
    GCP_REGION = os.getenv("GCP_REGION", "us-central1")

    # Credentials (local only)
    GCP_CREDENTIALS_PATH = (
        os.getenv("GCP_CREDENTIALS_PATH", None) if not IS_CLOUD else None
    )

    # Model Settings
    MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash-exp")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))

    # Conversation Settings
    MAX_TURNS = int(os.getenv("MAX_TURNS", "10"))
    MIN_COMPETENCY_COVERAGE = int(os.getenv("MIN_COMPETENCY_COVERAGE", "3"))

    # Cloud Run Settings
    CLOUD_RUN_TIMEOUT = int(
        os.getenv("CLOUD_RUN_TIMEOUT", "600")
    )  # seconds (default 10 minutes)

    # Logging Settings
    LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"

    # Local: write to ./logs directory
    # Cloud: write to Cloud Storage bucket
    if IS_CLOUD:
        LOG_BUCKET = os.getenv("LOG_BUCKET", "meded-feedback-bot-logs")
        LOG_DIRECTORY = f"gs://{LOG_BUCKET}"
    else:
        LOG_DIRECTORY = os.getenv("LOG_DIRECTORY", "./logs")
        LOG_BUCKET = None

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR

    # System Prompt Path
    SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "./prompts/system_prompt.md")

    # Authentication Settings (stubbed for future use)
    REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
    ALLOWED_USERS = [
        u.strip() for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()
    ]

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.GCP_PROJECT_ID:
            raise ValueError("GCP_PROJECT_ID must be set")
        if not cls.GCP_REGION:
            raise ValueError("GCP_REGION must be set")

        # In cloud, must have LOG_BUCKET
        if cls.IS_CLOUD and not cls.LOG_BUCKET:
            raise ValueError("LOG_BUCKET must be set in cloud deployment")

        return True

    @classmethod
    def get_model_display_name(cls):
        """Get human-readable model name"""
        model_map = {
            "gemini-2.5-flash": "Gemini 2.0 Flash",
            "gemini-1.5-pro": "Gemini 1.5 Pro",
            "gemini-1.5-flash": "Gemini 1.5 Flash",
            # Claude models - for future use
            "claude-3-5-sonnet-v2@20241022": "Claude 3.5 Sonnet",
            "claude-sonnet-4-5@20250514": "Claude Sonnet 4.5",
        }
        return model_map.get(cls.MODEL_NAME, cls.MODEL_NAME)

    @classmethod
    def get_deployment_info(cls):
        """Get deployment environment info for debugging"""
        return {
            "environment": cls.DEPLOYMENT_ENV,
            "is_cloud": cls.IS_CLOUD,
            "project": cls.GCP_PROJECT_ID,
            "region": cls.GCP_REGION,
            "model": cls.MODEL_NAME,
            "log_destination": cls.LOG_DIRECTORY,
            "auth_required": cls.REQUIRE_AUTH,
        }
