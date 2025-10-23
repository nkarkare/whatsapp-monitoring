#!/usr/bin/env python3
"""
MCP Server Entry Point for WhatsApp Monitoring

This is the main entry point for running the MCP (Model Context Protocol) server
that exposes WhatsApp monitoring and ERPNext integration to Claude Code.

Usage:
    python mcp_main.py

    Or add to Claude Code configuration:
    {
      "mcpServers": {
        "whatsapp-monitoring": {
          "command": "python",
          "args": ["/path/to/whatsapp-monitoring/mcp_main.py"],
          "env": {
            "ERPNEXT_URL": "https://your-erp-server.com",
            "ERPNEXT_API_KEY": "your_api_key",
            "ERPNEXT_API_SECRET": "your_api_secret",
            "ADMIN_WHATSAPP_NUMBER": "917498189688",
            "DEFAULT_TASK_ASSIGNEE": "your.email@company.com"
          }
        }
      }
    }
"""

import sys
import os
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

# Import and run the MCP server
from whatsapp_monitoring.mcp_server import run

if __name__ == "__main__":
    print("Starting WhatsApp Monitoring MCP Server...", file=sys.stderr)
    print(f"Project directory: {project_dir}", file=sys.stderr)
    print(f"Python version: {sys.version}", file=sys.stderr)

    # Check for required environment variables
    required_vars = ["ERPNEXT_URL", "ERPNEXT_API_KEY", "ERPNEXT_API_SECRET"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        print(f"WARNING: Missing environment variables: {', '.join(missing_vars)}", file=sys.stderr)
        print("MCP server will start with limited functionality", file=sys.stderr)

    # Run the server
    run()
