# WhatsApp Monitoring Test Suite

Comprehensive test suite for the WhatsApp-MCP-ERPNext integration system.

## Test Coverage

### 1. ERPNext Client Tests (`test_mcp_integration.py::TestERPNextClient`)
- ✅ Client initialization and configuration
- ✅ Task creation with success/error scenarios
- ✅ Task assignment workflow (primary and fallback methods)
- ✅ User listing with filters and pagination
- ✅ User search by name and email
- ✅ Specific user retrieval
- ✅ Network error handling
- ✅ API error handling

### 2. User Resolver Tests (`test_mcp_integration.py::TestUserResolver`)
- ✅ Single user match resolution
- ✅ Multiple user disambiguation workflow
- ✅ Default assignee fallback
- ✅ Fuzzy matching algorithm accuracy
- ✅ Match threshold enforcement
- ✅ Disambiguation response handling (numeric, cancel, invalid)
- ✅ Disambiguation timeout handling
- ✅ Wait for disambiguation with polling
- ✅ Expired resolution cleanup

### 3. MCP Server Tests (`test_mcp_integration.py::TestMCPIntegration`)
- ✅ MCP tool invocation for task creation
- ✅ MCP tool invocation for user resolution
- ✅ Response format validation
- ✅ Error handling and exceptions
- ✅ Async operation handling

### 4. End-to-End Integration Tests (`test_mcp_integration.py::TestEndToEndIntegration`)
- ✅ Simple task creation flow
- ✅ Task creation with user disambiguation
- ✅ WhatsApp message to ERP task flow
- ✅ Claude-flow hooks integration
- ✅ Error recovery and retry logic

### 5. Performance Tests (`test_mcp_integration.py::TestPerformance`)
- ✅ Bulk user search performance (1000+ users)
- ✅ Concurrent task creation
- ✅ Memory cleanup for pending resolutions

## Installation

Install test dependencies:

```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

Or using requirements-dev.txt:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

### Run all tests:
```bash
pytest tests/test_mcp_integration.py -v
```

### Run specific test class:
```bash
pytest tests/test_mcp_integration.py::TestERPNextClient -v
```

### Run specific test:
```bash
pytest tests/test_mcp_integration.py::TestERPNextClient::test_create_task_success -v
```

### Run with coverage:
```bash
pytest tests/test_mcp_integration.py --cov=whatsapp_monitoring --cov-report=html
```

### Run only unit tests:
```bash
pytest tests/test_mcp_integration.py -m unit -v
```

### Run only integration tests:
```bash
pytest tests/test_mcp_integration.py -m integration -v
```

### Run with verbose output:
```bash
pytest tests/test_mcp_integration.py -vv --tb=long
```

## Test Markers

Tests are marked with the following markers:
- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Integration tests with external dependencies
- `@pytest.mark.e2e` - End-to-end workflow tests
- `@pytest.mark.performance` - Performance and stress tests
- `@pytest.mark.slow` - Tests that take longer to run

## Mock Strategy

### ERPNext API Mocks
- Uses `unittest.mock` to mock `requests.Session`
- Simulates successful and error responses
- Tests both primary and fallback API methods

### WhatsApp MCP Client Mocks
- Mock WhatsApp sender function
- Mock message retrieval
- Simulates user responses for disambiguation

### Claude-Flow Hooks Mocks
- Mock subprocess execution for hook commands
- Test hook integration without actual execution

## Test Data

Sample test data is provided via fixtures:
- `sample_users` - 5 test users with varying names
- `sample_task_data` - Complete task creation payload
- `sample_task_response` - Successful ERP response
- `mock_whatsapp_messages` - WhatsApp message samples

## Coverage Goals

Target coverage metrics:
- **Statements**: >85%
- **Branches**: >80%
- **Functions**: >85%
- **Lines**: >85%

## Continuous Integration

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest tests/test_mcp_integration.py --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Import Errors
If you encounter import errors, ensure the parent directory is in the Python path:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

### Mock Issues
If mocks aren't working as expected:
1. Verify the patch path matches the actual import location
2. Use `mock_requests_session.post.assert_called()` to debug calls
3. Check mock return values match expected data structures

### Async Tests
For async tests, use `pytest-asyncio`:
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result is not None
```

## Contributing

When adding new tests:
1. Follow the existing test structure and naming conventions
2. Add appropriate markers (`@pytest.mark.unit`, etc.)
3. Include docstrings explaining what the test validates
4. Mock external dependencies
5. Update this README with new test coverage

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [Coverage.py](https://coverage.readthedocs.io/)
