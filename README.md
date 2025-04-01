# WhatsApp Monitoring

A monitoring system that connects to WhatsApp and provides automated responses through various integrations.

## Overview

This tool monitors a WhatsApp database for messages with specific tags (`#claude` or `#task`) and responds with:
- AI-generated answers using the Claude API
- Task creation in ERPNext

This project is a companion to the [WhatsApp MCP Server](https://github.com/lharries/whatsapp-mcp) and requires it to be installed and running.

## Features

- **Claude AI Integration**: Monitors for `#claude` messages and uses Claude API to respond with AI-generated answers
- **Task Management**: Creates tasks in ERPNext when detecting `#task` messages
- **Template Support**: Supports filling templates for task creation
- **Flexible Context**: Allows users to specify how many previous messages to include as context

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

Send a message with the `#task` tag followed by task details:

```
#task 
Subject: Schedule team meeting
Description: Weekly sync-up with the development team
Priority: Medium
Due date: tomorrow
Assigned To: john.doe@example.com
```

The system will create a task in ERPNext and provide a confirmation with the task link.

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