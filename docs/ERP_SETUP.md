# ERP Integration Setup Guide

This guide will help you configure the WhatsApp monitoring system to automatically create tasks in your ERP system.

## Overview

The system monitors WhatsApp messages for the `#task` tag and automatically creates tasks in your ERP system via API calls. No confirmation is required - tasks are created instantly when the tag is detected.

## Features

- **Automatic Task Creation**: Simply type `#task` followed by your task description
- **Two Input Formats**:
  - Simple: `#task Fix the login bug`
  - Detailed: Structured format with Subject, Description, Priority, etc.
- **Background Service**: Runs continuously, checking for new messages every 10 seconds
- **Instant Feedback**: Sends back task ID and link immediately after creation

## Configuration Steps

### 1. Get Your ERP API Credentials

You'll need three pieces of information from your ERP system:

1. **API Key** - Your ERP API authentication key
2. **API Secret** - Your ERP API secret token
3. **ERP URL** - The base URL of your ERP server (e.g., `https://erp.yourcompany.com`)

#### For ERPNext/Frappe:
1. Log into your ERPNext instance
2. Go to **Settings** → **API Access**
3. Click **Generate Keys**
4. Copy the **API Key** and **API Secret**
5. Note your server URL

### 2. Configure the Application

1. Navigate to the config directory:
   ```bash
   cd /home/happy/code/whatsapp-monitoring/config
   ```

2. Copy the template configuration file:
   ```bash
   cp settings.template.env settings.env
   ```

3. Edit the configuration file:
   ```bash
   nano settings.env
   ```

4. Update the ERP configuration section:
   ```env
   # ERP System Configuration
   ERPNEXT_API_KEY=your_actual_api_key_here
   ERPNEXT_API_SECRET=your_actual_api_secret_here
   ERPNEXT_URL=https://your-erp-server.com
   ```

5. **Important**: Also update the WhatsApp database path:
   ```env
   MESSAGES_DB_PATH=/path/to/your/whatsapp-bridge/store/messages.db
   ```

6. Save the file (Ctrl+O, Enter, Ctrl+X)

### 3. Test the Configuration

Before running in the background, test that everything works:

```bash
cd /home/happy/code/whatsapp-monitoring
python -m whatsapp_monitoring.cli --debug
```

Send a test message in WhatsApp:
```
#task Test task from WhatsApp integration
```

You should see:
- Log output showing the message was detected
- A response in WhatsApp with the task ID and link
- The task created in your ERP system

Press Ctrl+C to stop the test.

## Running in Background

### Start the Background Service

```bash
cd /home/happy/code/whatsapp-monitoring
./run_monitor.sh start
```

### Check Service Status

```bash
./run_monitor.sh status
```

### View Logs

```bash
./run_monitor.sh logs
```

Or view the full log file:
```bash
tail -f whatsapp_monitoring.log
```

### Stop the Service

```bash
./run_monitor.sh stop
```

### Restart the Service

```bash
./run_monitor.sh restart
```

## Usage Examples

### Simple Task (Recommended for Quick Tasks)

Just type `#task` followed by your task description:

```
#task Review the pull request for authentication module
```

**Result**: Creates a task with:
- Subject: "Review the pull request for authentication module"
- Priority: Medium (default)
- Status: Open

### Detailed Task (For Complex Tasks)

Use the structured format for more control:

```
#task
Subject: Implement user authentication
Description: Add JWT-based authentication to the API endpoints. Include refresh token mechanism and rate limiting.
Priority: High
Due date: 2025-11-01
Assigned To: developer@company.com
```

**Result**: Creates a task with all specified details

### Date Shortcuts

You can use these shortcuts for due dates:
- `today` - Sets due date to today
- `tomorrow` - Sets due date to tomorrow
- `next week` - Sets due date to 7 days from now
- `YYYY-MM-DD` - Specific date (e.g., `2025-11-15`)

Example:
```
#task
Subject: Deploy to production
Priority: High
Due date: tomorrow
```

## Troubleshooting

### Tasks Not Being Created

1. **Check the logs**:
   ```bash
   tail -50 whatsapp_monitoring.log
   ```

2. **Verify configuration**:
   - Ensure `settings.env` exists in the `config/` directory
   - Check that API credentials are correct
   - Verify ERP URL is accessible

3. **Test API connectivity**:
   ```bash
   curl -X GET \
     -H "Authorization: token YOUR_KEY:YOUR_SECRET" \
     https://your-erp-server.com/api/resource/Task
   ```

### Message Not Detected

1. **Check database path**:
   - Verify `MESSAGES_DB_PATH` points to the correct WhatsApp database
   - Ensure the database file is readable

2. **Check tag format**:
   - Tag must be exactly `#task` (case-insensitive)
   - Tag can appear anywhere in the message

3. **Check polling interval**:
   - Default is 10 seconds - wait at least 10 seconds after sending message
   - Can be changed in `settings.env` with `POLL_INTERVAL=5`

### Permission Denied Errors

```bash
# Make scripts executable
chmod +x run_monitor.sh
chmod +x install.sh

# Check file permissions
ls -la whatsapp_monitoring.log
ls -la config/settings.env
```

## Security Best Practices

1. **Protect your credentials**:
   ```bash
   chmod 600 config/settings.env
   ```

2. **Never commit credentials to git**:
   - The `.gitignore` already excludes `settings.env`
   - Double-check before committing

3. **Use environment variables** (optional but recommended):
   ```bash
   export ERPNEXT_API_KEY="your_key"
   export ERPNEXT_API_SECRET="your_secret"
   export ERPNEXT_URL="https://your-server.com"
   ```

4. **Rotate API keys** periodically in your ERP system

## Systemd Service (Optional - For Production)

To run the service automatically on system startup:

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/whatsapp-monitor.service
   ```

2. Add the following content:
   ```ini
   [Unit]
   Description=WhatsApp ERP Task Monitoring Service
   After=network.target

   [Service]
   Type=simple
   User=happy
   WorkingDirectory=/home/happy/code/whatsapp-monitoring
   ExecStart=/usr/bin/python3 -m whatsapp_monitoring.cli
   Restart=on-failure
   RestartSec=10
   StandardOutput=append:/home/happy/code/whatsapp-monitoring/whatsapp_monitoring.log
   StandardError=append:/home/happy/code/whatsapp-monitoring/whatsapp_monitoring.log

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable whatsapp-monitor
   sudo systemctl start whatsapp-monitor
   ```

4. Check status:
   ```bash
   sudo systemctl status whatsapp-monitor
   ```

## API Endpoint Reference

The system uses the following ERP API endpoints:

### Create Task
- **Endpoint**: `POST /api/resource/Task`
- **Headers**:
  - `Authorization: token API_KEY:API_SECRET`
  - `Content-Type: application/json`
- **Body**:
  ```json
  {
    "data": {
      "doctype": "Task",
      "subject": "Task title",
      "description": "Task details",
      "priority": "High",
      "status": "Open",
      "exp_end_date": "2025-11-01"
    }
  }
  ```

### Assign Task
- **Endpoint**: `POST /api/method/frappe.desk.form.assign_to.add`
- **Body**:
  ```json
  {
    "assign_to": ["user@example.com"],
    "doctype": "Task",
    "name": "TASK-0001",
    "description": "Assignment description",
    "notify": 1
  }
  ```

## Support

For issues or questions:
1. Check the logs: `tail -f whatsapp_monitoring.log`
2. Review this documentation
3. Check the main README.md for general setup
4. Open an issue on GitHub (if applicable)

## Advanced Configuration

### Custom Polling Interval

Change how often the system checks for new messages (default: 10 seconds):

```env
POLL_INTERVAL=5  # Check every 5 seconds
```

### Custom Tags

Change the task tag from `#task` to something else:

```env
TASK_TAG=#todo
```

Then use `#todo` in your WhatsApp messages instead.

### Multiple ERP Systems

To support multiple ERP systems, you can:
1. Run multiple instances with different config files
2. Use the `--config` flag:
   ```bash
   python -m whatsapp_monitoring.cli --config /path/to/custom-config.env
   ```

---

**Last Updated**: 2025-10-22
