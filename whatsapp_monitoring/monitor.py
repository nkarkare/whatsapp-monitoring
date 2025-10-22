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
import subprocess
import sys
from pathlib import Path

# Import configuration
from whatsapp_monitoring.config import load_config

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

# Claude API Configuration - Set these in environment variables for security
CLAUDE_API_KEY = get_env_or_default("CLAUDE_API_KEY", "")
CLAUDE_API_URL = get_env_or_default("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
CLAUDE_MODEL = get_env_or_default("CLAUDE_MODEL", "claude-3-opus-20240229")

# ERPNext API Configuration - Set these in environment variables for security
ERPNEXT_API_KEY = get_env_or_default("ERPNEXT_API_KEY", "")
ERPNEXT_API_SECRET = get_env_or_default("ERPNEXT_API_SECRET", "")
ERPNEXT_URL = get_env_or_default("ERPNEXT_URL", "")

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
    Create a task in ERPNext using the API
    
    Args:
        task_details: dict containing task data
        
    Returns:
        dict with success flag and task ID or error message
    """
    try:
        # Prepare API endpoint
        api_url = f"{ERPNEXT_URL}/api/resource/Task"
        
        # Prepare headers
        headers = {
            'Authorization': f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Prepare task data
        task_data = {
            "doctype": "Task",
            "subject": task_details.get('subject', 'Task from WhatsApp'),
            "description": task_details.get('description', ''),
            "priority": task_details.get('priority', 'Medium'),
            "status": "Open"
        }
        
        # Add due date if provided
        if 'due_date' in task_details:
            task_data["exp_end_date"] = task_details['due_date']
        
        # Make the API request to create the task
        response = requests.post(
            api_url,
            headers=headers,
            json={"data": task_data},
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            task_id = response_data.get('data', {}).get('name', 'Unknown')
            logger.info(f"Successfully created task in ERPNext with ID: {task_id}")
            
            # Now assign the task if assignee is provided
            if 'assigned_to' in task_details and task_details['assigned_to']:
                assign_url = f"{ERPNEXT_URL}/api/method/frappe.desk.form.assign_to.add"
                
                # Prepare assignment data
                assign_data = {
                    "doctype": "Task",
                    "name": task_id,
                    "assign_to": task_details['assigned_to'],
                    "description": task_details.get('description', "Task from WhatsApp"),
                    "notify": 1
                }
                
                # Try two different methods to assign the task
                logger.info(f"Assigning task {task_id} to {task_details['assigned_to']} with URL: {assign_url}")
                logger.info(f"Assignment data: {json.dumps(assign_data)}")
                
                # First method: using the assign_to.add API endpoint
                try:
                    # Try a different format for the request - some versions of ERPNext require arrays
                    alt_assign_data = {
                        "assign_to": [task_details['assigned_to']],
                        "doctype": "Task",
                        "name": task_id,
                        "description": task_details.get('description', "Task from WhatsApp"),
                        "notify": 1
                    }
                    
                    assign_response = requests.post(
                        assign_url,
                        headers=headers,
                        json=alt_assign_data,  # Try this format first
                        timeout=30
                    )
                    
                    logger.info(f"Assignment response status: {assign_response.status_code}")
                    logger.info(f"Assignment response content: {assign_response.text[:500]}")
                    
                    if assign_response.status_code in [200, 201, 202]:
                        logger.info(f"Successfully assigned task {task_id} to {task_details['assigned_to']}")
                    else:
                        logger.error(f"Failed to assign task with method 1: {assign_response.status_code} - {assign_response.text}")
                        
                        # Second method: update the _assign field directly
                        try:
                            update_url = f"{ERPNEXT_URL}/api/resource/Task/{task_id}"
                            
                            # Prepare update data
                            update_data = {
                                "_assign": json.dumps([task_details['assigned_to']])
                            }
                            
                            # Make the update request
                            logger.info(f"Trying alternative assignment method with URL: {update_url}")
                            logger.info(f"Alternative assignment data: {json.dumps(update_data)}")
                            
                            update_response = requests.put(
                                update_url,
                                headers=headers,
                                json={"data": update_data},
                                timeout=30
                            )
                            
                            logger.info(f"Alternative assignment response status: {update_response.status_code}")
                            logger.info(f"Alternative assignment response content: {update_response.text[:500]}")
                            
                            if update_response.status_code in [200, 201, 202]:
                                logger.info(f"Successfully assigned task {task_id} to {task_details['assigned_to']} with alternative method")
                            else:
                                logger.error(f"Failed to assign task with method 2: {update_response.status_code} - {update_response.text}")
                        except Exception as e:
                            logger.error(f"Exception during alternative task assignment: {str(e)}")
                        
                except Exception as e:
                    logger.error(f"Exception during task assignment: {str(e)}")
            
            # Generate task URL
            task_url = f"{ERPNEXT_URL}/app/task/{task_id}"
            
            return {"success": True, "task_id": task_id, "task_url": task_url}
        else:
            logger.error(f"Failed to create task in ERPNext: {response.status_code} - {response.text}")
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
            
    except requests.RequestException as e:
        logger.error(f"Request error with ERPNext API: {e}")
        return {"success": False, "error": f"Connection error: {str(e)}"}
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

def main():
    logger.info("Starting WhatsApp monitor for Claude and Task requests")
    
    # Check the database
    if not check_database():
        logger.error("Database check failed. Exiting.")
        return
    
    # Start with checking messages from the last 5 minutes
    # Use a slightly older timestamp to ensure we don't miss any messages
    last_check_time = datetime.now() - timedelta(minutes=5)
    
    try:
        while True:
            try:
                # Capture the current time at the START of this cycle
                # This prevents race conditions where messages arrive during processing
                cycle_start_time = datetime.now()

                # First, check for any confirmation responses
                check_for_confirmation_responses()

                # Check for task responses
                check_for_task_responses()

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

if __name__ == "__main__":
    main()