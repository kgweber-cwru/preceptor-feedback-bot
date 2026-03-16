"""
User API routes for dashboard and user-specific operations.
Handles conversation history listing, search, and filtering.
"""

from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.dependencies import get_current_user, get_firestore, templates
from app.services.firestore_service import FirestoreService
from app.services.conversation_service import ConversationService
from app.models.conversation import ConversationStatus

router = APIRouter()


@router.get("/api/conversations", response_class=HTMLResponse)
async def list_conversations(
    request: Request,
    search: Optional[str] = Query(None, description="Search by student name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Max conversations to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: dict = Depends(get_current_user),
    firestore: FirestoreService = Depends(get_firestore),
):
    """
    Get conversations for the current user with optional filters.
    Returns HTML fragments (conversation cards) for HTMX.
    """
    try:
        conv_service = ConversationService(firestore)

        # Parse status filter
        status_filter = None
        if status and status != "all":
            try:
                status_filter = ConversationStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        # Get conversations (always use firestore directly for ConversationSummary objects)
        if search:
            # Use search method (case-insensitive)
            conversations = await firestore.search_conversations(
                user_id=current_user["user_id"],
                query=search,
                status=status_filter,
                limit=limit,
                offset=offset,
            )
        else:
            # Use standard list method
            conversations = await firestore.list_conversations(
                user_id=current_user["user_id"],
                status=status_filter,
                limit=limit,
                offset=offset,
            )

        # If no conversations found
        if not conversations:
            if offset == 0:
                # First page - show empty state
                return HTMLResponse("""
                    <div class="text-center py-12">
                        <div class="text-gray-400 text-6xl mb-4">💬</div>
                        <h3 class="text-xl font-semibold text-gray-700 mb-2">No conversations yet</h3>
                        <p class="text-gray-500">Start a new feedback session above to get started</p>
                    </div>
                """)
            else:
                # No more results - return empty for infinite scroll
                return HTMLResponse("")

        # Render conversation cards
        cards_html = ""
        for conv in conversations:
            card_html = templates.get_template("components/conversation_card.html").render(
                conversation=conv,
                request=request,
            )
            cards_html += card_html

        # If this is pagination (offset > 0), add another scroll trigger if we got full results
        if offset > 0 and len(conversations) == limit:
            cards_html += f"""
                <div
                    hx-get="/api/conversations?offset={offset + limit}&status={status or ''}&search={search or ''}"
                    hx-trigger="revealed"
                    hx-swap="afterend"
                    class="loading-trigger"
                >
                    <div class="text-center py-4 text-gray-500">
                        <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                        <span class="ml-2">Loading more...</span>
                    </div>
                </div>
            """

        return HTMLResponse(cards_html)

    except HTTPException:
        raise
    except Exception as e:
        # Log the full traceback for debugging
        import traceback
        print(f"ERROR in list_conversations: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
