#!/usr/bin/env python3
"""
User Resolution Module

This module handles user matching, disambiguation, and interactive resolution
via WhatsApp when multiple matches are found.
"""

import os
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from difflib import SequenceMatcher
from datetime import datetime, timedelta

logger = logging.getLogger("user_resolver")


class UserResolver:
    """Handles user resolution with fuzzy matching and WhatsApp disambiguation"""

    def __init__(self, erpnext_client, whatsapp_sender, admin_number: str,
                 default_assignee: Optional[str] = None):
        """
        Initialize UserResolver

        Args:
            erpnext_client: ERPNextClient instance
            whatsapp_sender: Function to send WhatsApp messages (chat_jid, message)
            admin_number: Admin WhatsApp number for disambiguation
            default_assignee: Default assignee email if no user specified
        """
        self.erp_client = erpnext_client
        self.send_whatsapp = whatsapp_sender
        self.admin_number = admin_number
        self.default_assignee = default_assignee

        # Fuzzy matching threshold (0-100)
        self.match_threshold = int(os.environ.get('FUZZY_MATCH_THRESHOLD', '80'))
        self.max_suggestions = int(os.environ.get('MAX_USER_SUGGESTIONS', '5'))
        self.resolution_timeout = int(os.environ.get('USER_RESOLUTION_TIMEOUT', '300'))

        # Track pending resolutions
        # Format: {resolution_id: {'users': [...], 'timestamp': datetime, 'context': {}}}
        self.pending_resolutions = {}

    def resolve_user(self, user_query: Optional[str], context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Resolve a user from a query string

        Args:
            user_query: User name, email, or None for default
            context: Optional context dict for tracking

        Returns:
            Dictionary with:
                - resolved: bool - True if user was resolved
                - user: Dict - User data if resolved
                - needs_disambiguation: bool - True if multiple matches
                - resolution_id: str - ID for disambiguation if needed
                - error: str - Error message if failed
        """
        # Use default assignee if no query provided
        if not user_query:
            if self.default_assignee:
                logger.info(f"Using default assignee: {self.default_assignee}")
                result = self.erp_client.get_user(self.default_assignee)
                if result['success']:
                    return {
                        "resolved": True,
                        "user": result['user'],
                        "needs_disambiguation": False
                    }
                else:
                    logger.error(f"Default assignee not found: {self.default_assignee}")
                    return {
                        "resolved": False,
                        "error": f"Default assignee not found: {self.default_assignee}"
                    }
            else:
                return {
                    "resolved": False,
                    "error": "No user specified and no default assignee configured"
                }

        # Search for users
        search_result = self.erp_client.search_users(user_query)
        if not search_result['success']:
            return {
                "resolved": False,
                "error": f"Failed to search users: {search_result['error']}"
            }

        users = search_result['users']

        # No matches found
        if not users:
            logger.warning(f"No users found matching: {user_query}")
            return {
                "resolved": False,
                "error": f"No users found matching '{user_query}'"
            }

        # Fuzzy match and rank users
        ranked_users = self._rank_users_by_match(user_query, users)

        # Single clear match
        if len(ranked_users) == 1 or (
            len(ranked_users) > 1 and
            ranked_users[0]['match_score'] - ranked_users[1]['match_score'] > 20
        ):
            best_match = ranked_users[0]
            logger.info(f"Single match found: {best_match['user'].get('full_name')} "
                       f"(score: {best_match['match_score']})")
            return {
                "resolved": True,
                "user": best_match['user'],
                "needs_disambiguation": False,
                "match_score": best_match['match_score']
            }

        # Multiple matches - need disambiguation
        logger.info(f"Multiple matches found for '{user_query}': {len(ranked_users)}")
        resolution_id = self._create_disambiguation_request(
            ranked_users[:self.max_suggestions],
            user_query,
            context
        )

        return {
            "resolved": False,
            "needs_disambiguation": True,
            "resolution_id": resolution_id,
            "candidates": ranked_users[:self.max_suggestions]
        }

    def _rank_users_by_match(self, query: str, users: List[Dict]) -> List[Dict]:
        """
        Rank users by fuzzy match score

        Args:
            query: Search query
            users: List of user dictionaries

        Returns:
            List of dicts with 'user' and 'match_score' keys, sorted by score
        """
        ranked = []
        query_lower = query.lower()

        for user in users:
            full_name = user.get('full_name', '').lower()
            email = user.get('email', '').lower()
            username = user.get('name', '').lower()

            # Calculate match scores
            name_score = self._fuzzy_match(query_lower, full_name) * 100
            email_score = self._fuzzy_match(query_lower, email) * 80
            username_score = self._fuzzy_match(query_lower, username) * 90

            # Take the best score
            best_score = max(name_score, email_score, username_score)

            # Bonus for exact substring match
            if query_lower in full_name or query_lower in email:
                best_score += 10

            if best_score >= self.match_threshold:
                ranked.append({
                    'user': user,
                    'match_score': int(best_score)
                })

        # Sort by score descending
        ranked.sort(key=lambda x: x['match_score'], reverse=True)
        return ranked

    def _fuzzy_match(self, str1: str, str2: str) -> float:
        """Calculate fuzzy match score using SequenceMatcher"""
        return SequenceMatcher(None, str1, str2).ratio()

    def _create_disambiguation_request(self, candidates: List[Dict],
                                      original_query: str,
                                      context: Optional[Dict]) -> str:
        """
        Create a disambiguation request and send to WhatsApp

        Args:
            candidates: List of candidate users with match scores
            original_query: Original search query
            context: Optional context

        Returns:
            Resolution ID for tracking
        """
        resolution_id = f"user_resolve_{int(time.time() * 1000)}"

        # Format message
        message = f"🔍 Found multiple users matching '{original_query}':\n\n"
        for idx, candidate in enumerate(candidates, 1):
            user = candidate['user']
            name = user.get('full_name', 'Unknown')
            email = user.get('email', 'no-email')
            score = candidate['match_score']
            message += f"{idx}. {name} ({email}) - {score}% match\n"

        message += f"\nReply with the number (1-{len(candidates)}) to select a user, or 'cancel' to abort."

        # Send to admin WhatsApp
        logger.info(f"Sending disambiguation request {resolution_id} to {self.admin_number}")
        self.send_whatsapp(self.admin_number, message)

        # Store pending resolution
        self.pending_resolutions[resolution_id] = {
            'candidates': candidates,
            'timestamp': datetime.now(),
            'original_query': original_query,
            'context': context or {}
        }

        return resolution_id

    def check_disambiguation_response(self, resolution_id: str,
                                     response_checker) -> Optional[Dict[str, Any]]:
        """
        Check if user has responded to disambiguation request

        Args:
            resolution_id: Resolution ID to check
            response_checker: Function that returns latest message from admin

        Returns:
            Dictionary with resolved user or None if not yet resolved
        """
        if resolution_id not in self.pending_resolutions:
            logger.warning(f"Resolution ID not found: {resolution_id}")
            return {"error": "Resolution ID not found"}

        resolution_data = self.pending_resolutions[resolution_id]

        # Check timeout
        elapsed = (datetime.now() - resolution_data['timestamp']).total_seconds()
        if elapsed > self.resolution_timeout:
            logger.warning(f"Resolution {resolution_id} timed out after {elapsed}s")
            del self.pending_resolutions[resolution_id]
            return {"error": "Resolution timed out"}

        # Get latest response from admin
        latest_message = response_checker(self.admin_number, resolution_data['timestamp'])

        if not latest_message:
            return None  # No response yet

        message_text = latest_message.strip().lower()

        # Check for cancellation
        if message_text in ['cancel', 'abort', 'stop']:
            logger.info(f"Resolution {resolution_id} cancelled by user")
            del self.pending_resolutions[resolution_id]
            return {"cancelled": True}

        # Check for numeric selection
        if message_text.isdigit():
            selection = int(message_text)
            candidates = resolution_data['candidates']

            if 1 <= selection <= len(candidates):
                selected_user = candidates[selection - 1]['user']
                logger.info(f"User selected option {selection}: "
                           f"{selected_user.get('full_name')}")

                # Cleanup
                del self.pending_resolutions[resolution_id]

                return {
                    "resolved": True,
                    "user": selected_user,
                    "selection": selection
                }
            else:
                # Invalid selection
                self.send_whatsapp(
                    self.admin_number,
                    f"❌ Invalid selection '{selection}'. Please choose 1-{len(candidates)} or 'cancel'."
                )
                return None

        # Unrecognized response
        self.send_whatsapp(
            self.admin_number,
            f"❌ Unrecognized response '{latest_message}'. Please reply with a number (1-{len(resolution_data['candidates'])}) or 'cancel'."
        )
        return None

    def wait_for_disambiguation(self, resolution_id: str,
                                response_checker,
                                poll_interval: int = 2,
                                max_wait: Optional[int] = None) -> Dict[str, Any]:
        """
        Wait for disambiguation response (blocking)

        Args:
            resolution_id: Resolution ID to wait for
            response_checker: Function to check for responses
            poll_interval: Seconds between polls
            max_wait: Maximum seconds to wait (uses resolution_timeout if None)

        Returns:
            Dictionary with resolved user or error
        """
        max_wait = max_wait or self.resolution_timeout
        start_time = time.time()

        logger.info(f"Waiting for disambiguation response for {resolution_id}")

        while time.time() - start_time < max_wait:
            result = self.check_disambiguation_response(resolution_id, response_checker)

            if result is not None:
                if result.get('resolved'):
                    logger.info(f"Disambiguation resolved: {result['user'].get('full_name')}")
                    return result
                elif result.get('cancelled'):
                    return {"error": "Resolution cancelled by user"}
                elif result.get('error'):
                    return result

            time.sleep(poll_interval)

        # Timeout
        logger.warning(f"Disambiguation wait timed out for {resolution_id}")
        if resolution_id in self.pending_resolutions:
            del self.pending_resolutions[resolution_id]

        return {"error": "Disambiguation timed out"}

    def cleanup_expired_resolutions(self):
        """Remove expired disambiguation requests"""
        now = datetime.now()
        expired = []

        for res_id, data in self.pending_resolutions.items():
            elapsed = (now - data['timestamp']).total_seconds()
            if elapsed > self.resolution_timeout:
                expired.append(res_id)

        for res_id in expired:
            logger.info(f"Cleaning up expired resolution: {res_id}")
            del self.pending_resolutions[res_id]

        return len(expired)
