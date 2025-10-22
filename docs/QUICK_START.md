# Quick Start Guide - WhatsApp to ERP Task Integration

## What Changed?

The WhatsApp monitoring system now **automatically creates tasks in your ERP** when someone types `#task` in a WhatsApp message. No confirmation dialogs - tasks are created instantly!

## Prerequisites

✅ WhatsApp Bridge running and connected
✅ WhatsApp MCP Server running
✅ Python 3.8+ installed
✅ ERP system with API access

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd /home/happy/code/whatsapp-monitoring
./install.sh
```

### 2. Configure Your ERP Credentials

```bash
# Copy the template
cp config/settings.template.env config/settings.env

# Edit the configuration
nano config/settings.env
```

**Update these three lines with your actual ERP details:**

```env
ERPNEXT_API_KEY=your_actual_api_key
ERPNEXT_API_SECRET=your_actual_secret
ERPNEXT_URL=https://your-erp-server.com
```

Also verify the WhatsApp database path:
```env
MESSAGES_DB_PATH=/path/to/whatsapp-bridge/store/messages.db
```

Save and exit (Ctrl+O, Enter, Ctrl+X)

### 3. Test the Configuration

```bash
python -m whatsapp_monitoring.cli --debug
```

Send a test message in WhatsApp:
```
#task Test task from WhatsApp
```

You should see:
- ✅ Task created successfully message in WhatsApp
- Task appears in your ERP system
- Log output showing the task creation

Press Ctrl+C to stop the test.

### 4. Run in Background

```bash
./run_monitor.sh start
```

Check it's running:
```bash
./run_monitor.sh status
```

## How to Use

### Simple Tasks (Recommended)

Just type `#task` followed by what you need done:

```
#task Fix the login bug on the mobile app
```

```
#task Review Sarah's pull request #245
```

```
#task Schedule Q4 planning meeting
```

### Detailed Tasks

For more control, use the structured format:

```
#task
Subject: Implement OAuth2 authentication
Description: Add Google and Microsoft OAuth2 login options to the platform. Include token refresh mechanism.
Priority: High
Due date: 2025-11-15
Assigned To: dev@company.com
```

### Date Options

- `today` - Task due today
- `tomorrow` - Task due tomorrow
- `next week` - Task due in 7 days
- `2025-11-15` - Specific date

## Management Commands

```bash
# Start the background service
./run_monitor.sh start

# Check if it's running
./run_monitor.sh status

# View recent logs
./run_monitor.sh logs

# Stop the service
./run_monitor.sh stop

# Restart (after config changes)
./run_monitor.sh restart
```

## Troubleshooting

### "Failed to create task" Error

1. Check your ERP credentials in `config/settings.env`
2. Verify your ERP server is accessible:
   ```bash
   curl -X GET -H "Authorization: token KEY:SECRET" https://your-erp.com/api/resource/Task
   ```
3. Check the logs:
   ```bash
   tail -50 whatsapp_monitoring.log
   ```

### Tasks Not Being Detected

1. Verify the service is running:
   ```bash
   ./run_monitor.sh status
   ```

2. Check the database path is correct in `config/settings.env`

3. Make sure you're using exactly `#task` (case-insensitive)

4. Wait 10 seconds after sending the message (default polling interval)

### Permission Issues

```bash
chmod +x run_monitor.sh
chmod 600 config/settings.env
```

## Configuration Options

### Change Polling Speed

How often to check for new messages (default: 10 seconds):

```env
POLL_INTERVAL=5  # Check every 5 seconds
```

### Customize Messages

Change the emojis and response templates:

```env
TASK_SUCCESS_EMOJI=🎉
TASK_ERROR_EMOJI=⚠️
```

### Adjust Log Retention

```env
MAX_LOG_SIZE_MB=20  # Increase log file size
LOG_BACKUP_COUNT=10  # Keep more backup files
```

## What Happens When You Send #task?

```
1. WhatsApp Message Sent
   ↓
2. WhatsApp Bridge Saves to Database (within seconds)
   ↓
3. Monitor Detects New #task Message (within 10 seconds)
   ↓
4. Task Details Extracted Automatically
   ↓
5. ERP API Call to Create Task (instant)
   ↓
6. Success/Error Message Sent to WhatsApp (instant)
   ↓
7. You Get Task ID and Link
```

**Total Time**: Usually 10-15 seconds from sending message to getting confirmation

## Advanced: Run as System Service (Production)

For production environments, set up a systemd service:

```bash
sudo nano /etc/systemd/system/whatsapp-monitor.service
```

```ini
[Unit]
Description=WhatsApp ERP Task Monitor
After=network.target

[Service]
Type=simple
User=happy
WorkingDirectory=/home/happy/code/whatsapp-monitoring
ExecStart=/usr/bin/python3 -m whatsapp_monitoring.cli
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable whatsapp-monitor
sudo systemctl start whatsapp-monitor
sudo systemctl status whatsapp-monitor
```

## Need Help?

1. 📖 Full documentation: `docs/ERP_SETUP.md`
2. 📋 Check logs: `tail -f whatsapp_monitoring.log`
3. 🔧 Main README: `README.md`

## Summary of Changes

| Before | After |
|--------|-------|
| Manual confirmation required | ✅ Automatic task creation |
| Multi-step dialog | ✅ Single message = task created |
| Template required | ✅ Simple text works too |
| Takes ~30-60 seconds | ✅ Takes ~10-15 seconds |

---

**Ready to use!** Just start the service and type `#task` in WhatsApp. 🚀
