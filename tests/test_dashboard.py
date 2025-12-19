"""
Integration tests for dashboard, search, and filtering functionality.
Tests conversation listing, search, filtering by status, and pagination.
"""

import pytest
from datetime import datetime, timedelta
from app.models.conversation import ConversationStatus

pytestmark = [pytest.mark.integration, pytest.mark.dashboard]


class TestDashboardAccess:
    """Tests for dashboard page access."""

    @pytest.mark.asyncio
    async def test_dashboard_requires_authentication(self, unauthenticated_client):
        """Test that dashboard requires authentication."""
        response = await unauthenticated_client.get("/dashboard", follow_redirects=False)

        assert response.status_code == 302
        assert "/" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_authenticated_user_can_access_dashboard(self, client):
        """Test that authenticated user can access dashboard."""
        response = await client.get("/dashboard")

        assert response.status_code == 200
        assert "Dashboard" in response.text or "Feedback Session" in response.text


class TestConversationListing:
    """Tests for listing conversations on dashboard."""

    @pytest.mark.asyncio
    async def test_dashboard_shows_user_conversations(
        self, client, mock_firestore, test_user
    ):
        """Test that dashboard shows user's conversations."""
        # Create test conversations
        conv1 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Alice Johnson",
            model="gemini-2.5-flash",
        )
        conv2 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Bob Smith",
            model="gemini-2.5-flash",
        )

        response = await client.get("/api/conversations")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 2

        student_names = [c["student_name"] for c in data["conversations"]]
        assert "Alice Johnson" in student_names
        assert "Bob Smith" in student_names

    @pytest.mark.asyncio
    async def test_empty_dashboard_shows_no_conversations(self, client, mock_firestore):
        """Test that empty dashboard shows no conversations."""
        response = await client.get("/api/conversations")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 0

    @pytest.mark.asyncio
    async def test_conversations_sorted_by_recent(
        self, client, mock_firestore, test_user
    ):
        """Test that conversations are sorted by most recent first."""
        # Create conversations with different timestamps
        conv1 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Oldest",
            model="gemini-2.5-flash",
        )
        conv1.updated_at = datetime.utcnow() - timedelta(days=2)
        mock_firestore.conversations[conv1.conversation_id] = conv1

        conv2 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Newest",
            model="gemini-2.5-flash",
        )
        conv2.updated_at = datetime.utcnow()
        mock_firestore.conversations[conv2.conversation_id] = conv2

        conv3 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Middle",
            model="gemini-2.5-flash",
        )
        conv3.updated_at = datetime.utcnow() - timedelta(days=1)
        mock_firestore.conversations[conv3.conversation_id] = conv3

        response = await client.get("/api/conversations")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 3

        # Check order (newest first)
        assert data["conversations"][0]["student_name"] == "Newest"
        assert data["conversations"][1]["student_name"] == "Middle"
        assert data["conversations"][2]["student_name"] == "Oldest"


class TestConversationSearch:
    """Tests for searching conversations by student name."""

    @pytest.mark.asyncio
    async def test_search_by_student_name(self, client, mock_firestore, test_user):
        """Test searching conversations by student name."""
        # Create test conversations
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Alice Johnson",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Bob Smith",
            model="gemini-2.5-flash",
        )
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Charlie Johnson",
            model="gemini-2.5-flash",
        )

        # Search for "Johnson"
        response = await client.get("/api/conversations?search=Johnson")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 2

        student_names = [c["student_name"] for c in data["conversations"]]
        assert "Alice Johnson" in student_names
        assert "Charlie Johnson" in student_names
        assert "Bob Smith" not in student_names

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, client, mock_firestore, test_user):
        """Test that search is case-insensitive."""
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Alice Johnson",
            model="gemini-2.5-flash",
        )

        # Search with lowercase
        response = await client.get("/api/conversations?search=alice")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["student_name"] == "Alice Johnson"

    @pytest.mark.asyncio
    async def test_search_partial_match(self, client, mock_firestore, test_user):
        """Test that search matches partial names."""
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Christopher Williams",
            model="gemini-2.5-flash",
        )

        # Search with partial name
        response = await client.get("/api/conversations?search=Chris")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["student_name"] == "Christopher Williams"

    @pytest.mark.asyncio
    async def test_search_no_results(self, client, mock_firestore, test_user):
        """Test search with no matching results."""
        await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Alice Johnson",
            model="gemini-2.5-flash",
        )

        response = await client.get("/api/conversations?search=Nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 0


class TestConversationFiltering:
    """Tests for filtering conversations by status."""

    @pytest.mark.asyncio
    async def test_filter_by_active_status(self, client, mock_firestore, test_user):
        """Test filtering conversations by active status."""
        # Create conversations with different statuses
        conv1 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Active Student",
            model="gemini-2.5-flash",
        )

        conv2 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Completed Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.update_conversation_status(
            conv2.conversation_id, ConversationStatus.COMPLETED
        )

        # Filter for active only
        response = await client.get("/api/conversations?status=active")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["student_name"] == "Active Student"
        assert data["conversations"][0]["status"] == "active"

    @pytest.mark.asyncio
    async def test_filter_by_completed_status(self, client, mock_firestore, test_user):
        """Test filtering conversations by completed status."""
        conv1 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Active Student",
            model="gemini-2.5-flash",
        )

        conv2 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Completed Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.update_conversation_status(
            conv2.conversation_id, ConversationStatus.COMPLETED
        )

        # Filter for completed only
        response = await client.get("/api/conversations?status=completed")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["student_name"] == "Completed Student"
        assert data["conversations"][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_no_status_filter_shows_all(self, client, mock_firestore, test_user):
        """Test that no status filter shows all conversations."""
        conv1 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Active Student",
            model="gemini-2.5-flash",
        )

        conv2 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Completed Student",
            model="gemini-2.5-flash",
        )
        await mock_firestore.update_conversation_status(
            conv2.conversation_id, ConversationStatus.COMPLETED
        )

        # No status filter
        response = await client.get("/api/conversations")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 2


class TestPagination:
    """Tests for conversation list pagination."""

    @pytest.mark.asyncio
    async def test_pagination_limit(self, client, mock_firestore, test_user):
        """Test that pagination limit works."""
        # Create 25 conversations
        for i in range(25):
            await mock_firestore.create_conversation(
                user_id=test_user.user_id,
                student_name=f"Student {i}",
                model="gemini-2.5-flash",
            )

        # Request with limit
        response = await client.get("/api/conversations?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 10

    @pytest.mark.asyncio
    async def test_pagination_offset(self, client, mock_firestore, test_user):
        """Test that pagination offset works."""
        # Create conversations with predictable order
        for i in range(10):
            conv = await mock_firestore.create_conversation(
                user_id=test_user.user_id,
                student_name=f"Student {i:02d}",
                model="gemini-2.5-flash",
            )
            # Set timestamp to ensure predictable order
            conv.updated_at = datetime.utcnow() - timedelta(hours=i)
            mock_firestore.conversations[conv.conversation_id] = conv

        # Get first page
        response1 = await client.get("/api/conversations?limit=5&offset=0")
        data1 = response1.json()

        # Get second page
        response2 = await client.get("/api/conversations?limit=5&offset=5")
        data2 = response2.json()

        assert len(data1["conversations"]) == 5
        assert len(data2["conversations"]) == 5

        # Ensure different conversations
        ids1 = {c["conversation_id"] for c in data1["conversations"]}
        ids2 = {c["conversation_id"] for c in data2["conversations"]}
        assert ids1.isdisjoint(ids2)  # No overlap


class TestCombinedFilters:
    """Tests for combining search and filters."""

    @pytest.mark.asyncio
    async def test_search_and_status_filter(self, client, mock_firestore, test_user):
        """Test combining search and status filter."""
        # Create conversations
        conv1 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Alice Johnson",
            model="gemini-2.5-flash",
        )

        conv2 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Bob Johnson",
            model="gemini-2.5-flash",
        )
        await mock_firestore.update_conversation_status(
            conv2.conversation_id, ConversationStatus.COMPLETED
        )

        conv3 = await mock_firestore.create_conversation(
            user_id=test_user.user_id,
            student_name="Alice Smith",
            model="gemini-2.5-flash",
        )
        await mock_firestore.update_conversation_status(
            conv3.conversation_id, ConversationStatus.COMPLETED
        )

        # Search for "Johnson" with status "completed"
        response = await client.get("/api/conversations?search=Johnson&status=completed")

        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["student_name"] == "Bob Johnson"
        assert data["conversations"][0]["status"] == "completed"
