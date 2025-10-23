# MCP Server Quick Start Guide

Get the WhatsApp Monitoring MCP server running in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- ERPNext instance with API access
- (Optional) WhatsApp MCP for user disambiguation

## Installation

### Step 1: Install Dependencies

```bash
cd /home/happy/code/whatsapp-monitoring
pip install -r requirements.txt
```

This will install:
- `requests>=2.28.1` - HTTP client
- `python-dateutil>=2.8.2` - Date utilities
- `mcp>=0.9.0` - Model Context Protocol SDK

### Step 2: Configure Settings

Edit `/home/happy/code/whatsapp-monitoring/config/settings.env`:

```bash
# ERPNext (Required)
ERPNEXT_URL=https://your-erp.com
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret

# WhatsApp (Optional - for user disambiguation)
ADMIN_WHATSAPP_NUMBER=1234567890

# Defaults (Optional)
DEFAULT_TASK_ASSIGNEE=admin@example.com
```

### Step 3: Test the Setup

```bash
python3 scripts/test_mcp_server.py
```

Expected output:
```
============================================================
  WhatsApp Monitoring MCP Server Test Suite
============================================================

✅ ERPNEXT_URL is configured
✅ ERPNEXT_API_KEY is configured
✅ ERPNEXT_API_SECRET is configured
...
6/6 tests passed
✅ All tests passed! MCP server is ready to use.
```

### Step 4: Configure Claude Code

Add to your Claude Code MCP configuration (`~/.config/claude-code/mcp.json`):

```json
{
  "mcpServers": {
    "whatsapp-monitoring": {
      "command": "python3",
      "args": ["-m", "whatsapp_monitoring.mcp_server"],
      "cwd": "/home/happy/code/whatsapp-monitoring",
      "env": {
        "PYTHONPATH": "/home/happy/code/whatsapp-monitoring"
      }
    }
  }
}
```

Or use the provided config:
```bash
cp docs/claude_mcp_config.json ~/.config/claude-code/mcp.json
```

### Step 5: Restart Claude Code

Restart Claude Code to load the new MCP server.

## First Task

Create your first task via Claude Code:

```python
# Ask Claude Code to run this
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Test task from MCP server",
    "description": "Verifying MCP integration works",
    "priority": "Low"
})

print(f"Task created: {result['task_url']}")
```

## Available Tools

Once configured, you'll have access to:

1. **create_erp_task** - Create tasks with user resolution
2. **list_erp_users** - List all active users
3. **search_users** - Search users with fuzzy matching
4. **resolve_user_interactive** - Interactive WhatsApp disambiguation
5. **check_disambiguation** - Poll for disambiguation responses
6. **get_task_status** - Get task details

## Common Commands

### Create a Simple Task
```python
mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Fix the login bug"
})
```

### Create Task with Assignment
```python
mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Review code",
    "assigned_to": "john",
    "priority": "High",
    "due_date": "2025-10-30"
})
```

### Search for Users
```python
mcp__whatsapp_monitoring__search_users({
    "query": "developer"
})
```

### List All Users
```python
mcp__whatsapp_monitoring__list_erp_users({
    "limit": 50
})
```

## Troubleshooting

### MCP Package Not Found
```bash
pip install mcp>=0.9.0
```

### ERPNext Connection Failed
1. Verify URL: `echo $ERPNEXT_URL`
2. Test API:
   ```bash
   curl -H "Authorization: token $ERPNEXT_API_KEY:$ERPNEXT_API_SECRET" \
        $ERPNEXT_URL/api/resource/User
   ```

### MCP Server Not Appearing in Claude Code
1. Check config location: `~/.config/claude-code/mcp.json`
2. Verify Python path: `which python3`
3. Test server manually:
   ```bash
   python3 -m whatsapp_monitoring.mcp_server
   ```

### User Assignment Not Working
1. Set DEFAULT_TASK_ASSIGNEE in settings.env
2. Verify user exists: `mcp__whatsapp_monitoring__search_users({"query": "username"})`
3. Use exact email: `"assigned_to": "user@example.com"`

## Next Steps

- Read **MCP_SERVER.md** for complete API reference
- Check **USAGE_EXAMPLES.md** for 12+ practical examples
- Review **MCP_IMPLEMENTATION_SUMMARY.md** for architecture details

## Support

For issues:
1. Run test suite: `python3 scripts/test_mcp_server.py`
2. Check logs: Set `LOG_LEVEL=DEBUG` in settings.env
3. Verify configuration: Review all required environment variables

## Quick Reference

**File Locations:**
- MCP Server: `/home/happy/code/whatsapp-monitoring/whatsapp_monitoring/mcp_server.py`
- Configuration: `/home/happy/code/whatsapp-monitoring/config/settings.env`
- Test Suite: `/home/happy/code/whatsapp-monitoring/scripts/test_mcp_server.py`
- Documentation: `/home/happy/code/whatsapp-monitoring/docs/`

**Key Settings:**
- `ERPNEXT_URL` - Your ERPNext instance
- `ERPNEXT_API_KEY` - API key from ERPNext
- `ERPNEXT_API_SECRET` - API secret from ERPNext
- `ADMIN_WHATSAPP_NUMBER` - For user disambiguation
- `DEFAULT_TASK_ASSIGNEE` - Fallback assignee

**Common Priorities:**
- `Low` - Can wait
- `Medium` - Normal priority (default)
- `High` - Important
- `Urgent` - Critical

That's it! You're ready to automate ERPNext task creation via WhatsApp and Claude Code.
