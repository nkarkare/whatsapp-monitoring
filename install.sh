#!/bin/bash

# WhatsApp Monitoring Installation Script
echo "Installing WhatsApp Monitoring..."

# Set up virtual environment
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Create config directory if it doesn't exist
if [ ! -d "config" ]; then
  mkdir -p config
fi

# Copy template config file if not exists
if [ ! -f "config/settings.env" ]; then
  echo "Creating configuration file from template..."
  cp config/settings.template.env config/settings.env
  echo "Please edit config/settings.env with your API keys and configuration."
fi

# Make run_monitor.sh executable
chmod +x run_monitor.sh

echo "Installation complete!"
echo "Edit config/settings.env with your API keys and configuration."
echo "Then run ./run_monitor.sh start to start the monitoring service."