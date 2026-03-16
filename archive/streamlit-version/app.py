"""
Preceptor Feedback Bot - Streamlit Application
A conversational tool for faculty to provide structured feedback on medical students.
"""

import json
import os
import re
from datetime import datetime

import streamlit as st

from config import Config
from utils import logger
from utils.vertex_ai_client import VertexAIClient


# Authentication check (stubbed for future use)
def check_authentication():
    """
    Check if user is authenticated.
    Currently a stub - returns True to allow all users.

    To enable authentication later:
    1. Set REQUIRE_AUTH=true in environment variables
    2. Deploy Cloud Run with --no-allow-unauthenticated
    3. Implement one of these options:
       - Identity-Aware Proxy (IAP) - reads headers
       - Streamlit auth (if using Streamlit Cloud)
       - Custom OAuth flow
       - Simple password protection

    Returns:
        bool: True if user is authenticated, False otherwise
    """
    if not Config.REQUIRE_AUTH:
        return True

    # TODO: Implement actual authentication
    # Example using IAP headers (when enabled):
    # user_email = st.experimental_get_query_params().get("user_email")
    # if user_email and user_email[0] in Config.ALLOWED_USERS:
    #     return True

    # For now, allow everyone
    logger.debug("Authentication check bypassed (REQUIRE_AUTH=false)")
    return True


def show_authentication_error():
    """Display authentication error page"""
    st.error("🔒 Authentication Required")
    st.write("You must be authenticated to access this application.")
    st.write("Please contact the administrator for access.")
    st.stop()


# Check authentication before rendering app
if not check_authentication():
    show_authentication_error()

# Page configuration
st.set_page_config(
    page_title="Preceptor Feedback Bot",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="collapsed",  # Default to collapsed for mobile
)

# Initialize configuration
try:
    Config.validate()
except ValueError as e:
    logger.config_validation_failed(str(e))
    st.error(f"Configuration Error: {e}")
    st.stop()


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if "client" not in st.session_state:
        st.session_state.client = None
    if "conversation_started" not in st.session_state:
        st.session_state.conversation_started = False
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "feedback_generated" not in st.session_state:
        st.session_state.feedback_generated = False
    if "current_feedback" not in st.session_state:
        st.session_state.current_feedback = ""
    if "student_name" not in st.session_state:
        st.session_state.student_name = ""
    if "show_survey" not in st.session_state:
        st.session_state.show_survey = False


def start_conversation():
    """Initialize a new conversation"""
    # Require student name before starting
    if not st.session_state.student_name or not st.session_state.student_name.strip():
        st.error("Please enter a student name before starting the conversation.")
        return

    try:
        st.session_state.client = VertexAIClient()
        st.session_state.client.set_student_name(st.session_state.student_name)

        initial_message = st.session_state.client.start_conversation()

        st.session_state.messages = [{"role": "assistant", "content": initial_message}]
        st.session_state.conversation_started = True
        st.session_state.feedback_generated = False

    except Exception as e:
        logger.error(f"Failed to start conversation: {e}")
        st.error(f"Error starting conversation: {e}")
        st.session_state.conversation_started = False


def on_student_name_change():
    """Callback when student name input changes - auto-captures the value"""
    # Auto-save from the widget to session state
    # The key binding handles this automatically, this is just for logging
    if st.session_state.student_name_input:
        logger.debug(f"Student name captured: {st.session_state.student_name_input}")


def send_message(user_input: str):
    """Send user message and get response"""
    if not st.session_state.client:
        logger.error("send_message called without active client")
        st.error("No active conversation. Please start a new conversation.")
        return

    # Add user message to display
    st.session_state.messages.append({"role": "user", "content": user_input})

    try:
        # Get bot response (now returns tuple)
        response, contains_feedback = st.session_state.client.send_message(user_input)
        st.session_state.messages.append({"role": "assistant", "content": response})

        # If model generated feedback prematurely, flip the flag
        if contains_feedback and not st.session_state.feedback_generated:
            st.session_state.feedback_generated = True
            st.session_state.current_feedback = response
            st.warning(
                "⚠️ The model generated feedback early. You can now review and refine it below."
            )
            logger.feedback_generated(
                student_name=st.session_state.student_name or "unknown", premature=True
            )

        # Check if conversation should conclude
        if st.session_state.client.should_conclude_conversation():
            st.info(
                "🎯 Conversation limit reached or completion indicated. Ready to generate feedback."
            )

    except Exception as e:
        logger.error(
            f"Error in send_message: {e}", student=st.session_state.student_name
        )
        st.error(f"Error sending message: {e}")


def generate_feedback():
    """Generate final feedback summaries"""
    if not st.session_state.client:
        logger.error("generate_feedback called without active client")
        st.error("No active conversation.")
        return

    try:
        feedback = st.session_state.client.generate_feedback()
        st.session_state.current_feedback = feedback
        st.session_state.feedback_generated = True

        # Auto-save conversation log immediately
        st.session_state.client.save_conversation_log(
            st.session_state.student_name or "unknown"
        )

        # Auto-save feedback draft immediately
        feedback_path = save_feedback_file(
            feedback,
            st.session_state.student_name,
            show_success=False,  # Don't show success message yet
        )
        if feedback_path:
            logger.info(
                "Draft feedback auto-saved",
                student=st.session_state.student_name,
                path=feedback_path,
            )

    except Exception as e:
        logger.error(
            f"Error generating feedback: {e}", student=st.session_state.student_name
        )
        st.error(f"Error generating feedback: {e}")


def refine_feedback(refinement_request: str):
    """Refine the generated feedback"""
    if not st.session_state.client:
        logger.error("refine_feedback called without active client")
        st.error("No active conversation.")
        return

    try:
        refined = st.session_state.client.refine_feedback(refinement_request)
        st.session_state.current_feedback = refined

        # Auto-update the saved feedback file with refinements
        feedback_path = save_feedback_file(
            refined,
            st.session_state.student_name,
            show_success=False,  # Don't show success message for each refinement
        )
        if feedback_path:
            logger.info(
                "Feedback updated with refinement",
                student=st.session_state.student_name,
                path=feedback_path,
            )

    except Exception as e:
        logger.error(
            f"Error refining feedback: {e}", student=st.session_state.student_name
        )
        st.error(f"Error refining feedback: {e}")


def save_feedback_file(
    feedback_text: str, student_name: str, show_success: bool = True
) -> str:
    """Save feedback to file and return the path. Can be called multiple times to update."""
    if not feedback_text:
        return ""

    student_for_fname = student_name or "unknown"
    # Sanitize filename: allow alnum, dash, underscore
    safe_student = re.sub(r"[^A-Za-z0-9_-]", "_", student_for_fname.strip())

    # Use consistent timestamp stored in session state for this feedback session
    if "feedback_timestamp" not in st.session_state:
        st.session_state.feedback_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    timestamp = st.session_state.feedback_timestamp
    feedback_fname = f"feedback_{timestamp}_{safe_student}.txt"

    try:
        if Config.IS_CLOUD:
            # Cloud: Save to Cloud Storage
            from google.cloud import storage

            client = storage.Client()
            bucket = client.bucket(Config.LOG_BUCKET)
            blob = bucket.blob(feedback_fname)
            blob.upload_from_string(feedback_text, content_type="text/plain")
            feedback_path = f"gs://{Config.LOG_BUCKET}/{feedback_fname}"
            logger.info(
                "Feedback saved to Cloud Storage",
                student=student_for_fname,
                file=feedback_path,
            )
            if show_success:
                st.success(f"✅ Feedback saved: {feedback_path}")
        else:
            # Local: Save to ./output directory
            output_dir = os.path.join(".", "output")
            os.makedirs(output_dir, exist_ok=True)
            feedback_path = os.path.join(output_dir, feedback_fname)

            with open(feedback_path, "w") as f:
                f.write(feedback_text)

            logger.info(
                "Feedback saved to local file",
                student=student_for_fname,
                file=feedback_path,
            )
            if show_success:
                st.success(f"✅ Feedback saved: {feedback_path}")

        return feedback_path

    except Exception as e:
        logger.error(
            f"Failed to save feedback: {e}",
            student=student_name,
        )
        if show_success:
            st.error(f"Error saving feedback file: {e}")
        return ""


def save_and_finish():
    """Save conversation log and finish"""
    if st.session_state.client:
        try:
            # Conversation log already saved during generate_feedback() and refinements
            # Just confirm
            st.success("✅ Conversation and feedback saved!")

            # ALWAYS save final feedback to ensure we have the latest version
            if st.session_state.current_feedback:
                feedback_path = save_feedback_file(
                    st.session_state.current_feedback,
                    st.session_state.student_name,
                    show_success=False,  # Already showing success above
                )
                logger.info(
                    "Final feedback saved",
                    student=st.session_state.student_name,
                    path=feedback_path,
                )

            # Show survey instead of immediately resetting
            logger.info(
                "Session completed, showing survey",
                student=st.session_state.student_name,
            )
            st.session_state.show_survey = True

        except Exception as e:
            logger.error(
                f"Error saving conversation: {e}", student=st.session_state.student_name
            )
            st.error(f"Error saving conversation: {e}")
    else:
        logger.error("save_and_finish called without active client")
        st.error("No active conversation.")


def submit_survey():
    """Save survey responses and reset session"""
    # Gather survey data
    survey_data = {
        "timestamp": datetime.now().isoformat(),
        "preceptor_name": st.session_state.get("survey_preceptor_name", ""),
        "tool_rating": st.session_state.get("survey_rating", ""),
        "comments": st.session_state.get("survey_comments", ""),
        "student_name": st.session_state.student_name,
    }

    # Log survey response
    logger.info(
        "Survey response received",
        preceptor=survey_data["preceptor_name"],
        rating=survey_data["tool_rating"],
        student=survey_data["student_name"],
    )

    # Save survey to file
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        survey_fname = f"survey_{timestamp}.json"

        if Config.IS_CLOUD:
            from google.cloud import storage

            client = storage.Client()
            bucket = client.bucket(Config.LOG_BUCKET)
            blob = bucket.blob(survey_fname)
            blob.upload_from_string(
                json.dumps(survey_data, indent=2), content_type="application/json"
            )
            logger.info(f"Survey saved to gs://{Config.LOG_BUCKET}/{survey_fname}")
        else:
            # Save to output directory (same as feedback files)
            output_dir = os.path.join(".", "output")
            os.makedirs(output_dir, exist_ok=True)
            survey_path = os.path.join(output_dir, survey_fname)
            with open(survey_path, "w") as f:
                json.dump(survey_data, f, indent=2)
            logger.info(f"Survey saved to {survey_path}")
    except Exception as e:
        logger.error(f"Failed to save survey: {e}")

    # Reset session
    st.session_state.client = None
    st.session_state.conversation_started = False
    st.session_state.messages = []
    st.session_state.feedback_generated = False
    st.session_state.current_feedback = ""
    st.session_state.student_name = ""
    st.session_state.show_survey = False
    if "feedback_timestamp" in st.session_state:
        del st.session_state.feedback_timestamp


# Main UI
def main():
    """Main application UI"""
    initialize_session_state()

    # Log application start once per Streamlit session to avoid noisy repeats
    # (Streamlit re-runs the script on every interaction).
    if not st.session_state.get("app_started_logged"):
        logger.app_started()
        st.session_state.app_started_logged = True

    # Sidebar - Configuration info only (collapsible for mobile)
    with st.sidebar:
        st.title("⚙️ Configuration")

        st.markdown("### Model Settings")
        st.info(f"**Model**: {Config.get_model_display_name()}")
        st.text(f"Temperature: {Config.TEMPERATURE}")
        st.text(f"Max Tokens: {Config.MAX_OUTPUT_TOKENS}")

        st.markdown("### Conversation Settings")
        st.text(f"Max Turns: {Config.MAX_TURNS}")
        if Config.IS_CLOUD:
            st.text(f"Session Timeout: {Config.CLOUD_RUN_TIMEOUT // 60} min")

        if st.session_state.conversation_started and st.session_state.client:
            st.markdown("### Current Session")
            st.text(f"Turn: {st.session_state.client.turn_count}/{Config.MAX_TURNS}")

        st.markdown("---")
        with st.expander("ℹ️ Deployment Info"):
            st.caption(f"Environment: {Config.DEPLOYMENT_ENV}")
            st.caption(f"Project: {Config.GCP_PROJECT_ID}")
            st.caption(f"Region: {Config.GCP_REGION}")
            if Config.IS_CLOUD:
                st.caption(f"Logs: gs://{Config.LOG_BUCKET}")
            else:
                st.caption(f"Logs: {Config.LOG_DIRECTORY}")

    # Main content area
    st.title("🩺 Preceptor Feedback Bot")
    st.caption("A conversational tool for providing structured student feedback")

    # Show survey if session just completed
    if st.session_state.show_survey:
        st.success("✅ Feedback session completed and saved!")
        st.markdown("---")
        st.markdown(
            "### If you have another minute, we'd appreciate your feedback on this tool"
        )

        st.text_input(
            "Preceptor Name (optional)",
            key="survey_preceptor_name",
            placeholder="Your name",
        )

        st.radio(
            "This tool...",
            options=[
                "Was great on the first try",
                "Gave me something helpful I can edit",
                "Not especially helpful",
            ],
            key="survey_rating",
        )

        st.text_area(
            "Comments (optional)",
            key="survey_comments",
            placeholder="Any feedback or suggestions for improvement?",
        )

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("Submit Feedback", type="primary", use_container_width=True):
                submit_survey()
                st.rerun()
        with col2:
            if st.button("Skip", use_container_width=True):
                submit_survey()  # Still resets session, just doesn't save survey
                st.rerun()

        st.stop()  # Don't show rest of UI while survey is displayed

    # Student name input - REQUIRED before conversation starts
    if not st.session_state.conversation_started:
        st.markdown("### 👤 Student Information")

        st.text_input(
            "Student Name *",
            placeholder="e.g., Jane Doe",
            key="student_name_input",
            on_change=on_student_name_change,
            help="Required - This will be included in the feedback report",
        )

        # Auto-sync from widget to session_state.student_name
        if st.session_state.student_name_input:
            st.session_state.student_name = st.session_state.student_name_input

        # Show status message
        if not st.session_state.student_name:
            st.warning(
                "⚠️ Please enter the student's name before starting the conversation."
            )
        else:
            st.success(
                f"✓ Ready to provide feedback for: **{st.session_state.student_name}**. This session will time out after {Config.CLOUD_RUN_TIMEOUT // 60} minutes of inactivity."
            )

            # Start button appears below the success banner
            if st.button(
                "🔄 Start Conversation",
                type="primary",
                use_container_width=True,
            ):
                start_conversation()
                st.rerun()

        st.markdown("---")

    # Main conversation area
    if not st.session_state.conversation_started:
        # Instructions
        st.markdown(
            """
        ### How This Works
        
        1. **Enter student name** - Required for the feedback report
        2. **Start conversation** - Click the button above to begin
        3. **Answer questions** - The bot will ask about the student's performance
        4. **Generate feedback** - Click the button when conversation is complete
        5. **Review and refine** - Edit or request changes before finalizing
        6. **Download & Save** - Get a copy for yourself and save to server logs
        
        This tool organizes your observations according to CWRU's competency framework and generates 
        both a summary for administrators and constructive narrative feedback for the student.
        """
        )

    else:
        # Display conversation
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Action bar above chat input (always visible on mobile)
        if not st.session_state.feedback_generated:
            # Visual separator
            st.markdown("---")

            # Create action bar with progress + button
            col1, col2 = st.columns([1, 2])

            with col1:
                if st.session_state.client:
                    st.caption("**Conversation Progress**")
                    st.info(f"**{st.session_state.client.turn_count}** of {Config.MAX_TURNS} turns")

            with col2:
                st.caption("**Ready to continue?**")
                if st.button(
                    "📝 Generate Feedback",
                    type="primary",
                    use_container_width=True,
                    key="generate_feedback_button"
                ):
                    generate_feedback()
                    st.rerun()

            # Chat input appears at bottom (pinned by Streamlit)
            user_input = st.chat_input("Type your response here...")
            if user_input:
                send_message(user_input)
                st.rerun()

        # Feedback display and refinement
        if st.session_state.feedback_generated:
            st.markdown("---")
            st.markdown("## 📋 Generated Feedback")

            st.markdown(st.session_state.current_feedback)

            st.markdown("---")

            # Refinement input
            refinement = st.text_input(
                "Request changes (optional)",
                placeholder="e.g., 'Make it more concise' or 'Add more emphasis on teamwork'",
            )
            if refinement and st.button("🔄 Refine Feedback"):
                refine_feedback(refinement)
                st.rerun()

            st.markdown("---")

            # Action buttons
            col1, col2, col3 = st.columns([2, 2, 2])

            with col1:
                # Prepare download filename
                student_for_fname = st.session_state.student_name or "unknown"
                safe_student = re.sub(r"[^A-Za-z0-9_-]", "_", student_for_fname.strip())
                timestamp = st.session_state.get(
                    "feedback_timestamp", datetime.now().strftime("%Y%m%d_%H%M%S")
                )
                download_fname = f"feedback_{safe_student}_{timestamp}.txt"

                st.download_button(
                    label="📥 Download Feedback",
                    data=st.session_state.current_feedback,
                    file_name=download_fname,
                    mime="text/plain",
                    use_container_width=True,
                )

            with col2:
                if st.button(
                    "✅ Finish, Save, and Clear",
                    type="primary",
                    use_container_width=True,
                ):
                    save_and_finish()
                    st.success("Conversation completed and saved to server logs!")
                    st.rerun()

            with col3:
                # Empty column for spacing / future use
                pass


if __name__ == "__main__":
    main()
