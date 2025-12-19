# Test Suite for Preceptor Feedback Bot

Comprehensive integration test suite for the FastAPI application.

## Test Coverage

### 1. Authentication & Authorization (`test_auth.py`)
- OAuth login flow
- JWT token generation and validation
- Logout functionality
- Domain restriction enforcement

### 2. Conversations (`test_conversations.py`)
- Conversation creation
- Message sending and receiving
- Turn counter management
- Premature feedback detection
- MAX_TURNS enforcement

### 3. Feedback (`test_feedback.py`)
- Feedback generation
- Feedback refinement and versioning
- Feedback download as text file
- Finish conversation workflow

### 4. Dashboard (`test_dashboard.py`)
- Conversation listing
- Search functionality (case-insensitive, partial matching)
- Filtering by status (active, completed)
- Pagination (limit and offset)
- Combined search and filters

### 5. Authorization/Access Control (`test_authorization.py`)
- Users cannot access other users' conversations
- Users cannot access other users' feedback
- Users cannot refine other users' feedback
- Users only see their own data in listings

### 6. Survey (`test_survey.py`)
- Survey page access
- Survey submission (all fields, required only)
- Survey skip functionality
- Duplicate submission prevention
- Survey data retrieval

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Specific Test File
```bash
pytest tests/test_auth.py
pytest tests/test_conversations.py
pytest tests/test_feedback.py
pytest tests/test_dashboard.py
pytest tests/test_authorization.py
pytest tests/test_survey.py
```

### Run Specific Test Class
```bash
pytest tests/test_conversations.py::TestConversationCreation
```

### Run Specific Test
```bash
pytest tests/test_auth.py::TestOAuthLogin::test_login_redirects_to_google
```

### Run with Coverage
```bash
pytest tests/ --cov=app --cov-report=html
# Open htmlcov/index.html to view coverage report
```

### Run with Different Verbosity
```bash
pytest tests/ -v          # Verbose
pytest tests/ -vv         # Very verbose
pytest tests/ -q          # Quiet
```

### Run Tests by Marker
```bash
pytest tests/ -m auth          # Run only auth tests
pytest tests/ -m conversation  # Run only conversation tests
pytest tests/ -m feedback      # Run only feedback tests
pytest tests/ -m dashboard     # Run only dashboard tests
pytest tests/ -m survey        # Run only survey tests
```

## Test Architecture

### Fixtures (`conftest.py`)
- `mock_firestore`: In-memory Firestore mock for testing without database
- `client`: Authenticated async HTTP client for testing endpoints
- `unauthenticated_client`: Unauthenticated client for testing auth flows
- `test_user`, `test_user_2`: Test user objects for access control tests
- `mock_vertex_client`: Mock VertexAI client for testing AI interactions
- `mock_jwt_token`: Mock JWT token for authentication tests

### Mock Firestore
The `MockFirestoreService` in `conftest.py` provides an in-memory implementation of all Firestore operations:
- User management (create, get, update)
- Conversation management (create, get, update, list, search)
- Feedback management (create, get, refine)
- Survey management (create, get, list)

All tests use this mock to avoid requiring a real Firestore instance.

## Configuration

Test configuration is in `pytest.ini`:
- Async support enabled with `asyncio_mode = auto`
- Coverage minimum set to 70%
- Warnings filtered appropriately
- Test markers registered

## Writing New Tests

1. Add new test file in `tests/` directory with `test_` prefix
2. Use appropriate fixtures from `conftest.py`
3. Mark tests with appropriate markers (`@pytest.mark.integration`, `@pytest.mark.auth`, etc.)
4. Follow existing test patterns for consistency
5. Test both success and failure cases
6. Test authorization (users can't access other users' data)

## Known Issues

- Some Vertex AI mocking may need adjustment for complex scenarios
- Tests assume environment variables are set (handled in conftest.py)
- Coverage reports exclude test files themselves

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:
- No external dependencies required (mocked Firestore, Vertex AI)
- Fast execution (< 1 minute for full suite)
- Clear pass/fail indicators
- Coverage reporting built-in

## Troubleshooting

### Import Errors
Ensure you're running pytest from the project root:
```bash
cd /path/to/preceptor-feedback-bot
pytest tests/
```

### Async Warnings
pytest-asyncio is configured in pytest.ini. If you see async warnings, check that:
- Tests are marked with `@pytest.mark.asyncio`
- Async fixtures use `@pytest.fixture` (not `@pytest.fixture(scope="session")` for async)

### Mock Issues
If mocks aren't working:
- Check that patches are applied at the right import path
- Verify mock return values match expected types
- Use `--tb=long` flag for detailed tracebacks
