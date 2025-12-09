#!/usr/bin/env python3
"""
WhatsApp Monitoring Module

This module provides monitoring capabilities for WhatsApp messages, with integrations for:
- Claude AI for answering questions
- ERPNext for task management

Dependencies:
- WhatsApp MCP Server - Required to interface with WhatsApp
- WhatsApp Bridge - Required for the database connection
"""

import sqlite3
import time
import os
import logging
import logging.handlers
import requests
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import subprocess
import sys
import asyncio
from pathlib import Path

# Import configuration
from whatsapp_monitoring.config import load_config
# Import ERPNext client
from whatsapp_monitoring.erpnext_client import create_client_from_env

# Import new features (optional - will not break if not available)
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.keyword_monitor import create_from_env as create_keyword_monitor
    KEYWORD_MONITORING_AVAILABLE = True
except ImportError:
    KEYWORD_MONITORING_AVAILABLE = False
    logging.warning("Keyword monitoring not available")

# AI Task Detection feature
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.ai_task_detector import create_from_env as create_ai_task_detector
    AI_TASK_DETECTION_AVAILABLE = True
except ImportError:
    AI_TASK_DETECTION_AVAILABLE = False
    logging.warning("AI task detection not available")

# Daily summary feature (requires MCP)
try:
    from src.daily_summary import create_from_env as create_daily_summary
    from mcp import ClientSession, StdioServerParameters
    DAILY_SUMMARY_AVAILABLE = True
    MCP_AVAILABLE = True
except ImportError:
    DAILY_SUMMARY_AVAILABLE = False
    MCP_AVAILABLE = False
    logging.warning("Daily summary feature not available (requires MCP)")

# Define the app directory and config
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# Load configuration from environment or use defaults
def get_env_or_default(key, default):
    return os.environ.get(key, default)

# Setup logging with rotation
# Use a log directory in the user's home to avoid permission issues
log_dir = os.path.expanduser(get_env_or_default("LOG_DIR", "~/.local/share/whatsapp-monitoring/logs"))
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "whatsapp_monitoring.log")

max_log_size = int(get_env_or_default("MAX_LOG_SIZE_MB", "10")) * 1024 * 1024
backup_count = int(get_env_or_default("LOG_BACKUP_COUNT", "5"))

# Get log level from environment (DEBUG, INFO, WARNING, ERROR, CRITICAL)
log_level_str = get_env_or_default("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

# Configure rotating file handler
handler = logging.handlers.RotatingFileHandler(
    log_file, maxBytes=max_log_size, backupCount=backup_count
)
console_handler = logging.StreamHandler()

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[handler, console_handler]
)
logger = logging.getLogger("claude_monitor")
logger.info(f"Logging to: {log_file}")
logger.info(f"Log level: {log_level_str}")

# Create config directory if it doesn't exist
os.makedirs(CONFIG_DIR, exist_ok=True)

# Constants
MESSAGES_DB_PATH = get_env_or_default("MESSAGES_DB_PATH", 
                    os.path.join(os.path.dirname(BASE_DIR), 'whatsapp-mcp', 'whatsapp-bridge', 'store', 'messages.db'))
CLAUDE_TAG = get_env_or_default("CLAUDE_TAG", "#claude")
TASK_TAG = get_env_or_default("TASK_TAG", "#task")
POLL_INTERVAL = int(get_env_or_default("POLL_INTERVAL", "10"))  # seconds
WHATSAPP_API_URL = get_env_or_default("WHATSAPP_API_URL", "http://localhost:8080/api/send")  # WhatsApp Bridge API
DEFAULT_CONTEXT_MSGS = int(get_env_or_default("DEFAULT_CONTEXT_MSGS", "5"))  # Default number of messages for context

# Check if the database exists
if not os.path.exists(MESSAGES_DB_PATH):
    logger.warning(f"Database not found at {MESSAGES_DB_PATH}. Please verify WhatsApp Bridge is running.")
    logger.warning(f"You can set a custom path with the MESSAGES_DB_PATH environment variable.")

# Store pending confirmations
# Format: {message_id: {'timestamp': datetime, 'context_count': int, 'chat_jid': str, 'tagged_message': tuple}}
pending_confirmations = {}

# Store pending task details
# Format: {message_id: {'timestamp': datetime, 'chat_jid': str, 'tagged_message': tuple, 'task_details': dict}}
pending_tasks = {}

# Store pending AI-detected tasks (in-memory cache, synced with database)
# Format: {message_id: {'timestamp': datetime, 'detection': dict, 'stage': str, 'recipient': str, 'task_num': int}}
pending_ai_tasks = {}

# Track last processed response timestamp to avoid duplicate processing
last_ai_response_time = None

# Track last processed reaction ID to avoid duplicates
last_reaction_check_time = None

# Track processed reactions (in-memory set, persists via database)
processed_reactions = set()

# Claude API Configuration - Set these in environment variables for security
CLAUDE_API_KEY = get_env_or_default("CLAUDE_API_KEY", "")
CLAUDE_API_URL = get_env_or_default("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
CLAUDE_MODEL = get_env_or_default("CLAUDE_MODEL", "claude-3-opus-20240229")

# ERPNext API Configuration - Set these in environment variables for security
ERPNEXT_API_KEY = get_env_or_default("ERPNEXT_API_KEY", "")
ERPNEXT_API_SECRET = get_env_or_default("ERPNEXT_API_SECRET", "")
ERPNEXT_URL = get_env_or_default("ERPNEXT_URL", "")

# Initialize ERPNext client (will be set in main)
_erpnext_client = None

def get_erpnext_client():
    """Get or create the ERPNext client instance"""
    global _erpnext_client
    if _erpnext_client is None:
        try:
            _erpnext_client = create_client_from_env()
            logger.info("ERPNext client initialized successfully")
        except ValueError as e:
            logger.error(f"Failed to initialize ERPNext client: {e}")
            logger.warning("ERPNext functionality will be disabled")
    return _erpnext_client

# Message Templates - Configurable via environment variables
TASK_SUCCESS_EMOJI = get_env_or_default("TASK_SUCCESS_EMOJI", "✅")
TASK_ERROR_EMOJI = get_env_or_default("TASK_ERROR_EMOJI", "❌")
TASK_SUCCESS_TEMPLATE = get_env_or_default("TASK_SUCCESS_TEMPLATE",
    "{emoji} Task created successfully!\n\n"
    "Task ID: {task_id}\n"
    "Subject: {subject}\n"
    "Priority: {priority}\n"
    "Due Date: {due_date}\n"
    "Assigned To: {assigned_to}\n\n"
    "View task: {task_url}")
TASK_ERROR_TEMPLATE = get_env_or_default("TASK_ERROR_TEMPLATE",
    "{emoji} Failed to create task in ERP system.\n"
    "Error: {error}\n\n"
    "Please check the configuration or contact support.")
TASK_SIMPLE_SUCCESS_TEMPLATE = get_env_or_default("TASK_SIMPLE_SUCCESS_TEMPLATE",
    "{emoji} Task created successfully!\n\n"
    "Task ID: {task_id}\n"
    "Subject: {subject}\n\n"
    "View task: {task_url}")
TASK_HELP_TEMPLATE = get_env_or_default("TASK_HELP_TEMPLATE",
    "To create a task, use one of these formats:\n\n"
    "1. Simple: #task Your task description here\n\n"
    "2. Detailed:\n"
    "#task\n"
    "Subject: Task title\n"
    "Description: Task details\n"
    "Priority: Low/Medium/High\n"
    "Due date: YYYY-MM-DD, today, tomorrow, or next week\n"
    "Assigned To: username or email")

def check_database():
    """Check if the database exists and has the expected tables"""
    try:
        if not os.path.exists(MESSAGES_DB_PATH):
            logger.error(f"Database file not found at: {MESSAGES_DB_PATH}")
            return False
            
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        # Check for tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cursor.fetchone():
            logger.error("Messages table not found in database")
            return False
            
        # Check for messages with #claude tag
        cursor.execute("SELECT COUNT(*) FROM messages WHERE content LIKE ?", (f"%{CLAUDE_TAG}%",))
        count = cursor.fetchone()[0]
        logger.info(f"Found {count} total messages with {CLAUDE_TAG} tag in database")
            
        logger.info(f"Database at {MESSAGES_DB_PATH} looks valid")
        return True
    except Exception as e:
        logger.error(f"Error checking database: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def extract_context_count(message_content):
    """Extract the number of context messages requested from the message content"""
    # Look for patterns like "#claude 10" or "#claude n=15" to extract context count
    patterns = [
        r'#claude\s+(\d+)',        # #claude 10
        r'#claude\s+n=(\d+)',      # #claude n=10
        r'#claude\s+context=(\d+)', # #claude context=10
        r'#claude\s+c=(\d+)'       # #claude c=10
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_content, re.IGNORECASE)
        if match:
            try:
                count = int(match.group(1))
                return min(max(count, 1), 20)  # Limit between 1 and 20 messages
            except ValueError:
                pass
    
    # Default if no match found
    return DEFAULT_CONTEXT_MSGS

def get_recent_tagged_messages(last_check_time, tag=CLAUDE_TAG):
    """
    Get messages containing a specific tag that were received after last_check_time
    
    Args:
        last_check_time: datetime, the time of the last check
        tag: str, the tag to search for (default: CLAUDE_TAG)
        
    Returns:
        list of tuples: [(timestamp, sender, chat_name, content, chat_jid, message_id)]
    """
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        # Convert datetime to string for SQLite comparison
        last_check_str = last_check_time.strftime("%Y-%m-%d %H:%M:%S")
        logger.debug(f"Looking for messages after {last_check_str} with tag {tag}")

        # Debug: print recent messages with timestamps
        cursor.execute("""
            SELECT timestamp, content FROM messages
            ORDER BY timestamp DESC LIMIT 5
        """)
        recent_msgs = cursor.fetchall()
        logger.debug(f"Recent messages in database: {recent_msgs}")
        
        # Query for tagged messages - handle timezone offset in timestamps
        query = """
        SELECT 
            m.timestamp,
            m.sender,
            c.name,
            m.content,
            c.jid,
            m.id
        FROM messages m
        JOIN chats c ON m.chat_jid = c.jid
        WHERE 
            m.content LIKE ?
        ORDER BY m.timestamp ASC
        """
        
        cursor.execute(query, (f"%{tag}%",))
        all_messages = cursor.fetchall()
        
        # Filter messages based on timestamp in Python to handle timezone correctly
        messages = []
        for msg in all_messages:
            # Extract timestamp and handle timezone
            msg_timestamp_str = msg[0]
            if '+' in msg_timestamp_str:
                # Remove timezone offset for comparison
                msg_timestamp_str = msg_timestamp_str.split('+')[0]
            
            # Parse timestamp and compare with last_check_time
            msg_timestamp = datetime.fromisoformat(msg_timestamp_str)
            if msg_timestamp > last_check_time:
                messages.append(msg)
        
        if messages:
            logger.info(f"Found {len(messages)} new messages with {tag} tag")
            for msg in messages:
                logger.info(f"New message: [{msg[0]}] {msg[3][:50]}...")
            
        return messages
    except sqlite3.Error as e:
        logger.error(f"Error querying messages: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def extract_task_details(message_content):
    """
    Extract task details from the message content if they match the template format
    
    Args:
        message_content: str, the message content
        
    Returns:
        dict with task details or empty dict if not found
    """
    # Remove the #task tag
    clean_content = re.sub(r'#task\s*', '', message_content, flags=re.IGNORECASE).strip()
    
    # Initialize task details
    task_details = {
        'has_details': False
    }
    
    # Check if content has lines with Subject:, Description:, etc.
    subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', clean_content, re.IGNORECASE)
    description_match = re.search(r'Description:\s*(.+?)(?:\n|$)', clean_content, re.IGNORECASE)
    priority_match = re.search(r'Priority:\s*(.+?)(?:\n|$)', clean_content, re.IGNORECASE)
    due_date_match = re.search(r'Due date:\s*(.+?)(?:\n|$)', clean_content, re.IGNORECASE)
    assigned_to_match = re.search(r'Assigned To:\s*(.+?)(?:\n|$)', clean_content, re.IGNORECASE)
    
    # If we have at least subject, consider it a valid template
    if subject_match:
        task_details['has_details'] = True
        task_details['subject'] = subject_match.group(1).strip()
        
        if description_match:
            task_details['description'] = description_match.group(1).strip()
        
        if priority_match:
            priority = priority_match.group(1).strip().lower()
            if priority in ['low', 'medium', 'high']:
                task_details['priority'] = priority.capitalize()
            else:
                task_details['priority'] = 'Medium'  # Default
        
        if due_date_match:
            due_date = due_date_match.group(1).strip().lower()
            # Parse due date
            if due_date == 'today':
                due_date = datetime.now().strftime('%Y-%m-%d')
            elif due_date == 'tomorrow':
                due_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            elif due_date == 'next week':
                due_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            task_details['due_date'] = due_date
        
        if assigned_to_match:
            task_details['assigned_to'] = assigned_to_match.group(1).strip()
    
    return task_details

def check_for_task_responses():
    """Check for responses to task creation requests"""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        # List of message IDs to process after this check
        to_process = []
        
        # Check each pending task
        for msg_id, data in list(pending_tasks.items()):
            chat_jid = data['chat_jid']
            since_time = data['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
            current_stage = data.get('stage', 'template')
            task_details = data.get('task_details', {})
            
            # Query for recent messages in this chat
            query = """
            SELECT m.content
            FROM messages m
            WHERE 
                m.chat_jid = ?
                AND datetime(substr(m.timestamp, 1, 19)) > datetime(?)
            ORDER BY m.timestamp DESC
            LIMIT 10
            """
            
            cursor.execute(query, (chat_jid, since_time))
            responses = cursor.fetchall()
            
            if not responses:
                continue
                
            # Get the latest response
            latest_response = responses[0][0].strip()
            
            # Check for cancellation
            if latest_response.lower() in ['cancel', 'stop', 'abort']:
                logger.info(f"Received task creation cancellation for message {msg_id}")
                del pending_tasks[msg_id]
                send_whatsapp_response(chat_jid, "Task creation cancelled.")
                continue
                
            # Update task details based on current stage
            if current_stage == 'template':
                # Check if the response contains template details
                template_details = extract_task_details(latest_response)
                
                if template_details.get('has_details', False):
                    # Template filled, proceed to confirmation
                    data['task_details'] = template_details
                    data['stage'] = 'confirmation'
                    data['timestamp'] = datetime.now()
                    
                    # Send confirmation
                    subject = template_details.get('subject', 'No subject')
                    description = template_details.get('description', 'No description')
                    priority = template_details.get('priority', 'Medium')
                    due_date = template_details.get('due_date', 'No due date')
                    assigned_to = template_details.get('assigned_to', 'Unassigned')
                    
                    confirmation_msg = (
                        f"Please confirm the task details:\n\n"
                        f"Subject: {subject}\n"
                        f"Description: {description}\n"
                        f"Priority: {priority}\n"
                        f"Due Date: {due_date}\n"
                        f"Assigned To: {assigned_to}\n\n"
                        f"Reply with 'confirm' to create this task, or 'cancel' to abort."
                    )
                    
                    send_whatsapp_response(chat_jid, confirmation_msg)
                else:
                    # Template not recognized, reminder
                    send_whatsapp_response(
                        chat_jid,
                        "I couldn't recognize the task details in your message. Please use the template format:\n\n"
                        "Subject: [Your task subject]\n"
                        "Description: [Your task description]\n"
                        "Priority: (Low/Medium/High)\n"
                        "Due date: (YYYY-MM-DD, today, tomorrow, or next week)\n"
                        "Assigned To: (username or email)"
                    )
                
            elif current_stage == 'confirmation':
                if latest_response.lower() in ['confirm', 'yes', 'ok', 'create']:
                    # Ready to create task in ERPNext
                    to_process.append((msg_id, data))
                elif latest_response.lower() in ['cancel', 'no', 'abort']:
                    logger.info(f"Task creation cancelled for message {msg_id}")
                    del pending_tasks[msg_id]
                    send_whatsapp_response(chat_jid, "Task creation cancelled.")
        
        # Process confirmed tasks
        for msg_id, data in to_process:
            # Create the task in ERPNext
            result = create_erpnext_task(data['task_details'])
            
            # Send result back to user
            chat_jid = data['chat_jid']
            if result.get('success'):
                task_id = result.get('task_id', 'Unknown')
                task_url = result.get('task_url', f"{ERPNEXT_URL}/app/task/{task_id}")
                assignee = data['task_details'].get('assigned_to', 'N/A')
                
                success_msg = (
                    f"✅ Task created successfully in ERPNext!\n\n"
                    f"Task ID: {task_id}\n"
                    f"Assigned To: {assignee}\n"
                    f"View task: {task_url}"
                )
                
                send_whatsapp_response(chat_jid, success_msg)
            else:
                error = result.get('error', 'Unknown error')
                send_whatsapp_response(
                    chat_jid, 
                    f"Failed to create task in ERPNext. Error: {error}"
                )
            
            # Remove from pending list
            del pending_tasks[msg_id]
            
    except Exception as e:
        logger.error(f"Error checking for task responses: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def create_erpnext_task(task_details):
    """
    Create a task in ERPNext using the ERPNextClient

    Args:
        task_details: dict containing task data

    Returns:
        dict with success flag and task ID or error message
    """
    try:
        # Get or create ERPNext client
        client = get_erpnext_client()

        if client is None:
            logger.error("ERPNext client not available")
            return {"success": False, "error": "ERPNext client not configured"}

        # Use the ERPNextClient to create the task
        logger.info(f"Creating task via ERPNextClient: {task_details.get('subject', 'No subject')}")
        result = client.create_task(task_details)

        return result

    except Exception as e:
        logger.error(f"Error creating ERPNext task: {e}")
        return {"success": False, "error": str(e)}

def check_for_confirmation_responses():
    """Check for confirmation responses from users"""
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        # List of message IDs to process after this check
        to_process = []
        
        # Check each pending confirmation
        for msg_id, data in list(pending_confirmations.items()):
            # Check for numeric response for context count
            chat_jid = data['chat_jid']
            since_time = data['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
            
            # Query for recent messages in this chat
            query = """
            SELECT m.content
            FROM messages m
            WHERE 
                m.chat_jid = ?
                AND datetime(substr(m.timestamp, 1, 19)) > datetime(?)
            ORDER BY m.timestamp DESC
            LIMIT 10
            """
            
            cursor.execute(query, (chat_jid, since_time))
            responses = cursor.fetchall()
            
            # Check for a numeric response
            number_response = None
            for resp in responses:
                content = resp[0].strip()
                if content.isdigit():
                    number_response = content
                    break
                    
            if number_response:
                try:
                    # Update context count based on user's response
                    count = int(number_response)
                    # Limit between 1 and 20 messages
                    count = min(max(count, 1), 20)
                    data['context_count'] = count
                    logger.info(f"Updated context count for message {msg_id} to {count} based on user response")
                    
                    # Process with updated count
                    to_process.append((msg_id, data))
                except ValueError:
                    pass
            
            # Check for rejection/cancellation
            cancel_response = None
            for resp in responses:
                content = resp[0].lower()
                if any(word in content for word in ['cancel', 'stop', 'abort']):
                    cancel_response = content
                    break
            
            if cancel_response:
                logger.info(f"Received rejection for message {msg_id}: {cancel_response}")
                del pending_confirmations[msg_id]
                send_whatsapp_response(chat_jid, "Request cancelled.")
        
        # Process confirmed messages
        for msg_id, data in to_process:
            # Process the message
            process_confirmed_message(data)
            # Remove from pending list
            del pending_confirmations[msg_id]
            
    except sqlite3.Error as e:
        logger.error(f"Error checking for confirmation: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def get_message_context(chat_jid, message_timestamp, context_messages=5):
    """
    Get messages before the tagged message for context
    
    Args:
        chat_jid: str, the chat JID
        message_timestamp: str, ISO format timestamp of the message
        context_messages: int, number of preceding messages to include
        
    Returns:
        list of tuples: [(timestamp, sender, content)]
    """
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()
        
        # Extract the date part for comparison
        timestamp_for_comparison = message_timestamp[:19]
        
        query = """
        SELECT 
            m.timestamp,
            m.sender,
            m.content
        FROM messages m
        WHERE 
            m.chat_jid = ?
            AND datetime(substr(m.timestamp, 1, 19)) < datetime(?)
        ORDER BY m.timestamp DESC
        LIMIT ?
        """
        
        cursor.execute(query, (chat_jid, timestamp_for_comparison, context_messages))
        context = cursor.fetchall()
        
        logger.info(f"Retrieved {len(context)} messages for context")
        
        # Return in chronological order
        return list(reversed(context))
    except sqlite3.Error as e:
        logger.error(f"Error retrieving message context: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def process_confirmed_message(data):
    """Process a message after confirmation"""
    context_count = data['context_count']
    chat_jid = data['chat_jid']
    tagged_message = data['tagged_message']
    
    try:
        # Get context
        context = get_message_context(chat_jid, tagged_message[0], context_count)
        
        # Format the conversation
        conversation = format_conversation(context, tagged_message)
        
        # Format the Claude prompts
        claude_prompt = format_claude_prompt(conversation, tagged_message)
        system_prompt = format_claude_system_prompt(tagged_message)
        
        # Send processing message
        send_whatsapp_response(
            chat_jid, 
            f"Processing request with Claude... (including {context_count} previous messages for context)..."
        )
        
        # Request a response from Claude
        logger.info(f"Sending prompt to Claude API: {claude_prompt[:100]}...")
        claude_response = get_claude_response(claude_prompt, system_prompt)
        
        # Send Claude's response back to the original chat
        send_whatsapp_response(chat_jid, claude_response)
        
        logger.info(f"Processed message from {tagged_message[1]} in chat {tagged_message[2] or 'Unknown Chat'}")
    except Exception as e:
        logger.error(f"Error processing confirmed message: {e}")
        send_whatsapp_response(chat_jid, f"Error processing your request: {str(e)}")

def format_conversation(context, tagged_message):
    """Format the conversation for sending to Claude"""
    conversation = ""
    
    # Add context messages
    for msg in context:
        # Parse the timestamp, handling timezone if present
        ts_str = msg[0]
        if '+' in ts_str:
            ts_str = ts_str.split('+')[0]
        timestamp = datetime.fromisoformat(ts_str)
        
        sender = msg[1]
        content = msg[2]
        conversation += f"[{timestamp:%Y-%m-%d %H:%M:%S}] {sender}: {content}\n\n"
    
    # Add the tagged message (without the tag)
    ts_str = tagged_message[0]
    if '+' in ts_str:
        ts_str = ts_str.split('+')[0]
    timestamp = datetime.fromisoformat(ts_str)
    
    sender = tagged_message[1]
    
    # Remove #claude tag and any context count parameters
    content = tagged_message[3]
    content = re.sub(r'#claude\s+(?:n=|context=|c=)?(?:\d+)?', '', content, flags=re.IGNORECASE)
    content = content.strip()
    
    conversation += f"[{timestamp:%Y-%m-%d %H:%M:%S}] {sender}: {content}\n\n"
    
    return conversation

def get_claude_response(conversation, system_prompt=None):
    """
    Get a response from Claude using the official API
    
    Args:
        conversation: str, the formatted conversation
        system_prompt: str, optional system prompt
        
    Returns:
        str: Claude's response
    """
    if CLAUDE_API_KEY == "YOUR_CLAUDE_API_KEY_HERE":
        logger.warning("Claude API key not configured. Using simulated response.")
        return "This is a simulated response from Claude. To get real responses, please configure your Claude API key in the script."
    
    try:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01"
        }
        
        # Prepare the request payload
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": conversation}
            ]
        }
        
        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt
            
        logger.info(f"Sending request to Claude API with model: {CLAUDE_MODEL}")
        
        # Send the request to Claude API
        response = requests.post(
            CLAUDE_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            response_data = response.json()
            # Extract the response text from the API response
            if "content" in response_data and len(response_data["content"]) > 0:
                return response_data["content"][0]["text"]
            else:
                logger.error(f"Invalid response format from Claude API: {response_data}")
                return "Error: Invalid response format from Claude API."
        else:
            logger.error(f"Error from Claude API: {response.status_code} - {response.text}")
            return f"Error from Claude API: HTTP {response.status_code}"
            
    except requests.RequestException as e:
        logger.error(f"Request error with Claude API: {e}")
        return f"Error connecting to Claude API: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting Claude response: {e}")
        return f"Error: Could not get a response from Claude. {str(e)}"

def send_whatsapp_response(chat_jid, response):
    """
    Send Claude's response back to the WhatsApp chat
    
    Args:
        chat_jid: str, the chat JID to respond to
        response: str, Claude's response
    """
    try:
        # WhatsApp API endpoint
        url = WHATSAPP_API_URL
        payload = {
            "recipient": chat_jid,
            "message": response
        }
        
        logger.info(f"Sending to WhatsApp: Response to {chat_jid}")
        logger.info(f"Response content: {response[:100]}...")
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Message sent: {result.get('message', 'Unknown response')}")
            return True
        else:
            logger.error(f"Error sending message: HTTP {response.status_code} - {response.text}")
            return False
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        return False

def format_claude_prompt(conversation, chat_info):
    """Format a prompt for Claude with instructions"""
    chat_name = chat_info[2] if chat_info[2] else "Unknown Chat"
    
    # This will be used as the user message content
    prompt = f"""I'm forwarding you a conversation from a WhatsApp chat. Please respond to the request in the last message.

CONVERSATION:
{conversation}

Please provide a helpful, accurate, and concise response. Be conversational and friendly.
"""
    return prompt

def format_claude_system_prompt(chat_info):
    """Format a system prompt for Claude"""
    chat_name = chat_info[2] if chat_info[2] else "Unknown Chat"
    
    # This will be used as the system prompt
    system_prompt = f"""You are Claude, an AI assistant responding to requests from a WhatsApp chat named "{chat_name}".
Be helpful, respectful, and accurate in your responses. Keep your responses concise and to the point,
as this is a chat conversation.

The user is expecting a direct response to the last message in the conversation they've shared.
"""
    return system_prompt

async def init_mcp_client():
    """Initialize WhatsApp MCP client for new features"""
    if not MCP_AVAILABLE:
        return None

    try:
        logger.info("Initializing WhatsApp MCP client...")
        from mcp import stdio_client

        # Use stdio_client context manager for proper initialization
        server_params = StdioServerParameters(
            command="npx",
            args=["--yes", "@raaedkabir/whatsapp-mcp-server"],
            env=os.environ.copy()
        )

        # Create client using stdio_client as a context manager
        stdio_ctx = stdio_client(server_params)
        read_stream, write_stream = await stdio_ctx.__aenter__()
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        logger.info("✓ WhatsApp MCP client initialized")
        return session
    except Exception as e:
        logger.error(f"Failed to initialize MCP client: {e}")
        return None


def get_recent_group_messages(since_time: datetime) -> List[Dict[str, Any]]:
    """
    Get recent messages from monitored groups

    Args:
        since_time: Get messages after this time

    Returns:
        List of message dictionaries
    """
    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        since_str = since_time.strftime("%Y-%m-%d %H:%M:%S")

        # Get recent messages from groups only
        query = """
        SELECT
            m.id,
            m.timestamp,
            m.sender,
            m.content,
            m.chat_jid,
            c.name
        FROM messages m
        JOIN chats c ON m.chat_jid = c.jid
        WHERE
            m.chat_jid LIKE '%@g.us'
            AND datetime(substr(m.timestamp, 1, 19)) > datetime(?)
        ORDER BY m.timestamp ASC
        """

        cursor.execute(query, (since_str,))
        results = cursor.fetchall()

        messages = []
        for row in results:
            messages.append({
                'id': row[0],
                'timestamp': row[1],
                'sender_name': row[2] or 'Unknown',
                'content': row[3],
                'message': row[3],  # Compatibility
                'chat_jid': row[4],
                'group_name': row[5] or 'Unknown Group'
            })

        return messages

    except Exception as e:
        logger.error(f"Error getting recent group messages: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def format_ai_detection_confirmation(detection: Dict[str, Any], task_num: int) -> str:
    """
    Format AI detection for user confirmation

    Args:
        detection: Detection result dict
        task_num: Unique task number for this suggestion

    Returns:
        Formatted confirmation message
    """
    subject = detection.get('subject', 'Untitled Task')
    message_content = detection.get('original_message', {}).get('content', '')
    sender_name = detection.get('sender_name', 'Unknown')
    group_name = detection.get('group_name', 'Unknown Group')
    confidence = detection.get('confidence', 0)
    task_type = detection.get('type', 'unknown')
    priority = detection.get('priority', 'Medium')
    due_date = detection.get('due_date', None)
    assignee_mentions = detection.get('assignee_mentions', [])

    # Build confirmation message
    lines = []
    lines.append(f"🤖 *Task #{task_num}*")
    lines.append("")
    lines.append(f"📋 *Subject:* {subject}")
    lines.append(f"📝 *Original:* \"{message_content[:150]}{'...' if len(message_content) > 150 else ''}\"")
    lines.append("")
    lines.append(f"👤 *Sender:* {sender_name}")
    lines.append(f"📱 *Group:* {group_name}")

    if assignee_mentions:
        lines.append(f"👥 *Mentions:* {', '.join(assignee_mentions)}")

    if due_date:
        lines.append(f"📅 *Due Date:* {due_date}")

    lines.append(f"⚡ *Priority:* {priority}")
    lines.append(f"🏷️ *Type:* {task_type}")
    lines.append(f"🎯 *AI Confidence:* {confidence}%")
    lines.append("")
    lines.append("─" * 30)
    lines.append(f"Reply *'{task_num}'* to create | *'no {task_num}'* to skip")

    return "\n".join(lines)


def check_keywords(keyword_monitor, last_check):
    """Check for keywords in recent messages"""
    if keyword_monitor and keyword_monitor.enabled:
        try:
            alerts = keyword_monitor.check_recent_messages(last_check)
            if alerts > 0:
                logger.info(f"Sent {alerts} keyword alerts")
        except Exception as e:
            logger.error(f"Error in keyword monitoring: {e}")


def check_ai_task_responses(ai_detector):
    """Check for responses to AI-detected task suggestions"""
    global pending_ai_tasks, last_ai_response_time

    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        # Load pending suggestions from database (handles session restarts)
        # Only load tasks from the last 24 hours to avoid duplicates
        one_day_ago = datetime.now() - timedelta(days=1)

        if ai_detector.learning_engine:
            db_suggestions = ai_detector.learning_engine.get_pending_suggestions()
            for sugg in db_suggestions:
                msg_id = sugg['message_id']

                # Parse created_at and skip if older than 1 day
                try:
                    created_at = datetime.strptime(sugg['created_at'], "%Y-%m-%d %H:%M:%S") if sugg.get('created_at') else datetime.now()
                    if created_at < one_day_ago:
                        # Mark as expired in database
                        ai_detector.learning_engine.update_suggestion_status(msg_id, 'expired')
                        continue
                except:
                    created_at = datetime.now()

                if msg_id not in pending_ai_tasks:
                    # Reload from database
                    pending_ai_tasks[msg_id] = {
                        'timestamp': created_at,
                        'detection': sugg['detection'],
                        'stage': 'initial',
                        'recipient': os.environ.get("KEYWORD_ALERT_RECIPIENT", "").strip("'\""),
                        'task_num': sugg['task_num']
                    }

        if not pending_ai_tasks:
            return

        # Only look at messages from the last 5 minutes to avoid processing old responses
        # This prevents reprocessing after restarts
        five_mins_ago = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        since_time = five_mins_ago

        # Use last_ai_response_time if set and more recent
        if last_ai_response_time and last_ai_response_time > since_time:
            since_time = last_ai_response_time

        # Get any recipient to check (they should all be the same)
        recipient = list(pending_ai_tasks.values())[0]['recipient']

        # Query for recent messages from the recipient (user's responses)
        # Only get responses NEWER than since_time to avoid duplicates
        query = """
        SELECT m.content, m.timestamp
        FROM messages m
        WHERE
            m.sender LIKE ?
            AND datetime(substr(m.timestamp, 1, 19)) > datetime(?)
        ORDER BY m.timestamp ASC
        LIMIT 10
        """

        # Match on recipient number
        cursor.execute(query, (f"%{recipient.replace('91', '')}%", since_time))
        responses = cursor.fetchall()

        if not responses:
            return

        # Process each response
        to_approve = []
        to_reject = []

        for response_content, response_timestamp in responses:
            # Update last processed time to avoid reprocessing this response
            last_ai_response_time = response_timestamp
            response = response_content.strip().lower()

            # Check for "all" responses
            if response in ['all', 'yes all', 'create all']:
                # Approve all pending tasks
                for msg_id, data in pending_ai_tasks.items():
                    if data.get('stage') == 'initial':
                        to_approve.append((msg_id, data))
                logger.info(f"User approved ALL {len(to_approve)} pending tasks")
                break

            elif response in ['no all', 'skip all', 'reject all', 'none']:
                # Reject all pending tasks
                for msg_id, data in pending_ai_tasks.items():
                    if data.get('stage') == 'initial':
                        to_reject.append((msg_id, data))
                logger.info(f"User rejected ALL {len(to_reject)} pending tasks")
                break

            # Check for specific task number (e.g., "3" or "yes 3" or "create 3")
            num_match = re.match(r'^(?:yes\s+|create\s+|ok\s+)?(\d+)$', response)
            if num_match:
                task_num = int(num_match.group(1))
                # Find the task with this number
                for msg_id, data in pending_ai_tasks.items():
                    if data.get('task_num') == task_num and data.get('stage') == 'initial':
                        if (msg_id, data) not in to_approve:
                            to_approve.append((msg_id, data))
                            logger.info(f"User approved task #{task_num}")
                        break

            # Check for rejection of specific task (e.g., "no 3" or "skip 3")
            reject_match = re.match(r'^(?:no|skip|reject)\s+(\d+)$', response)
            if reject_match:
                task_num = int(reject_match.group(1))
                for msg_id, data in pending_ai_tasks.items():
                    if data.get('task_num') == task_num and data.get('stage') == 'initial':
                        if (msg_id, data) not in to_reject:
                            to_reject.append((msg_id, data))
                            logger.info(f"User rejected task #{task_num}")
                        break

            # Check for multiple numbers (e.g., "1,3,5" or "1 3 5")
            multi_match = re.match(r'^[\d,\s]+$', response)
            if multi_match and len(response) > 1:
                nums = [int(n) for n in re.findall(r'\d+', response)]
                for task_num in nums:
                    for msg_id, data in pending_ai_tasks.items():
                        if data.get('task_num') == task_num and data.get('stage') == 'initial':
                            if (msg_id, data) not in to_approve:
                                to_approve.append((msg_id, data))
                                logger.info(f"User approved task #{task_num}")
                            break

        # Process approved tasks
        for msg_id, data in to_approve:
            task_id = process_ai_task_approval(data, ai_detector)
            # Update database status
            if ai_detector.learning_engine:
                ai_detector.learning_engine.update_suggestion_status(msg_id, 'approved', task_id)
            if msg_id in pending_ai_tasks:
                del pending_ai_tasks[msg_id]

        # Process rejected tasks
        for msg_id, data in to_reject:
            process_ai_task_rejection(data, ai_detector)
            # Update database status
            if ai_detector.learning_engine:
                ai_detector.learning_engine.update_suggestion_status(msg_id, 'rejected')
            if msg_id in pending_ai_tasks:
                del pending_ai_tasks[msg_id]

    except Exception as e:
        logger.error(f"Error checking AI task responses: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


def check_reaction_tasks(ai_detector):
    """
    Check for 👍 reactions to create tasks directly.
    Only processes reactions from the authorized user (KEYWORD_ALERT_RECIPIENT).
    """
    global last_reaction_check_time, processed_reactions

    try:
        conn = sqlite3.connect(MESSAGES_DB_PATH)
        cursor = conn.cursor()

        # Get authorized user phone number
        authorized_user = os.environ.get("KEYWORD_ALERT_RECIPIENT", "").strip("'\"")
        if not authorized_user:
            return

        # Only check reactions from the last 5 minutes
        five_mins_ago = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        since_time = five_mins_ago

        if last_reaction_check_time and last_reaction_check_time > since_time:
            since_time = last_reaction_check_time

        # Query for recent thumbs up reactions from ME (is_from_me = 1)
        # Only in direct chats (not groups which end with @g.us)
        query = """
        SELECT r.id, r.chat_jid, r.sender, r.emoji, r.timestamp, r.reacted_message_id
        FROM reactions r
        WHERE r.emoji = '👍'
            AND r.is_from_me = 1
            AND r.chat_jid NOT LIKE '%@g.us'
            AND datetime(substr(r.timestamp, 1, 19)) > datetime(?)
        ORDER BY r.timestamp ASC
        LIMIT 20
        """

        cursor.execute(query, (since_time,))
        reactions = cursor.fetchall()

        if not reactions:
            return

        for reaction_id, chat_jid, sender, emoji, timestamp, reacted_msg_id in reactions:
            # Skip already processed reactions
            if reaction_id in processed_reactions:
                continue

            # Update last check time
            last_reaction_check_time = timestamp

            # Get the original message content
            msg_query = """
            SELECT m.content, m.sender, m.timestamp
            FROM messages m
            WHERE m.id = ?
            LIMIT 1
            """
            cursor.execute(msg_query, (reacted_msg_id,))
            msg_result = cursor.fetchone()

            if not msg_result:
                logger.warning(f"Could not find message {reacted_msg_id} for reaction")
                processed_reactions.add(reaction_id)
                continue

            message_content, msg_sender, msg_timestamp = msg_result

            if not message_content or not message_content.strip():
                logger.debug(f"Empty message content for {reacted_msg_id}")
                processed_reactions.add(reaction_id)
                continue

            # Check if this is a task prompt message (bot's confirmation message)
            # If so, extract the original content from it
            if "🤖 *Task #" in message_content and "📝 *Original:*" in message_content:
                # Extract original message from the prompt
                import re
                original_match = re.search(r'📝 \*Original:\* ["\']?(.+?)["\']?\n', message_content, re.DOTALL)
                if original_match:
                    message_content = original_match.group(1).strip().rstrip('"\'')
                    logger.info(f"Extracted original content from task prompt: {message_content[:50]}...")
                else:
                    # Try to extract subject
                    subject_match = re.search(r'📋 \*Subject:\* (.+?)\n', message_content)
                    if subject_match:
                        message_content = subject_match.group(1).strip()
                        logger.info(f"Using subject from task prompt: {message_content[:50]}...")

            # Mark as processed
            processed_reactions.add(reaction_id)

            # Get next task number (monthly reset)
            task_num = 1
            if ai_detector and ai_detector.learning_engine:
                task_num = ai_detector.learning_engine.get_next_task_num()

            logger.info(f"Creating task #{task_num} from 👍 reaction to: {message_content[:50]}...")

            # Build detection dict in same format as AI-detected tasks
            detection = {
                'message_id': reacted_msg_id,
                'subject': message_content[:130].strip(),
                'type': 'reaction-task',
                'confidence': 100,
                'priority': 'Medium',
                'due_date': '',
                'assignee_mentions': [],
                'reasoning': 'Created via 👍 reaction',
                'sender_name': msg_sender,
                'sender_id': msg_sender,
                'group_name': 'Direct Chat',
                'group_jid': chat_jid,
                'timestamp': msg_timestamp,
                'original_message': {
                    'content': message_content
                },
                'is_action_item': True
            }

            # Build data dict for process_ai_task_approval
            data = {
                'detection': detection,
                'recipient': authorized_user,
                'task_num': task_num
            }

            # Use same task creation flow as numbered task approval
            process_ai_task_approval(data, ai_detector)

    except Exception as e:
        logger.error(f"Error checking reaction tasks: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


def process_ai_task_approval(data: Dict, ai_detector):
    """
    Process approved AI task creation

    Args:
        data: Pending task data
        ai_detector: AI detector instance
    """
    try:
        detection = data['detection']
        recipient = data['recipient']

        # Record positive feedback
        if ai_detector and ai_detector.learning_engine:
            ai_detector.record_feedback(detection, user_approved=True)

        # Extract task details from AI analysis
        subject = detection.get('subject', 'Task from AI detection')
        description = detection.get('description', '')
        original_message = detection.get('original_message', {})
        message_content = original_message.get('content', '')
        sender_name = detection.get('sender_name', 'Unknown')
        group_name = detection.get('group_name', 'Unknown')
        timestamp = detection.get('timestamp', '')

        # Build full description with context
        full_description = f"""{subject}

Original message: "{message_content}"

Group: {group_name}
Sender: {sender_name}
Time: {timestamp}

AI Analysis:
- Type: {detection.get('type', 'unknown')}
- Priority: {detection.get('priority', 'Medium')}
- Confidence: {detection.get('confidence', 0)}%
"""

        # Prepare task details
        task_details = {
            'subject': subject[:200],  # Limit subject length
            'description': full_description,
            'priority': detection.get('priority', 'Medium'),
            'has_details': True
        }

        # Add due date if detected
        due_date = detection.get('due_date')
        if due_date:
            task_details['due_date'] = due_date

        # Check for assignee mentions
        assignee_mentions = detection.get('assignee_mentions', [])
        if assignee_mentions:
            # Try to resolve first mentioned person
            first_mention = assignee_mentions[0]
            send_whatsapp_response(
                recipient,
                f"Looking up assignee '{first_mention}' in ERPNext..."
            )

            # Try to search ERPNext for this person
            erpnext_client = get_erpnext_client()
            if erpnext_client:
                try:
                    # Check learning database first
                    if ai_detector and ai_detector.learning_engine:
                        cached_email = ai_detector.learning_engine.get_assignee_mapping(first_mention)
                        if cached_email:
                            logger.info(f"Found cached assignee mapping: {first_mention} -> {cached_email}")
                            task_details['assigned_to'] = cached_email
                        else:
                            # Search ERPNext
                            users = erpnext_client.search_users(first_mention, ['name', 'email', 'full_name'])
                            if users and len(users) == 1:
                                # Single match - use it
                                task_details['assigned_to'] = users[0].get('email')
                                # Save mapping for future
                                if ai_detector and ai_detector.learning_engine:
                                    ai_detector.learning_engine.save_assignee_mapping(
                                        first_mention,
                                        users[0].get('email')
                                    )
                                logger.info(f"Auto-assigned to {users[0].get('full_name')} ({users[0].get('email')})")
                                send_whatsapp_response(
                                    recipient,
                                    f"✓ Assigned to {users[0].get('full_name')}"
                                )
                            elif users and len(users) > 1:
                                # Multiple matches - notify user
                                user_list = "\n".join([f"  • {u.get('full_name')} ({u.get('email')})" for u in users[:5]])
                                send_whatsapp_response(
                                    recipient,
                                    f"⚠️ Multiple users found for '{first_mention}':\n{user_list}\n\nPlease reply with the correct email to assign, or I'll create without assignment."
                                )
                            else:
                                # No users found - ask user for help
                                send_whatsapp_response(
                                    recipient,
                                    f"❌ User '{first_mention}' not found in ERPNext.\n\nPlease reply with their email address to assign the task, or I'll create it unassigned."
                                )
                except Exception as e:
                    logger.error(f"Error searching for assignee: {e}")

        # Create task in ERPNext
        logger.info(f"Creating AI-detected task: {subject}")
        result = create_erpnext_task(task_details)

        if result.get('success'):
            # Success message
            task_id = result.get('task_id', 'Unknown')
            task_url = result.get('task_url', '')
            assignee = task_details.get('assigned_to', 'Unassigned')

            success_msg = f"""✅ AI Task created successfully!

📋 Task ID: {task_id}
📝 Subject: {subject}
👤 Assigned To: {assignee}
⚡ Priority: {detection.get('priority', 'Medium')}
📅 Due: {due_date or 'Not set'}

View task: {task_url}

🤖 AI Confidence: {detection.get('confidence')}%
"""
            send_whatsapp_response(recipient, success_msg)

            return task_id

        else:
            # Error message
            error = result.get('error', 'Unknown error')
            send_whatsapp_response(
                recipient,
                f"❌ Failed to create task: {error}"
            )
            return None

    except Exception as e:
        logger.error(f"Error processing AI task approval: {e}")
        return None


def process_ai_task_rejection(data: Dict, ai_detector):
    """
    Process rejected AI task creation

    Args:
        data: Pending task data
        ai_detector: AI detector instance
    """
    try:
        detection = data['detection']
        recipient = data['recipient']

        # Record negative feedback
        if ai_detector and ai_detector.learning_engine:
            ai_detector.record_feedback(detection, user_approved=False)

        # Send confirmation
        send_whatsapp_response(
            recipient,
            "✓ Task suggestion ignored. AI will learn from this feedback."
        )

        logger.info(f"AI task rejected - recorded as learning example")

    except Exception as e:
        logger.error(f"Error processing AI task rejection: {e}")


def check_mcp_server_running():
    """Check if the WhatsApp MCP server is running"""
    import socket

    # Check if port 8080 is open (WhatsApp Bridge API)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 8080))
        sock.close()

        if result == 0:
            logger.info("✓ WhatsApp Bridge API is accessible on port 8080")
            return True
    except Exception as e:
        logger.debug(f"Could not connect to port 8080: {e}")

    # Alternative: Check for the whatsapp-client process
    try:
        result = subprocess.run(
            ["pgrep", "-f", "whatsapp-client"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            logger.info("✓ WhatsApp client process is running")
            return True
    except Exception as e:
        logger.debug(f"Could not check for whatsapp-client process: {e}")

    return False


def start_mcp_server():
    """Start the WhatsApp MCP server if it's not running"""
    logger.info("Starting WhatsApp Bridge server...")

    try:
        # Use the whatsapp-bridge directory
        bridge_dir = os.path.join(os.path.dirname(BASE_DIR), 'whatsapp-mcp', 'whatsapp-bridge')
        client_binary = os.path.join(bridge_dir, 'whatsapp-client')

        if os.path.exists(client_binary):
            logger.info(f"Starting WhatsApp Bridge from: {bridge_dir}")
            # Start the Go binary in the background
            process = subprocess.Popen(
                [client_binary],
                cwd=bridge_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            logger.info(f"Started WhatsApp Bridge process (PID: {process.pid})")
        else:
            logger.error(f"WhatsApp client binary not found at: {client_binary}")
            logger.info("Please build the WhatsApp Bridge:")
            logger.info(f"  cd {bridge_dir}")
            logger.info("  go build -o whatsapp-client")
            return False

        # Wait a few seconds for the server to start
        logger.info("Waiting for WhatsApp Bridge to initialize...")
        time.sleep(5)

        # Verify it started
        if check_mcp_server_running():
            logger.info("✓ WhatsApp Bridge started successfully")
            return True
        else:
            logger.warning("⚠ WhatsApp Bridge may not have started properly")
            return False

    except Exception as e:
        logger.error(f"Failed to start WhatsApp Bridge: {e}")
        return False


def ensure_mcp_server():
    """Ensure the WhatsApp Bridge server is running, start it if needed"""
    logger.info("Checking WhatsApp Bridge server status...")

    if check_mcp_server_running():
        logger.info("✓ WhatsApp Bridge is already running")
        return True

    logger.warning("WhatsApp Bridge is not running")

    # Try to start it
    if start_mcp_server():
        return True
    else:
        logger.error("=" * 60)
        logger.error("❌ Failed to start WhatsApp Bridge!")
        logger.error("=" * 60)
        logger.error("")
        logger.error("Please start the WhatsApp Bridge manually:")
        logger.error("  cd ../whatsapp-mcp/whatsapp-bridge")
        logger.error("  ./whatsapp-client")
        logger.error("")
        logger.error("Or build it first if needed:")
        logger.error("  cd ../whatsapp-mcp/whatsapp-bridge")
        logger.error("  go build -o whatsapp-client")
        logger.error("")
        logger.error("=" * 60)
        return False


def ensure_single_instance():
    """Ensure only one instance of the monitor is running"""
    import fcntl

    # Create lock file path
    lock_file_path = os.path.join(BASE_DIR, ".monitor.lock")

    try:
        # Open lock file
        lock_file = open(lock_file_path, 'w')

        # Try to acquire exclusive lock (non-blocking)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Write current PID to lock file
        lock_file.write(str(os.getpid()))
        lock_file.flush()

        logger.info(f"✓ Single instance lock acquired (PID: {os.getpid()})")
        return lock_file  # Keep file open to maintain lock

    except IOError:
        logger.error("=" * 60)
        logger.error("❌ Another instance of the monitor is already running!")
        logger.error("=" * 60)
        logger.error("")
        logger.error("To stop the existing instance:")
        logger.error("  ./run_monitor.sh stop")
        logger.error("")
        logger.error("Or manually kill it:")
        logger.error("  ps aux | grep whatsapp_monitoring")
        logger.error("  kill <PID>")
        logger.error("")
        logger.error("=" * 60)
        sys.exit(1)


def main():
    logger.info("Starting WhatsApp monitor for Claude and Task requests")
    logger.info("=" * 60)

    # Ensure only one instance is running
    lock_file = ensure_single_instance()

    # Check the database
    if not check_database():
        logger.error("Database check failed. Exiting.")
        return

    # Ensure WhatsApp MCP server is running
    if not ensure_mcp_server():
        logger.warning("WhatsApp MCP server is not running. Some features may not work.")
        logger.warning("Continuing anyway, but you may need to start it manually.")

    logger.info("=" * 60)

    # Initialize keyword monitoring (no MCP required)
    keyword_monitor = None
    if KEYWORD_MONITORING_AVAILABLE:
        try:
            logger.info("Initializing keyword monitoring...")
            keyword_monitor = create_keyword_monitor()
            if keyword_monitor and keyword_monitor.enabled:
                logger.info("✓ Keyword monitoring feature enabled")
                logger.info(f"  Monitoring keywords: {', '.join(keyword_monitor.keywords)}")
                logger.info(f"  Alert cooldown: {keyword_monitor.cooldown}s")
            else:
                logger.info("Keyword monitoring feature disabled")
        except Exception as e:
            logger.error(f"Error initializing keyword monitoring: {e}")
    else:
        logger.info("Keyword monitoring not available")

    # Initialize AI Task Detection
    ai_detector = None
    if AI_TASK_DETECTION_AVAILABLE:
        try:
            logger.info("Initializing AI task detection...")
            ai_detector = create_ai_task_detector()
            if ai_detector and ai_detector.enabled:
                logger.info("✓ AI Task Detection enabled")
                logger.info(f"  Model: {ai_detector.claude_model}")
                logger.info(f"  Confidence threshold: {ai_detector.confidence_threshold}%")
                logger.info(f"  Daily budget: {ai_detector.daily_budget} API calls")
                if ai_detector.batch_analysis:
                    logger.info(f"  Batch analysis: enabled (size={ai_detector.batch_size})")
                else:
                    logger.info(f"  Batch analysis: disabled")
                if ai_detector.learning_enabled:
                    logger.info(f"  Learning: enabled")
            else:
                logger.info("AI Task Detection disabled")
        except Exception as e:
            logger.error(f"Error initializing AI task detection: {e}")
            logger.info("Continuing without AI task detection...")
    else:
        logger.info("AI Task Detection not available")

    # Initialize daily summary (requires MCP)
    daily_summary = None
    mcp_client = None

    if DAILY_SUMMARY_AVAILABLE and MCP_AVAILABLE:
        logger.info("Initializing daily summary feature...")

        try:
            # Initialize MCP client
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            mcp_client = loop.run_until_complete(init_mcp_client())

            if mcp_client:
                # Create daily summary generator
                daily_summary = create_daily_summary(mcp_client)
                if daily_summary and daily_summary.enabled:
                    daily_summary.start_scheduler()
                    logger.info("✓ Daily summary feature enabled")
                else:
                    logger.info("Daily summary feature disabled")
            else:
                logger.warning("MCP client not available, daily summary disabled")

        except Exception as e:
            logger.error(f"Error initializing daily summary: {e}")
            logger.info("Continuing without daily summary...")
    else:
        logger.info("Daily summary feature not available")

    logger.info("=" * 60)
    
    # Start with checking messages from the last 5 minutes
    # Use a slightly older timestamp to ensure we don't miss any messages
    last_check_time = datetime.now() - timedelta(minutes=5)
    keyword_check_time = last_check_time
    last_purge_date = None  # Track when we last purged old suggestions

    try:
        while True:
            try:
                # Capture the current time at the START of this cycle
                # This prevents race conditions where messages arrive during processing
                cycle_start_time = datetime.now()

                # Daily purge of old pending suggestions (once per day at startup or after midnight)
                today = cycle_start_time.date()
                if ai_detector and ai_detector.enabled and ai_detector.learning_engine:
                    if last_purge_date != today:
                        purged = ai_detector.learning_engine.purge_old_pending_suggestions(hours=24)
                        if purged > 0:
                            logger.info(f"Daily cleanup: purged {purged} expired task suggestions")
                        last_purge_date = today

                # First, check for any confirmation responses
                check_for_confirmation_responses()

                # Check for task responses
                check_for_task_responses()

                # Check for AI task responses
                if ai_detector and ai_detector.enabled:
                    try:
                        check_ai_task_responses(ai_detector)
                    except Exception as e:
                        logger.error(f"Error checking AI task responses: {e}")

                # Check for 👍 reaction-based task creation
                try:
                    check_reaction_tasks(ai_detector)
                except Exception as e:
                    logger.error(f"Error checking reaction tasks: {e}")

                # Check for keywords (new feature)
                if keyword_monitor and keyword_monitor.enabled:
                    try:
                        check_keywords(keyword_monitor, keyword_check_time)
                        keyword_check_time = cycle_start_time
                    except Exception as e:
                        logger.error(f"Error in keyword monitoring: {e}")

                # AI Task Detection - analyze group messages
                if ai_detector and ai_detector.enabled:
                    try:
                        # Get recent group messages for AI analysis
                        recent_messages = get_recent_group_messages(last_check_time)

                        # Filter out already processed messages
                        messages_to_analyze = [
                            msg for msg in recent_messages
                            if msg.get('id', '') not in pending_ai_tasks
                        ]

                        if messages_to_analyze:
                            # Use batch analysis if enabled and multiple messages
                            if ai_detector.batch_analysis and len(messages_to_analyze) > 1:
                                logger.info(f"Batch analyzing {len(messages_to_analyze)} messages (batch_size={ai_detector.batch_size})")

                                # Process in batches
                                for i in range(0, len(messages_to_analyze), ai_detector.batch_size):
                                    batch = messages_to_analyze[i:i + ai_detector.batch_size]
                                    results = ai_detector.analyze_messages_batch(batch)

                                    # Process each result
                                    for message, detection in zip(batch, results):
                                        if detection and detection.get('is_action_item') and detection.get('confidence', 0) >= ai_detector.confidence_threshold:
                                            # Get next task number from database
                                            task_num = ai_detector.learning_engine.get_next_task_num() if ai_detector.learning_engine else 1

                                            logger.info(f"AI detected task #{task_num}: confidence={detection['confidence']}%, subject={detection.get('subject', 'N/A')}")

                                            # Format and send confirmation
                                            confirmation_msg = format_ai_detection_confirmation(detection, task_num)
                                            recipient = os.environ.get("KEYWORD_ALERT_RECIPIENT", "").strip("'\"")
                                            send_whatsapp_response(recipient, confirmation_msg)

                                            # Save to database
                                            if ai_detector.learning_engine:
                                                ai_detector.learning_engine.save_pending_suggestion(task_num, detection)

                                            # Store in-memory cache
                                            pending_ai_tasks[detection['message_id']] = {
                                                'timestamp': datetime.now(),
                                                'detection': detection,
                                                'stage': 'initial',
                                                'recipient': recipient,
                                                'task_num': task_num
                                            }
                            else:
                                # Individual analysis (single message or batch disabled)
                                for message in messages_to_analyze:
                                    detection = ai_detector.analyze_message(message)

                                    if detection and detection.get('is_action_item') and detection.get('confidence', 0) >= ai_detector.confidence_threshold:
                                        # Get next task number from database (persists across sessions)
                                        task_num = ai_detector.learning_engine.get_next_task_num() if ai_detector.learning_engine else 1

                                        # AI detected a potential task
                                        logger.info(f"AI detected task #{task_num}: confidence={detection['confidence']}%, subject={detection.get('subject', 'N/A')}")

                                        # Format confirmation message with task number
                                        confirmation_msg = format_ai_detection_confirmation(detection, task_num)

                                        # Send to configured recipient
                                        recipient = os.environ.get("KEYWORD_ALERT_RECIPIENT", "").strip("'\"")
                                        send_whatsapp_response(recipient, confirmation_msg)

                                        # Save to database for persistence across sessions
                                        if ai_detector.learning_engine:
                                            ai_detector.learning_engine.save_pending_suggestion(task_num, detection)

                                        # Store in-memory cache for quick lookups
                                        pending_ai_tasks[detection['message_id']] = {
                                            'timestamp': datetime.now(),
                                            'detection': detection,
                                            'stage': 'initial',
                                            'recipient': recipient,
                                            'task_num': task_num
                                        }

                    except Exception as e:
                        logger.error(f"Error in AI task detection: {e}")

                # Get recent messages with the #claude tag
                claude_messages = get_recent_tagged_messages(last_check_time, CLAUDE_TAG)

                if claude_messages:
                    # Process each Claude message
                    for message in claude_messages:
                        logger.info(f"Processing Claude request: {message[3][:50]}...")

                        # Extract context count from message
                        context_count = extract_context_count(message[3])
                        logger.info(f"Suggested context count: {context_count}")

                        # Send confirmation request to the user asking for message count
                        confirmation_msg = (
                            f"I found your request for Claude with the #{CLAUDE_TAG} tag.\n\n"
                            f"How many previous messages should I include for context?\n\n"
                            f"Reply with a number between 1-20, or 'cancel' to abort."
                        )
                        send_whatsapp_response(message[4], confirmation_msg)

                        # Add to pending confirmations with current timestamp
                        pending_confirmations[message[5]] = {
                            'timestamp': datetime.now(),
                            'context_count': context_count,
                            'chat_jid': message[4],
                            'tagged_message': message
                        }

                # Get recent messages with the #task tag
                task_messages = get_recent_tagged_messages(last_check_time, TASK_TAG)

                if task_messages:
                    # Process each Task message
                    for message in task_messages:
                        logger.info(f"Processing Task request: {message[3][:50]}...")

                        # Check if the message already contains task details
                        content = message[3]
                        task_details = extract_task_details(content)

                        if task_details.get('has_details', False):
                            # Task details provided in the message - create task immediately
                            logger.info("Task details found in the message, creating task automatically")

                            # Create the task in ERP
                            result = create_erpnext_task(task_details)

                            if result['success']:
                                # Send success message with task link
                                success_msg = TASK_SUCCESS_TEMPLATE.format(
                                    emoji=TASK_SUCCESS_EMOJI,
                                    task_id=result.get('task_id', 'Unknown'),
                                    subject=task_details.get('subject', 'No subject'),
                                    priority=task_details.get('priority', 'Medium'),
                                    due_date=task_details.get('due_date', 'Not set'),
                                    assigned_to=task_details.get('assigned_to', 'Unassigned'),
                                    task_url=result.get('task_url', '')
                                )
                                send_whatsapp_response(message[4], success_msg)
                            else:
                                # Send error message
                                error_msg = TASK_ERROR_TEMPLATE.format(
                                    emoji=TASK_ERROR_EMOJI,
                                    error=result.get('error', 'Unknown error')
                                )
                                send_whatsapp_response(message[4], error_msg)
                        else:
                            # No proper template found - try to extract from plain text
                            # Remove the #task tag and use the rest as subject
                            clean_content = re.sub(r'#task\s*', '', content, flags=re.IGNORECASE).strip()

                            if clean_content:
                                # Use the message content as task subject
                                simple_task = {
                                    'subject': clean_content[:200],  # Limit subject length
                                    'description': clean_content,
                                    'priority': 'Medium',
                                    'has_details': True
                                }

                                logger.info(f"Creating simple task from plain text: {clean_content[:50]}...")

                                # Create the task
                                result = create_erpnext_task(simple_task)

                                if result['success']:
                                    success_msg = TASK_SIMPLE_SUCCESS_TEMPLATE.format(
                                        emoji=TASK_SUCCESS_EMOJI,
                                        task_id=result.get('task_id', 'Unknown'),
                                        subject=simple_task['subject'],
                                        task_url=result.get('task_url', '')
                                    )
                                    send_whatsapp_response(message[4], success_msg)
                                else:
                                    error_msg = TASK_ERROR_TEMPLATE.format(
                                        emoji=TASK_ERROR_EMOJI,
                                        error=result.get('error', 'Unknown error')
                                    )
                                    send_whatsapp_response(message[4], error_msg)
                            else:
                                # Empty message - send help
                                logger.info("Empty #task message received, sending help template")
                                send_whatsapp_response(message[4], TASK_HELP_TEMPLATE)

                # Update last check time to the START of this cycle
                # This ensures we don't miss messages that arrived during processing
                last_check_time = cycle_start_time
                logger.debug(f"Updated last_check_time to {last_check_time}")

                # Sleep before next check
                time.sleep(POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(POLL_INTERVAL)  # Sleep and try again
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    finally:
        # Cleanup new features
        if daily_summary and daily_summary.scheduler:
            logger.info("Stopping daily summary scheduler...")
            daily_summary.stop_scheduler()

        if mcp_client:
            logger.info("Closing MCP client...")
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(mcp_client.__aexit__(None, None, None))
            except Exception as e:
                logger.error(f"Error closing MCP client: {e}")

        # Release lock file
        if 'lock_file' in locals() and lock_file:
            try:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                logger.info("✓ Lock released")
            except Exception as e:
                logger.debug(f"Error releasing lock: {e}")

        logger.info("Shutdown complete")

if __name__ == "__main__":
    main()