# WhatsApp Monitor System Service

Quick reference for managing the WhatsApp monitoring systemd service.

## Installation

Run the setup script with sudo:

```bash
cd /home/happy/code/whatsapp-monitoring
sudo ./setup-service.sh
```

This will:
- ✅ Create the systemd service
- ✅ Enable auto-start on boot
- ✅ Start the service immediately
- ✅ Show service status

## Service Management

### Start the Service
```bash
sudo systemctl start whatsapp-monitor
```

### Stop the Service
```bash
sudo systemctl stop whatsapp-monitor
```

### Restart the Service
```bash
sudo systemctl restart whatsapp-monitor
```

### Check Service Status
```bash
sudo systemctl status whatsapp-monitor
```

### View Live Logs
```bash
# System logs
sudo journalctl -u whatsapp-monitor -f

# Application logs
tail -f /home/happy/code/whatsapp-monitoring/whatsapp_monitoring.log
```

### View Recent Logs (last 50 lines)
```bash
sudo journalctl -u whatsapp-monitor -n 50
```

### Disable Auto-Start on Boot
```bash
sudo systemctl disable whatsapp-monitor
```

### Enable Auto-Start on Boot
```bash
sudo systemctl enable whatsapp-monitor
```

## Removal

To completely remove the service:

```bash
sudo ./remove-service.sh
```

This will:
- Stop the service
- Disable auto-start
- Remove the systemd service file
- Application files remain intact

## Service Details

- **Service Name:** whatsapp-monitor
- **Service File:** `/etc/systemd/system/whatsapp-monitor.service`
- **Working Directory:** `/home/happy/code/whatsapp-monitoring`
- **Log File:** `/home/happy/code/whatsapp-monitoring/whatsapp_monitoring.log`
- **Runs as User:** happy
- **Auto-restart:** Yes (on failure, after 10 seconds)

## Troubleshooting

### Service won't start

Check the status for error messages:
```bash
sudo systemctl status whatsapp-monitor
```

Check the logs:
```bash
sudo journalctl -u whatsapp-monitor -n 100
```

Check configuration:
```bash
cat /home/happy/code/whatsapp-monitoring/config/settings.env
```

### Service starts but doesn't create tasks

1. Check if the service is running:
   ```bash
   sudo systemctl status whatsapp-monitor
   ```

2. Check the application logs:
   ```bash
   tail -50 /home/happy/code/whatsapp-monitoring/whatsapp_monitoring.log
   ```

3. Verify ERP credentials in config:
   ```bash
   grep ERPNEXT /home/happy/code/whatsapp-monitoring/config/settings.env
   ```

4. Check WhatsApp database path:
   ```bash
   ls -la /home/happy/code/whatsapp-mcp/whatsapp-bridge/store/messages.db
   ```

### Service starts on boot but not working

The service might start before the network or WhatsApp Bridge is ready. Check:
```bash
sudo systemctl status whatsapp-monitor
```

If needed, restart manually:
```bash
sudo systemctl restart whatsapp-monitor
```

## Configuration Changes

After changing `config/settings.env`, restart the service:

```bash
sudo systemctl restart whatsapp-monitor
```

## Alternative: Run Without Systemd

If you prefer not to use systemd, you can use the original script:

```bash
# Start in background
./run_monitor.sh start

# Check status
./run_monitor.sh status

# Stop
./run_monitor.sh stop

# View logs
./run_monitor.sh logs
```

Note: This method won't auto-start on system boot.
