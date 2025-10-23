#!/usr/bin/env python3
"""
Manual MCP Server Validation Script

This script performs practical validation of the MCP server without unittest complexity.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test all critical imports"""
    print("\n=== Testing Imports ===")
    try:
        print("✓ Importing MCP SDK...")
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
        print("  SUCCESS: MCP SDK imports working")
    except ImportError as e:
        print(f"  FAILED: MCP SDK import error: {e}")
        return False

    try:
        print("✓ Importing ERPNext client...")
        from whatsapp_monitoring.erpnext_client import ERPNextClient, create_client_from_env
        print("  SUCCESS: ERPNext client imports working")
    except ImportError as e:
        print(f"  FAILED: ERPNext client import error: {e}")
        return False

    try:
        print("✓ Importing User Resolver...")
        from whatsapp_monitoring.user_resolver import UserResolver
        print("  SUCCESS: User resolver imports working")
    except ImportError as e:
        print(f"  FAILED: User resolver import error: {e}")
        return False

    try:
        print("✓ Importing MCP Server...")
        from whatsapp_monitoring.mcp_server import app, list_tools, call_tool
        print("  SUCCESS: MCP server imports working")
    except ImportError as e:
        print(f"  FAILED: MCP server import error: {e}")
        return False

    return True


def test_server_creation():
    """Test MCP server object creation"""
    print("\n=== Testing Server Creation ===")
    try:
        from whatsapp_monitoring.mcp_server import app
        assert app is not None
        assert app.name == "whatsapp-monitoring"
        print(f"✓ Server created: {app.name}")
        return True
    except Exception as e:
        print(f"  FAILED: Server creation error: {e}")
        return False


async def test_tool_definitions():
    """Test tool definitions"""
    print("\n=== Testing Tool Definitions ===")
    try:
        from whatsapp_monitoring.mcp_server import list_tools

        tools = await list_tools()
        print(f"✓ Found {len(tools)} tools")

        expected_tools = [
            'create_erp_task',
            'list_erp_users',
            'search_users',
            'resolve_user_interactive',
            'check_disambiguation',
            'get_task_status'
        ]

        tool_names = [tool.name for tool in tools]

        for expected in expected_tools:
            if expected in tool_names:
                print(f"  ✓ {expected}")
            else:
                print(f"  ✗ Missing: {expected}")
                return False

        # Check tool schemas
        for tool in tools:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'inputSchema')
            schema = tool.inputSchema
            assert schema.get('type') == 'object'
            assert 'properties' in schema

        print("✓ All tool schemas valid")
        return True

    except Exception as e:
        print(f"  FAILED: Tool definition error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_erpnext_client_creation():
    """Test ERPNext client creation"""
    print("\n=== Testing ERPNext Client ===")

    # Test with config
    os.environ['ERPNEXT_URL'] = 'https://test.example.com'
    os.environ['ERPNEXT_API_KEY'] = 'test_key'
    os.environ['ERPNEXT_API_SECRET'] = 'test_secret'

    try:
        from whatsapp_monitoring.erpnext_client import create_client_from_env
        client = create_client_from_env()
        assert client.url == 'https://test.example.com'
        print("✓ ERPNext client creation with config: SUCCESS")
    except Exception as e:
        print(f"  FAILED: Client creation error: {e}")
        return False

    # Test without config
    for key in ['ERPNEXT_URL', 'ERPNEXT_API_KEY', 'ERPNEXT_API_SECRET']:
        os.environ.pop(key, None)

    try:
        from whatsapp_monitoring.erpnext_client import create_client_from_env
        client = create_client_from_env()
        print("  FAILED: Should have raised ValueError for missing config")
        return False
    except ValueError as e:
        print(f"✓ Proper error handling for missing config: {e}")
        return True


async def test_error_handling():
    """Test error handling in tools"""
    print("\n=== Testing Error Handling ===")

    try:
        from whatsapp_monitoring.mcp_server import call_tool
        import json

        # Test unknown tool
        result = await call_tool("unknown_tool", {})
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "error" in response_data
        print("✓ Unknown tool error handling: SUCCESS")

        return True
    except Exception as e:
        print(f"  FAILED: Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_structure():
    """Test that required files exist"""
    print("\n=== Testing File Structure ===")

    files_to_check = [
        "mcp_main.py",
        "whatsapp_monitoring/__init__.py",
        "whatsapp_monitoring/mcp_server.py",
        "whatsapp_monitoring/erpnext_client.py",
        "whatsapp_monitoring/user_resolver.py",
        "whatsapp_monitoring/config.py",
        "scripts/run_mcp.sh",
        "config/settings.template.env",
        "requirements.txt"
    ]

    all_exist = True
    for filepath in files_to_check:
        full_path = project_root / filepath
        if full_path.exists():
            print(f"  ✓ {filepath}")
        else:
            print(f"  ✗ Missing: {filepath}")
            all_exist = False

    # Check run_mcp.sh is executable
    script_path = project_root / "scripts" / "run_mcp.sh"
    if script_path.exists() and os.access(script_path, os.X_OK):
        print("  ✓ run_mcp.sh is executable")
    else:
        print("  ✗ run_mcp.sh not executable")
        all_exist = False

    return all_exist


def test_configuration_loading():
    """Test configuration loading"""
    print("\n=== Testing Configuration Loading ===")

    try:
        from whatsapp_monitoring.config import load_config

        # Should not raise error even if config file missing
        load_config()
        print("✓ Configuration loader works")
        return True
    except Exception as e:
        print(f"  FAILED: Configuration loading error: {e}")
        return False


async def run_all_tests():
    """Run all validation tests"""
    print("=" * 70)
    print("MCP SERVER PRODUCTION VALIDATION")
    print("=" * 70)

    results = {}

    # Run tests
    results['imports'] = test_imports()
    results['server_creation'] = test_server_creation()
    results['tool_definitions'] = await test_tool_definitions()
    results['erpnext_client'] = test_erpnext_client_creation()
    results['error_handling'] = await test_error_handling()
    results['file_structure'] = test_file_structure()
    results['configuration'] = test_configuration_loading()

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name.replace('_', ' ').title()}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL VALIDATION TESTS PASSED - PRODUCTION READY!")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - REVIEW REQUIRED")
        return 1


if __name__ == '__main__':
    import asyncio
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
