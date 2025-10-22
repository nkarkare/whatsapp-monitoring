#!/bin/bash
# Update WhatsApp Monitor Service Configuration

echo "This script will update the systemd service configuration."
echo "It requires sudo privileges."
echo ""

# Create log directory
echo "Creating log directory..."
mkdir -p ~/.local/share/whatsapp-monitoring/logs

# Remove old log file
echo "Removing old log file..."
rm -f /home/happy/code/whatsapp-monitoring/whatsapp_monitoring.log

# Copy new service file
echo "Installing new service configuration..."
sudo cp /home/happy/code/whatsapp-monitoring/scripts/whatsapp-monitor.service /etc/systemd/system/whatsapp-monitor.service

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Restart service
echo "Restarting service..."
sudo systemctl restart whatsapp-monitor.service

# Wait and check status
echo "Waiting 3 seconds..."
sleep 3

echo ""
echo "Service status:"
sudo systemctl status whatsapp-monitor.service

echo ""
echo "Recent logs:"
tail -n 20 ~/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log

echo ""
echo "Done! Log files are now at: ~/.local/share/whatsapp-monitoring/logs/"
