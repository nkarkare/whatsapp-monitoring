# WhatsApp Monitoring

A monitoring system that connects to WhatsApp and provides automated responses through various integrations.

## Overview

This tool monitors a WhatsApp database for messages with specific tags (`#claude` or `#task`) and responds with:
- AI-generated answers using the Claude API
- Task creation in ERPNext

This project is a companion to the [WhatsApp MCP Server](https://github.com/lharries/whatsapp-mcp) and requires it to be installed and running.

## Features

- **Claude AI Integration**: Monitors for `#claude` messages and uses Claude API to respond with AI-generated answers
- **Automatic Task Creation**: Instantly creates tasks in your ERP system when detecting `#task` messages
- **Dual Input Modes**:
  - Simple format: `#task Your task description`
  - Detailed template: Structured format with Subject, Description, Priority, Due date, and Assignment
- **Background Service**: Runs continuously as a daemon, checking for new messages every 10 seconds
- **Instant Feedback**: Sends task ID and clickable link back to WhatsApp immediately after creation
- **No Confirmation Required**: Tasks are created automatically without user confirmation
- **Flexible Context**: Allows users to specify how many previous messages to include for AI responses

## Dependencies

This project **requires** the [WhatsApp MCP Server](https://github.com/lharries/whatsapp-mcp) to be installed and running. It depends on:

1. **[WhatsApp MCP Server](https://github.com/lharries/whatsapp-mcp)** - Provides the API to send messages to WhatsApp
2. **WhatsApp Bridge** (included in the MCP repo) - Maintains the SQLite database that this tool monitors

### Installing the Required Dependencies

Before installing this monitoring tool, you must first set up the WhatsApp MCP Server:

1. Clone the WhatsApp MCP repository:
```bash
git clone https://github.com/lharries/whatsapp-mcp.git
cd whatsapp-mcp
```

2. Follow the installation instructions in the WhatsApp MCP repository to set up:
   - WhatsApp Bridge (Go application that connects to WhatsApp)
   - WhatsApp MCP Server (Python server that provides the API)

3. Make sure both the WhatsApp Bridge and MCP Server are running before proceeding with this installation.

## Prerequisites

- Python 3.8+
- WhatsApp MCP Server (must be installed and running)
- WhatsApp Bridge (must be installed and running)
- Access to Claude AI API (for AI responses)
- Access to ERPNext API (for task management)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/nkarkare/whatsapp-monitoring.git
cd whatsapp-monitoring
```

2. Run the installation script:
```bash
./install.sh
```

This will:
- Create a virtual environment
- Install dependencies
- Create configuration files

3. Configure your settings:
```bash
# Edit the configuration file with your API keys and settings
nano config/settings.env
```

4. Ensure your configuration points to the correct WhatsApp MCP Server:
```
# In config/settings.env
MESSAGES_DB_PATH=/path/to/whatsapp-mcp/whatsapp-bridge/store/messages.db
WHATSAPP_API_URL=http://localhost:8080/api/send
```

## Configuration

All configuration is managed through environment variables or the `config/settings.env` file:

```
# WhatsApp Bridge Configuration
MESSAGES_DB_PATH=/path/to/whatsapp-mcp/whatsapp-bridge/store/messages.db
WHATSAPP_API_URL=http://localhost:8080/api/send

# Message Monitoring
CLAUDE_TAG=#claude
TASK_TAG=#task
POLL_INTERVAL=10
DEFAULT_CONTEXT_MSGS=5

# Claude AI Configuration
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_API_URL=https://api.anthropic.com/v1/messages
CLAUDE_MODEL=claude-3-opus-20240229

# ERPNext Configuration
ERPNEXT_API_KEY=your_erpnext_api_key_here
ERPNEXT_API_SECRET=your_erpnext_api_secret_here
ERPNEXT_URL=https://your-erpnext-server.com
```

## MCP Server Integration (Claude Code)

This project now includes an MCP (Model Context Protocol) server that allows Claude Code to directly interact with your WhatsApp monitoring system and ERPNext installation.

### What is the MCP Server?

The MCP server exposes the WhatsApp monitoring functionality as a set of tools that Claude Code can use to:
- Create ERPNext tasks with automatic user resolution
- Search and list ERPNext users
- Resolve user ambiguities via WhatsApp disambiguation
- Get task status and details

### Quick Start with Claude Code

1. **Install the MCP SDK** (if not already installed):
```bash
pip install mcp
```

2. **Configure the MCP server in Claude Code**:

Add to your Claude Code configuration file (`~/.config/Claude/claude_desktop_config.json` on Linux):

```json
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
```

Or use the provided startup script:

```json
{
  "mcpServers": {
    "whatsapp-monitoring": {
      "command": "bash",
      "args": ["/path/to/whatsapp-monitoring/scripts/run_mcp.sh"],
      "env": {}
    }
  }
}
```

3. **Configure MCP-specific settings** in `config/settings.env`:

```bash
# Admin WhatsApp number for user disambiguation
ADMIN_WHATSAPP_NUMBER=917498189688

# Default task assignee
DEFAULT_TASK_ASSIGNEE=your.email@company.com

# User resolution timeout (seconds)
USER_RESOLUTION_TIMEOUT=300

# Fuzzy matching threshold (0-100)
FUZZY_MATCH_THRESHOLD=80

# Maximum user suggestions
MAX_USER_SUGGESTIONS=5
```

4. **Start Claude Code** and the MCP server will be available automatically.

### Available MCP Tools

The MCP server provides the following tools to Claude Code:

#### 1. `create_erp_task`
Create tasks in ERPNext with automatic user resolution.

**Parameters:**
- `subject` (required): Task title
- `description` (optional): Task details
- `priority` (optional): Low/Medium/High/Urgent
- `due_date` (optional): YYYY-MM-DD format
- `assigned_to` (optional): User name or email (fuzzy matched)
- `auto_resolve` (optional): Auto-select best match (default: true)

**Example:**
```
Create a task titled "Review authentication module"
assigned to "John Doe" with high priority
```

#### 2. `list_erp_users`
List all active users from ERPNext.

**Parameters:**
- `limit` (optional): Maximum users to return (default: 1000)
- `fields` (optional): Specific fields to retrieve

#### 3. `search_users`
Search for users by name or email with fuzzy matching.

**Parameters:**
- `query` (required): Search query
- `fields` (optional): Specific fields to retrieve

#### 4. `resolve_user_interactive`
Start interactive user resolution via WhatsApp when multiple matches are found.

**Parameters:**
- `query` (required): User name/email to resolve
- `context` (optional): Additional context

#### 5. `check_disambiguation`
Check status of a user disambiguation request.

**Parameters:**
- `resolution_id` (required): ID from resolve_user_interactive
- `wait` (optional): Wait for response (default: false)
- `timeout` (optional): Max seconds to wait (default: 60)

#### 6. `get_task_status`
Get status and details of a task by ID.

**Parameters:**
- `task_id` (required): Task ID

### User Resolution with Fuzzy Matching

The MCP server includes intelligent user resolution:

1. **Exact Match**: If the query exactly matches a user's name or email, it's used immediately
2. **Fuzzy Match**: If the match score is above the threshold (default 80%), the user is auto-selected
3. **Multiple Matches**: If multiple users match with similar scores:
   - With `auto_resolve=true`: Best match is selected automatically
   - With `auto_resolve=false`: Disambiguation request is sent to admin via WhatsApp

**Example Queries:**
- "John" → Finds "John Doe"
- "j.doe" → Finds "john.doe@company.com"
- "Jane" → Multiple matches → WhatsApp disambiguation

### Manual Testing

You can test the MCP server manually:

```bash
# Start the MCP server
./scripts/run_mcp.sh

# Or directly with Python
python mcp_main.py
```

### Integration Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│                 │         │                  │         │                 │
│   Claude Code   │ ◄────► │   MCP Server     │ ◄────► │    ERPNext      │
│                 │         │ (whatsapp-       │         │      API        │
│                 │         │  monitoring)     │         │                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                     ▲
                                     │
                                     │ (disambiguation)
                                     ▼
                            ┌─────────────────┐
                            │                 │
                            │    WhatsApp     │
                            │   (via admin)   │
                            │                 │
                            └─────────────────┘
```

### Documentation

For more details, see:
- [MCP Server Documentation](docs/MCP_SERVER.md) - Complete API reference
- [Quick Start Guide](docs/MCP_QUICK_START.md) - Setup and usage examples
- [Usage Examples](docs/USAGE_EXAMPLES.md) - Real-world use cases
- [Implementation Summary](docs/MCP_IMPLEMENTATION_SUMMARY.md) - Technical details

## Usage

### Starting the Monitor

```bash
./run_monitor.sh start
```

### Checking Status

```bash
./run_monitor.sh status
```

### Viewing Logs

```bash
./run_monitor.sh logs
```

### Stopping the Monitor

```bash
./run_monitor.sh stop
```

### Restarting the Monitor

```bash
./run_monitor.sh restart
```

## Usage Examples

### Claude AI Queries

Send a message with the `#claude` tag followed by your question:

```
#claude What is the capital of France?
```

The system will ask how many previous messages to include for context, and then process your request using Claude AI.

### Task Creation

The system **automatically creates tasks** when it detects the `#task` tag. No confirmation required!

#### Simple Format (Quick Tasks)
```
#task Review the authentication module pull request
```

The system will instantly create a task with the message content as the subject.

#### Detailed Format (Complex Tasks)
```
#task
Subject: Schedule team meeting
Description: Weekly sync-up with the development team
Priority: High
Due date: tomorrow
Assigned To: john.doe@example.com
```

The system will create a task with all specified details and send back:
- ✅ Task ID
- Direct link to view the task in your ERP system
- All task details for confirmation

**Date Shortcuts:**
- `today` - Due date is today
- `tomorrow` - Due date is tomorrow
- `next week` - Due date is 7 days from now
- `YYYY-MM-DD` - Specific date (e.g., 2025-11-15)

**Example Response:**
```
✅ Task created successfully!

Task ID: TASK-00123
Subject: Review authentication module
Priority: High
Due Date: 2025-10-23
Assigned To: developer@company.com

View task: https://erp.company.com/app/task/TASK-00123
```

## System Architecture

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│                 │         │              │         │                 │
│  WhatsApp App   │ ◄────► │  WhatsApp    │ ◄────► │   WhatsApp MCP   │
│  (Mobile/Web)   │         │  Bridge (Go) │         │   Server (API)  │
│                 │         │              │         │                 │
└─────────────────┘         └──────────────┘         └─────────────────┘
                                   ▲                         ▲
                                   │                         │
                                   │                         │
                                   ▼                         │
                            ┌──────────────┐                 │
                            │              │                 │
                            │  SQLite DB   │                 │
                            │              │                 │
                            └──────────────┘                 │
                                   ▲                         │
                                   │                         │
                                   │                         │
                                   ▼                         ▼
                            ┌───────────────────────────────────┐
                            │                                   │
                            │      WhatsApp Monitoring          │
                            │      (This Repository)            │
                            │                                   │
                            └───────────────────────────────────┘
                                           ▲  ▲
                                           │  │
                     ┌─────────────────────┘  └──────────────────────┐
                     │                                               │
                     ▼                                               ▼
            ┌─────────────────┐                             ┌─────────────────┐
            │                 │                             │                 │
            │    Claude AI    │                             │     ERPNext     │
            │      API        │                             │      API        │
            │                 │                             │                 │
            └─────────────────┘                             └─────────────────┘
```

## Troubleshooting

- **Monitor not finding the database**: Check that the `MESSAGES_DB_PATH` in your config points to the correct WhatsApp Bridge SQLite database
- **API keys not working**: Verify your API keys in the configuration file
- **Monitor not starting**: Check the log files with `./run_monitor.sh logs`
- **No responses being sent**: Ensure the WhatsApp MCP Server is running and the API URL is correct

## License

MIT

## Acknowledgements

This project is built on top of [WhatsApp MCP Server](https://github.com/lharries/whatsapp-mcp) by [@lharries](https://github.com/lharries) and uses:
- [Claude AI API](https://anthropic.com) for intelligent responses
- [ERPNext](https://erpnext.com) for task management

## Author

Created by [@nkarkare](https://github.com/nkarkare)