#!/usr/bin/env python3
"""
Claude-Flow Swarm Coordinator for WhatsApp Monitoring MCP Server

This module orchestrates distributed task creation workflows using claude-flow's
mesh topology for peer-to-peer coordination between specialized agents.

Architecture:
- Mesh topology for fault-tolerant, distributed coordination
- Specialized agents for task creation, user resolution, WhatsApp communication, and state management
- Memory-based state sharing across agents
- Hooks integration for session persistence and performance tracking

Agents:
1. Task Creation Agent - Processes task requests, validates inputs
2. User Resolution Agent - Handles user matching and disambiguation
3. WhatsApp Communication Agent - Manages WhatsApp message sending
4. State Manager Agent - Maintains state across async operations
"""

import os
import sys
import json
import logging
import subprocess
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
from enum import Enum

logger = logging.getLogger("swarm_coordinator")


class AgentType(Enum):
    """Available agent types in the swarm"""
    TASK_CREATOR = "task-creation-agent"
    USER_RESOLVER = "user-resolution-agent"
    WHATSAPP_COMM = "whatsapp-communication-agent"
    STATE_MANAGER = "state-manager-agent"


class TaskState(Enum):
    """Task creation workflow states"""
    PENDING = "pending"
    USER_RESOLUTION = "user_resolution"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CREATING = "creating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SwarmCoordinator:
    """
    Coordinates multi-agent task creation workflows using claude-flow

    Features:
    - Mesh topology for distributed coordination
    - Memory-based state management
    - Hooks integration for persistence
    - Fault tolerance and error recovery
    - Progress tracking
    """

    def __init__(self,
                 erpnext_client=None,
                 whatsapp_sender: Optional[Callable] = None,
                 admin_number: Optional[str] = None,
                 session_id: Optional[str] = None):
        """
        Initialize swarm coordinator

        Args:
            erpnext_client: ERPNextClient instance
            whatsapp_sender: Function to send WhatsApp messages (chat_jid, message)
            admin_number: Admin WhatsApp number for disambiguation
            session_id: Optional session ID for restoring state
        """
        self.erp_client = erpnext_client
        self.send_whatsapp = whatsapp_sender
        self.admin_number = admin_number

        # Generate session ID
        self.session_id = session_id or f"swarm-whatsapp-{int(time.time())}"

        # Swarm configuration
        self.swarm_initialized = False
        self.swarm_topology = "mesh"  # Peer-to-peer coordination
        self.max_agents = 4  # One per agent type

        # Base directory for swarm data
        self.base_dir = Path.cwd()
        self.swarm_dir = self.base_dir / ".swarm"
        self.swarm_dir.mkdir(exist_ok=True)

        # Task state tracking
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.pending_resolutions: Dict[str, Dict[str, Any]] = {}

        # Agent health tracking
        self.agent_health: Dict[AgentType, Dict[str, Any]] = {}

        # Performance metrics
        self.metrics = {
            'tasks_created': 0,
            'tasks_failed': 0,
            'user_resolutions': 0,
            'messages_sent': 0,
            'errors': []
        }

        logger.info(f"SwarmCoordinator initialized with session: {self.session_id}")

    def initialize_swarm(self) -> bool:
        """
        Initialize claude-flow swarm with mesh topology

        Returns:
            bool: True if successful
        """
        try:
            logger.info("Initializing claude-flow swarm with mesh topology")

            # Execute pre-task hook
            self._execute_hook("pre-task", {
                "description": f"Initialize swarm coordinator - {self.session_id}",
                "session_id": self.session_id
            })

            # Try to restore previous session
            self._execute_hook("session-restore", {
                "session_id": self.session_id
            })

            # Initialize swarm topology via subprocess
            # Note: In production, this would use MCP tools, but we ensure
            # Claude Code's Task tool will spawn actual agents
            result = subprocess.run(
                ["npx", "claude-flow@alpha", "swarm", "init",
                 "--topology", self.swarm_topology,
                 "--max-agents", str(self.max_agents),
                 "--session-id", self.session_id],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Swarm initialized successfully: {result.stdout}")
                self.swarm_initialized = True

                # Store swarm configuration in memory
                self._store_memory("swarm/config", {
                    "session_id": self.session_id,
                    "topology": self.swarm_topology,
                    "max_agents": self.max_agents,
                    "initialized_at": datetime.now().isoformat()
                })

                return True
            else:
                logger.error(f"Failed to initialize swarm: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Swarm initialization timed out")
            return False
        except Exception as e:
            logger.error(f"Error initializing swarm: {e}")
            return False

    def spawn_agent(self, agent_type: AgentType, context: Optional[Dict] = None) -> bool:
        """
        Spawn a specialized agent in the swarm

        Args:
            agent_type: Type of agent to spawn
            context: Optional context data for the agent

        Returns:
            bool: True if successful
        """
        try:
            logger.info(f"Spawning agent: {agent_type.value}")

            agent_config = {
                "type": agent_type.value,
                "session_id": self.session_id,
                "context": context or {},
                "spawned_at": datetime.now().isoformat()
            }

            # Execute agent spawn via subprocess
            result = subprocess.run(
                ["npx", "claude-flow@alpha", "agent", "spawn",
                 "--type", agent_type.value,
                 "--session-id", self.session_id,
                 "--context", json.dumps(context or {})],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Agent {agent_type.value} spawned successfully")

                # Store agent configuration in memory
                self._store_memory(f"swarm/agents/{agent_type.value}", agent_config)

                # Initialize agent health tracking
                self.agent_health[agent_type] = {
                    "status": "active",
                    "last_heartbeat": datetime.now(),
                    "tasks_processed": 0,
                    "errors": 0
                }

                return True
            else:
                logger.error(f"Failed to spawn agent {agent_type.value}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error spawning agent {agent_type.value}: {e}")
            return False

    def create_task_distributed(self,
                                task_details: Dict[str, Any],
                                chat_jid: str,
                                message_id: str) -> Dict[str, Any]:
        """
        Create a task using distributed swarm coordination

        This orchestrates multiple agents to handle:
        1. Task validation (Task Creation Agent)
        2. User resolution if needed (User Resolution Agent)
        3. Task creation in ERPNext (Task Creation Agent)
        4. WhatsApp notification (WhatsApp Communication Agent)
        5. State management (State Manager Agent)

        Args:
            task_details: Task information
            chat_jid: WhatsApp chat JID
            message_id: WhatsApp message ID

        Returns:
            Dictionary with operation result
        """
        task_id = f"task-{message_id}-{int(time.time())}"

        logger.info(f"Starting distributed task creation: {task_id}")

        # Initialize task state
        task_state = {
            "task_id": task_id,
            "message_id": message_id,
            "chat_jid": chat_jid,
            "details": task_details,
            "state": TaskState.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "updates": []
        }

        self.active_tasks[task_id] = task_state

        # Store initial state in memory
        self._store_memory(f"swarm/tasks/{task_id}", task_state)

        # Execute task orchestration via hooks
        self._execute_hook("pre-task", {
            "description": f"Create task via swarm - {task_details.get('subject', 'Untitled')}",
            "task_id": task_id,
            "session_id": self.session_id
        })

        try:
            # Step 1: Validate task details (Task Creation Agent)
            logger.info(f"[{task_id}] Step 1: Validating task details")
            validation_result = self._validate_task_details(task_id, task_details)

            if not validation_result["valid"]:
                self._update_task_state(task_id, TaskState.FAILED,
                                       f"Validation failed: {validation_result['error']}")
                return {"success": False, "error": validation_result["error"]}

            # Step 2: Resolve user if assignee specified (User Resolution Agent)
            assignee = task_details.get('assigned_to')
            resolved_user = None

            if assignee:
                logger.info(f"[{task_id}] Step 2: Resolving user '{assignee}'")
                self._update_task_state(task_id, TaskState.USER_RESOLUTION)

                resolution_result = self._resolve_user_distributed(task_id, assignee)

                if resolution_result.get("needs_disambiguation"):
                    # Store pending resolution
                    resolution_id = resolution_result["resolution_id"]
                    self.pending_resolutions[resolution_id] = {
                        "task_id": task_id,
                        "chat_jid": chat_jid,
                        "timestamp": datetime.now()
                    }

                    self._update_task_state(task_id, TaskState.AWAITING_CONFIRMATION,
                                           f"Awaiting user disambiguation: {resolution_id}")

                    return {
                        "success": False,
                        "pending": True,
                        "resolution_id": resolution_id,
                        "message": "User disambiguation required"
                    }

                elif resolution_result.get("resolved"):
                    resolved_user = resolution_result["user"]
                    task_details["assigned_to"] = resolved_user.get("email") or resolved_user.get("name")
                    logger.info(f"[{task_id}] User resolved: {resolved_user.get('full_name')}")
                else:
                    # User resolution failed, but continue without assignee
                    logger.warning(f"[{task_id}] User resolution failed: {resolution_result.get('error')}")
                    task_details.pop("assigned_to", None)

            # Step 3: Create task in ERPNext (Task Creation Agent)
            logger.info(f"[{task_id}] Step 3: Creating task in ERPNext")
            self._update_task_state(task_id, TaskState.CREATING)

            create_result = self._create_task_in_erp(task_id, task_details)

            if not create_result["success"]:
                self._update_task_state(task_id, TaskState.FAILED,
                                       f"ERPNext creation failed: {create_result['error']}")
                self.metrics['tasks_failed'] += 1
                return create_result

            # Step 4: Send WhatsApp notification (WhatsApp Communication Agent)
            logger.info(f"[{task_id}] Step 4: Sending WhatsApp notification")

            success_message = self._format_success_message(
                create_result["task_id"],
                task_details,
                create_result["task_url"]
            )

            self._send_whatsapp_distributed(task_id, chat_jid, success_message)

            # Step 5: Finalize and store state (State Manager Agent)
            logger.info(f"[{task_id}] Step 5: Finalizing task state")
            self._update_task_state(task_id, TaskState.COMPLETED,
                                   f"Task created: {create_result['task_id']}")

            # Execute post-task hook
            self._execute_hook("post-task", {
                "task_id": task_id,
                "session_id": self.session_id,
                "result": "success"
            })

            self.metrics['tasks_created'] += 1

            return {
                "success": True,
                "task_id": create_result["task_id"],
                "task_url": create_result["task_url"],
                "swarm_task_id": task_id
            }

        except Exception as e:
            logger.error(f"[{task_id}] Error in distributed task creation: {e}")
            self._update_task_state(task_id, TaskState.FAILED, str(e))
            self.metrics['tasks_failed'] += 1
            self.metrics['errors'].append({
                "task_id": task_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

            return {"success": False, "error": str(e)}

    def check_pending_resolutions(self) -> List[Dict[str, Any]]:
        """
        Check for responses to pending user disambiguation requests

        Returns:
            List of resolved tasks
        """
        resolved = []

        for resolution_id, data in list(self.pending_resolutions.items()):
            task_id = data["task_id"]

            # Check if resolution has timed out (5 minutes)
            elapsed = (datetime.now() - data["timestamp"]).total_seconds()
            if elapsed > 300:
                logger.warning(f"Resolution {resolution_id} timed out")
                self._update_task_state(task_id, TaskState.CANCELLED, "User resolution timed out")
                del self.pending_resolutions[resolution_id]
                continue

            # In production, this would check for WhatsApp responses
            # For now, we just track the pending state
            logger.debug(f"Resolution {resolution_id} still pending ({elapsed:.0f}s)")

        return resolved

    def _validate_task_details(self, task_id: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate task details (Task Creation Agent)

        Args:
            task_id: Task ID
            details: Task details to validate

        Returns:
            Validation result
        """
        logger.debug(f"[{task_id}] Validating task details")

        # Store operation in memory
        self._store_memory(f"swarm/tasks/{task_id}/validation", {
            "timestamp": datetime.now().isoformat(),
            "details": details
        })

        # Check required fields
        if not details.get("subject"):
            return {"valid": False, "error": "Task subject is required"}

        # Validate priority
        priority = details.get("priority", "Medium")
        if priority not in ["Low", "Medium", "High"]:
            return {"valid": False, "error": f"Invalid priority: {priority}"}

        # Validate due date format if provided
        if "due_date" in details:
            try:
                # Simple validation - should be YYYY-MM-DD format
                due_date = details["due_date"]
                if not isinstance(due_date, str) or len(due_date) != 10:
                    return {"valid": False, "error": "Invalid due date format (expected YYYY-MM-DD)"}
            except Exception as e:
                return {"valid": False, "error": f"Invalid due date: {e}"}

        return {"valid": True}

    def _resolve_user_distributed(self, task_id: str, user_query: str) -> Dict[str, Any]:
        """
        Resolve user via User Resolution Agent

        Args:
            task_id: Task ID
            user_query: User search query

        Returns:
            Resolution result
        """
        logger.debug(f"[{task_id}] Resolving user: {user_query}")

        # Store operation in memory
        self._store_memory(f"swarm/tasks/{task_id}/user_resolution", {
            "timestamp": datetime.now().isoformat(),
            "query": user_query
        })

        if not self.erp_client:
            return {"resolved": False, "error": "ERPNext client not configured"}

        # Search for users
        search_result = self.erp_client.search_users(user_query)

        if not search_result["success"]:
            return {"resolved": False, "error": search_result["error"]}

        users = search_result["users"]

        if not users:
            return {"resolved": False, "error": f"No users found matching '{user_query}'"}

        # Single match
        if len(users) == 1:
            self.metrics['user_resolutions'] += 1
            return {"resolved": True, "user": users[0]}

        # Multiple matches - need disambiguation
        logger.info(f"[{task_id}] Multiple users found, creating disambiguation request")

        resolution_id = f"user-resolve-{task_id}-{int(time.time())}"

        # Send disambiguation message via WhatsApp Communication Agent
        message = f"🔍 Found multiple users matching '{user_query}':\n\n"
        for idx, user in enumerate(users[:5], 1):
            name = user.get('full_name', 'Unknown')
            email = user.get('email', 'no-email')
            message += f"{idx}. {name} ({email})\n"

        message += f"\nReply with the number (1-{min(len(users), 5)}) to select, or 'cancel' to abort."

        if self.admin_number and self.send_whatsapp:
            self._send_whatsapp_distributed(task_id, self.admin_number, message)

        # Store disambiguation data in memory
        self._store_memory(f"swarm/resolutions/{resolution_id}", {
            "task_id": task_id,
            "candidates": users[:5],
            "query": user_query,
            "timestamp": datetime.now().isoformat()
        })

        self.metrics['user_resolutions'] += 1

        return {
            "resolved": False,
            "needs_disambiguation": True,
            "resolution_id": resolution_id,
            "candidates": users[:5]
        }

    def _create_task_in_erp(self, task_id: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create task in ERPNext (Task Creation Agent)

        Args:
            task_id: Task ID
            details: Task details

        Returns:
            Creation result
        """
        logger.debug(f"[{task_id}] Creating task in ERPNext")

        # Store operation in memory
        self._store_memory(f"swarm/tasks/{task_id}/erp_creation", {
            "timestamp": datetime.now().isoformat(),
            "details": details
        })

        if not self.erp_client:
            return {"success": False, "error": "ERPNext client not configured"}

        try:
            result = self.erp_client.create_task(details)

            # Store result in memory
            self._store_memory(f"swarm/tasks/{task_id}/erp_result", {
                "timestamp": datetime.now().isoformat(),
                "result": result
            })

            return result

        except Exception as e:
            logger.error(f"[{task_id}] Error creating task in ERP: {e}")
            return {"success": False, "error": str(e)}

    def _send_whatsapp_distributed(self, task_id: str, chat_jid: str, message: str) -> bool:
        """
        Send WhatsApp message via WhatsApp Communication Agent

        Args:
            task_id: Task ID
            chat_jid: WhatsApp chat JID
            message: Message to send

        Returns:
            bool: True if successful
        """
        logger.debug(f"[{task_id}] Sending WhatsApp message to {chat_jid}")

        # Store operation in memory
        self._store_memory(f"swarm/tasks/{task_id}/whatsapp_comm", {
            "timestamp": datetime.now().isoformat(),
            "chat_jid": chat_jid,
            "message_preview": message[:100]
        })

        if not self.send_whatsapp:
            logger.warning(f"[{task_id}] WhatsApp sender not configured")
            return False

        try:
            result = self.send_whatsapp(chat_jid, message)
            self.metrics['messages_sent'] += 1
            return result
        except Exception as e:
            logger.error(f"[{task_id}] Error sending WhatsApp message: {e}")
            return False

    def _update_task_state(self, task_id: str, state: TaskState, note: Optional[str] = None):
        """
        Update task state (State Manager Agent)

        Args:
            task_id: Task ID
            state: New state
            note: Optional note
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found in active tasks")
            return

        task = self.active_tasks[task_id]
        old_state = task["state"]
        task["state"] = state.value
        task["updated_at"] = datetime.now().isoformat()

        update_entry = {
            "timestamp": datetime.now().isoformat(),
            "from_state": old_state,
            "to_state": state.value,
            "note": note
        }

        task["updates"].append(update_entry)

        logger.info(f"[{task_id}] State: {old_state} -> {state.value}" +
                   (f" ({note})" if note else ""))

        # Store updated state in memory
        self._store_memory(f"swarm/tasks/{task_id}", task)
        self._store_memory(f"swarm/tasks/{task_id}/updates/{len(task['updates'])}", update_entry)

    def _format_success_message(self, task_id: str, details: Dict[str, Any], task_url: str) -> str:
        """Format success message for WhatsApp"""
        subject = details.get("subject", "Untitled")
        priority = details.get("priority", "Medium")
        due_date = details.get("due_date", "Not set")
        assigned_to = details.get("assigned_to", "Unassigned")

        return (
            f"✅ Task created successfully!\n\n"
            f"Task ID: {task_id}\n"
            f"Subject: {subject}\n"
            f"Priority: {priority}\n"
            f"Due Date: {due_date}\n"
            f"Assigned To: {assigned_to}\n\n"
            f"View task: {task_url}"
        )

    def _store_memory(self, key: str, value: Any):
        """
        Store data in swarm memory via hooks

        Args:
            key: Memory key
            value: Value to store
        """
        try:
            self._execute_hook("memory-store", {
                "key": key,
                "value": json.dumps(value) if not isinstance(value, str) else value,
                "session_id": self.session_id
            })
        except Exception as e:
            logger.warning(f"Failed to store memory key '{key}': {e}")

    def _retrieve_memory(self, key: str) -> Optional[Any]:
        """
        Retrieve data from swarm memory via hooks

        Args:
            key: Memory key

        Returns:
            Stored value or None
        """
        try:
            result = self._execute_hook("memory-retrieve", {
                "key": key,
                "session_id": self.session_id
            })

            if result and result.returncode == 0:
                data = result.stdout.strip()
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return data

            return None
        except Exception as e:
            logger.warning(f"Failed to retrieve memory key '{key}': {e}")
            return None

    def _execute_hook(self, hook_name: str, params: Dict[str, Any]) -> Optional[subprocess.CompletedProcess]:
        """
        Execute a claude-flow hook

        Args:
            hook_name: Hook name (e.g., 'pre-task', 'post-task')
            params: Hook parameters

        Returns:
            Subprocess result or None
        """
        try:
            args = ["npx", "claude-flow@alpha", "hooks", hook_name]

            # Add parameters as command-line arguments
            for key, value in params.items():
                param_key = f"--{key.replace('_', '-')}"
                param_value = str(value) if not isinstance(value, dict) else json.dumps(value)
                args.extend([param_key, param_value])

            logger.debug(f"Executing hook: {hook_name} with params: {params}")

            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.debug(f"Hook {hook_name} executed successfully")
            else:
                logger.warning(f"Hook {hook_name} returned non-zero: {result.stderr}")

            return result

        except subprocess.TimeoutExpired:
            logger.warning(f"Hook {hook_name} timed out")
            return None
        except Exception as e:
            logger.warning(f"Error executing hook {hook_name}: {e}")
            return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get swarm coordination metrics"""
        return {
            **self.metrics,
            "active_tasks": len(self.active_tasks),
            "pending_resolutions": len(self.pending_resolutions),
            "agent_health": {
                agent_type.value: health
                for agent_type, health in self.agent_health.items()
            }
        }

    def shutdown(self):
        """Shutdown swarm coordinator and persist state"""
        logger.info("Shutting down swarm coordinator")

        # Execute session-end hook
        self._execute_hook("session-end", {
            "session_id": self.session_id,
            "export_metrics": "true"
        })

        # Store final metrics
        self._store_memory(f"swarm/metrics/final", {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.get_metrics()
        })

        logger.info(f"Swarm coordinator shutdown complete. Session: {self.session_id}")


def create_coordinator_from_env(erpnext_client=None,
                                whatsapp_sender=None,
                                session_id: Optional[str] = None) -> SwarmCoordinator:
    """
    Create a SwarmCoordinator from environment variables

    Args:
        erpnext_client: Optional ERPNextClient instance
        whatsapp_sender: Optional WhatsApp sender function
        session_id: Optional session ID

    Returns:
        SwarmCoordinator instance
    """
    admin_number = os.environ.get("ADMIN_WHATSAPP_NUMBER")

    coordinator = SwarmCoordinator(
        erpnext_client=erpnext_client,
        whatsapp_sender=whatsapp_sender,
        admin_number=admin_number,
        session_id=session_id
    )

    return coordinator


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create coordinator
    coordinator = create_coordinator_from_env()

    # Initialize swarm
    if coordinator.initialize_swarm():
        print("✅ Swarm initialized successfully")

        # Spawn agents
        for agent_type in AgentType:
            if coordinator.spawn_agent(agent_type):
                print(f"✅ Agent spawned: {agent_type.value}")

        # Show metrics
        print("\n📊 Swarm Metrics:")
        print(json.dumps(coordinator.get_metrics(), indent=2))

        # Shutdown
        coordinator.shutdown()
    else:
        print("❌ Failed to initialize swarm")
