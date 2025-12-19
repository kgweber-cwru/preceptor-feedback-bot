"""
Survey API routes for collecting user feedback about the tool.
Handles survey display, submission, and skip functionality.
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.dependencies import get_current_user, get_firestore
from app.services.firestore_service import FirestoreService
from app.models.survey import SurveyCreate, ToolRating

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/conversations/{conversation_id}/survey", response_class=HTMLResponse)
async def show_survey(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Show survey form after finishing feedback session.
    """
    try:
        # Get conversation to extract student name and check ownership
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if survey already submitted for this conversation
        existing_survey = await firestore.get_survey_by_conversation(conversation_id)
        if existing_survey:
            # Survey already submitted, redirect to dashboard
            return RedirectResponse(url="/dashboard", status_code=302)

        return templates.TemplateResponse(
            "survey.html",
            {
                "request": request,
                "conversation": conversation,
                "tool_ratings": [rating.value for rating in ToolRating],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/survey")
async def submit_survey(
    conversation_id: str,
    preceptor_name: Optional[str] = Form(None),
    tool_rating: str = Form(...),
    comments: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Submit survey response and redirect to dashboard.
    Uses standard form submission (not HTMX).
    """
    try:
        # Get conversation to extract student name and check ownership
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if survey already submitted
        existing_survey = await firestore.get_survey_by_conversation(conversation_id)
        if existing_survey:
            # Already submitted, just redirect
            return RedirectResponse(url="/dashboard", status_code=302)

        # Validate and create survey
        try:
            survey_data = SurveyCreate(
                preceptor_name=preceptor_name,
                tool_rating=ToolRating(tool_rating),
                comments=comments,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid survey data: {str(e)}")

        # Save survey to Firestore
        await firestore.create_survey(
            conversation_id=conversation_id,
            user_id=current_user["user_id"],
            student_name=conversation.student_name,
            survey_data=survey_data,
            skipped=False,
        )

        # Redirect to dashboard
        return RedirectResponse(url="/dashboard", status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/survey/skip")
async def skip_survey(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Skip survey (still record the skip in Firestore).
    """
    try:
        # Get conversation to extract student name and check ownership
        conversation = await firestore.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conversation.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if survey already submitted
        existing_survey = await firestore.get_survey_by_conversation(conversation_id)
        if not existing_survey:
            # Create empty survey with skipped=True
            # Use first rating as placeholder (won't be used since skipped=True)
            survey_data = SurveyCreate(
                preceptor_name=None,
                tool_rating=ToolRating.GREAT_FIRST_TRY,
                comments=None,
            )

            await firestore.create_survey(
                conversation_id=conversation_id,
                user_id=current_user["user_id"],
                student_name=conversation.student_name,
                survey_data=survey_data,
                skipped=True,
            )

        # Redirect to dashboard
        return RedirectResponse(url="/dashboard", status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
