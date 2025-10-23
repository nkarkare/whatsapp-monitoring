#!/bin/bash
# health_check.sh - Quick MCP server health check

echo "=== MCP Server Health Check ==="

# Change to project directory
cd "$(dirname "$0")/.."

# Check Python
echo -n "Python version: "
python --version || echo "❌ Python not found"

# Check MCP SDK
python -c "import mcp; print(f'✅ MCP SDK {mcp.__version__} installed')" 2>/dev/null || echo "❌ MCP SDK missing"

# Check config
if [ -f config/settings.env ]; then
    echo "✅ Config file exists"
else
    echo "❌ Config file missing"
    exit 1
fi

# Check required variables
source config/settings.env
MISSING=""
[ -z "$ERPNEXT_URL" ] && MISSING="$MISSING ERPNEXT_URL"
[ -z "$ERPNEXT_API_KEY" ] && MISSING="$MISSING ERPNEXT_API_KEY"
[ -z "$ERPNEXT_API_SECRET" ] && MISSING="$MISSING ERPNEXT_API_SECRET"

if [ -n "$MISSING" ]; then
    echo "❌ Missing required variables:$MISSING"
    exit 1
else
    echo "✅ All required variables set"
fi

# Check ERPNext connectivity
echo -n "Checking ERPNext connectivity... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$ERPNEXT_URL" 2>/dev/null)
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "301" ]; then
    echo "✅ ERPNext accessible (HTTP $HTTP_CODE)"
else
    echo "⚠️  ERPNext returned HTTP $HTTP_CODE"
fi

# Check virtual environment
if [ -d venv ]; then
    echo "✅ Virtual environment exists"
else
    echo "⚠️  Virtual environment not found (will use system Python)"
fi

# Check scripts are executable
if [ -x scripts/run_mcp.sh ]; then
    echo "✅ run_mcp.sh is executable"
else
    echo "❌ run_mcp.sh not executable"
fi

echo ""
echo "=== Health Check Complete ==="
