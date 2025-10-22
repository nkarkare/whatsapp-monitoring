#!/bin/bash
# Fix WhatsApp Monitor Service

echo "Removing old log files..."
rm -f /home/happy/code/whatsapp-monitoring/whatsapp_monitoring.log

echo "Creating log directory..."
mkdir -p ~/.local/share/whatsapp-monitoring/logs

echo "Restarting service..."
sudo systemctl restart whatsapp-monitor.service

echo "Waiting 3 seconds..."
sleep 3

echo "Checking service status..."
sudo systemctl status whatsapp-monitor.service

echo ""
echo "Checking recent logs from new location..."
tail -n 30 ~/.local/share/whatsapp-monitoring/logs/whatsapp_monitoring.log
