#!/usr/bin/env python3
"""Command-line interface for WhatsApp monitoring."""

import argparse
import sys
import logging
import os
from pathlib import Path

# Load configuration first
from whatsapp_monitoring.config import load_config
from whatsapp_monitoring.monitor import main as monitor_main

def setup_logging(debug=False):
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description='WhatsApp Monitoring CLI')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--config', help='Path to config file')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.debug)
    
    # Load custom config if provided
    if args.config:
        if os.path.exists(args.config):
            from whatsapp_monitoring.config import load_env_file
            load_env_file(args.config)
        else:
            print(f"Config file not found: {args.config}")
            sys.exit(1)
    
    try:
        monitor_main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
        sys.exit(0)

if __name__ == '__main__':
    main()