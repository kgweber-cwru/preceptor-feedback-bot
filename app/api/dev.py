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


# ---------------------------------------------------------------------------
# Canned conversation for MSA quick-test.
# Scenario: emergent appendectomy, covering Patient Care, Knowledge for Practice,
# Teamwork, Communication, and Professionalism. Numeric rating (4/5).
# ---------------------------------------------------------------------------
_CANNED_MESSAGES_MSA = [
    ("assistant", 0,
     "Thanks for taking a moment to share feedback on your student! I'll ask a few quick questions. "
     "First — what was the clinical setting, and roughly how long did you work together?"),
    ("user", 1,
     "We were in the OR for an emergent appendectomy that came in overnight. "
     "The student is Jordan Lee. We were together for about three hours including pre-op and PACU handoff."),
    ("assistant", 1,
     "Got it — overnight emergent case with Jordan Lee. That's a high-pressure setting. "
     "What stood out about how Jordan handled the pre-op assessment and preparation for induction?"),
    ("user", 2,
     "Really impressed. Jordan had already reviewed the chart before I arrived and flagged that the patient "
     "had a full stomach and a history of reflux. Brought up RSI without me having to prompt. "
     "Drug dosing was accurate and well-reasoned — knew the succinylcholine contraindications cold."),
    ("assistant", 2,
     "Excellent — strong knowledge base and good anticipation. How did Jordan do during induction and "
     "maintenance, and how did they interact with the surgical team and OR nurses?"),
    ("user", 3,
     "Induction was smooth. Jordan was calm, communicated clearly with the circulator about positioning, "
     "and checked in with the surgeon before draping. During maintenance, they stayed engaged — "
     "noticed an early trend toward hypotension and mentioned it before I did. "
     "Good situational awareness throughout."),
    ("assistant", 3,
     "That's a strong picture. Any areas where you'd like to see Jordan develop further?"),
    ("user", 4,
     "The one thing is decisiveness. When I asked Jordan to call the vasopressor dose, there was a pause "
     "and they looked to me for confirmation before acting. The reasoning was right, "
     "they just need to trust their judgment more in the moment. Also the PACU handoff was a bit rushed — "
     "good information but could be more structured."),
    ("assistant", 4,
     "Very helpful. Last question — on a scale of 1 to 5, where 1 is unacceptable, "
     "3 is meets expectations, and 5 is exemplary, how would you rate Jordan's overall performance?"),
    ("user", 5,
     "I'd say a 4. Strong performance, above what I'd expect at this stage, just that decisiveness piece to work on."),
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


@router.get("/quick-test-msa")
async def quick_test_msa(
    request: Request,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    DEV ONLY: Create a pre-seeded MSA conversation and redirect to it.
    Scenario: emergent appendectomy, numeric rating 4/5.
    """
    _dev_only()

    conversation = await firestore.create_conversation(
        user_id=current_user["user_id"],
        student_name="Jordan Lee (Quick Test — MSA)",
        model=settings.MODEL_NAME,
    )

    messages = [
        Message(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            turn=turn,
            role=MessageRole(role),
            content=content,
            response_time_ms=None if role == "user" else 350.0,
        )
        for role, turn, content in _CANNED_MESSAGES_MSA
    ]

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
