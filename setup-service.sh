#!/bin/bash
# WhatsApp Monitor Systemd Service Setup Script
# Run this script with: sudo ./setup-service.sh

set -e  # Exit on any error

echo "=========================================="
echo "WhatsApp Monitor Service Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo ./setup-service.sh"
    exit 1
fi

# Get the actual user (not root when using sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
WORKING_DIR="/home/$ACTUAL_USER/code/whatsapp-monitoring"

echo "📁 Working directory: $WORKING_DIR"
echo "👤 Service will run as user: $ACTUAL_USER"
echo ""

# Create systemd service file
echo "📝 Creating systemd service file..."
cat > /etc/systemd/system/whatsapp-monitor.service <<EOF
[Unit]
Description=WhatsApp ERP Task Monitoring Service
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$WORKING_DIR
ExecStart=/usr/bin/python3 -m whatsapp_monitoring.cli
Restart=on-failure
RestartSec=10
StandardOutput=append:$WORKING_DIR/whatsapp_monitoring.log
StandardError=append:$WORKING_DIR/whatsapp_monitoring.log

# Security settings
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

# Set correct permissions
chmod 644 /etc/systemd/system/whatsapp-monitor.service
echo "✅ Service file created at /etc/systemd/system/whatsapp-monitor.service"
echo ""

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload
echo "✅ Systemd reloaded"
echo ""

# Enable service
echo "🔧 Enabling service to start on boot..."
systemctl enable whatsapp-monitor.service
echo "✅ Service enabled"
echo ""

# Start service
echo "🚀 Starting WhatsApp monitoring service..."
systemctl start whatsapp-monitor.service
echo "✅ Service started"
echo ""

# Wait a moment for service to initialize
sleep 2

# Show status
echo "=========================================="
echo "Service Status:"
echo "=========================================="
systemctl status whatsapp-monitor.service --no-pager
echo ""

echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📋 Useful Commands:"
echo "  Start:   sudo systemctl start whatsapp-monitor"
echo "  Stop:    sudo systemctl stop whatsapp-monitor"
echo "  Restart: sudo systemctl restart whatsapp-monitor"
echo "  Status:  sudo systemctl status whatsapp-monitor"
echo "  Logs:    sudo journalctl -u whatsapp-monitor -f"
echo "  Disable: sudo systemctl disable whatsapp-monitor"
echo ""
echo "📁 Application logs: $WORKING_DIR/whatsapp_monitoring.log"
echo ""
echo "🎉 WhatsApp monitoring is now running as a system service!"
echo "   It will automatically start on system boot."
echo ""
