#!/bin/bash
# Manual test to see what the API actually returns

# First, get a JWT token by logging in (you'll need to do this manually in browser)
# Then extract the token from cookies

echo "Testing message send endpoint..."
echo ""

# You need to replace these values:
# - CONVERSATION_ID from a real conversation
# - JWT_TOKEN from your browser cookies

CONVERSATION_ID="${1:-YOUR_CONVERSATION_ID}"
JWT_TOKEN="${2:-YOUR_JWT_TOKEN}"

if [ "$CONVERSATION_ID" = "YOUR_CONVERSATION_ID" ]; then
    echo "Usage: $0 <conversation_id> <jwt_token>"
    echo ""
    echo "1. Create a conversation in the browser"
    echo "2. Get the conversation ID from the URL"
    echo "3. Get the JWT token from browser dev tools (Application > Cookies > preceptor_session)"
    echo "4. Run: $0 conv_abc123 eyJ..."
    exit 1
fi

echo "Sending POST to /conversations/$CONVERSATION_ID/messages"
echo ""

curl -v -X POST "http://localhost:8080/conversations/$CONVERSATION_ID/messages" \
  -H "Content-Type: application/json" \
  -H "Cookie: preceptor_session=$JWT_TOKEN" \
  -d '{"content": "Test message to check turn counter"}' \
  2>&1 | tee /tmp/api_response.txt

echo ""
echo "---"
echo "Response saved to /tmp/api_response.txt"
echo "Check for the turn counter HTML in the response"
