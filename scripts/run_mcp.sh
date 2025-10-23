#!/bin/bash
#
# MCP Server Startup Script for WhatsApp Monitoring
#
# This script provides a convenient way to start the MCP server with proper
# environment configuration.
#
# Usage:
#   ./scripts/run_mcp.sh                    # Start with config/settings.env
#   ./scripts/run_mcp.sh /path/to/env       # Start with custom env file
#

set -e  # Exit on error

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration file
CONFIG_FILE="${1:-$PROJECT_ROOT/config/settings.env}"

# Check if configuration file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Configuration file not found: $CONFIG_FILE" >&2
    echo "" >&2
    echo "Please create a configuration file with the following variables:" >&2
    echo "  ERPNEXT_URL=https://your-erp-server.com" >&2
    echo "  ERPNEXT_API_KEY=your_api_key" >&2
    echo "  ERPNEXT_API_SECRET=your_api_secret" >&2
    echo "  ADMIN_WHATSAPP_NUMBER=917498189688" >&2
    echo "  DEFAULT_TASK_ASSIGNEE=your.email@company.com" >&2
    echo "" >&2
    echo "You can copy from the template:" >&2
    echo "  cp $PROJECT_ROOT/config/settings.template.env $PROJECT_ROOT/config/settings.env" >&2
    exit 1
fi

# Load environment variables from config file
echo "Loading configuration from: $CONFIG_FILE" >&2
set -a  # Export all variables
source "$CONFIG_FILE"
set +a

# Check for required variables
REQUIRED_VARS=(
    "ERPNEXT_URL"
    "ERPNEXT_API_KEY"
    "ERPNEXT_API_SECRET"
)

OPTIONAL_VARS=(
    "ADMIN_WHATSAPP_NUMBER"
    "DEFAULT_TASK_ASSIGNEE"
    "USER_RESOLUTION_TIMEOUT"
    "FUZZY_MATCH_THRESHOLD"
    "MAX_USER_SUGGESTIONS"
)

missing_vars=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "ERROR: Missing required environment variables:" >&2
    printf '  %s\n' "${missing_vars[@]}" >&2
    echo "" >&2
    echo "Please configure them in: $CONFIG_FILE" >&2
    exit 1
fi

# Display configuration (without secrets)
echo "=== MCP Server Configuration ===" >&2
echo "Project Root: $PROJECT_ROOT" >&2
echo "ERPNext URL: $ERPNEXT_URL" >&2
echo "Admin WhatsApp: ${ADMIN_WHATSAPP_NUMBER:-not configured}" >&2
echo "Default Assignee: ${DEFAULT_TASK_ASSIGNEE:-not configured}" >&2
echo "================================" >&2
echo "" >&2

# Change to project directory
cd "$PROJECT_ROOT"

# Check if Python virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..." >&2
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..." >&2
    source .venv/bin/activate
else
    echo "WARNING: No virtual environment found. Using system Python." >&2
fi

# Check if mcp module is installed
if ! python -c "import mcp" 2>/dev/null; then
    echo "ERROR: MCP SDK not installed. Installing..." >&2
    pip install mcp
fi

# Start the MCP server
echo "Starting WhatsApp Monitoring MCP Server..." >&2
exec python "$PROJECT_ROOT/mcp_main.py"
