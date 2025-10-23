# WhatsApp Monitoring MCP Server

This document describes the Model Context Protocol (MCP) server implementation for the WhatsApp monitoring project, which enables Claude Code and other MCP clients to interact with ERPNext and WhatsApp for task management.

## Overview

The MCP server (`whatsapp_monitoring/mcp_server.py`) exposes six tools for creating tasks, managing users, and handling user disambiguation via WhatsApp.

## Installation

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Or install MCP SDK separately
pip install mcp>=0.9.0
```

### Configuration

Configure the following environment variables in `/home/happy/code/whatsapp-monitoring/config/settings.env`:

```bash
# ERPNext Configuration (Required)
ERPNEXT_URL=https://erp.walnutedu.in
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret

# WhatsApp Configuration (Required for user disambiguation)
ADMIN_WHATSAPP_NUMBER=1234567890

# Optional Configuration
DEFAULT_TASK_ASSIGNEE=user@example.com
FUZZY_MATCH_THRESHOLD=80
MAX_USER_SUGGESTIONS=5
USER_RESOLUTION_TIMEOUT=300
```

## Running the MCP Server

### Standalone Mode

```bash
python3 -m whatsapp_monitoring.mcp_server
```

### With Claude Code

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "whatsapp-monitoring": {
      "command": "python3",
      "args": [
        "-m",
        "whatsapp_monitoring.mcp_server"
      ],
      "cwd": "/home/happy/code/whatsapp-monitoring",
      "env": {
        "PYTHONPATH": "/home/happy/code/whatsapp-monitoring"
      }
    }
  }
}
```

## Available Tools

### 1. create_erp_task

Create a task in ERPNext with automatic user resolution.

**Parameters:**
- `subject` (string, required): Task subject/title
- `description` (string, optional): Task description
- `priority` (string, optional): Low/Medium/High/Urgent (default: Medium)
- `due_date` (string, optional): Due date in YYYY-MM-DD format
- `assigned_to` (string, optional): User name or email (will be resolved)
- `auto_resolve` (boolean, optional): Auto-select best user match (default: true)

**Example:**

```python
# Via Claude Code
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Fix login bug",
    "description": "Users unable to login with SSO",
    "priority": "High",
    "due_date": "2025-10-25",
    "assigned_to": "John",
    "auto_resolve": True
})
```

**Response:**

```json
{
  "success": true,
  "task_id": "TASK-00123",
  "task_url": "https://erp.walnutedu.in/app/task/TASK-00123",
  "subject": "Fix login bug",
  "priority": "High",
  "assigned_to": "john.doe@example.com",
  "user_resolution": {
    "resolved": true,
    "user": "John Doe (john.doe@example.com) - Active",
    "match_score": 95
  }
}
```

### 2. list_erp_users

List all active users from ERPNext.

**Parameters:**
- `limit` (integer, optional): Maximum users to return (default: 1000)
- `fields` (array, optional): Specific fields to retrieve

**Example:**

```python
result = mcp__whatsapp_monitoring__list_erp_users({
    "limit": 50
})
```

**Response:**

```json
{
  "success": true,
  "count": 42,
  "users": [
    {
      "name": "John Doe",
      "email": "john.doe@example.com",
      "username": "john.doe@example.com",
      "enabled": true
    },
    ...
  ]
}
```

### 3. search_users

Search for users by name or email with fuzzy matching.

**Parameters:**
- `query` (string, required): Search query (name or email)
- `fields` (array, optional): Specific fields to retrieve

**Example:**

```python
result = mcp__whatsapp_monitoring__search_users({
    "query": "john"
})
```

**Response:**

```json
{
  "success": true,
  "query": "john",
  "count": 3,
  "users": [
    {
      "name": "John Doe",
      "email": "john.doe@example.com",
      "username": "john.doe@example.com",
      "match_score": 95,
      "enabled": true
    },
    {
      "name": "Johnny Smith",
      "email": "johnny.smith@example.com",
      "username": "johnny.smith@example.com",
      "match_score": 82,
      "enabled": true
    }
  ]
}
```

### 4. resolve_user_interactive

Start interactive user resolution via WhatsApp for ambiguous matches.

**Parameters:**
- `query` (string, required): User name or email to resolve
- `context` (object, optional): Additional context for tracking

**Example:**

```python
result = mcp__whatsapp_monitoring__resolve_user_interactive({
    "query": "john",
    "context": {"task": "TASK-00123"}
})
```

**Response (Single Match):**

```json
{
  "success": true,
  "resolved": true,
  "user": "John Doe (john.doe@example.com) - Active",
  "email": "john.doe@example.com",
  "username": "john.doe@example.com",
  "match_score": 100
}
```

**Response (Multiple Matches):**

```json
{
  "success": true,
  "needs_disambiguation": true,
  "resolution_id": "user_resolve_1729614000123",
  "message": "WhatsApp message sent to admin. Use check_disambiguation to poll for response.",
  "candidates": [
    {
      "user": "John Doe (john.doe@example.com) - Active",
      "match_score": 95,
      "email": "john.doe@example.com"
    },
    {
      "user": "Johnny Smith (johnny.smith@example.com) - Active",
      "match_score": 82,
      "email": "johnny.smith@example.com"
    }
  ],
  "note": "Admin will receive a WhatsApp message to select from 2 options"
}
```

**WhatsApp Message Sent to Admin:**

```
🔍 Found multiple users matching 'john':

1. John Doe (john.doe@example.com) - 95% match
2. Johnny Smith (johnny.smith@example.com) - 82% match

Reply with the number (1-2) to select a user, or 'cancel' to abort.
```

### 5. check_disambiguation

Check the status of a user disambiguation request.

**Parameters:**
- `resolution_id` (string, required): Resolution ID from resolve_user_interactive
- `wait` (boolean, optional): Wait for response instead of polling (default: false)
- `timeout` (integer, optional): Maximum seconds to wait if wait=true (default: 60)

**Example (Polling):**

```python
result = mcp__whatsapp_monitoring__check_disambiguation({
    "resolution_id": "user_resolve_1729614000123"
})
```

**Example (Blocking):**

```python
result = mcp__whatsapp_monitoring__check_disambiguation({
    "resolution_id": "user_resolve_1729614000123",
    "wait": True,
    "timeout": 120
})
```

**Response (Pending):**

```json
{
  "pending": true,
  "message": "No response yet. Poll again or use wait=true"
}
```

**Response (Resolved):**

```json
{
  "success": true,
  "resolved": true,
  "user": "John Doe (john.doe@example.com) - Active",
  "email": "john.doe@example.com",
  "username": "john.doe@example.com",
  "selection": 1
}
```

**Response (Cancelled):**

```json
{
  "success": false,
  "cancelled": true,
  "message": "User disambiguation was cancelled"
}
```

### 6. get_task_status

Get the status and details of a task by task_id.

**Parameters:**
- `task_id` (string, required): Task ID to query

**Example:**

```python
result = mcp__whatsapp_monitoring__get_task_status({
    "task_id": "TASK-00123"
})
```

**Response:**

```json
{
  "success": true,
  "task_id": "TASK-00123",
  "task_url": "https://erp.walnutedu.in/app/task/TASK-00123",
  "note": "Full task details require additional ERPNext API implementation"
}
```

## User Resolution Workflow

### Automatic Resolution (Default)

When `auto_resolve=true` (default), the system automatically selects the best matching user:

```python
# Automatically resolves to best match
result = create_erp_task({
    "subject": "Update documentation",
    "assigned_to": "john",
    "auto_resolve": True  # Default
})
```

### Interactive Resolution

When `auto_resolve=false` or using `resolve_user_interactive`, the system initiates WhatsApp disambiguation:

```python
# Step 1: Start interactive resolution
resolution = resolve_user_interactive({
    "query": "john"
})

# Step 2: Admin receives WhatsApp message with options

# Step 3: Poll for admin response
result = check_disambiguation({
    "resolution_id": resolution["resolution_id"],
    "wait": True,
    "timeout": 120
})

# Step 4: Create task with resolved user
task = create_erp_task({
    "subject": "Update documentation",
    "assigned_to": result["email"]
})
```

## Integration with WhatsApp MCP

The MCP server integrates with WhatsApp via Claude Code's WhatsApp MCP client. The integration points are:

### Sending Disambiguation Messages

```python
# Internal implementation (handled by MCP server)
# Claude Code calls: mcp__whatsapp__send_message
send_whatsapp_message(admin_number, disambiguation_message)
```

### Receiving Admin Responses

```python
# Internal implementation (handled by MCP server)
# Claude Code calls: mcp__whatsapp__list_messages
get_whatsapp_messages(admin_number, after_timestamp, limit=10)
```

## Error Handling

All tools return structured error responses:

```json
{
  "success": false,
  "error": "Error description"
}
```

Common errors:
- `"ERPNext client not initialized"` - Check ERPNext configuration
- `"User resolver not initialized"` - Check configuration and ERPNext connection
- `"Admin WhatsApp number not configured"` - Set ADMIN_WHATSAPP_NUMBER
- `"No users found matching 'query'"` - User doesn't exist or query is too specific
- `"Resolution timed out"` - Admin didn't respond within timeout period

## Configuration Options

### Fuzzy Matching

```bash
# Minimum match score (0-100) for user suggestions
FUZZY_MATCH_THRESHOLD=80
```

### User Suggestions

```bash
# Maximum number of user suggestions to send for disambiguation
MAX_USER_SUGGESTIONS=5
```

### Resolution Timeout

```bash
# Maximum time (seconds) to wait for admin response
USER_RESOLUTION_TIMEOUT=300
```

## Advanced Usage

### Batch Task Creation

```python
# Create multiple tasks with user resolution
tasks = []
for task_data in task_list:
    result = mcp__whatsapp_monitoring__create_erp_task({
        "subject": task_data["subject"],
        "description": task_data["description"],
        "assigned_to": task_data["user"],
        "auto_resolve": True
    })
    tasks.append(result)
```

### User Pre-validation

```python
# Validate user before creating task
users = mcp__whatsapp_monitoring__search_users({
    "query": "john"
})

if users["count"] == 1:
    # Clear match, create task
    result = create_erp_task({
        "subject": "Task",
        "assigned_to": users["users"][0]["email"]
    })
elif users["count"] > 1:
    # Multiple matches, use interactive resolution
    resolution = resolve_user_interactive({
        "query": "john"
    })
```

## Logging

The MCP server uses Python's logging module. Configure log level:

```python
# In your environment or code
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Security Considerations

1. **API Credentials**: Store ERPNext credentials securely in environment variables
2. **WhatsApp Access**: Only admin number can respond to disambiguation requests
3. **Input Validation**: All inputs are validated before processing
4. **Timeout Protection**: Resolution requests timeout after configured period

## Troubleshooting

### MCP Server Not Starting

```bash
# Check dependencies
pip install -r requirements.txt

# Verify configuration
python3 -c "from whatsapp_monitoring.config import load_config; load_config(); import os; print('ERPNext URL:', os.getenv('ERPNEXT_URL'))"

# Test ERPNext connection
python3 -c "from whatsapp_monitoring.erpnext_client import create_client_from_env; client = create_client_from_env(); print('Connection successful')"
```

### User Resolution Not Working

```bash
# Check admin WhatsApp number configured
echo $ADMIN_WHATSAPP_NUMBER

# Verify WhatsApp MCP is available in Claude Code
# Tools should include: mcp__whatsapp__send_message, mcp__whatsapp__list_messages
```

### Tasks Created Without Assignment

- Check `DEFAULT_TASK_ASSIGNEE` is set
- Verify user exists in ERPNext
- Check fuzzy match threshold isn't too strict

## Performance Tips

1. **Cache User Lists**: Call `list_erp_users` once and cache results
2. **Use Auto-Resolve**: Enable `auto_resolve=true` for faster task creation
3. **Batch Operations**: Create multiple tasks in parallel
4. **Optimize Timeouts**: Reduce `USER_RESOLUTION_TIMEOUT` for faster failures

## Future Enhancements

Potential improvements to the MCP server:

1. **Full Task Retrieval**: Implement complete task details in `get_task_status`
2. **Task Updates**: Add tool to update existing tasks
3. **Bulk Operations**: Add batch task creation tool
4. **User Caching**: Cache user lookups for better performance
5. **Assignment History**: Track which users are assigned most frequently
6. **Smart Suggestions**: Use ML to improve user matching over time

## API Reference

See the tool definitions in the code for complete JSON schemas and parameter specifications.

## License

This MCP server is part of the WhatsApp Monitoring project.

## Support

For issues or questions, check:
- Project documentation: `/home/happy/code/whatsapp-monitoring/README.md`
- ERPNext API: https://frappeframework.com/docs/user/en/api
- MCP Protocol: https://modelcontextprotocol.io/
