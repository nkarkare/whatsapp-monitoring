#!/usr/bin/env python3
"""
ERPNext API Client Module

This module provides a reusable client for interacting with ERPNext API
for task management and user operations.
"""

import os
import logging
import requests
import json
from typing import Dict, List, Optional, Any

logger = logging.getLogger("erpnext_client")


class ERPNextClient:
    """Client for interacting with ERPNext API"""

    def __init__(self, url: str, api_key: str, api_secret: str):
        """
        Initialize ERPNext client

        Args:
            url: ERPNext instance URL (e.g., https://erp.company.com)
            api_key: API key for authentication
            api_secret: API secret for authentication
        """
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f"token {api_key}:{api_secret}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def create_task(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a task in ERPNext

        Args:
            task_details: Dictionary containing task data with keys:
                - subject: str (required) - Task title
                - description: str (optional) - Task description
                - priority: str (optional) - Low/Medium/High
                - due_date: str (optional) - YYYY-MM-DD format
                - assigned_to: str (optional) - User email or username

        Returns:
            Dictionary with:
                - success: bool
                - task_id: str (if successful)
                - task_url: str (if successful)
                - error: str (if failed)
        """
        try:
            api_url = f"{self.url}/api/resource/Task"

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

            # Create the task
            logger.info(f"Creating task: {task_data['subject']}")
            response = self.session.post(
                api_url,
                json={"data": task_data},
                timeout=30
            )

            if response.status_code in [200, 201]:
                response_data = response.json()
                task_id = response_data.get('data', {}).get('name', 'Unknown')
                logger.info(f"Successfully created task: {task_id}")

                # Assign the task if assignee is provided
                if 'assigned_to' in task_details and task_details['assigned_to']:
                    assign_result = self._assign_task(task_id, task_details['assigned_to'],
                                                     task_details.get('description', ''))
                    if not assign_result['success']:
                        logger.warning(f"Task created but assignment failed: {assign_result['error']}")

                # Generate task URL
                task_url = f"{self.url}/app/task/{task_id}"

                return {
                    "success": True,
                    "task_id": task_id,
                    "task_url": task_url
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Failed to create task: {error_msg}")
                return {"success": False, "error": error_msg}

        except requests.RequestException as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(f"Request error: {error_msg}")
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Unexpected error creating task: {error_msg}")
            return {"success": False, "error": error_msg}

    def _assign_task(self, task_id: str, assigned_to: str, description: str = "") -> Dict[str, Any]:
        """
        Assign a task to a user

        Args:
            task_id: Task ID to assign
            assigned_to: User email or username
            description: Task description for notification

        Returns:
            Dictionary with success status and error if failed
        """
        try:
            assign_url = f"{self.url}/api/method/frappe.desk.form.assign_to.add"

            # Try assigning with array format (newer ERPNext versions)
            assign_data = {
                "assign_to": [assigned_to],
                "doctype": "Task",
                "name": task_id,
                "description": description or "Task assigned via API",
                "notify": 1
            }

            logger.info(f"Assigning task {task_id} to {assigned_to}")
            response = self.session.post(
                assign_url,
                json=assign_data,
                timeout=30
            )

            if response.status_code in [200, 201, 202]:
                logger.info(f"Successfully assigned task {task_id} to {assigned_to}")
                return {"success": True}
            else:
                # Try alternative method: update _assign field directly
                logger.warning(f"Primary assignment method failed, trying alternative")
                return self._assign_task_alternative(task_id, assigned_to)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error assigning task: {error_msg}")
            return {"success": False, "error": error_msg}

    def _assign_task_alternative(self, task_id: str, assigned_to: str) -> Dict[str, Any]:
        """Alternative method to assign task by updating _assign field"""
        try:
            update_url = f"{self.url}/api/resource/Task/{task_id}"
            update_data = {"_assign": json.dumps([assigned_to])}

            response = self.session.put(
                update_url,
                json={"data": update_data},
                timeout=30
            )

            if response.status_code in [200, 201, 202]:
                logger.info(f"Successfully assigned task {task_id} via alternative method")
                return {"success": True}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Alternative assignment failed: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Alternative assignment error: {error_msg}")
            return {"success": False, "error": error_msg}

    def list_users(self, fields: Optional[List[str]] = None, limit: int = 1000) -> Dict[str, Any]:
        """
        List users from ERPNext

        Args:
            fields: List of fields to retrieve (default: name, email, full_name)
            limit: Maximum number of users to retrieve

        Returns:
            Dictionary with:
                - success: bool
                - users: List[Dict] (if successful)
                - error: str (if failed)
        """
        try:
            if fields is None:
                fields = ["name", "email", "full_name", "enabled"]

            api_url = f"{self.url}/api/resource/User"
            params = {
                "fields": json.dumps(fields),
                "limit_page_length": limit,
                "filters": json.dumps([["enabled", "=", 1]])  # Only active users
            }

            logger.debug(f"Fetching users from ERPNext")
            response = self.session.get(api_url, params=params, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                users = response_data.get('data', [])
                logger.info(f"Retrieved {len(users)} users from ERPNext")
                return {"success": True, "users": users}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Failed to list users: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error listing users: {error_msg}")
            return {"success": False, "error": error_msg}

    def search_users(self, query: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Search for users by name or email

        Args:
            query: Search query string
            fields: List of fields to retrieve

        Returns:
            Dictionary with:
                - success: bool
                - users: List[Dict] (if successful)
                - error: str (if failed)
        """
        try:
            if fields is None:
                fields = ["name", "email", "full_name", "enabled"]

            api_url = f"{self.url}/api/resource/User"

            # Search in full_name or email
            filters = [
                ["enabled", "=", 1],
                ["full_name", "like", f"%{query}%"]
            ]

            params = {
                "fields": json.dumps(fields),
                "filters": json.dumps(filters),
                "limit_page_length": 20
            }

            logger.debug(f"Searching users with query: {query}")
            response = self.session.get(api_url, params=params, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                users = response_data.get('data', [])

                # Also search by email if no results from name
                if not users:
                    filters[1] = ["email", "like", f"%{query}%"]
                    params["filters"] = json.dumps(filters)
                    response = self.session.get(api_url, params=params, timeout=30)
                    if response.status_code == 200:
                        users = response.json().get('data', [])

                logger.info(f"Found {len(users)} users matching '{query}'")
                return {"success": True, "users": users}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Failed to search users: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error searching users: {error_msg}")
            return {"success": False, "error": error_msg}

    def get_user(self, identifier: str) -> Dict[str, Any]:
        """
        Get a specific user by email or username

        Args:
            identifier: User email or username

        Returns:
            Dictionary with:
                - success: bool
                - user: Dict (if successful)
                - error: str (if failed)
        """
        try:
            api_url = f"{self.url}/api/resource/User/{identifier}"

            logger.debug(f"Fetching user: {identifier}")
            response = self.session.get(api_url, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                user = response_data.get('data', {})
                logger.info(f"Retrieved user: {user.get('full_name', identifier)}")
                return {"success": True, "user": user}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Failed to get user: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error getting user: {error_msg}")
            return {"success": False, "error": error_msg}


def create_client_from_env() -> ERPNextClient:
    """
    Create an ERPNext client from environment variables

    Returns:
        ERPNextClient instance

    Raises:
        ValueError: If required environment variables are not set
    """
    url = os.environ.get('ERPNEXT_URL')
    api_key = os.environ.get('ERPNEXT_API_KEY')
    api_secret = os.environ.get('ERPNEXT_API_SECRET')

    if not all([url, api_key, api_secret]):
        raise ValueError(
            "Missing required ERPNext configuration. "
            "Please set ERPNEXT_URL, ERPNEXT_API_KEY, and ERPNEXT_API_SECRET"
        )

    return ERPNextClient(url, api_key, api_secret)
