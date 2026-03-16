"""
Vertex AI client for conversational interactions using google-genai SDK.
Supports Gemini models through Vertex AI.
Migrated from utils/ for FastAPI integration.
"""

import os
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

from google import genai
from google.api_core import exceptions
from google.genai import types

from app.config import settings


class VertexAIClient:
    """Client for interacting with Vertex AI models using google-genai SDK"""

    def __init__(self, conversation_id: Optional[str] = None):
        """
        Initialize Vertex AI client with google-genai.

        Args:
            conversation_id: Optional Firestore conversation ID for tracking
        """
        self.conversation_id = conversation_id

        # Set credentials based on environment
        if settings.IS_CLOUD:
            # Cloud Run: Use Application Default Credentials (automatic)
            pass
        else:
            # Local: Use service account JSON if provided
            if settings.GCP_CREDENTIALS_PATH and os.path.exists(
                settings.GCP_CREDENTIALS_PATH
            ):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
                    settings.GCP_CREDENTIALS_PATH
                )

        try:
            # Initialize the genai client for Vertex AI
            self.client = genai.Client(
                vertexai=True,
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_REGION,
            )
        except Exception as e:
            raise Exception(f"Failed to initialize Vertex AI client: {e}")

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        # Track conversation
        self.chat = None
        self.conversation_history: List[Dict] = []
        self.turn_count = 0
        self.student_name = "unknown"

    def set_student_name(self, student_name: str):
        """Set or update the student name for this conversation"""
        self.student_name = student_name or "unknown"

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
                    raise Exception(
                        f"Max retries ({max_retries}) exceeded for API call: {e}"
                    )

                # Exponential backoff with jitter: 2^attempt + random(0-1) seconds
                base_wait = 2**attempt
                jitter = random.uniform(0, 1)
                wait_time = base_wait + jitter

                print(
                    f"Rate limit hit (429), retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
            except Exception:
                # For non-429 errors, raise immediately
                raise

    def _load_system_prompt(self) -> str:
        """Load system prompt from file"""
        try:
            with open(settings.SYSTEM_PROMPT_PATH, "r") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"System prompt not found at {settings.SYSTEM_PROMPT_PATH}"
            )

    def start_conversation(self) -> str:
        """
        Start a new conversation and return initial greeting.

        Returns:
            str: Initial AI greeting message
        """
        try:
            # Create chat configuration
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=settings.TEMPERATURE,
                max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            )

            # Initialize chat
            self.chat = self.client.chats.create(
                model=settings.MODEL_NAME, config=config
            )

            self.conversation_history = []
            self.turn_count = 0

            # Get initial greeting from bot - include student name if available
            if self.student_name and self.student_name != "unknown":
                initial_prompt = f"The preceptor is providing feedback on student: {self.student_name}. Please provide your transparency statement and first question to the preceptor, acknowledging the student's name."
            else:
                initial_prompt = "Please provide your transparency statement and first question to the preceptor."

            response = self._call_with_backoff(self.chat.send_message, initial_prompt)

            if response is None or not response.text:
                raise ValueError("No response received from model")

            # Log the exchange (initial greeting counts as turn 0)
            self._log_turn("system", initial_prompt)
            self._log_turn("assistant", response.text)

            # Don't increment turn count for initial greeting
            # First user message will be turn 1
            # (Turn count stays at 0 for the initial greeting)

            return response.text

        except Exception as e:
            raise Exception(f"Error starting conversation: {str(e)}")

    def restore_conversation(self, conversation_history: List[Dict]) -> None:
        """
        Restore a chat session from existing conversation history.

        This method recreates the chat context by initializing a new chat with
        the full conversation history. This preserves the conversational context
        without needing to replay messages.

        Args:
            conversation_history: List of message dicts with role, content, timestamp, turn
        """
        try:
            # Create chat configuration
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=settings.TEMPERATURE,
                max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            )

            # Convert conversation history to format expected by chat API
            # Filter out system messages (like initial prompt), keep only user/assistant exchanges
            chat_history = []
            for msg in conversation_history:
                role = msg["role"]
                # Skip system messages - they're not part of the user/assistant exchange
                if role in ["user", "assistant"]:
                    # Map 'assistant' to 'model' (required by API)
                    api_role = "model" if role == "assistant" else "user"
                    chat_history.append({
                        "role": api_role,
                        "parts": [{"text": msg["content"]}]
                    })

            # Initialize chat with existing history
            self.chat = self.client.chats.create(
                model=settings.MODEL_NAME,
                config=config,
                history=chat_history
            )

            # Restore conversation history and turn count
            self.conversation_history = conversation_history.copy()
            self.turn_count = max([msg["turn"] for msg in conversation_history if isinstance(msg["turn"], int)], default=0)

        except Exception as e:
            raise Exception(f"Error restoring conversation: {str(e)}")

    def send_message(self, user_message: str) -> Dict:
        """
        Send a message and get response.

        Args:
            user_message: User's message text

        Returns:
            dict: Response data with role, content, timestamp, turn, contains_feedback
        """
        if not self.chat:
            raise ValueError(
                "Conversation not started. Call start_conversation() first."
            )

        self.turn_count += 1

        # Log user message
        self._log_turn("user", user_message)

        try:
            # Send message to model with backoff and track response time
            start_time = time.time()
            response = self._call_with_backoff(self.chat.send_message, user_message)
            response_time_ms = (time.time() - start_time) * 1000

            if response is None or not response.text:
                raise ValueError("No response received from model")

            # Log assistant response with timing
            self._log_turn("assistant", response.text, response_time_ms)

            # Check if model generated feedback prematurely
            premature_feedback = self._contains_formal_feedback(response.text)

            return {
                "role": "assistant",
                "content": response.text,
                "timestamp": datetime.utcnow().isoformat(),
                "turn": self.turn_count,
                "response_time_ms": round(response_time_ms, 2),
                "contains_feedback": premature_feedback,
            }

        except Exception as e:
            raise Exception(f"Error in turn {self.turn_count}: {str(e)}")

    def generate_feedback(self, conversation_summary: str = None) -> str:
        """
        Generate final feedback summaries.

        Returns:
            str: Generated feedback text
        """
        if not self.chat:
            raise ValueError("No active conversation")

        prompt = """Based on our conversation, generate the two feedback outputs now.

OUTPUT MUST START WITH EXACTLY THIS LINE (no text before it):
### Structured Summary

Then a blank line, then these bullet points in this exact format where every label AND its text are on the SAME line:
* **Context of evaluation**: [setting and timeframe]
* **Strengths**:
  * **[Competency Name]**: [one or two sentences describing what the student did well in that competency]
  * **[Competency Name]**: [one or two sentences]
* **Areas for Improvement**: [one or two sentences]
* **Suggested Focus for Development**: [one or two sentences]
* **Clinical Performance**: [rating]

Then a blank line, then:
### Student-Facing Narrative

Then a blank line, then the narrative paragraph(s).

ABSOLUTE RULES:
1. NEVER use definition-list syntax. FORBIDDEN: putting a label on its own line and then starting the next line with ": ". RIGHT: `* **Label**: text on same line`. WRONG: `Label\n: text on next line`.
2. Every competency under Strengths gets its own indented sub-bullet `  * **Name**: text`.
3. There must be a blank line immediately after each `###` heading.
4. Do not wrap the output in a code block or add any preamble."""

        try:
            # Log the feedback generation request
            self.conversation_history.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "turn": "feedback_generation",
                    "role": "system",
                    "content": prompt,
                }
            )

            start_time = time.time()
            response = self._call_with_backoff(self.chat.send_message, prompt)
            response_time_ms = (time.time() - start_time) * 1000

            if response is None or not response.text:
                raise ValueError("No response received from model")

            # Log feedback generation
            self.conversation_history.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "turn": "feedback_generation",
                    "role": "assistant",
                    "content": response.text,
                    "response_time_ms": round(response_time_ms, 2),
                }
            )

            return self._fix_markdown_formatting(response.text)

        except Exception as e:
            raise Exception(f"Error generating feedback: {str(e)}")

    def refine_feedback(self, refinement_request: str) -> str:
        """
        Refine the generated feedback based on user request.

        Args:
            refinement_request: User's refinement request

        Returns:
            str: Refined feedback text
        """
        if not self.chat:
            raise ValueError("No active conversation")

        try:
            # Create explicit refinement prompt
            # Direct and concise - no apologies or explanations needed
            refinement_prompt = f"""Apply this refinement and regenerate BOTH outputs:

{refinement_request}

Use the same exact format as the original: `### Structured Summary` and `### Student-Facing Narrative` headings, each followed by a blank line. Every bullet label and text on the same line (`* **Label**: text`). No definition-list syntax. Just the refined feedback, no explanation."""

            # Log the user's refinement request
            self.conversation_history.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "turn": "feedback_refinement",
                    "role": "user",
                    "content": refinement_prompt,
                }
            )

            start_time = time.time()
            response = self._call_with_backoff(
                self.chat.send_message, refinement_prompt
            )
            response_time_ms = (time.time() - start_time) * 1000

            if response is None or not response.text:
                raise ValueError("No response received from model")

            # Log the assistant's refined response
            self.conversation_history.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "turn": "feedback_refinement",
                    "role": "assistant",
                    "content": response.text,
                    "response_time_ms": round(response_time_ms, 2),
                }
            )

            return self._fix_markdown_formatting(response.text)

        except Exception as e:
            raise Exception(f"Error refining feedback: {str(e)}")

    def _fix_markdown_formatting(self, text: str) -> str:
        """
        Post-process LLM output to fix definition-list syntax into proper bullet format.

        Converts (definition-list style):
          Term
          : Definition
        into:
          * **Term**: Definition

        Items that follow a header-only bullet (e.g. "Strengths\n:") are
        indented as sub-bullets:
          * **Strengths**:
            * **Competency**: text

        Also ensures a blank line follows every ### heading.
        """
        lines = text.split("\n")
        fixed: list[str] = []
        # Track whether the last converted bullet was a "header-only" bullet
        # (no inline text, just "* **Label**:") — if so, subsequent converted
        # items become indented sub-bullets.
        in_sub_block = False
        i = 0
        while i < len(lines):
            current = lines[i]
            next_line = lines[i + 1] if i + 1 < len(lines) else None
            stripped = current.strip()

            # Leave headings and already-formatted bullets/indented lines untouched
            if (
                current.startswith("#")
                or current.startswith("*")
                or current.startswith(" ")
            ):
                # A top-level bullet with content ends the sub-block
                if current.startswith("* ") and not current.rstrip().endswith(":"):
                    in_sub_block = False
                fixed.append(current)
                i += 1
                continue

            # Blank lines pass through and do NOT reset sub-block state
            if not stripped:
                fixed.append(current)
                i += 1
                continue

            if next_line is not None and next_line.startswith(": ") and stripped:
                # "Term\n: definition" — inline definition
                definition = next_line[2:]
                if in_sub_block:
                    fixed.append(f"  * **{stripped}**: {definition}")
                else:
                    fixed.append(f"* **{stripped}**: {definition}")
                in_sub_block = False
                i += 2
            elif next_line is not None and next_line.strip() == ":" and stripped:
                # "Term\n:" — header-only bullet (e.g. "Strengths\n:")
                fixed.append(f"* **{stripped}**:")
                in_sub_block = True
                i += 2
            else:
                in_sub_block = False
                fixed.append(current)
                i += 1

        result = "\n".join(fixed)

        # Ensure blank line after every ### heading
        result = re.sub(
            r"(^#{1,6} .+$)\n([^\n])",
            r"\1\n\n\2",
            result,
            flags=re.MULTILINE,
        )

        return result

    def _log_turn(self, role: str, content: str, response_time_ms: float = None):
        """Log a conversation turn"""
        turn_data = {
            "timestamp": datetime.utcnow().isoformat(),
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

    def should_conclude_conversation(self) -> bool:
        """Check if conversation should conclude"""
        # Check turn limit
        if self.turn_count >= settings.MAX_TURNS:
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

            done_phrases = [
                "done",
                "that's all",
                "finished",
                "nothing else",
                "no more",
            ]
            if any(phrase in last_user_message for phrase in done_phrases):
                return True

        return False
