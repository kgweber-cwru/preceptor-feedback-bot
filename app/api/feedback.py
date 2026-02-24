"""
Feedback API routes for generating and refining feedback.
Handles feedback generation, refinement, and download.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import tempfile
import os
from datetime import datetime

from app.dependencies import get_current_user, get_firestore, templates
from app.services.firestore_service import FirestoreService
from app.services.conversation_service import ConversationService
from app.models.feedback import FeedbackRefinementRequest

router = APIRouter()


@router.get("/conversations/{conversation_id}/feedback")
async def get_feedback_page(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Get feedback page - either shows existing feedback or generates new feedback.
    """
    try:
        # Get conversation
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if feedback already exists
        feedback = await firestore.get_feedback_by_conversation(conversation_id)

        if feedback:
            # Show existing feedback
            return templates.TemplateResponse(
                "feedback.html",
                {
                    "request": request,
                    "conversation": conversation,
                    "feedback": feedback,
                    "current_content": feedback.get_current_content(),
                },
            )
        else:
            # Generate new feedback
            conv_service = ConversationService(firestore)
            feedback = await conv_service.generate_feedback(conversation_id)

            return templates.TemplateResponse(
                "feedback.html",
                {
                    "request": request,
                    "conversation": conversation,
                    "feedback": feedback,
                    "current_content": feedback.get_current_content(),
                },
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/feedback/refine")
async def refine_feedback(
    conversation_id: str,
    request: Request,
    refinement_data: FeedbackRefinementRequest,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Refine existing feedback based on user request.
    HTMX: Returns updated feedback HTML fragment.
    """
    try:
        # Get conversation to check ownership
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Refine feedback
        conv_service = ConversationService(firestore)
        feedback = await conv_service.refine_feedback(
            conversation_id=conversation_id,
            refinement_request=refinement_data.refinement_request
        )

        # Return updated feedback content as HTML (not TemplateResponse)
        # This ensures HTMX can swap it properly
        content_html = templates.get_template("components/feedback_content.html").render(
            request=request,
            feedback=feedback,
            current_content=feedback.get_current_content(),
            conversation_id=conversation_id,
        )

        return HTMLResponse(content=content_html)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/feedback/download")
async def download_feedback(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Download feedback as a text file.
    """
    try:
        # Get conversation and feedback
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        feedback = await firestore.get_feedback_by_conversation(conversation_id)

        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        # Create temporary file
        timestamp = feedback.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"feedback_{timestamp}_{conversation.student_name.replace(' ', '_')}.txt"

        # Write feedback to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(f"Feedback for {conversation.student_name}\n")
            f.write(f"Generated: {feedback.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Version: {feedback.current_version}\n")
            f.write("=" * 80 + "\n\n")
            f.write(feedback.get_current_content())
            temp_path = f.name

        # Return file and clean up after download
        return FileResponse(
            path=temp_path,
            filename=filename,
            media_type='text/plain',
            background=lambda: os.unlink(temp_path)  # Delete temp file after download
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/finish")
async def finish_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Mark conversation as completed and redirect to survey page.
    """
    try:
        # Get conversation
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Update status to completed
        from app.models.conversation import ConversationStatus
        await firestore.update_conversation_status(conversation_id, ConversationStatus.COMPLETED)

        # Redirect to survey page
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/conversations/{conversation_id}/survey"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
