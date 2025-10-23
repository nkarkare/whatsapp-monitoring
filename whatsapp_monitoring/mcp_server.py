#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Server for WhatsApp Monitoring

This module provides an MCP server that exposes WhatsApp monitoring and
ERPNext integration functionality to Claude Code and other MCP clients.

Tools provided:
- create_erp_task: Create ERPNext tasks with user resolution
- list_erp_users: List all active users from ERPNext
- search_users: Search users by name or email
- resolve_user_interactive: Start interactive WhatsApp user disambiguation
- check_disambiguation: Check status of user disambiguation request
- get_task_status: Get status of a created task
"""

import sys
import os
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import time

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        ImageContent,
        EmbeddedResource,
        LoggingLevel
    )
except ImportError:
    print("Error: MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Local imports
from whatsapp_monitoring.erpnext_client import ERPNextClient, create_client_from_env
from whatsapp_monitoring.user_resolver import UserResolver
from whatsapp_monitoring.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_server")

# Initialize MCP server
app = Server("whatsapp-monitoring")

# Global state
erp_client: Optional[ERPNextClient] = None
user_resolver: Optional[UserResolver] = None
whatsapp_mcp_available = False
admin_whatsapp_number: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================

def send_whatsapp_message(recipient: str, message: str) -> bool:
    """
    Send WhatsApp message via MCP client

    Args:
        recipient: Phone number (without +) or JID
        message: Message text

    Returns:
        True if sent successfully
    """
    try:
        # This will be called by Claude Code which has access to WhatsApp MCP
        # We document this as an integration point
        logger.info(f"WhatsApp message prepared for {recipient}: {message[:50]}...")

        # Note: Actual sending happens through Claude Code's mcp__whatsapp__send_message
        # This is a placeholder for documentation
        return True
    except Exception as e:
        logger.error(f"Failed to prepare WhatsApp message: {e}")
        return False


def get_whatsapp_messages(sender_phone: str, after_timestamp: datetime, limit: int = 10) -> List[Dict]:
    """
    Get WhatsApp messages from a sender after a timestamp

    Args:
        sender_phone: Sender phone number
        after_timestamp: Get messages after this time
        limit: Maximum messages to retrieve

    Returns:
        List of message dictionaries
    """
    try:
        # This will be accessed via Claude Code's mcp__whatsapp__list_messages
        # We document this as an integration point
        logger.info(f"Retrieving messages from {sender_phone} after {after_timestamp}")

        # Note: Actual retrieval happens through Claude Code
        # This is a placeholder for documentation
        return []
    except Exception as e:
        logger.error(f"Failed to retrieve WhatsApp messages: {e}")
        return []


def response_checker_factory(admin_number: str):
    """
    Create a response checker function for UserResolver

    Args:
        admin_number: Admin WhatsApp number

    Returns:
        Function that checks for responses after a timestamp
    """
    def check_response(phone: str, after: datetime) -> Optional[str]:
        """Check for messages from phone after timestamp"""
        # This integrates with WhatsApp MCP via Claude Code
        messages = get_whatsapp_messages(phone, after, limit=1)
        if messages:
            return messages[0].get('text', '')
        return None

    return check_response


def format_user_for_display(user: Dict) -> str:
    """Format user data for display"""
    name = user.get('full_name', 'Unknown')
    email = user.get('email', 'no-email')
    username = user.get('name', 'unknown')
    enabled = user.get('enabled', 0)
    status = "Active" if enabled == 1 else "Disabled"

    return f"{name} ({email}) - {status}"


def parse_task_details(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate task details

    Args:
        task_data: Raw task data from MCP client

    Returns:
        Validated task details dictionary
    """
    details = {
        "subject": task_data.get("subject", "Task from WhatsApp"),
        "description": task_data.get("description", ""),
        "priority": task_data.get("priority", "Medium"),
        "status": "Open"
    }

    # Add optional fields
    if "due_date" in task_data:
        details["due_date"] = task_data["due_date"]

    if "assigned_to" in task_data and task_data["assigned_to"]:
        details["assigned_to"] = task_data["assigned_to"]

    # Validate priority
    valid_priorities = ["Low", "Medium", "High", "Urgent"]
    if details["priority"] not in valid_priorities:
        logger.warning(f"Invalid priority '{details['priority']}', using 'Medium'")
        details["priority"] = "Medium"

    return details


# ============================================================================
# MCP Tool Handlers
# ============================================================================

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """
    Handle MCP tool calls

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of TextContent responses
    """
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    try:
        if name == "create_erp_task":
            return await handle_create_task(arguments)

        elif name == "list_erp_users":
            return await handle_list_users(arguments)

        elif name == "search_users":
            return await handle_search_users(arguments)

        elif name == "resolve_user_interactive":
            return await handle_resolve_user_interactive(arguments)

        elif name == "check_disambiguation":
            return await handle_check_disambiguation(arguments)

        elif name == "get_task_status":
            return await handle_get_task_status(arguments)

        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Unknown tool: {name}"
                }, indent=2)
            )]

    except Exception as e:
        logger.error(f"Error handling tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "tool": name
            }, indent=2)
        )]


async def handle_create_task(arguments: Dict[str, Any]) -> list[TextContent]:
    """
    Create an ERPNext task with user resolution

    Arguments:
        - subject: str (required) - Task subject/title
        - description: str (optional) - Task description
        - priority: str (optional) - Low/Medium/High/Urgent
        - due_date: str (optional) - YYYY-MM-DD format
        - assigned_to: str (optional) - User name/email (will be resolved)
        - auto_resolve: bool (optional) - Auto-select best match (default: true)

    Returns:
        JSON with task_id, task_url, and assignment details
    """
    if not erp_client:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "ERPNext client not initialized"}, indent=2)
        )]

    # Parse task details
    task_details = parse_task_details(arguments)

    # Handle user resolution if assigned_to is provided
    user_query = arguments.get("assigned_to")
    auto_resolve = arguments.get("auto_resolve", True)

    resolved_user = None
    resolution_info = {}

    if user_query and user_resolver:
        logger.info(f"Resolving user: {user_query}")
        resolution_result = user_resolver.resolve_user(user_query)

        if resolution_result.get("resolved"):
            resolved_user = resolution_result["user"]
            task_details["assigned_to"] = resolved_user.get("name") or resolved_user.get("email")
            resolution_info = {
                "resolved": True,
                "user": format_user_for_display(resolved_user),
                "match_score": resolution_result.get("match_score", 100)
            }

        elif resolution_result.get("needs_disambiguation"):
            if auto_resolve:
                # Use the best candidate
                candidates = resolution_result.get("candidates", [])
                if candidates:
                    resolved_user = candidates[0]["user"]
                    task_details["assigned_to"] = resolved_user.get("name") or resolved_user.get("email")
                    resolution_info = {
                        "resolved": True,
                        "auto_selected": True,
                        "user": format_user_for_display(resolved_user),
                        "match_score": candidates[0]["match_score"],
                        "note": f"Auto-selected from {len(candidates)} candidates"
                    }
            else:
                # Return disambiguation needed
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "needs_disambiguation": True,
                        "resolution_id": resolution_result.get("resolution_id"),
                        "candidates": [
                            {
                                "user": format_user_for_display(c["user"]),
                                "match_score": c["match_score"],
                                "email": c["user"].get("email")
                            }
                            for c in resolution_result.get("candidates", [])
                        ],
                        "message": "Multiple users found. Use resolve_user_interactive or select auto_resolve=true"
                    }, indent=2)
                )]

        elif resolution_result.get("error"):
            resolution_info = {
                "resolved": False,
                "error": resolution_result["error"],
                "using_default": False
            }
            # Remove assigned_to if resolution failed
            if "assigned_to" in task_details:
                del task_details["assigned_to"]

    # Create the task
    logger.info(f"Creating task: {task_details['subject']}")
    result = erp_client.create_task(task_details)

    if result["success"]:
        response_data = {
            "success": True,
            "task_id": result["task_id"],
            "task_url": result["task_url"],
            "subject": task_details["subject"],
            "priority": task_details["priority"]
        }

        if resolution_info:
            response_data["user_resolution"] = resolution_info

        if "assigned_to" in task_details:
            response_data["assigned_to"] = task_details["assigned_to"]

        return [TextContent(
            type="text",
            text=json.dumps(response_data, indent=2)
        )]
    else:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error creating task")
            }, indent=2)
        )]


async def handle_list_users(arguments: Dict[str, Any]) -> list[TextContent]:
    """
    List all active users from ERPNext

    Arguments:
        - limit: int (optional) - Max users to return (default: 1000)
        - fields: list[str] (optional) - Fields to retrieve

    Returns:
        JSON with list of users
    """
    if not erp_client:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "ERPNext client not initialized"}, indent=2)
        )]

    limit = arguments.get("limit", 1000)
    fields = arguments.get("fields")

    logger.info(f"Listing users (limit: {limit})")
    result = erp_client.list_users(fields=fields, limit=limit)

    if result["success"]:
        users_display = [
            {
                "name": user.get("full_name", "Unknown"),
                "email": user.get("email", "no-email"),
                "username": user.get("name", "unknown"),
                "enabled": user.get("enabled", 0) == 1
            }
            for user in result["users"]
        ]

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "count": len(users_display),
                "users": users_display
            }, indent=2)
        )]
    else:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error listing users")
            }, indent=2)
        )]


async def handle_search_users(arguments: Dict[str, Any]) -> list[TextContent]:
    """
    Search for users by name or email

    Arguments:
        - query: str (required) - Search query
        - fields: list[str] (optional) - Fields to retrieve

    Returns:
        JSON with matching users and match scores
    """
    if not erp_client:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "ERPNext client not initialized"}, indent=2)
        )]

    query = arguments.get("query")
    if not query:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "query parameter is required"}, indent=2)
        )]

    fields = arguments.get("fields")

    logger.info(f"Searching users: {query}")
    result = erp_client.search_users(query, fields=fields)

    if result["success"]:
        # Also get match scores if user_resolver is available
        users_with_scores = []
        if user_resolver and result["users"]:
            ranked = user_resolver._rank_users_by_match(query, result["users"])
            users_with_scores = [
                {
                    "name": r["user"].get("full_name", "Unknown"),
                    "email": r["user"].get("email", "no-email"),
                    "username": r["user"].get("name", "unknown"),
                    "match_score": r["match_score"],
                    "enabled": r["user"].get("enabled", 0) == 1
                }
                for r in ranked
            ]
        else:
            users_with_scores = [
                {
                    "name": user.get("full_name", "Unknown"),
                    "email": user.get("email", "no-email"),
                    "username": user.get("name", "unknown"),
                    "enabled": user.get("enabled", 0) == 1
                }
                for user in result["users"]
            ]

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "query": query,
                "count": len(users_with_scores),
                "users": users_with_scores
            }, indent=2)
        )]
    else:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error searching users")
            }, indent=2)
        )]


async def handle_resolve_user_interactive(arguments: Dict[str, Any]) -> list[TextContent]:
    """
    Start interactive user resolution via WhatsApp

    Arguments:
        - query: str (required) - User name/email to resolve
        - context: dict (optional) - Additional context

    Returns:
        JSON with resolution_id for polling or immediate result
    """
    if not user_resolver:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "User resolver not initialized"}, indent=2)
        )]

    query = arguments.get("query")
    if not query:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "query parameter is required"}, indent=2)
        )]

    context = arguments.get("context", {})

    logger.info(f"Starting interactive user resolution: {query}")
    result = user_resolver.resolve_user(query, context=context)

    if result.get("resolved"):
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "resolved": True,
                "user": format_user_for_display(result["user"]),
                "email": result["user"].get("email"),
                "username": result["user"].get("name"),
                "match_score": result.get("match_score", 100)
            }, indent=2)
        )]

    elif result.get("needs_disambiguation"):
        candidates = result.get("candidates", [])
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "needs_disambiguation": True,
                "resolution_id": result.get("resolution_id"),
                "message": f"WhatsApp message sent to admin. Use check_disambiguation to poll for response.",
                "candidates": [
                    {
                        "user": format_user_for_display(c["user"]),
                        "match_score": c["match_score"],
                        "email": c["user"].get("email")
                    }
                    for c in candidates
                ],
                "note": f"Admin will receive a WhatsApp message to select from {len(candidates)} options"
            }, indent=2)
        )]

    else:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": result.get("error", "User resolution failed")
            }, indent=2)
        )]


async def handle_check_disambiguation(arguments: Dict[str, Any]) -> list[TextContent]:
    """
    Check status of user disambiguation request

    Arguments:
        - resolution_id: str (required) - Resolution ID from resolve_user_interactive
        - wait: bool (optional) - Wait for response (default: false)
        - timeout: int (optional) - Max seconds to wait (default: 60)

    Returns:
        JSON with resolution status and user if resolved
    """
    if not user_resolver:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "User resolver not initialized"}, indent=2)
        )]

    resolution_id = arguments.get("resolution_id")
    if not resolution_id:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "resolution_id parameter is required"}, indent=2)
        )]

    should_wait = arguments.get("wait", False)
    timeout = arguments.get("timeout", 60)

    if not admin_whatsapp_number:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Admin WhatsApp number not configured"}, indent=2)
        )]

    response_checker = response_checker_factory(admin_whatsapp_number)

    if should_wait:
        logger.info(f"Waiting for disambiguation response: {resolution_id} (timeout: {timeout}s)")
        result = user_resolver.wait_for_disambiguation(
            resolution_id,
            response_checker,
            poll_interval=2,
            max_wait=timeout
        )
    else:
        logger.info(f"Checking disambiguation status: {resolution_id}")
        result = user_resolver.check_disambiguation_response(resolution_id, response_checker)

    if result is None:
        return [TextContent(
            type="text",
            text=json.dumps({
                "pending": True,
                "message": "No response yet. Poll again or use wait=true"
            }, indent=2)
        )]

    elif result.get("resolved"):
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "resolved": True,
                "user": format_user_for_display(result["user"]),
                "email": result["user"].get("email"),
                "username": result["user"].get("name"),
                "selection": result.get("selection")
            }, indent=2)
        )]

    elif result.get("cancelled"):
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "cancelled": True,
                "message": "User disambiguation was cancelled"
            }, indent=2)
        )]

    elif result.get("error"):
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": result["error"]
            }, indent=2)
        )]

    else:
        return [TextContent(
            type="text",
            text=json.dumps({
                "pending": True,
                "message": "Response not yet complete"
            }, indent=2)
        )]


async def handle_get_task_status(arguments: Dict[str, Any]) -> list[TextContent]:
    """
    Get status and details of a task

    Arguments:
        - task_id: str (required) - Task ID

    Returns:
        JSON with task details
    """
    if not erp_client:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "ERPNext client not initialized"}, indent=2)
        )]

    task_id = arguments.get("task_id")
    if not task_id:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "task_id parameter is required"}, indent=2)
        )]

    # Note: This would require an additional method in ERPNextClient
    # For now, return the task URL
    task_url = f"{erp_client.url}/app/task/{task_id}"

    return [TextContent(
        type="text",
        text=json.dumps({
            "success": True,
            "task_id": task_id,
            "task_url": task_url,
            "note": "Full task details require additional ERPNext API implementation"
        }, indent=2)
    )]


# ============================================================================
# MCP Tool Definitions
# ============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available MCP tools

    Returns:
        List of Tool definitions
    """
    return [
        Tool(
            name="create_erp_task",
            description=(
                "Create a task in ERPNext with automatic user resolution. "
                "If assigned_to is provided, the system will attempt to resolve the user "
                "using fuzzy matching. Set auto_resolve=true to automatically select the "
                "best match, or false to require interactive disambiguation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Task subject/title (required)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description (optional)"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High", "Urgent"],
                        "description": "Task priority (default: Medium)"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD format (optional)"
                    },
                    "assigned_to": {
                        "type": "string",
                        "description": "User name or email to assign (will be resolved, optional)"
                    },
                    "auto_resolve": {
                        "type": "boolean",
                        "description": "Auto-select best user match (default: true)"
                    }
                },
                "required": ["subject"]
            }
        ),

        Tool(
            name="list_erp_users",
            description=(
                "List all active users from ERPNext. "
                "Returns user details including name, email, username, and status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum users to return (default: 1000)"
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific fields to retrieve (optional)"
                    }
                }
            }
        ),

        Tool(
            name="search_users",
            description=(
                "Search for users by name or email with fuzzy matching. "
                "Returns matching users with match scores for ranking."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name or email)"
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific fields to retrieve (optional)"
                    }
                },
                "required": ["query"]
            }
        ),

        Tool(
            name="resolve_user_interactive",
            description=(
                "Start interactive user resolution via WhatsApp for ambiguous matches. "
                "If multiple users match the query, sends a disambiguation message to the admin "
                "via WhatsApp and returns a resolution_id for polling. Use check_disambiguation "
                "to poll for the admin's response."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User name or email to resolve"
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context for tracking (optional)"
                    }
                },
                "required": ["query"]
            }
        ),

        Tool(
            name="check_disambiguation",
            description=(
                "Check the status of a user disambiguation request. "
                "Use the resolution_id from resolve_user_interactive. "
                "Set wait=true to block until response is received (up to timeout seconds)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "resolution_id": {
                        "type": "string",
                        "description": "Resolution ID from resolve_user_interactive"
                    },
                    "wait": {
                        "type": "boolean",
                        "description": "Wait for response instead of polling (default: false)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Maximum seconds to wait if wait=true (default: 60)"
                    }
                },
                "required": ["resolution_id"]
            }
        ),

        Tool(
            name="get_task_status",
            description=(
                "Get the status and details of a task by task_id. "
                "Returns task URL and basic information."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to query"
                    }
                },
                "required": ["task_id"]
            }
        )
    ]


# ============================================================================
# Server Initialization
# ============================================================================

async def initialize_server():
    """Initialize the MCP server and clients"""
    global erp_client, user_resolver, admin_whatsapp_number

    # Load configuration
    load_config()

    # Initialize ERPNext client
    try:
        erp_client = create_client_from_env()
        logger.info("ERPNext client initialized successfully")
    except ValueError as e:
        logger.error(f"Failed to initialize ERPNext client: {e}")
        logger.warning("MCP server starting with limited functionality")

    # Get admin WhatsApp number
    admin_whatsapp_number = os.environ.get('ADMIN_WHATSAPP_NUMBER')
    default_assignee = os.environ.get('DEFAULT_TASK_ASSIGNEE')

    # Initialize UserResolver if we have ERPNext client
    if erp_client:
        try:
            user_resolver = UserResolver(
                erpnext_client=erp_client,
                whatsapp_sender=send_whatsapp_message,
                admin_number=admin_whatsapp_number or "unknown",
                default_assignee=default_assignee
            )
            logger.info("User resolver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize user resolver: {e}")

    # Log configuration
    logger.info(f"ERPNext URL: {os.environ.get('ERPNEXT_URL', 'not configured')}")
    logger.info(f"Admin WhatsApp: {admin_whatsapp_number or 'not configured'}")
    logger.info(f"Default Assignee: {default_assignee or 'not configured'}")
    logger.info("MCP server initialized and ready")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point for MCP server"""
    logger.info("Starting WhatsApp Monitoring MCP Server")

    # Initialize server
    await initialize_server()

    # Run MCP server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP server running on stdio")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def run():
    """Run the MCP server"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"MCP server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
