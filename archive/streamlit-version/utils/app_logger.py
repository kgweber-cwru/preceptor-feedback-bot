"""
Application logging for Preceptor Feedback Bot.
Handles logging to local files (development) or Cloud Storage (production).
"""

import logging
import os
from datetime import datetime

from config import Config

# Try to import GCS client (only needed in cloud)
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False


class CloudStorageHandler(logging.Handler):
    """Custom logging handler that writes to Google Cloud Storage"""
    
    def __init__(self, bucket_name: str):
        super().__init__()
        if not GCS_AVAILABLE:
            raise ImportError("google-cloud-storage package required for cloud logging")
        
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        
        # Buffer for log entries (write in batches)
        self.log_buffer = []
        self.buffer_size = 10
        
        # Current log file name
        self.log_filename = f"app_{datetime.now().strftime('%Y%m%d')}.log"
    
    def emit(self, record):
        """Emit a log record to Cloud Storage"""
        try:
            log_entry = self.format(record)
            self.log_buffer.append(log_entry + '\n')
            
            # Write to GCS when buffer is full
            if len(self.log_buffer) >= self.buffer_size:
                self.flush()
                
        except Exception:
            self.handleError(record)
    
    def flush(self):
        """Flush buffered logs to Cloud Storage"""
        if not self.log_buffer:
            return
        
        try:
            blob = self.bucket.blob(self.log_filename)
            
            # Append to existing content
            existing_content = ""
            if blob.exists():
                existing_content = blob.download_as_text()
            
            new_content = existing_content + ''.join(self.log_buffer)
            blob.upload_from_string(new_content)
            
            self.log_buffer = []
            
        except Exception as e:
            # Fallback to stderr if GCS write fails
            import sys
            sys.stderr.write(f"Failed to write logs to GCS: {e}\n")

class AppLogger:
    """Application logger for tracking system events"""

    _instance = None
    _logger = None

    def __new__(cls):
        """Singleton pattern to ensure one logger instance"""
        if cls._instance is None:
            cls._instance = super(AppLogger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self):
        """Set up the application logger"""
        # Create logger
        self._logger = logging.getLogger("preceptor_feedback_bot")
        self._logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper()))
        
        # Prevent duplicate handlers if reinitialized
        if self._logger.handlers:
            return
        
        # Console handler - always add for development/debugging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Format with timestamp, level, and message
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
        
        # File/Cloud handler based on environment
        if Config.LOG_TO_FILE:
            if Config.IS_CLOUD and Config.LOG_BUCKET:
                # Cloud: Use Cloud Storage handler
                try:
                    cloud_handler = CloudStorageHandler(Config.LOG_BUCKET)
                    cloud_handler.setLevel(logging.DEBUG)
                    cloud_handler.setFormatter(formatter)
                    self._logger.addHandler(cloud_handler)
                    self._logger.debug("Cloud Storage logging initialized")
                except Exception as e:
                    self._logger.error(f"Failed to initialize Cloud Storage logging: {e}")
            else:
                # Local: Use file handler
                os.makedirs(Config.LOG_DIRECTORY, exist_ok=True)
                log_filename = f"{Config.LOG_DIRECTORY}/app_{datetime.now().strftime('%Y%m%d')}.log"
                file_handler = logging.FileHandler(log_filename)
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                self._logger.addHandler(file_handler)
                self._logger.debug("File logging initialized")


    def info(self, message: str, **kwargs):
        """Log info message with optional context"""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with optional context"""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with optional context"""
        self._log_with_context(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message with optional context"""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log message with additional context fields"""
        if kwargs:
            context_str = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            full_message = f"{message} | {context_str}"
        else:
            full_message = message

        self._logger.log(level, full_message)  # type: ignore

    def conversation_started(self, student_name: str = "unknown", model: str = None):
        """Log conversation start event"""
        self.info(
            "Conversation started",
            student=student_name,
            model=model or Config.MODEL_NAME,
        )

    def conversation_completed(
        self,
        student_name: str = "unknown",
        turn_count: int = 0,
        conversation_log_path: str = None,
    ):
        """Log conversation completion event"""
        self.info(
            "Conversation completed",
            student=student_name,
            turns=turn_count,
            log_file=conversation_log_path,
        )

    def feedback_generated(
        self, student_name: str = "unknown", premature: bool = False
    ):
        """Log feedback generation event"""
        if premature:
            self.warning(
                "Feedback generated prematurely by model", student=student_name
            )
        else:
            self.info("Feedback generated", student=student_name)

    def feedback_refined(self, student_name: str = "unknown", refinement: str = ""):
        """Log feedback refinement event"""
        self.info(
            "Feedback refined",
            student=student_name,
            request=refinement[:50],  # Truncate long refinement requests
        )

    def model_error(self, error_message: str, student_name: str = "unknown"):
        """Log model/API errors"""
        self.error(f"Model error: {error_message}", student=student_name)

    def app_started(self):
        """Log application startup"""
        self.info(
            "Application started",
            project=Config.GCP_PROJECT_ID,
            region=Config.GCP_REGION,
            model=Config.MODEL_NAME,
        )

    def config_validation_failed(self, error: str):
        """Log configuration validation failure"""
        self.error(f"Configuration validation failed: {error}")

    def flush(self):
        """Flush any buffered logs (important for cloud deployment)"""
        for handler in self._logger.handlers:  # type: ignore
            if hasattr(handler, 'flush'):
                handler.flush()

# Global logger instance
logger = AppLogger()
