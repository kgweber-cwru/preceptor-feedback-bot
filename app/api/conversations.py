"""
Conversation API routes for managing AI conversations.
Handles conversation creation, messaging, and retrieval.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.dependencies import get_current_user, get_firestore, templates
from app.services.firestore_service import FirestoreService
from app.services.conversation_service import ConversationService
from app.models.conversation import ConversationCreate, MessageCreate

router = APIRouter()


@router.post("")
async def create_conversation(
    request: Request,
    conversation_data: ConversationCreate,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Create new conversation and return initial greeting.
    HTMX: Returns conversation ID and redirects to conversation page.
    """
    try:
        conv_service = ConversationService(firestore)

        # Create conversation
        conversation, initial_message = await conv_service.create_conversation(
            user_id=current_user["user_id"],
            student_name=conversation_data.student_name,
        )

        # For HTMX: Set HX-Redirect header to conversation page
        headers = {"HX-Redirect": f"/conversations/{conversation.conversation_id}"}

        return HTMLResponse(content="", headers=headers)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Get conversation page with full chat interface.
    """
    try:
        # Get conversation
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Check ownership
        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if should show "Generate Feedback" button
        conv_service = ConversationService(firestore)
        should_conclude = await conv_service.check_should_conclude(conversation_id)

        # Get feedback if it exists
        feedback = await firestore.get_feedback_by_conversation(conversation_id)

        return templates.TemplateResponse(
            "conversation.html",
            {
                "request": request,
                "user": current_user,
                "conversation": conversation,
                "should_conclude": should_conclude,
                "feedback": feedback,
                "current_content": feedback.get_current_content() if feedback else None,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: Request,
    message_data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Send message in conversation and get AI response.
    HTMX: Returns message HTML fragments to append to chat.
    """
    try:
        # Get conversation to check ownership
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Send message
        conv_service = ConversationService(firestore)
        ai_response, premature_feedback = await conv_service.send_message(
            conversation_id=conversation_id, user_message=message_data.content
        )

        # If premature feedback detected, handle it
        if premature_feedback:
            # Return warning message
            return HTMLResponse(
                f'''
                <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 my-4">
                    <p class="text-yellow-800 font-medium">⚠️ The AI generated feedback early</p>
                    <p class="text-sm text-yellow-700 mt-1">Click "Generate Feedback" below to proceed.</p>
                </div>
                {templates.get_template("components/message.html").render(
                    message={"role": "user", "content": message_data.content}
                )}
                {templates.get_template("components/message.html").render(
                    message={"role": "assistant", "content": ai_response.content}
                )}
                ''',
                headers={"HX-Trigger": "prematureFeedback"},
            )

        # Get updated conversation for turn count
        updated_conversation = await firestore.get_conversation(conversation_id)

        # Return user message + AI response as HTML fragments
        user_message_html = templates.get_template("components/message.html").render(
            message={"role": "user", "content": message_data.content}
        )

        ai_message_html = templates.get_template("components/message.html").render(
            message={"role": "assistant", "content": ai_response.content}
        )

        # Update turn counter using custom header
        # More reliable than out-of-band swaps which can be finicky
        print(f"DEBUG: Returning turn count: {updated_conversation.metadata.total_turns}")

        return HTMLResponse(
            content=user_message_html + ai_message_html,
            headers={
                "HX-Trigger": f'{{"updateTurnCounter": {{"count": {updated_conversation.metadata.total_turns}}}}}'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
