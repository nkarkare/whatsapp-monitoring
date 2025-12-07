#!/bin/bash

# =============================================================================
# WhatsApp Monitoring - Complete Stack Manager
# Manages: WhatsApp Bridge Client, MCP Server, and Python Monitor
# =============================================================================

# Define paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORK_DIR="$SCRIPT_DIR"
LOG_FILE="$WORK_DIR/monitor_script.log"

# PID files for each component
MONITOR_PID_FILE="$WORK_DIR/.monitor.pid"
BRIDGE_PID_FILE="$WORK_DIR/.bridge.pid"
MCP_PID_FILE="$WORK_DIR/.mcp.pid"

# Component paths
BRIDGE_DIR="/home/happy/code/whatsapp-mcp/whatsapp-bridge"
MCP_DIR="/home/happy/code/whatsapp-mcp/whatsapp-mcp-server"

# Change to the working directory
cd "$WORK_DIR"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
    echo "$1"
}

# =============================================================================
# WhatsApp Bridge Client Management
# =============================================================================

start_bridge() {
    if is_bridge_running; then
        log "WhatsApp Bridge is already running"
        return 0
    fi

    log "Starting WhatsApp Bridge Client..."

    if [ ! -f "$BRIDGE_DIR/whatsapp-client" ]; then
        log "ERROR: WhatsApp Bridge client not found at $BRIDGE_DIR/whatsapp-client"
        return 1
    fi

    cd "$BRIDGE_DIR"
    ./whatsapp-client >> "$WORK_DIR/bridge.log" 2>&1 &
    BRIDGE_PID=$!
    echo $BRIDGE_PID > "$BRIDGE_PID_FILE"
    cd "$WORK_DIR"

    # Wait for bridge to connect
    sleep 3

    if ps -p $BRIDGE_PID > /dev/null 2>&1; then
        log "✓ WhatsApp Bridge started (PID: $BRIDGE_PID)"
        return 0
    else
        log "ERROR: WhatsApp Bridge failed to start"
        rm -f "$BRIDGE_PID_FILE"
        return 1
    fi
}

stop_bridge() {
    if [ -f "$BRIDGE_PID_FILE" ]; then
        PID=$(cat "$BRIDGE_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log "Stopping WhatsApp Bridge (PID: $PID)..."
            kill $PID 2>/dev/null
            sleep 1
            # Force kill if still running
            if ps -p $PID > /dev/null 2>&1; then
                kill -9 $PID 2>/dev/null
            fi
        fi
        rm -f "$BRIDGE_PID_FILE"
    fi

    # Also kill any orphaned whatsapp-client processes
    pkill -f "whatsapp-client" 2>/dev/null
}

is_bridge_running() {
    if [ -f "$BRIDGE_PID_FILE" ]; then
        PID=$(cat "$BRIDGE_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0
        fi
    fi

    # Check for process even without PID file
    if pgrep -f "whatsapp-client" > /dev/null 2>&1; then
        return 0
    fi

    return 1
}

# =============================================================================
# MCP Server Management
# =============================================================================

start_mcp() {
    if is_mcp_running; then
        log "MCP Server is already running"
        return 0
    fi

    log "Starting MCP Server..."

    if [ ! -d "$MCP_DIR" ]; then
        log "ERROR: MCP Server directory not found at $MCP_DIR"
        return 1
    fi

    cd "$MCP_DIR"

    # Use uv if available, otherwise python
    if command -v uv &> /dev/null; then
        uv run main.py >> "$WORK_DIR/mcp.log" 2>&1 &
    else
        python main.py >> "$WORK_DIR/mcp.log" 2>&1 &
    fi

    MCP_PID=$!
    echo $MCP_PID > "$MCP_PID_FILE"
    cd "$WORK_DIR"

    sleep 2

    if ps -p $MCP_PID > /dev/null 2>&1; then
        log "✓ MCP Server started (PID: $MCP_PID)"
        return 0
    else
        log "ERROR: MCP Server failed to start"
        rm -f "$MCP_PID_FILE"
        return 1
    fi
}

stop_mcp() {
    if [ -f "$MCP_PID_FILE" ]; then
        PID=$(cat "$MCP_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log "Stopping MCP Server (PID: $PID)..."
            kill $PID 2>/dev/null
            sleep 1
        fi
        rm -f "$MCP_PID_FILE"
    fi

    # Kill any orphaned MCP processes
    pkill -f "whatsapp-mcp-server.*main.py" 2>/dev/null
}

is_mcp_running() {
    if [ -f "$MCP_PID_FILE" ]; then
        PID=$(cat "$MCP_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0
        fi
    fi

    if pgrep -f "whatsapp-mcp-server.*main.py" > /dev/null 2>&1; then
        return 0
    fi

    return 1
}

# =============================================================================
# Python Monitor Management
# =============================================================================

start_monitor() {
    if is_monitor_running; then
        log "Python Monitor is already running"
        return 0
    fi

    log "Starting Python Monitor..."

    # Load environment variables from config
    if [ -f "$WORK_DIR/config/settings.env" ]; then
        log "Loading configuration from config/settings.env"
        export $(grep -v '^#' "$WORK_DIR/config/settings.env" | xargs)
    else
        log "WARNING: config/settings.env not found, some features may not work"
    fi

    # Activate virtual environment if exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    python -m whatsapp_monitoring.cli >> "$LOG_FILE" 2>&1 &

    MONITOR_PID=$!
    echo $MONITOR_PID > "$MONITOR_PID_FILE"

    sleep 2

    if ps -p $MONITOR_PID > /dev/null 2>&1; then
        log "✓ Python Monitor started (PID: $MONITOR_PID)"
        return 0
    else
        log "ERROR: Python Monitor failed to start"
        rm -f "$MONITOR_PID_FILE"
        return 1
    fi
}

stop_monitor() {
    if [ -f "$MONITOR_PID_FILE" ]; then
        PID=$(cat "$MONITOR_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log "Stopping Python Monitor (PID: $PID)..."
            kill $PID 2>/dev/null
            sleep 1
        fi
        rm -f "$MONITOR_PID_FILE"
    fi

    pkill -f "whatsapp_monitoring.cli" 2>/dev/null
}

is_monitor_running() {
    if [ -f "$MONITOR_PID_FILE" ]; then
        PID=$(cat "$MONITOR_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0
        fi
    fi

    if pgrep -f "whatsapp_monitoring.cli" > /dev/null 2>&1; then
        return 0
    fi

    return 1
}

# =============================================================================
# Full Stack Management
# =============================================================================

start_all() {
    log "=========================================="
    log "Starting WhatsApp Monitoring Stack"
    log "=========================================="

    # Start in order: Bridge -> MCP -> Monitor
    start_bridge
    BRIDGE_STATUS=$?

    start_mcp
    MCP_STATUS=$?

    # Wait for services to be ready
    sleep 2

    start_monitor
    MONITOR_STATUS=$?

    log "=========================================="
    log "Startup Complete"
    log "=========================================="

    show_status
}

stop_all() {
    log "=========================================="
    log "Stopping WhatsApp Monitoring Stack"
    log "=========================================="

    # Stop in reverse order: Monitor -> MCP -> Bridge
    stop_monitor
    stop_mcp
    stop_bridge

    log "All services stopped"
}

show_status() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║   WhatsApp Monitoring Stack Status       ║"
    echo "╠══════════════════════════════════════════╣"

    if is_bridge_running; then
        PID=$(cat "$BRIDGE_PID_FILE" 2>/dev/null || pgrep -f "whatsapp-client")
        echo "║ ✅ WhatsApp Bridge    : Running (PID: $PID)"
    else
        echo "║ ❌ WhatsApp Bridge    : Stopped"
    fi

    if is_mcp_running; then
        PID=$(cat "$MCP_PID_FILE" 2>/dev/null || pgrep -f "whatsapp-mcp-server")
        echo "║ ✅ MCP Server         : Running (PID: $PID)"
    else
        echo "║ ❌ MCP Server         : Stopped"
    fi

    if is_monitor_running; then
        PID=$(cat "$MONITOR_PID_FILE" 2>/dev/null || pgrep -f "whatsapp_monitoring")
        echo "║ ✅ Python Monitor     : Running (PID: $PID)"
    else
        echo "║ ❌ Python Monitor     : Stopped"
    fi

    echo "╚══════════════════════════════════════════╝"
    echo ""
}

show_logs() {
    echo "=== Bridge Logs (last 20 lines) ==="
    tail -n 20 "$WORK_DIR/bridge.log" 2>/dev/null || echo "No bridge logs"
    echo ""
    echo "=== MCP Logs (last 20 lines) ==="
    tail -n 20 "$WORK_DIR/mcp.log" 2>/dev/null || echo "No MCP logs"
    echo ""
    echo "=== Monitor Logs (last 20 lines) ==="
    tail -n 20 "$HOME/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log" 2>/dev/null || echo "No monitor logs"
}

# =============================================================================
# Command Processing
# =============================================================================

case "$1" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        start_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;

    # Individual component control
    start-bridge)
        start_bridge
        ;;
    stop-bridge)
        stop_bridge
        ;;
    start-mcp)
        start_mcp
        ;;
    stop-mcp)
        stop_mcp
        ;;
    start-monitor)
        start_monitor
        ;;
    stop-monitor)
        stop_monitor
        ;;

    *)
        echo "WhatsApp Monitoring Stack Manager"
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "Full Stack Commands:"
        echo "  start     - Start all services (Bridge + MCP + Monitor)"
        echo "  stop      - Stop all services"
        echo "  restart   - Restart all services"
        echo "  status    - Show status of all services"
        echo "  logs      - Show recent logs from all services"
        echo ""
        echo "Individual Component Commands:"
        echo "  start-bridge   - Start WhatsApp Bridge only"
        echo "  stop-bridge    - Stop WhatsApp Bridge only"
        echo "  start-mcp      - Start MCP Server only"
        echo "  stop-mcp       - Stop MCP Server only"
        echo "  start-monitor  - Start Python Monitor only"
        echo "  stop-monitor   - Stop Python Monitor only"
        echo ""
        exit 1
        ;;
esac

exit 0
