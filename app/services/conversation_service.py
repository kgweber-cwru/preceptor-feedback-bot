"""
Conversation service - integrates VertexAIClient with Firestore.
Handles business logic for creating and managing conversations.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from app.config import settings
from app.services.vertex_ai_client import VertexAIClient
from app.services.firestore_service import FirestoreService
from app.models.conversation import (
    Conversation,
    ConversationCreate,
    ConversationStatus,
    Message,
    MessageRole,
)


class ConversationService:
    """Service for managing AI conversations with Firestore persistence"""

    def __init__(self, firestore: FirestoreService):
        """
        Initialize conversation service.

        Args:
            firestore: Firestore service instance
        """
        self.firestore = firestore

    async def create_conversation(
        self, user_id: str, student_name: str
    ) -> tuple[Conversation, str]:
        """
        Create new conversation and get initial AI greeting.

        Args:
            user_id: User's Firestore document ID
            student_name: Student being evaluated

        Returns:
            tuple: (Conversation object, initial greeting message)
        """
        # Create conversation in Firestore
        conversation = await self.firestore.create_conversation(
            user_id=user_id, student_name=student_name, model=settings.MODEL_NAME
        )

        # Initialize AI client
        ai_client = VertexAIClient(conversation_id=conversation.conversation_id)
        ai_client.set_student_name(student_name)

        # Get initial greeting
        initial_message = ai_client.start_conversation()

        # Create message objects from AI client's conversation history
        messages = []
        for turn_data in ai_client.conversation_history:
            message = Message(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                timestamp=datetime.fromisoformat(turn_data["timestamp"]),
                turn=turn_data["turn"],
                role=MessageRole(turn_data["role"]),
                content=turn_data["content"],
                response_time_ms=turn_data.get("response_time_ms"),
            )
            messages.append(message)

        # Update conversation in Firestore with initial messages
        messages_dict = [msg.model_dump() for msg in messages]
        await self.firestore.update_conversation_messages(
            conversation_id=conversation.conversation_id,
            messages=messages_dict,
            total_turns=ai_client.turn_count,
        )

        # Update conversation object
        conversation.messages = messages
        conversation.metadata.total_turns = ai_client.turn_count

        return conversation, initial_message

    async def send_message(
        self, conversation_id: str, user_message: str
    ) -> tuple[Message, bool]:
        """
        Send message in conversation and get AI response.

        Args:
            conversation_id: Conversation document ID
            user_message: User's message text

        Returns:
            tuple: (AI response message, premature_feedback flag)
        """
        # Get conversation from Firestore
        conversation = await self.firestore.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Initialize AI client
        ai_client = VertexAIClient(conversation_id=conversation_id)
        ai_client.set_student_name(conversation.student_name)

        # Convert Firestore messages to dict format for restoration
        conversation_history = [
            {
                "timestamp": msg.timestamp.isoformat(),
                "turn": msg.turn,
                "role": msg.role.value,
                "content": msg.content,
                "response_time_ms": msg.response_time_ms,
            }
            for msg in conversation.messages
        ]

        # Restore conversation context by replaying history
        ai_client.restore_conversation(conversation_history)

        # Send user message
        response_data = ai_client.send_message(user_message)

        # Create user message object
        user_msg = Message(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            turn=ai_client.turn_count,
            role=MessageRole.USER,
            content=user_message,
        )

        # Create AI response message object
        ai_msg = Message(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.fromisoformat(response_data["timestamp"]),
            turn=response_data["turn"],
            role=MessageRole(response_data["role"]),
            content=response_data["content"],
            response_time_ms=response_data.get("response_time_ms"),
        )

        # Update Firestore with new messages
        all_messages = conversation.messages + [user_msg, ai_msg]
        messages_dict = [msg.model_dump() for msg in all_messages]

        await self.firestore.update_conversation_messages(
            conversation_id=conversation_id,
            messages=messages_dict,
            total_turns=ai_client.turn_count,
        )

        return ai_msg, response_data.get("contains_feedback", False)

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation by ID.

        Args:
            conversation_id: Conversation document ID

        Returns:
            Conversation object or None
        """
        return await self.firestore.get_conversation(conversation_id)

    async def list_user_conversations(
        self,
        user_id: str,
        status: Optional[ConversationStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[dict]:
        """
        List conversations for a user.

        Args:
            user_id: User document ID
            status: Optional status filter
            limit: Max conversations to return
            offset: Pagination offset

        Returns:
            List of conversation summaries
        """
        summaries = await self.firestore.list_conversations(
            user_id=user_id, status=status, limit=limit, offset=offset
        )

        return [summary.model_dump() for summary in summaries]

    async def check_should_conclude(self, conversation_id: str) -> bool:
        """
        Check if conversation should conclude.

        Args:
            conversation_id: Conversation document ID

        Returns:
            bool: True if should conclude
        """
        conversation = await self.firestore.get_conversation(conversation_id)
        if not conversation:
            return False

        # Check turn limit
        if conversation.metadata.total_turns >= settings.MAX_TURNS:
            return True

        # Check last user message for completion indicators
        user_messages = [
            msg for msg in reversed(conversation.messages) if msg.role == MessageRole.USER
        ]

        if user_messages:
            last_message = user_messages[0].content.lower()
            done_phrases = [
                "done",
                "that's all",
                "finished",
                "nothing else",
                "no more",
            ]
            if any(phrase in last_message for phrase in done_phrases):
                return True

        return False

    async def generate_feedback(self, conversation_id: str) -> 'Feedback':
        """
        Generate feedback for a conversation.

        Args:
            conversation_id: Conversation document ID

        Returns:
            Feedback object with initial version
        """
        from app.models.feedback import Feedback, FeedbackVersion, FeedbackVersionType

        # Get conversation
        conversation = await self.firestore.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Check if feedback already exists
        existing_feedback = await self.firestore.get_feedback_by_conversation(conversation_id)
        if existing_feedback:
            return existing_feedback

        # Initialize AI client and restore conversation
        ai_client = VertexAIClient(conversation_id=conversation_id)
        ai_client.set_student_name(conversation.student_name)

        # Convert Firestore messages to dict format for restoration
        conversation_history = [
            {
                "timestamp": msg.timestamp.isoformat(),
                "turn": msg.turn,
                "role": msg.role.value,
                "content": msg.content,
                "response_time_ms": msg.response_time_ms,
            }
            for msg in conversation.messages
        ]

        # Restore conversation context
        ai_client.restore_conversation(conversation_history)

        # Generate feedback
        feedback_content = ai_client.generate_feedback()

        # Create feedback object
        feedback = await self.firestore.create_feedback(
            conversation_id=conversation_id,
            user_id=conversation.user_id,
            student_name=conversation.student_name,
            initial_content=feedback_content,
        )

        return feedback

    async def refine_feedback(self, conversation_id: str, refinement_request: str) -> 'Feedback':
        """
        Refine existing feedback based on user request.

        Args:
            conversation_id: Conversation document ID
            refinement_request: User's refinement request

        Returns:
            Updated Feedback object with new version
        """
        # Get conversation
        conversation = await self.firestore.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Get existing feedback
        feedback = await self.firestore.get_feedback_by_conversation(conversation_id)
        if not feedback:
            raise ValueError(f"No feedback found for conversation {conversation_id}")

        # Initialize AI client and restore conversation
        ai_client = VertexAIClient(conversation_id=conversation_id)
        ai_client.set_student_name(conversation.student_name)

        # Convert Firestore messages to dict format for restoration
        conversation_history = [
            {
                "timestamp": msg.timestamp.isoformat(),
                "turn": msg.turn,
                "role": msg.role.value,
                "content": msg.content,
                "response_time_ms": msg.response_time_ms,
            }
            for msg in conversation.messages
        ]

        # Restore conversation context
        ai_client.restore_conversation(conversation_history)

        # Refine feedback
        refined_content = ai_client.refine_feedback(refinement_request)

        # Add refinement version to feedback
        updated_feedback = await self.firestore.add_feedback_refinement(
            feedback_id=feedback.feedback_id,
            refinement_content=refined_content,
            refinement_request=refinement_request,
        )

        return updated_feedback
