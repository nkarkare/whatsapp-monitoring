# WhatsApp Monitoring System - Knowledge Base

## Project Overview

A comprehensive WhatsApp monitoring system that integrates with:
- **Claude AI** - For intelligent message responses via the Anthropic API
- **ERPNext** - For automatic task creation and management
- **WhatsApp MCP Server** - For WhatsApp message interface
- **WhatsApp Bridge** - For database connectivity

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                  WhatsApp Messages                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              WhatsApp MCP Server                            │
│         (Message Collection & API)                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│            WhatsApp Bridge                                  │
│       (SQLite Database: messages.db)                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│        WhatsApp Monitoring System                           │
│                                                             │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Monitor Module (monitor.py)                      │    │
│  │  - Poll messages.db for tagged messages           │    │
│  │  - Process #claude and #task tags                 │    │
│  │  - Coordinate confirmations and responses         │    │
│  └───────────────────────────────────────────────────┘    │
│                                                             │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Config Module (config.py)                        │    │
│  │  - Load environment variables                     │    │
│  │  - Manage .env file                               │    │
│  └───────────────────────────────────────────────────┘    │
│                                                             │
│  ┌───────────────────────────────────────────────────┐    │
│  │  CLI Module (cli.py)                              │    │
│  │  - Command-line interface                         │    │
│  │  - Argument parsing                               │    │
│  └───────────────────────────────────────────────────┘    │
└──────────────┬──────────────────────┬─────────────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐   ┌──────────────────────┐
│   Claude API         │   │   ERPNext API        │
│   (Anthropic)        │   │   (Task Management)  │
└──────────────────────┘   └──────────────────────┘
```

### File Structure

```
whatsapp-monitoring/
├── whatsapp_monitoring/
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # CLI entry point
│   ├── monitor.py            # Main monitoring logic
│   └── config.py             # Configuration management
├── setup.py                  # Package installation
├── requirements.txt          # Python dependencies
├── .env.example             # Example environment variables
├── .env                     # Actual config (gitignored)
├── scripts/
│   ├── install.sh           # Installation script
│   ├── setup-service.sh     # Systemd service setup
│   ├── start-service.sh     # Start systemd service
│   └── stop-service.sh      # Stop systemd service
└── docs/
    └── PROJECT_KNOWLEDGE_BASE.md  # This file
```

## Key Components Explained

### 1. Monitor Module (`monitor.py`)

**Purpose**: Core monitoring logic that polls the WhatsApp database and processes tagged messages.

**Key Functions**:
- `get_env_or_default(key, default)` - Helper to get environment variables (monitor.py:35)
- `check_database()` - Verify database exists and has correct schema (monitor.py:122)
- `get_recent_tagged_messages(last_check_time, tag)` - Query database for new tagged messages (monitor.py:174)
- `extract_context_count(message_content)` - Parse context count from #claude tag (monitor.py:152)
- `extract_task_details(message_content)` - Parse task details from #task tag (monitor.py:249)
- `get_message_context(chat_jid, timestamp, context_messages)` - Retrieve previous messages for context (monitor.py:649)
- `get_claude_response(conversation, system_prompt)` - Call Claude API (monitor.py:763)
- `create_erpnext_task(task_details)` - Create task in ERPNext (monitor.py:434)
- `send_whatsapp_response(chat_jid, response)` - Send message via WhatsApp Bridge API (monitor.py:828)
- `check_for_confirmation_responses()` - Monitor for user confirmation responses (monitor.py:572)
- `check_for_task_responses()` - Monitor for task creation responses (monitor.py:305)
- `main()` - Main monitoring loop (monitor.py:889)

**Flow**:
1. Polls `messages.db` every `POLL_INTERVAL` seconds (default: 10)
2. Looks for messages containing `#claude` or `#task` tags
3. For `#claude` messages:
   - Sends confirmation request for context count
   - Waits for user response
   - Retrieves context messages
   - Sends to Claude API
   - Returns response to WhatsApp
4. For `#task` messages:
   - Parses task details (if provided)
   - Creates task in ERPNext
   - Sends confirmation to WhatsApp

**State Management**:
- `pending_confirmations` dict - Tracks #claude messages awaiting context count confirmation
- `pending_tasks` dict - Tracks #task messages in multi-step creation flow

### 2. Config Module (`config.py`)

**Purpose**: Manages environment variables and configuration loading.

**Key Functions**:
- `load_env_file(env_path)` - Load variables from .env file
- `load_config()` - Initialize configuration on module import

**Configuration Sources** (in priority order):
1. Environment variables (highest priority)
2. `.env` file in project root
3. `.env.example` as fallback template
4. Hardcoded defaults (lowest priority)

### 3. CLI Module (`cli.py`)

**Purpose**: Command-line interface for starting the monitoring system.

**Features**:
- `--debug` flag for verbose logging
- `--config` flag for custom config file path
- Graceful KeyboardInterrupt handling

### 4. Database Schema (WhatsApp Bridge)

**Database Path**: Default is `../whatsapp-mcp/whatsapp-bridge/store/messages.db`

**Key Tables**:
- `messages` - Stores all WhatsApp messages
  - `id` - Message ID
  - `timestamp` - ISO format timestamp (with timezone)
  - `sender` - Phone number or contact name
  - `content` - Message text content
  - `chat_jid` - Chat identifier (JID)

- `chats` - Stores chat metadata
  - `jid` - Chat identifier
  - `name` - Chat name

## Configuration

### Environment Variables

**Database & Polling**:
- `MESSAGES_DB_PATH` - Path to messages.db (default: `../whatsapp-mcp/whatsapp-bridge/store/messages.db`)
- `POLL_INTERVAL` - Seconds between database polls (default: 10)
- `DEFAULT_CONTEXT_MSGS` - Default context messages for #claude (default: 5)

**Tags**:
- `CLAUDE_TAG` - Tag for Claude requests (default: `#claude`)
- `TASK_TAG` - Tag for task creation (default: `#task`)

**Claude API**:
- `CLAUDE_API_KEY` - Anthropic API key (required for Claude responses)
- `CLAUDE_API_URL` - API endpoint (default: `https://api.anthropic.com/v1/messages`)
- `CLAUDE_MODEL` - Model to use (default: `claude-3-opus-20240229`)

**ERPNext API**:
- `ERPNEXT_API_KEY` - ERPNext API key
- `ERPNEXT_API_SECRET` - ERPNext API secret
- `ERPNEXT_URL` - ERPNext instance URL (e.g., `https://erp.example.com`)

**WhatsApp Bridge**:
- `WHATSAPP_API_URL` - WhatsApp Bridge send API (default: `http://localhost:8080/api/send`)

**Logging**:
- `MAX_LOG_SIZE_MB` - Max log file size in MB (default: 10)
- `LOG_BACKUP_COUNT` - Number of backup log files (default: 5)

**Message Templates**:
- `TASK_SUCCESS_EMOJI` - Success emoji (default: ✅)
- `TASK_ERROR_EMOJI` - Error emoji (default: ❌)
- `TASK_SUCCESS_TEMPLATE` - Success message template
- `TASK_ERROR_TEMPLATE` - Error message template
- `TASK_SIMPLE_SUCCESS_TEMPLATE` - Simple success template
- `TASK_HELP_TEMPLATE` - Help message template

### Configuration File (.env)

Create a `.env` file in the project root:

```bash
# Database
MESSAGES_DB_PATH=/path/to/messages.db
POLL_INTERVAL=10

# API Keys
CLAUDE_API_KEY=sk-ant-api03-...
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret
ERPNEXT_URL=https://erp.example.com

# WhatsApp
WHATSAPP_API_URL=http://localhost:8080/api/send

# Tags
CLAUDE_TAG=#claude
TASK_TAG=#task
DEFAULT_CONTEXT_MSGS=5

# Logging
MAX_LOG_SIZE_MB=10
LOG_BACKUP_COUNT=5
```

## Usage Patterns

### 1. Claude AI Integration

**Simple Query**:
```
#claude What is the weather today?
```

**With Context Count**:
```
#claude 10 Summarize the last discussion
#claude n=15 What was decided about the project?
#claude context=8 Give me a summary
#claude c=5 Answer based on above
```

**Flow**:
1. User sends message with `#claude` tag
2. System detects message
3. System asks: "How many previous messages should I include for context?"
4. User replies with a number (1-20)
5. System retrieves context messages
6. System sends to Claude API
7. System sends Claude's response back to WhatsApp

### 2. Task Creation

**Simple Task** (automatic creation):
```
#task Fix the login bug in production
```

**Detailed Task** (automatic creation):
```
#task
Subject: Implement user authentication
Description: Add OAuth2 support for Google and GitHub
Priority: High
Due date: 2025-11-15
Assigned To: john@example.com
```

**Alternative Formats**:
- `Due date: today` - Sets due date to today
- `Due date: tomorrow` - Sets due date to tomorrow
- `Due date: next week` - Sets due date to 7 days from now
- `Priority: Low` / `Medium` / `High`

**Flow**:
1. User sends message with `#task` tag
2. System parses task details
3. If details found, creates task immediately
4. If simple text, creates task with text as subject
5. System sends confirmation with task ID and URL

## Common Issues & Solutions

### Issue 1: NameError - get_env_or_default not defined

**Symptom**:
```
NameError: name 'get_env_or_default' is not defined
```

**Root Cause**: Function was called before it was defined (monitor.py:36-37 called function defined at line 56)

**Solution**: Function definition moved to line 35, before first use (FIXED)

### Issue 2: PermissionError on log file

**Symptom**:
```
PermissionError: [Errno 13] Permission denied: '/path/to/whatsapp_monitoring.log'
```

**Root Cause**: Log file path inside Python package directory requires write permissions

**Solutions**:
1. Change `BASE_DIR` calculation in monitor.py to use a writable location:
   ```python
   BASE_DIR = Path.home() / ".whatsapp-monitoring"
   ```
2. Set log file path via environment variable:
   ```bash
   LOG_FILE_PATH=/var/log/whatsapp-monitoring/app.log
   ```
3. Run with appropriate permissions

### Issue 3: Database not found

**Symptom**:
```
Database not found at /path/to/messages.db
```

**Solutions**:
1. Verify WhatsApp Bridge is running and creating messages.db
2. Set correct path in .env:
   ```bash
   MESSAGES_DB_PATH=/correct/path/to/messages.db
   ```
3. Check file permissions on database directory

### Issue 4: Claude API errors

**Symptom**:
```
Error from Claude API: HTTP 401
```

**Solutions**:
1. Verify API key is set correctly in .env:
   ```bash
   CLAUDE_API_KEY=sk-ant-api03-...
   ```
2. Check API key has not expired
3. Verify API endpoint URL is correct
4. Check rate limits

### Issue 5: ERPNext task creation fails

**Symptom**:
```
Failed to create task in ERPNext
```

**Solutions**:
1. Verify ERPNext URL is accessible
2. Check API key and secret are correct
3. Verify Task doctype exists in your ERPNext instance
4. Check user permissions for task creation
5. Review ERPNext logs for detailed errors

### Issue 6: WhatsApp messages not sending

**Symptom**: System processes requests but no WhatsApp responses appear

**Solutions**:
1. Verify WhatsApp Bridge API is running at configured URL
2. Check `WHATSAPP_API_URL` in .env
3. Test API manually:
   ```bash
   curl -X POST http://localhost:8080/api/send \
     -H "Content-Type: application/json" \
     -d '{"recipient":"1234567890@s.whatsapp.net","message":"test"}'
   ```
4. Check WhatsApp Bridge logs

### Issue 7: Messages not being detected

**Symptom**: Tagged messages in WhatsApp but system doesn't process them

**Solutions**:
1. Check database path is correct
2. Verify `CLAUDE_TAG` and `TASK_TAG` match what you're using
3. Check system logs for errors
4. Verify database has messages table with correct schema
5. Check timestamp handling for timezone issues
6. Verify last_check_time is not too far in the future

## Dependencies

### Python Packages (requirements.txt)
- `requests>=2.31.0` - HTTP library for API calls
- `python-dotenv>=1.0.0` - Environment variable loading

### External Services
- **WhatsApp MCP Server** - Provides WhatsApp message collection
- **WhatsApp Bridge** - Provides SQLite database and send API
- **Claude API (Anthropic)** - AI response generation
- **ERPNext** - Task management system

### System Requirements
- Python 3.8+
- SQLite 3
- Network access to Claude API and ERPNext
- Access to WhatsApp Bridge database

## Deployment

### Manual Start
```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with configuration
cp .env.example .env
nano .env

# Run monitor
python -m whatsapp_monitoring.cli
```

### Systemd Service

**Install Service**:
```bash
./scripts/setup-service.sh
```

**Manage Service**:
```bash
# Start
sudo systemctl start whatsapp-monitor

# Stop
sudo systemctl stop whatsapp-monitor

# Status
sudo systemctl status whatsapp-monitor

# Enable auto-start
sudo systemctl enable whatsapp-monitor

# View logs
journalctl -u whatsapp-monitor -f
```

**Service Configuration** (`/etc/systemd/system/whatsapp-monitor.service`):
- Runs as current user
- Auto-restarts on failure
- Starts after network is available
- Uses virtual environment if present

## Development Notes

### Code Style
- Python 3.8+ syntax
- Type hints where appropriate
- Comprehensive error handling
- Logging for all major operations

### Testing Strategy
1. Unit tests for individual functions
2. Integration tests with mock database
3. API mocking for Claude and ERPNext
4. Manual testing with real WhatsApp messages

### Future Enhancements
1. Add message queuing for high-volume scenarios
2. Support for media messages (images, documents)
3. Multi-language support
4. Web dashboard for monitoring
5. Message history and analytics
6. Configurable workflow automations
7. Multiple AI model support
8. Rate limiting and cost tracking

## Monitoring & Logs

### Log Locations
- **Application logs**: `whatsapp_monitoring.log` (in package directory by default)
- **Systemd logs**: `journalctl -u whatsapp-monitor`

### Log Format
```
YYYY-MM-DD HH:MM:SS - logger_name - LEVEL - message
```

Example:
```
2025-10-22 14:23:10 - claude_monitor - INFO - Found 1 new messages with #claude tag
2025-10-22 14:23:15 - claude_monitor - INFO - Processing Claude request: #claude What is the weather...
2025-10-22 14:23:20 - claude_monitor - INFO - Sending prompt to Claude API: I'm forwarding you a conversation...
```

### Log Rotation
- Max size: 10 MB (configurable via `MAX_LOG_SIZE_MB`)
- Backup count: 5 files (configurable via `LOG_BACKUP_COUNT`)
- Old logs automatically compressed

### Monitoring Metrics
Monitor these metrics for system health:
- Messages processed per minute
- API response times (Claude, ERPNext)
- Error rates
- Database query performance
- Pending confirmation count
- Pending task count

## API Reference

### Claude API

**Endpoint**: `POST https://api.anthropic.com/v1/messages`

**Headers**:
```
Content-Type: application/json
x-api-key: <CLAUDE_API_KEY>
anthropic-version: 2023-06-01
```

**Request Body**:
```json
{
  "model": "claude-3-opus-20240229",
  "max_tokens": 1000,
  "messages": [
    {"role": "user", "content": "conversation text"}
  ],
  "system": "optional system prompt"
}
```

**Response**:
```json
{
  "content": [
    {"text": "Claude's response", "type": "text"}
  ],
  "model": "claude-3-opus-20240229",
  "role": "assistant"
}
```

### ERPNext API

**Task Creation**: `POST {ERPNEXT_URL}/api/resource/Task`

**Headers**:
```
Authorization: token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}
Content-Type: application/json
Accept: application/json
```

**Request Body**:
```json
{
  "data": {
    "doctype": "Task",
    "subject": "Task title",
    "description": "Task description",
    "priority": "Medium",
    "status": "Open",
    "exp_end_date": "2025-11-15"
  }
}
```

**Task Assignment**: `POST {ERPNEXT_URL}/api/method/frappe.desk.form.assign_to.add`

**Request Body**:
```json
{
  "assign_to": ["user@example.com"],
  "doctype": "Task",
  "name": "TASK-0001",
  "description": "Task description",
  "notify": 1
}
```

### WhatsApp Bridge API

**Send Message**: `POST http://localhost:8080/api/send`

**Headers**:
```
Content-Type: application/json
```

**Request Body**:
```json
{
  "recipient": "1234567890@s.whatsapp.net",
  "message": "Message text"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Message sent successfully"
}
```

## Troubleshooting Checklist

When system is not working as expected, check:

1. **Database connectivity**:
   - [ ] messages.db file exists
   - [ ] File has read permissions
   - [ ] Path in .env is correct
   - [ ] WhatsApp Bridge is running

2. **API connectivity**:
   - [ ] Claude API key is valid
   - [ ] ERPNext URL is accessible
   - [ ] WhatsApp Bridge API responds
   - [ ] Network connectivity is stable

3. **Configuration**:
   - [ ] .env file exists and is loaded
   - [ ] All required variables are set
   - [ ] Tags match what users are typing
   - [ ] Paths are absolute, not relative

4. **Permissions**:
   - [ ] Log file location is writable
   - [ ] Database file is readable
   - [ ] Process has network access

5. **Logs**:
   - [ ] Check application logs for errors
   - [ ] Review systemd logs if using service
   - [ ] Look for API error responses
   - [ ] Check WhatsApp Bridge logs

## Security Considerations

### Sensitive Data
- Store API keys in .env file (gitignored)
- Never commit API keys to version control
- Use environment variables in production
- Restrict log file permissions (contains message content)

### Network Security
- Use HTTPS for all API endpoints
- Validate SSL certificates
- Consider firewall rules for WhatsApp Bridge
- Use private networks when possible

### Database Security
- Restrict database file permissions
- Use read-only access if possible
- Consider encryption at rest
- Regular backups

### Access Control
- Limit who can deploy systemd service
- Restrict WhatsApp Bridge API access
- Use ERPNext user permissions
- Monitor API usage for anomalies

## Contributing

When modifying the code:

1. Follow existing code style
2. Add logging for new operations
3. Handle errors gracefully
4. Update this knowledge base
5. Test with mock data first
6. Consider backward compatibility

## Support Resources

- **GitHub Issues**: Report bugs and request features
- **Documentation**: README.md, .env.example
- **Logs**: Application and systemd logs
- **API Docs**: Anthropic and ERPNext documentation

---

**Last Updated**: 2025-10-22
**Version**: 1.0.0
**Maintainer**: See git history
