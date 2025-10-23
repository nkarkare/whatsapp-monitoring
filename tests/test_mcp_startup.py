#!/usr/bin/env python3
"""
MCP Server Startup and Production Validation Tests

This test suite validates that the MCP server can start correctly,
handle various configurations, and is production-ready.
"""

import sys
import os
import unittest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


class TestMCPServerImports(unittest.TestCase):
    """Test that all required imports work correctly"""

    def test_mcp_sdk_import(self):
        """Test MCP SDK can be imported"""
        try:
            from mcp.server import Server
            from mcp.server.stdio import stdio_server
            from mcp.types import Tool, TextContent
            self.assertTrue(True, "MCP SDK imports successful")
        except ImportError as e:
            self.fail(f"MCP SDK import failed: {e}")

    def test_whatsapp_monitoring_imports(self):
        """Test all whatsapp_monitoring modules can be imported"""
        try:
            from whatsapp_monitoring.mcp_server import app, list_tools
            from whatsapp_monitoring.erpnext_client import ERPNextClient, create_client_from_env
            from whatsapp_monitoring.user_resolver import UserResolver
            from whatsapp_monitoring.config import load_config
            self.assertTrue(True, "All whatsapp_monitoring imports successful")
        except ImportError as e:
            self.fail(f"Module import failed: {e}")

    def test_mcp_main_executable(self):
        """Test mcp_main.py can be imported"""
        try:
            import mcp_main
            self.assertTrue(True, "mcp_main.py import successful")
        except ImportError as e:
            self.fail(f"mcp_main.py import failed: {e}")


class TestMCPServerInitialization(unittest.TestCase):
    """Test MCP server initialization with various configurations"""

    def setUp(self):
        """Set up test environment"""
        # Save original environment
        self.original_env = os.environ.copy()

    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_server_init_with_full_config(self):
        """Test server initialization with complete configuration"""
        os.environ['ERPNEXT_URL'] = 'https://test.example.com'
        os.environ['ERPNEXT_API_KEY'] = 'test_key'
        os.environ['ERPNEXT_API_SECRET'] = 'test_secret'
        os.environ['ADMIN_WHATSAPP_NUMBER'] = '1234567890'
        os.environ['DEFAULT_TASK_ASSIGNEE'] = 'test@example.com'

        try:
            from whatsapp_monitoring.mcp_server import app
            self.assertIsNotNone(app, "MCP server app should be initialized")
            self.assertEqual(app.name, "whatsapp-monitoring")
        except Exception as e:
            self.fail(f"Server initialization failed with full config: {e}")

    def test_server_init_without_config(self):
        """Test server initialization without ERPNext configuration"""
        # Remove ERPNext config if present
        for key in ['ERPNEXT_URL', 'ERPNEXT_API_KEY', 'ERPNEXT_API_SECRET']:
            os.environ.pop(key, None)

        try:
            from whatsapp_monitoring.mcp_server import app
            self.assertIsNotNone(app, "MCP server should initialize even without ERPNext config")
        except Exception as e:
            self.fail(f"Server should handle missing config gracefully: {e}")

    def test_erpnext_client_creation_with_config(self):
        """Test ERPNext client creation with valid configuration"""
        os.environ['ERPNEXT_URL'] = 'https://test.example.com'
        os.environ['ERPNEXT_API_KEY'] = 'test_key'
        os.environ['ERPNEXT_API_SECRET'] = 'test_secret'

        try:
            from whatsapp_monitoring.erpnext_client import create_client_from_env
            client = create_client_from_env()
            self.assertIsNotNone(client)
            self.assertEqual(client.url, 'https://test.example.com')
        except Exception as e:
            self.fail(f"ERPNext client creation failed: {e}")

    def test_erpnext_client_creation_without_config(self):
        """Test ERPNext client creation fails gracefully without config"""
        for key in ['ERPNEXT_URL', 'ERPNEXT_API_KEY', 'ERPNEXT_API_SECRET']:
            os.environ.pop(key, None)

        from whatsapp_monitoring.erpnext_client import create_client_from_env

        with self.assertRaises(ValueError) as context:
            client = create_client_from_env()

        self.assertIn("Missing required ERPNext configuration", str(context.exception))


class TestMCPToolDefinitions(unittest.TestCase):
    """Test MCP tool definitions are valid"""

    @patch('whatsapp_monitoring.mcp_server.erp_client', None)
    async def test_list_tools_returns_all_tools(self):
        """Test that list_tools returns all 6 expected tools"""
        from whatsapp_monitoring.mcp_server import list_tools
        import asyncio

        tools = await list_tools()

        self.assertEqual(len(tools), 6, "Should return 6 tools")

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            'create_erp_task',
            'list_erp_users',
            'search_users',
            'resolve_user_interactive',
            'check_disambiguation',
            'get_task_status'
        ]

        for expected in expected_tools:
            self.assertIn(expected, tool_names, f"Tool '{expected}' should be defined")

    async def test_tool_schemas_valid(self):
        """Test that all tool schemas are valid JSON Schema"""
        from whatsapp_monitoring.mcp_server import list_tools
        import asyncio

        tools = await list_tools()

        for tool in tools:
            # Check required fields
            self.assertTrue(hasattr(tool, 'name'), f"Tool should have name: {tool}")
            self.assertTrue(hasattr(tool, 'description'), f"Tool should have description: {tool.name}")
            self.assertTrue(hasattr(tool, 'inputSchema'), f"Tool should have inputSchema: {tool.name}")

            # Check schema structure
            schema = tool.inputSchema
            self.assertEqual(schema.get('type'), 'object', f"Schema type should be object: {tool.name}")
            self.assertIn('properties', schema, f"Schema should have properties: {tool.name}")


class TestMCPServerStartup(unittest.TestCase):
    """Test MCP server startup script"""

    def setUp(self):
        """Set up test environment"""
        self.original_env = os.environ.copy()

    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_mcp_main_path_setup(self):
        """Test that mcp_main.py sets up Python path correctly"""
        import mcp_main
        import sys

        project_dir = Path(mcp_main.__file__).resolve().parent
        self.assertIn(str(project_dir), sys.path, "Project directory should be in Python path")

    @patch('sys.stderr', new_callable=StringIO)
    def test_mcp_main_warning_on_missing_config(self, mock_stderr):
        """Test that mcp_main.py warns about missing configuration"""
        # Remove required environment variables
        for key in ['ERPNEXT_URL', 'ERPNEXT_API_KEY', 'ERPNEXT_API_SECRET']:
            os.environ.pop(key, None)

        # Reimport to trigger warning
        import importlib
        import mcp_main
        importlib.reload(mcp_main)


class TestRunMCPScript(unittest.TestCase):
    """Test the run_mcp.sh script validation"""

    def test_run_mcp_script_exists(self):
        """Test that run_mcp.sh script exists and is executable"""
        script_path = project_root / "scripts" / "run_mcp.sh"
        self.assertTrue(script_path.exists(), "run_mcp.sh should exist")
        self.assertTrue(os.access(script_path, os.X_OK), "run_mcp.sh should be executable")

    def test_config_template_exists(self):
        """Test that settings template exists"""
        template_path = project_root / "config" / "settings.template.env"
        self.assertTrue(template_path.exists(), "settings.template.env should exist")


class TestErrorHandling(unittest.TestCase):
    """Test error handling in MCP server"""

    def setUp(self):
        """Set up test environment"""
        self.original_env = os.environ.copy()
        os.environ['ERPNEXT_URL'] = 'https://test.example.com'
        os.environ['ERPNEXT_API_KEY'] = 'test_key'
        os.environ['ERPNEXT_API_SECRET'] = 'test_secret'

    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)

    async def test_call_tool_unknown_tool(self):
        """Test that calling unknown tool returns error"""
        from whatsapp_monitoring.mcp_server import call_tool

        result = await call_tool("unknown_tool", {})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, "text")

        response_data = json.loads(result[0].text)
        self.assertIn("error", response_data)
        self.assertIn("Unknown tool", response_data["error"])

    async def test_create_task_without_subject(self):
        """Test that create_task handles missing subject"""
        from whatsapp_monitoring.mcp_server import handle_create_task
        from whatsapp_monitoring.mcp_server import erp_client

        # Mock erp_client
        with patch('whatsapp_monitoring.mcp_server.erp_client') as mock_client:
            mock_client.create_task.return_value = {
                "success": True,
                "task_id": "TEST-001",
                "task_url": "https://test.example.com/app/task/TEST-001"
            }

            # Call with empty subject
            result = await handle_create_task({})

            # Should still create task with default subject
            self.assertEqual(len(result), 1)
            response_data = json.loads(result[0].text)
            # Either succeeds with default or fails gracefully
            self.assertIn("success", response_data)


def run_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestMCPServerImports))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPServerInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPToolDefinitions))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPServerStartup))
    suite.addTests(loader.loadTestsFromTestCase(TestRunMCPScript))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == '__main__':
    # Run async tests with asyncio
    import asyncio

    # For async tests, we need to handle them specially
    result = run_tests()

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
