# MCP Server Integration Checklist

This checklist ensures proper integration of the WhatsApp Monitoring MCP Server with Claude Code.

---

## Pre-Integration Setup

### 1. Environment Setup ✅

- [x] Python 3.8+ installed
- [x] Virtual environment created (`venv/`)
- [x] Dependencies installed (`pip install -r requirements.txt`)
- [x] MCP SDK version 0.9.0+ installed

**Verify:**
```bash
python --version  # Should be 3.8+
source venv/bin/activate
python -c "import mcp; print(mcp.__version__)"
```

---

### 2. Configuration ✅

- [x] `config/settings.env` created from template
- [x] ERPNext URL configured
- [x] API key and secret set
- [x] Admin WhatsApp number configured (optional)
- [x] Default task assignee set (optional)

**Verify:**
```bash
# Check config file exists
ls -l config/settings.env

# Verify required variables (without exposing secrets)
grep "ERPNEXT_URL" config/settings.env
grep "ERPNEXT_API_KEY" config/settings.env
grep "ERPNEXT_API_SECRET" config/settings.env
```

**Environment Variables:**
```bash
# Required
ERPNEXT_URL=https://your-erp-server.com
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret

# Optional
ADMIN_WHATSAPP_NUMBER=917498189688
DEFAULT_TASK_ASSIGNEE=your.email@company.com
USER_RESOLUTION_TIMEOUT=300
FUZZY_MATCH_THRESHOLD=80
MAX_USER_SUGGESTIONS=5
```

---

### 3. File Permissions ✅

- [x] `scripts/run_mcp.sh` executable
- [x] `config/settings.env` readable
- [x] `mcp_main.py` executable

**Set permissions:**
```bash
chmod +x scripts/run_mcp.sh
chmod +x mcp_main.py
chmod 600 config/settings.env  # Restrict to owner only
```

---

## Integration Testing

### 4. Standalone Testing ✅

Test the MCP server starts correctly before integrating with Claude Code.

**Test 1: Manual startup**
```bash
./scripts/run_mcp.sh
```

**Expected output:**
```
Loading configuration from: /home/happy/code/whatsapp-monitoring/config/settings.env
=== MCP Server Configuration ===
Project Root: /home/happy/code/whatsapp-monitoring
ERPNext URL: https://erp.walnutedu.in
Admin WhatsApp: 917498189688
Default Assignee: happy.karkare@walnutedu.in
================================

Starting WhatsApp Monitoring MCP Server...
INFO - ERPNext client initialized successfully
INFO - User resolver initialized successfully
INFO - MCP server initialized and ready
INFO - MCP server running on stdio
```

**Test 2: Validation tests**
```bash
source venv/bin/activate
python tests/test_mcp_manual.py
```

**Expected:** All 7/7 tests pass

---

### 5. Claude Code Integration ✅

Add the MCP server to Claude Code's configuration.

**Configuration File Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Option 1: Using mcp_main.py directly**

```json
{
  "mcpServers": {
    "whatsapp-monitoring": {
      "command": "python",
      "args": ["/home/happy/code/whatsapp-monitoring/mcp_main.py"],
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
```

**Option 2: Using run_mcp.sh (recommended)**

```json
{
  "mcpServers": {
    "whatsapp-monitoring": {
      "command": "/home/happy/code/whatsapp-monitoring/scripts/run_mcp.sh",
      "args": []
    }
  }
}
```

**Benefits of Option 2:**
- Automatic virtual environment activation
- Configuration validation
- Better error messages
- Easier troubleshooting

---

### 6. Verify Claude Code Connection ✅

**Steps:**

1. Save the configuration file
2. Restart Claude Code completely
3. Open Claude Code
4. Check MCP server status in settings/tools

**Verification:**

In Claude Code, run:
```
List available MCP tools
```

**Expected tools:**
- `create_erp_task`
- `list_erp_users`
- `search_users`
- `resolve_user_interactive`
- `check_disambiguation`
- `get_task_status`

---

## Functional Testing

### 7. Test Each MCP Tool

**Test 1: List Users**
```
Use the list_erp_users tool to show me all active users
```

**Expected:** JSON list of users with names and emails

---

**Test 2: Search Users**
```
Use search_users to find users matching "john"
```

**Expected:** Ranked list of matching users with scores

---

**Test 3: Create Task**
```
Use create_erp_task to create a task:
- Subject: "Test task from Claude Code"
- Description: "Testing MCP integration"
- Priority: "High"
- Assigned to: "john.doe@company.com"
```

**Expected:**
```json
{
  "success": true,
  "task_id": "TASK-XXX",
  "task_url": "https://erp.../app/task/TASK-XXX",
  "user_resolution": {
    "resolved": true,
    "user": "John Doe (john.doe@company.com)"
  }
}
```

---

**Test 4: Error Handling**
```
Use create_erp_task with an invalid user:
- Subject: "Test error handling"
- Assigned to: "nonexistent.user@fake.com"
```

**Expected:** Clear error message about user not found

---

### 8. WhatsApp Integration Testing (Optional)

If WhatsApp MCP server is also configured:

**Test 5: User Disambiguation**
```
Use create_erp_task with ambiguous user:
- Subject: "Test disambiguation"
- Assigned to: "smith"
- Auto-resolve: false
```

**Expected:**
1. Disambiguation request sent to admin WhatsApp
2. Response with resolution_id
3. Admin receives WhatsApp message with options
4. Use `check_disambiguation` to poll for response

---

## Production Deployment

### 9. Production Checklist

#### Security
- [ ] `config/settings.env` has restrictive permissions (600)
- [ ] API credentials rotated if previously exposed
- [ ] Configuration file in `.gitignore`
- [ ] HTTPS enforced for ERPNext URL
- [ ] Audit logging enabled

#### Monitoring
- [ ] Server startup logs reviewed
- [ ] ERPNext connectivity verified
- [ ] Tool response times acceptable
- [ ] Error rates monitored
- [ ] Usage patterns tracked

#### Documentation
- [ ] Team trained on available tools
- [ ] Usage examples shared
- [ ] Troubleshooting guide accessible
- [ ] Escalation path defined
- [ ] Change log maintained

#### Backup & Recovery
- [ ] Configuration backed up
- [ ] ERPNext API keys documented (securely)
- [ ] Rollback procedure defined
- [ ] Alternative access methods ready
- [ ] Disaster recovery tested

---

## Troubleshooting Guide

### Server Won't Start

**Symptom:** MCP server fails to initialize

**Solutions:**
1. Check Python version: `python --version` (must be 3.8+)
2. Verify MCP SDK installed: `pip list | grep mcp`
3. Check configuration file exists: `ls -l config/settings.env`
4. Review startup logs for specific errors

---

### ERPNext Connection Failed

**Symptom:** "Failed to initialize ERPNext client"

**Solutions:**
1. Verify ERPNext URL is accessible: `curl -I https://your-erp-server.com`
2. Check API key/secret are correct
3. Verify network connectivity
4. Check ERPNext API is enabled
5. Review ERPNext logs for authentication errors

---

### Tools Not Visible in Claude Code

**Symptom:** MCP tools don't appear in Claude Code

**Solutions:**
1. Verify configuration file location is correct
2. Check JSON syntax is valid (use `jsonlint`)
3. Restart Claude Code completely
4. Check MCP server is running (look in logs)
5. Verify file paths are absolute, not relative

---

### User Resolution Fails

**Symptom:** "No users found matching..."

**Solutions:**
1. Verify user exists in ERPNext
2. Check user is enabled (not disabled)
3. Try exact email instead of name
4. Review fuzzy match threshold setting
5. Check ERPNext user permissions

---

### Disambiguation Timeout

**Symptom:** "Resolution timed out"

**Solutions:**
1. Increase `USER_RESOLUTION_TIMEOUT` (default: 300s)
2. Check WhatsApp number is correct
3. Verify admin can receive WhatsApp messages
4. Use `auto_resolve: true` for automatic selection
5. Check WhatsApp MCP server is running

---

## Maintenance

### Regular Tasks

**Daily:**
- Monitor server logs for errors
- Check ERPNext connectivity
- Review tool usage patterns

**Weekly:**
- Update dependencies if needed
- Review and rotate logs
- Check for MCP SDK updates

**Monthly:**
- Rotate API credentials
- Review and update documentation
- Audit user access patterns
- Test disaster recovery

---

## Support Contacts

### Technical Issues
- MCP Server Logs: Check stderr output
- ERPNext Issues: Contact ERPNext administrator
- WhatsApp Integration: Check WhatsApp MCP server

### Documentation
- MCP Server Guide: `docs/MCP_SERVER.md`
- Usage Examples: `docs/USAGE_EXAMPLES.md`
- Quick Start: `docs/MCP_QUICK_START.md`
- Implementation Details: `docs/MCP_IMPLEMENTATION_SUMMARY.md`

---

## Appendix: Testing Scripts

### Quick Health Check

```bash
#!/bin/bash
# health_check.sh - Quick MCP server health check

echo "=== MCP Server Health Check ==="

# Check Python
python --version || echo "❌ Python not found"

# Check MCP SDK
python -c "import mcp" 2>/dev/null && echo "✅ MCP SDK installed" || echo "❌ MCP SDK missing"

# Check config
[ -f config/settings.env ] && echo "✅ Config file exists" || echo "❌ Config file missing"

# Check ERPNext connectivity
ERPNEXT_URL=$(grep ERPNEXT_URL config/settings.env | cut -d= -f2)
curl -s -o /dev/null -w "%{http_code}" "$ERPNEXT_URL" | grep -q "200\|302" && echo "✅ ERPNext accessible" || echo "❌ ERPNext unreachable"

echo "=== Health Check Complete ==="
```

### Tool Testing Script

```bash
#!/bin/bash
# test_tools.sh - Test all MCP tools

echo "=== Testing MCP Tools ==="

source venv/bin/activate

# Run validation tests
python tests/test_mcp_manual.py

echo "=== Tool Testing Complete ==="
```

---

## Sign-Off

**Integration Completed:** [ ]
**Tested By:** __________________
**Date:** __________________
**Production Approved:** [ ]
**Approved By:** __________________

---

**Version:** 1.0.0
**Last Updated:** 2025-10-22
**Next Review:** 2025-11-22
