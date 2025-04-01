#!/bin/bash

# Define configuration paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORK_DIR="$SCRIPT_DIR"
LOG_FILE="$WORK_DIR/monitor_script.log"
PID_FILE="$WORK_DIR/monitor.pid"

# Change to the working directory
cd "$WORK_DIR"

# Function to start the monitor
start_monitor() {
  echo "$(date): Starting WhatsApp monitor..." >> $LOG_FILE
  
  # Activate the virtual environment and run the Python script
  if [ -d "venv" ]; then
    source venv/bin/activate
  fi
  
  python -m whatsapp_monitoring.cli >> $LOG_FILE 2>&1 &
  
  # Save the process ID
  MONITOR_PID=$!
  echo "$(date): Monitor started with PID: $MONITOR_PID" >> $LOG_FILE
  echo $MONITOR_PID > $PID_FILE
}

# Function to stop the monitor
stop_monitor() {
  if [ -f $PID_FILE ]; then
    PID=$(cat $PID_FILE)
    echo "$(date): Stopping monitor with PID: $PID" >> $LOG_FILE
    kill $PID 2>/dev/null
    rm $PID_FILE
  else
    echo "$(date): No PID file found" >> $LOG_FILE
  fi
}

# Function to check if the monitor is running
is_running() {
  if [ -f $PID_FILE ]; then
    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null; then
      return 0  # Running
    else
      return 1  # Not running but PID file exists
    fi
  else
    return 1  # Not running
  fi
}

# Command processing
case "$1" in
  start)
    if is_running; then
      echo "$(date): Monitor is already running" >> $LOG_FILE
      echo "Monitor is already running"
    else
      start_monitor
      echo "Monitor started"
    fi
    ;;
  stop)
    stop_monitor
    echo "Monitor stopped"
    ;;
  restart)
    stop_monitor
    sleep 2
    start_monitor
    echo "Monitor restarted"
    ;;
  status)
    if is_running; then
      PID=$(cat $PID_FILE)
      echo "Monitor is running (PID: $PID)"
    else
      echo "Monitor is not running"
    fi
    ;;
  logs)
    echo "=== Monitor Script Logs ==="
    tail -n 50 $LOG_FILE
    echo ""
    echo "=== Python Monitor Logs ==="
    tail -n 50 $WORK_DIR/whatsapp_monitoring.log
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac

exit 0