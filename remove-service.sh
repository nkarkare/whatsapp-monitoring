#!/bin/bash
# WhatsApp Monitor Systemd Service Removal Script
# Run this script with: sudo ./remove-service.sh

set -e  # Exit on any error

echo "=========================================="
echo "WhatsApp Monitor Service Removal"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo ./remove-service.sh"
    exit 1
fi

# Check if service exists
if [ ! -f /etc/systemd/system/whatsapp-monitor.service ]; then
    echo "⚠️  Service file not found. Service may not be installed."
    exit 0
fi

# Stop service if running
echo "🛑 Stopping WhatsApp monitoring service..."
systemctl stop whatsapp-monitor.service 2>/dev/null || true
echo "✅ Service stopped"
echo ""

# Disable service
echo "🔧 Disabling service..."
systemctl disable whatsapp-monitor.service 2>/dev/null || true
echo "✅ Service disabled"
echo ""

# Remove service file
echo "🗑️  Removing service file..."
rm -f /etc/systemd/system/whatsapp-monitor.service
echo "✅ Service file removed"
echo ""

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload
echo "✅ Systemd reloaded"
echo ""

echo "=========================================="
echo "✅ Service Removed Successfully!"
echo "=========================================="
echo ""
echo "Note: Application files and logs are still in place."
echo "To manually start/stop, use: ./run_monitor.sh start|stop"
echo ""
