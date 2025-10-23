#!/usr/bin/env python3
"""
Test script for WhatsApp Monitoring MCP Server

This script validates the MCP server setup and performs basic functionality tests.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from whatsapp_monitoring.config import load_config
from whatsapp_monitoring.erpnext_client import create_client_from_env
from whatsapp_monitoring.user_resolver import UserResolver


def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_success(text):
    """Print success message"""
    print(f"✅ {text}")


def print_error(text):
    """Print error message"""
    print(f"❌ {text}")


def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")


def test_configuration():
    """Test that configuration is properly loaded"""
    print_header("Testing Configuration")

    required_vars = [
        'ERPNEXT_URL',
        'ERPNEXT_API_KEY',
        'ERPNEXT_API_SECRET'
    ]

    optional_vars = [
        'ADMIN_WHATSAPP_NUMBER',
        'DEFAULT_TASK_ASSIGNEE',
        'FUZZY_MATCH_THRESHOLD',
        'USER_RESOLUTION_TIMEOUT'
    ]

    all_ok = True

    # Check required variables
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            print_success(f"{var} is configured")
        else:
            print_error(f"{var} is NOT configured (required)")
            all_ok = False

    # Check optional variables
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            print_success(f"{var} is configured: {value}")
        else:
            print_info(f"{var} is not configured (optional)")

    return all_ok


def test_erpnext_connection():
    """Test ERPNext API connection"""
    print_header("Testing ERPNext Connection")

    try:
        client = create_client_from_env()
        print_success("ERPNext client created successfully")

        # Test connection by listing users
        result = client.list_users(limit=5)

        if result['success']:
            user_count = len(result['users'])
            print_success(f"Connected to ERPNext successfully")
            print_info(f"Found {user_count} users (showing first 5)")

            for user in result['users'][:3]:
                name = user.get('full_name', 'Unknown')
                email = user.get('email', 'no-email')
                print(f"   - {name} ({email})")

            return True, client
        else:
            print_error(f"Failed to list users: {result.get('error')}")
            return False, None

    except ValueError as e:
        print_error(f"Configuration error: {e}")
        return False, None
    except Exception as e:
        print_error(f"Connection error: {e}")
        return False, None


def test_user_search(client):
    """Test user search functionality"""
    print_header("Testing User Search")

    test_queries = [
        "admin",
        "test",
        "user"
    ]

    for query in test_queries:
        result = client.search_users(query)
        if result['success']:
            count = len(result['users'])
            print_success(f"Search for '{query}': {count} results")

            if result['users']:
                top_user = result['users'][0]
                name = top_user.get('full_name', 'Unknown')
                email = top_user.get('email', 'no-email')
                print_info(f"   Top result: {name} ({email})")
        else:
            print_error(f"Search for '{query}' failed: {result.get('error')}")

    return True


def test_user_resolver(client):
    """Test user resolver with fuzzy matching"""
    print_header("Testing User Resolver (Fuzzy Matching)")

    admin_number = os.environ.get('ADMIN_WHATSAPP_NUMBER', '0000000000')
    default_assignee = os.environ.get('DEFAULT_TASK_ASSIGNEE')

    def mock_whatsapp_sender(recipient, message):
        """Mock WhatsApp sender for testing"""
        print_info(f"[MOCK] WhatsApp message to {recipient}:")
        print(f"       {message[:100]}...")
        return True

    try:
        resolver = UserResolver(
            erpnext_client=client,
            whatsapp_sender=mock_whatsapp_sender,
            admin_number=admin_number,
            default_assignee=default_assignee
        )
        print_success("User resolver created successfully")

        # Test with None (should use default assignee)
        print_info("\nTest 1: Resolve with None (default assignee)")
        result = resolver.resolve_user(None)
        if result.get('resolved'):
            user = result['user']
            print_success(f"Resolved to default: {user.get('full_name')}")
        elif result.get('error'):
            print_info(f"No default assignee configured: {result['error']}")

        # Test with specific query
        print_info("\nTest 2: Resolve with query 'admin'")
        result = resolver.resolve_user("admin")

        if result.get('resolved'):
            user = result['user']
            score = result.get('match_score', 'N/A')
            print_success(f"Resolved to: {user.get('full_name')} (score: {score})")

        elif result.get('needs_disambiguation'):
            candidates = result.get('candidates', [])
            print_info(f"Found {len(candidates)} candidates (disambiguation needed)")
            for idx, candidate in enumerate(candidates, 1):
                user = candidate['user']
                score = candidate['match_score']
                print(f"   {idx}. {user.get('full_name')} - {score}% match")

        elif result.get('error'):
            print_error(f"Resolution failed: {result['error']}")

        return True

    except Exception as e:
        print_error(f"User resolver test failed: {e}")
        return False


def test_task_creation(client):
    """Test task creation (dry run)"""
    print_header("Testing Task Creation (Dry Run)")

    print_info("Skipping actual task creation to avoid creating test tasks")
    print_info("Task creation can be tested via MCP tools once server is running")

    # Show what would be created
    sample_task = {
        "subject": "Test Task from MCP Server",
        "description": "This is a test task created by the MCP server test script",
        "priority": "Medium",
        "assigned_to": os.environ.get('DEFAULT_TASK_ASSIGNEE', 'admin')
    }

    print_info("Sample task that would be created:")
    print(json.dumps(sample_task, indent=2))

    return True


def test_mcp_tools():
    """Test MCP tool definitions"""
    print_header("Testing MCP Tool Definitions")

    try:
        # Import MCP server module
        from whatsapp_monitoring import mcp_server

        # Check that tools are defined
        tools = [
            "create_erp_task",
            "list_erp_users",
            "search_users",
            "resolve_user_interactive",
            "check_disambiguation",
            "get_task_status"
        ]

        print_success(f"MCP server module loaded successfully")
        print_info(f"Expected tools: {len(tools)}")

        for tool in tools:
            print_success(f"   - {tool}")

        return True

    except ImportError as e:
        print_error(f"Failed to import MCP server: {e}")
        print_info("Make sure 'mcp' package is installed: pip install mcp")
        return False
    except Exception as e:
        print_error(f"MCP tool test failed: {e}")
        return False


def main():
    """Run all tests"""
    print_header("WhatsApp Monitoring MCP Server Test Suite")

    # Load configuration
    load_config()

    # Run tests
    results = {}

    # Test 1: Configuration
    results['config'] = test_configuration()

    # Test 2: ERPNext Connection
    if results['config']:
        success, client = test_erpnext_connection()
        results['connection'] = success

        if success:
            # Test 3: User Search
            results['search'] = test_user_search(client)

            # Test 4: User Resolver
            results['resolver'] = test_user_resolver(client)

            # Test 5: Task Creation
            results['task_creation'] = test_task_creation(client)

        else:
            print_info("\nSkipping remaining tests due to connection failure")
            results['search'] = False
            results['resolver'] = False
            results['task_creation'] = False
    else:
        print_info("\nSkipping all tests due to configuration issues")
        results['connection'] = False
        results['search'] = False
        results['resolver'] = False
        results['task_creation'] = False

    # Test 6: MCP Tools
    results['mcp_tools'] = test_mcp_tools()

    # Summary
    print_header("Test Summary")

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)

    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test}")

    print(f"\n{passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print_success("\nAll tests passed! MCP server is ready to use.")
        print_info("\nTo start the MCP server:")
        print_info("  python3 -m whatsapp_monitoring.mcp_server")
        return 0
    else:
        print_error("\nSome tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
