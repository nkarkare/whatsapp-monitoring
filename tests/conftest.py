"""
Pytest Configuration and Shared Fixtures

This file contains pytest configuration and fixtures shared across all test modules.
"""

import pytest
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow running tests")


@pytest.fixture(scope='session')
def test_env_vars():
    """Set up test environment variables"""
    test_vars = {
        'ERPNEXT_URL': 'https://erp.example.com',
        'ERPNEXT_API_KEY': 'test_api_key',
        'ERPNEXT_API_SECRET': 'test_api_secret',
        'FUZZY_MATCH_THRESHOLD': '80',
        'MAX_USER_SUGGESTIONS': '5',
        'USER_RESOLUTION_TIMEOUT': '300',
        'LOG_LEVEL': 'ERROR'  # Reduce log noise during tests
    }

    # Save original values
    original_values = {}
    for key, value in test_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value

    yield test_vars

    # Restore original values
    for key, value in original_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
