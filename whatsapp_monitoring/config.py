"""Configuration loader for WhatsApp Monitoring."""

import os
import logging
from pathlib import Path

logger = logging.getLogger("whatsapp_monitoring")

def load_env_file(filepath):
    """Load environment variables from a file."""
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Split on the first equals sign
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        return True
    except Exception as e:
        logger.error(f"Error loading environment variables: {e}")
        return False

def load_config():
    """Load configuration from environment and config files."""
    # Define the app directory and config paths
    base_dir = Path(__file__).resolve().parent.parent
    config_dir = os.path.join(base_dir, "config")
    
    # Default config file
    default_config = os.path.join(config_dir, "settings.env")
    
    # Load from environment file if it exists
    if os.path.exists(default_config):
        load_env_file(default_config)
    else:
        logger.warning(f"Config file not found: {default_config}")
        logger.warning("Using default settings or environment variables.")

# Load configuration when module is imported
load_config()