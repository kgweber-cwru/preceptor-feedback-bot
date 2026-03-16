"""
Test script for Phase 4: Dashboard functionality
Tests conversation listing, search, and filtering
"""

import asyncio
from datetime import datetime, timedelta
from app.services.firestore_service import FirestoreService
from app.config import settings
from app.models.conversation import ConversationStatus

async def test_dashboard():
    """Test dashboard conversation listing"""
    print("=" * 60)
    print("Testing Phase 4: Dashboard & Conversation History")
    print("=" * 60)

    # Initialize Firestore
    firestore = FirestoreService()

    # Test user ID (replace with actual user ID from your OAuth login)
    test_user_id = "test_user_123"

    print("\n1. Testing list_conversations (basic)...")
    conversations = await firestore.list_conversations(
        user_id=test_user_id,
        limit=10,
        offset=0
    )
    print(f"   ✓ Found {len(conversations)} conversations")
    for conv in conversations:
        print(f"     - {conv.student_name} ({conv.status.value}) - {conv.total_turns} turns")

    print("\n2. Testing list_conversations with status filter (active only)...")
    active_convs = await firestore.list_conversations(
        user_id=test_user_id,
        status=ConversationStatus.ACTIVE,
        limit=10,
        offset=0
    )
    print(f"   ✓ Found {len(active_convs)} active conversations")

    print("\n3. Testing list_conversations with status filter (completed only)...")
    completed_convs = await firestore.list_conversations(
        user_id=test_user_id,
        status=ConversationStatus.COMPLETED,
        limit=10,
        offset=0
    )
    print(f"   ✓ Found {len(completed_convs)} completed conversations")

    print("\n4. Testing search_conversations...")
    if conversations:
        # Search for first student's name
        search_query = conversations[0].student_name.split()[0]  # First word of name
        print(f"   Searching for: '{search_query}'")

        search_results = await firestore.search_conversations(
            user_id=test_user_id,
            query=search_query,
            limit=10,
            offset=0
        )
        print(f"   ✓ Found {len(search_results)} matching conversations")
        for conv in search_results:
            print(f"     - {conv.student_name}")
    else:
        print("   ⚠ No conversations to test search with")

    print("\n5. Testing pagination (offset)...")
    page1 = await firestore.list_conversations(
        user_id=test_user_id,
        limit=2,
        offset=0
    )
    page2 = await firestore.list_conversations(
        user_id=test_user_id,
        limit=2,
        offset=2
    )
    print(f"   ✓ Page 1: {len(page1)} conversations")
    print(f"   ✓ Page 2: {len(page2)} conversations")

    print("\n6. Testing ConversationSummary fields...")
    if conversations:
        conv = conversations[0]
        print(f"   conversation_id: {conv.conversation_id}")
        print(f"   student_name: {conv.student_name}")
        print(f"   status: {conv.status.value}")
        print(f"   total_turns: {conv.total_turns}")
        print(f"   last_message_preview: {conv.last_message_preview[:50] if conv.last_message_preview else 'None'}...")
        print(f"   created_at: {conv.created_at}")
        print(f"   updated_at: {conv.updated_at}")
        print("   ✓ All fields present")

    print("\n" + "=" * 60)
    print("Phase 4 Backend Tests Complete!")
    print("=" * 60)

    print("\n📋 Next Steps:")
    print("1. Visit http://localhost:8080 in your browser")
    print("2. Login with Google OAuth")
    print("3. You should see the new dashboard with conversation history")
    print("4. Test search by typing a student name")
    print("5. Test filtering by status dropdown")
    print("6. Click on a conversation card to open it")
    print("7. Create multiple conversations to test pagination")

if __name__ == "__main__":
    asyncio.run(test_dashboard())
