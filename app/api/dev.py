"""
Developer-only routes for local testing.
All endpoints in this router return 404 unless DEPLOYMENT_ENV=local.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_current_user, get_firestore
from app.models.conversation import Message, MessageRole
from app.services.firestore_service import FirestoreService

router = APIRouter(prefix="/dev", tags=["dev"])

# ---------------------------------------------------------------------------
# Canned conversation used for quick feedback testing.
# Covers several CWRU competency domains so the generated feedback is rich.
# ---------------------------------------------------------------------------
_CANNED_MESSAGES = [
    ("assistant", 0,
     "Thanks for taking a moment to share feedback on your student! I'll ask a few quick questions. "
     "First — what was the clinical setting, and roughly how long did you work together?"),
    ("user", 1,
     "We were in the outpatient primary care clinic for a half-day. The student is Alex Johnson."),
    ("assistant", 1,
     "Got it — primary care clinic, half-day with Alex Johnson. What stood out about their performance?"),
    ("user", 2,
     "Alex was excellent at taking histories. Very thorough and patient-centered. "
     "Picked up on a subtle detail about a patient's medication history that I had missed."),
    ("assistant", 2,
     "That's a great example of strong patient care and clinical reasoning. "
     "Did you notice anything about how Alex interacted with the rest of the team or communicated with patients?"),
    ("user", 3,
     "Really good communication — patients clearly felt comfortable. "
     "Also worked well with the MA and the nurse. No issues there. "
     "Knowledge of hypertension guidelines was impressive for their level."),
    ("assistant", 3,
     "Nice. Anything you'd like Alex to work on or a suggestion for their next rotation?"),
    ("user", 4,
     "The main thing is presentation skills. The oral presentations were accurate but a bit disorganized. "
     "I'd suggest working on a consistent SOAP structure when presenting."),
    ("assistant", 4,
     "Helpful, thank you. Last question — how would you rate the overall clinical performance: "
     "below expectations, meets expectations, exceeds expectations, or outstanding?"),
    ("user", 5,
     "Exceeds expectations overall."),
    ("assistant", 5,
     "Perfect — I have everything I need. Click 'Generate Feedback' when you're ready."),
]


def _dev_only():
    """Raise 404 if not running in local dev mode."""
    if settings.DEPLOYMENT_ENV != "local":
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/quick-test")
async def quick_test(
    request: Request,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    DEV ONLY: Create a pre-seeded conversation and redirect to it.
    Skips the chat phase so you can test feedback generation immediately.
    """
    _dev_only()

    # Create the conversation record
    conversation = await firestore.create_conversation(
        user_id=current_user["user_id"],
        student_name="Alex Johnson (Quick Test)",
        model=settings.MODEL_NAME,
    )

    # Build canned Message objects
    messages = [
        Message(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            turn=turn,
            role=MessageRole(role),
            content=content,
            response_time_ms=None if role == "user" else 350.0,
        )
        for role, turn, content in _CANNED_MESSAGES
    ]

    # Persist the messages and set turn count
    messages_dict = [msg.model_dump() for msg in messages]
    await firestore.update_conversation_messages(
        conversation_id=conversation.conversation_id,
        messages=messages_dict,
        total_turns=5,
    )

    return RedirectResponse(
        url=f"/conversations/{conversation.conversation_id}",
        status_code=302,
    )
