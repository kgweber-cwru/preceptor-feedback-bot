#!/usr/bin/env python3
"""
Test script to debug conversation flow issues.
Tests turn counting and feedback refinement.
"""

import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app.services.firestore_service import FirestoreService
from app.services.conversation_service import ConversationService
from app.config import settings


async def test_turn_counting():
    """Test that turn counting works correctly"""
    print("=" * 60)
    print("TEST 1: Turn Counter")
    print("=" * 60)
    print()

    firestore = FirestoreService()
    conv_service = ConversationService(firestore)

    # Create conversation
    print("1. Creating conversation...")
    conversation, initial_message = await conv_service.create_conversation(
        user_id="test_user_123",
        student_name="Test Student"
    )
    print(f"✓ Created conversation: {conversation.conversation_id}")
    print(f"  Initial turn count: {conversation.metadata.total_turns}")
    print(f"  Number of messages: {len(conversation.messages)}")
    print()

    # Send first message
    print("2. Sending first user message...")
    ai_response, premature = await conv_service.send_message(
        conversation_id=conversation.conversation_id,
        user_message="The student did very well today."
    )

    # Get updated conversation
    updated_conv = await firestore.get_conversation(conversation.conversation_id)
    print(f"✓ Sent message 1")
    print(f"  Turn count after message 1: {updated_conv.metadata.total_turns}")
    print(f"  Number of messages: {len(updated_conv.messages)}")
    print()

    # Send second message
    print("3. Sending second user message...")
    ai_response, premature = await conv_service.send_message(
        conversation_id=conversation.conversation_id,
        user_message="They showed great communication skills."
    )

    # Get updated conversation
    updated_conv = await firestore.get_conversation(conversation.conversation_id)
    print(f"✓ Sent message 2")
    print(f"  Turn count after message 2: {updated_conv.metadata.total_turns}")
    print(f"  Number of messages: {len(updated_conv.messages)}")
    print()

    # Check message details
    print("4. Message details:")
    for i, msg in enumerate(updated_conv.messages):
        print(f"  Message {i}: turn={msg.turn}, role={msg.role.value}")
    print()

    # Expected results
    print("Expected Results:")
    print("  - Initial turn count: 0")
    print("  - After message 1: 1")
    print("  - After message 2: 2")
    print()

    if updated_conv.metadata.total_turns == 2:
        print("✅ PASS: Turn counting works correctly!")
    else:
        print(f"❌ FAIL: Expected turn count 2, got {updated_conv.metadata.total_turns}")

    return conversation.conversation_id


async def test_feedback_refinement(conversation_id: str):
    """Test that feedback refinement returns updated content"""
    print()
    print("=" * 60)
    print("TEST 2: Feedback Refinement")
    print("=" * 60)
    print()

    firestore = FirestoreService()
    conv_service = ConversationService(firestore)

    # Generate initial feedback
    print("1. Generating initial feedback...")
    feedback = await conv_service.generate_feedback(conversation_id)
    print(f"✓ Generated feedback: {feedback.feedback_id}")
    print(f"  Version: {feedback.current_version}")
    print(f"  Number of versions: {len(feedback.versions)}")
    initial_content = feedback.get_current_content()
    print(f"  Content length: {len(initial_content)} chars")
    print(f"  First 100 chars: {initial_content[:100]}...")
    print()

    # Refine feedback
    print("2. Refining feedback...")
    refined_feedback = await conv_service.refine_feedback(
        conversation_id=conversation_id,
        refinement_request="Add more emphasis on teamwork skills"
    )
    print(f"✓ Refined feedback")
    print(f"  Version: {refined_feedback.current_version}")
    print(f"  Number of versions: {len(refined_feedback.versions)}")
    refined_content = refined_feedback.get_current_content()
    print(f"  Content length: {len(refined_content)} chars")
    print(f"  First 100 chars: {refined_content[:100]}...")
    print()

    # Check versions
    print("3. Version details:")
    for v in refined_feedback.versions:
        print(f"  Version {v.version}: type={v.type.value}, length={len(v.content)} chars")
        if v.request:
            print(f"    Request: {v.request}")
    print()

    # Expected results
    print("Expected Results:")
    print("  - Initial version: 1")
    print("  - After refinement: 2")
    print("  - Content should be different")
    print()

    if refined_feedback.current_version == 2 and initial_content != refined_content:
        print("✅ PASS: Feedback refinement works correctly!")
    else:
        print(f"❌ FAIL: Version={refined_feedback.current_version}, content_changed={initial_content != refined_content}")

    return feedback.feedback_id


async def test_html_response():
    """Test what the API endpoint actually returns"""
    print()
    print("=" * 60)
    print("TEST 3: API Response Format")
    print("=" * 60)
    print()

    from app.api.conversations import send_message
    from app.dependencies import get_firestore
    from fastapi import Request
    from unittest.mock import MagicMock
    from app.models.conversation import MessageCreate

    # This would need a full request context
    print("⚠️  Skipping API test - requires full HTTP context")
    print("    Manual test needed in browser with network inspector")
    print()


async def main():
    """Run all tests"""
    try:
        # Test 1: Turn counting
        conversation_id = await test_turn_counting()

        # Test 2: Feedback refinement
        await test_feedback_refinement(conversation_id)

        # Test 3: HTML response
        await test_html_response()

        print()
        print("=" * 60)
        print("Tests Complete")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
