"""
Vertex AI client for conversational interactions using google-genai SDK.
Supports Gemini models through Vertex AI.
"""

import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from google import genai
from google.api_core import exceptions
from google.genai import types

from config import Config

from .app_logger import logger  # Add this import


class VertexAIClient:
    """Client for interacting with Vertex AI models using google-genai SDK"""

    def __init__(self):
        """Initialize Vertex AI client with google-genai"""
        logger.debug("Initializing VertexAIClient")

        # Set credentials based on environment
        if Config.IS_CLOUD:
            # Cloud Run: Use Application Default Credentials (automatic)
            logger.debug(
                "Using Application Default Credentials (Cloud Run service account)"
            )
        else:
            # Local: Use service account JSON if provided
            if Config.GCP_CREDENTIALS_PATH and os.path.exists(
                Config.GCP_CREDENTIALS_PATH
            ):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
                    Config.GCP_CREDENTIALS_PATH
                )
                logger.debug(
                    f"Using service account credentials from {Config.GCP_CREDENTIALS_PATH}"
                )
            else:
                logger.warning(
                    "No credentials path specified, attempting Application Default Credentials"
                )

        try:
            # Initialize the genai client for Vertex AI
            self.client = genai.Client(
                vertexai=True, project=Config.GCP_PROJECT_ID, location=Config.GCP_REGION
            )
            logger.info(
                "Vertex AI client initialized",
                project=Config.GCP_PROJECT_ID,
                region=Config.GCP_REGION,
                model=Config.MODEL_NAME,
                environment=Config.DEPLOYMENT_ENV,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI client: {e}")
            raise

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        # Track conversation
        self.chat = None
        self.conversation_history: List[Dict] = []
        self.turn_count = 0
        self.student_name = "unknown"

    def set_student_name(self, student_name: str):
        """Set or update the student name for this conversation"""
        old_name = self.student_name
        self.student_name = student_name or "unknown"
        if old_name != self.student_name:
            logger.debug(f"Student name updated: {old_name} -> {self.student_name}")

    def _call_with_backoff(self, func, *args, max_retries=5, **kwargs):
        """
        Call a function with exponential backoff on 429 errors.

        Uses exponential backoff with jitter to handle rate limits gracefully.
        Retries up to 5 times with increasing delays: ~2s, ~4s, ~8s, ~16s, ~32s
        Total max wait time: ~60 seconds
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except exceptions.ResourceExhausted as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Max retries ({max_retries}) exceeded for API call",
                        student=self.student_name,
                        error=str(e),
                    )
                    raise

                # Exponential backoff with jitter: 2^attempt + random(0-1) seconds
                # This prevents multiple clients from retrying simultaneously
                base_wait = 2**attempt
                jitter = random.uniform(0, 1)
                wait_time = base_wait + jitter

                logger.warning(
                    f"Rate limit hit (429), retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})",
                    student=self.student_name,
                )
                time.sleep(wait_time)
            except Exception:
                # For non-429 errors, raise immediately
                raise

    def _load_system_prompt(self) -> str:
        """Load system prompt from file"""
        try:
            with open(Config.SYSTEM_PROMPT_PATH, "r") as f:
                prompt = f.read()
                logger.debug(f"System prompt loaded from {Config.SYSTEM_PROMPT_PATH}")
                return prompt
        except FileNotFoundError:
            logger.error(f"System prompt not found at {Config.SYSTEM_PROMPT_PATH}")
            raise FileNotFoundError(
                f"System prompt not found at {Config.SYSTEM_PROMPT_PATH}"
            )

    def start_conversation(self) -> str:
        """Start a new conversation and return initial greeting"""
        # Log with current student name (might be 'unknown' initially)
        logger.conversation_started(
            student_name=self.student_name, model=Config.MODEL_NAME
        )

        try:
            # Create chat configuration
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=Config.TEMPERATURE,
                max_output_tokens=Config.MAX_OUTPUT_TOKENS,
            )

            # Initialize chat
            self.chat = self.client.chats.create(model=Config.MODEL_NAME, config=config)

            self.conversation_history = []
            self.turn_count = 0

            # Get initial greeting from bot - include student name if available
            if self.student_name and self.student_name != "unknown":
                initial_prompt = f"The preceptor is providing feedback on student: {self.student_name}. Please provide your transparency statement and first question to the preceptor, acknowledging the student's name."
            else:
                initial_prompt = "Please provide your transparency statement and first question to the preceptor."

            response = self._call_with_backoff(self.chat.send_message, initial_prompt)
            if response is None or not response.text:
                logger.error("No response received from model on conversation start")
                raise ValueError("No response received from model")  # Log the exchange
            self._log_turn("system", initial_prompt)
            self._log_turn("assistant", response.text)

            logger.debug(f"Initial greeting generated for {self.student_name}")
            return response.text

        except Exception as e:
            logger.model_error(
                f"Error starting conversation: {str(e)}", student_name=self.student_name
            )
            raise

    def send_message(self, user_message: str) -> Tuple[str, bool]:
        """Send a message and get response"""
        if not self.chat:
            logger.error("send_message called without active conversation")
            raise ValueError(
                "Conversation not started. Call start_conversation() first."
            )

        self.turn_count += 1
        logger.debug(
            f"Turn {self.turn_count} started",
            student=self.student_name,
            message_preview=user_message[:50],
        )

        # Log user message
        self._log_turn("user", user_message)

        try:
            # Send message to model with backoff and track response time
            start_time = time.time()
            response = self._call_with_backoff(self.chat.send_message, user_message)
            response_time_ms = (time.time() - start_time) * 1000

            if response is None or not response.text:
                logger.error("No response received from model")
                raise ValueError("No response received from model")

            # Log assistant response with timing
            self._log_turn("assistant", response.text, response_time_ms)

            # Check if model generated feedback prematurely
            premature_feedback = self._contains_formal_feedback(response.text)

            if premature_feedback:
                logger.warning(
                    "Model generated premature feedback",
                    student=self.student_name,
                    turn=self.turn_count,
                )

            logger.debug(
                f"Turn {self.turn_count} completed",
                student=self.student_name,
                premature_feedback=premature_feedback,
            )

            return response.text, premature_feedback

        except Exception as e:
            logger.model_error(
                f"Error in turn {self.turn_count}: {str(e)}",
                student_name=self.student_name,
            )
            raise

    def generate_feedback(self, conversation_summary: str = None) -> str:
        """Generate final feedback summaries"""
        if not self.chat:
            logger.error("generate_feedback called without active conversation")
            raise ValueError("No active conversation")

        logger.feedback_generated(student_name=self.student_name, premature=False)

        prompt = """Based on our conversation, please generate both outputs:

1. **Structured Summary** (structured bullets with Context, Strengths, Areas for Improvement, Suggested Focus)
2. **Student-Facing Narrative** (constructive paragraph with context, strengths, 1-2 actionable suggestions, encouragement)

Please format clearly with headers."""

        try:
            # Log the feedback generation request
            self.conversation_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "turn": "feedback_generation",
                    "role": "system",
                    "content": prompt,
                }
            )

            start_time = time.time()
            response = self._call_with_backoff(self.chat.send_message, prompt)
            response_time_ms = (time.time() - start_time) * 1000

            if response is None or not response.text:
                logger.error(
                    "No response received from model during feedback generation"
                )
                raise ValueError("No response received from model")

            # Log feedback generation with special turn marker (not a regular conversation turn)
            self.conversation_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "turn": "feedback_generation",
                    "role": "assistant",
                    "content": response.text,
                    "response_time_ms": round(response_time_ms, 2),
                }
            )

            logger.info(
                "Feedback generation completed",
                student=self.student_name,
                feedback_length=len(response.text),
                response_time_ms=round(response_time_ms, 2),
            )

            return response.text

        except Exception as e:
            logger.model_error(
                f"Error generating feedback: {str(e)}", student_name=self.student_name
            )
            raise

    def refine_feedback(self, refinement_request: str) -> str:
        """Refine the generated feedback based on user request"""
        if not self.chat:
            logger.error("refine_feedback called without active conversation")
            raise ValueError("No active conversation")

        logger.feedback_refined(
            student_name=self.student_name, refinement=refinement_request
        )

        try:
            # Log the user's refinement request with special turn marker
            self.conversation_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "turn": "feedback_refinement",
                    "role": "user",
                    "content": refinement_request,
                }
            )

            start_time = time.time()
            response = self._call_with_backoff(
                self.chat.send_message, refinement_request
            )
            response_time_ms = (time.time() - start_time) * 1000

            if response is None or not response.text:
                logger.error(
                    "No response received from model during feedback refinement"
                )
                raise ValueError("No response received from model")

            # Log the assistant's refined response with special turn marker
            self.conversation_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "turn": "feedback_refinement",
                    "role": "assistant",
                    "content": response.text,
                    "response_time_ms": round(response_time_ms, 2),
                }
            )

            logger.debug("Feedback refinement completed", student=self.student_name)

            return response.text

        except Exception as e:
            logger.model_error(
                f"Error refining feedback: {str(e)}", student_name=self.student_name
            )
            raise

    def _log_turn(self, role: str, content: str, response_time_ms: float = None):
        """Log a conversation turn"""
        turn_data = {
            "timestamp": datetime.now().isoformat(),
            "turn": self.turn_count,
            "role": role,
            "content": content,
        }
        if response_time_ms is not None:
            turn_data["response_time_ms"] = round(response_time_ms, 2)

        self.conversation_history.append(turn_data)

    def _contains_formal_feedback(self, text: str) -> bool:
        """
        Detect if response contains formal feedback outputs.
        This is a fallback for when the model ignores instructions.
        """
        # Look for telltale signs of formal feedback structure
        feedback_markers = [
            "**Structured Summary",
            "**Student-Facing Narrative",
            "## Structured Summary",
            "## Student-Facing Narrative",
            "**Context of evaluation**",
            "**Strengths**",
            "**Areas for Improvement**",
            "**Suggested Focus for Development**",
        ]

        # Count how many markers appear
        marker_count = sum(1 for marker in feedback_markers if marker in text)

        # If we see multiple formal feedback markers, it's probably feedback
        return marker_count >= 3

    def save_conversation_log(self, student_name: str = "unknown"):
        """Save conversation to JSON file (local) or Cloud Storage (cloud)"""
        if not Config.LOG_TO_FILE:
            logger.debug("Conversation logging disabled, skipping save")
            return None

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_{timestamp}_{student_name}.json"

        # Prepare log data
        log_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "model": Config.MODEL_NAME,
                "student_name": student_name,
                "total_turns": self.turn_count,
                "project_id": Config.GCP_PROJECT_ID,
                "environment": Config.DEPLOYMENT_ENV,
            },
            "conversation": self.conversation_history,
        }

        try:
            if Config.IS_CLOUD:
                # Write to Cloud Storage
                from google.cloud import storage

                client = storage.Client()
                bucket = client.bucket(Config.LOG_BUCKET)
                blob = bucket.blob(filename)
                blob.upload_from_string(
                    json.dumps(log_data, indent=2), content_type="application/json"
                )
                full_path = f"gs://{Config.LOG_BUCKET}/{filename}"
            else:
                # Write to local file
                os.makedirs(Config.LOG_DIRECTORY, exist_ok=True)
                full_path = f"{Config.LOG_DIRECTORY}/{filename}"
                with open(full_path, "w") as f:
                    json.dump(log_data, f, indent=2)

            logger.conversation_completed(
                student_name=student_name,
                turn_count=self.turn_count,
                conversation_log_path=full_path,
            )

            return full_path

        except Exception as e:
            logger.error(f"Failed to save conversation log: {e}", student=student_name)
            raise

    def should_conclude_conversation(self) -> bool:
        """Check if conversation should conclude"""
        # Check turn limit
        if self.turn_count >= Config.MAX_TURNS:
            logger.debug(
                "Conversation turn limit reached",
                student=self.student_name,
                turns=self.turn_count,
            )
            return True

        # Check if user indicated they're done
        if self.conversation_history:
            last_user_message = next(
                (
                    turn["content"]
                    for turn in reversed(self.conversation_history)
                    if turn["role"] == "user"
                ),
                "",
            ).lower()

            done_phrases = ["done", "that's all", "finished", "nothing else", "no more"]
            if any(phrase in last_user_message for phrase in done_phrases):
                logger.debug(
                    "User indicated conversation completion", student=self.student_name
                )
                return True

        return False
