# Logging Configuration Guide

## Controlling Log Verbosity

The WhatsApp monitoring system supports configurable logging levels through the `LOG_LEVEL` environment variable.

### Available Log Levels

- **DEBUG** - Most verbose, shows all polling activity, message checks, and internal operations
- **INFO** - Normal operation (default), shows only important events like task creation and errors
- **WARNING** - Only warnings and errors
- **ERROR** - Only error messages
- **CRITICAL** - Only critical failures

### How to Configure

Edit `config/settings.env` and set the `LOG_LEVEL` variable:

```bash
# For troubleshooting - see all activity
LOG_LEVEL=DEBUG

# For production - quiet operation (default)
LOG_LEVEL=INFO

# For critical issues only
LOG_LEVEL=ERROR
```

### Applying Changes

After changing `LOG_LEVEL` in `config/settings.env`, restart the service:

```bash
sudo systemctl restart whatsapp-monitor.service
```

Or if running manually:
```bash
pkill -f monitor.py
python3 -m whatsapp_monitoring.monitor
```

### What You'll See

#### With LOG_LEVEL=INFO (Default)
```
2025-10-22 10:30:15 - claude_monitor - INFO - Logging to: ~/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log
2025-10-22 10:30:15 - claude_monitor - INFO - Log level: INFO
2025-10-22 10:30:15 - claude_monitor - INFO - Starting WhatsApp monitor for Claude and Task requests
2025-10-22 10:30:25 - claude_monitor - INFO - Found 1 new messages with #task tag
2025-10-22 10:30:25 - claude_monitor - INFO - Processing Task request: #task...
```

#### With LOG_LEVEL=DEBUG
```
2025-10-22 10:30:15 - claude_monitor - INFO - Logging to: ~/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log
2025-10-22 10:30:15 - claude_monitor - INFO - Log level: DEBUG
2025-10-22 10:30:15 - claude_monitor - INFO - Starting WhatsApp monitor for Claude and Task requests
2025-10-22 10:30:15 - claude_monitor - DEBUG - Looking for messages after 2025-10-22 10:30:15 with tag #claude
2025-10-22 10:30:15 - claude_monitor - DEBUG - Recent messages in database: [...]
2025-10-22 10:30:15 - claude_monitor - DEBUG - Looking for messages after 2025-10-22 10:30:15 with tag #task
2025-10-22 10:30:15 - claude_monitor - DEBUG - Recent messages in database: [...]
2025-10-22 10:30:15 - claude_monitor - DEBUG - Updated last_check_time to 2025-10-22 10:30:15
```

### Viewing Logs

```bash
# Follow logs in real-time
tail -f ~/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log

# View recent logs
tail -50 ~/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log

# Search for errors
grep ERROR ~/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log
```

### Troubleshooting

If you're having issues with tasks not being created or messages not being processed:

1. **Enable DEBUG mode** in `config/settings.env`:
   ```bash
   LOG_LEVEL=DEBUG
   ```

2. **Restart the service**:
   ```bash
   sudo systemctl restart whatsapp-monitor.service
   ```

3. **Monitor the logs**:
   ```bash
   tail -f ~/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log
   ```

4. **Send a test message** in WhatsApp with `#task Test`

5. **Check the logs** for:
   - "Found X new messages" - Confirms message detection
   - "Processing Task request" - Confirms processing started
   - Any ERROR messages - Shows what went wrong

6. **Once resolved**, switch back to INFO mode for cleaner logs.

### Log Rotation

Logs automatically rotate when they reach the configured size:
- `MAX_LOG_SIZE_MB=10` - Maximum log file size (default: 10MB)
- `LOG_BACKUP_COUNT=5` - Number of backup files to keep (default: 5)

Old logs are kept as:
- `whatsapp_monitoring.log` - Current log
- `whatsapp_monitoring.log.1` - Most recent backup
- `whatsapp_monitoring.log.2` - Second most recent
- etc.
