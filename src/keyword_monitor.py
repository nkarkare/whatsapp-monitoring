#!/usr/bin/env python3
"""
Keyword Monitoring Module

Real-time keyword detection in WhatsApp messages with alerting.
"""

import os
import logging
import sqlite3
import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set, Optional

logger = logging.getLogger("whatsapp_monitoring.keyword_monitor")


class KeywordMonitor:
    """Monitors WhatsApp messages for specific keywords and sends alerts"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize keyword monitor

        Args:
            config: Configuration dictionary with:
                - enabled: bool
                - recipient: str (phone number)
                - keywords: List[str] (keywords to monitor)
                - groups: List[str] (group JIDs or 'all')
                - cooldown: int (seconds between alerts for same keyword)
                - db_path: str (path to messages database)
                - api_url: str (WhatsApp API URL)
        """
        self.config = config

        # Validate configuration
        self.enabled = config.get("enabled", False)
        self.recipient = config.get("recipient", "").strip("'\"")
        self.keywords = self._parse_keywords(config.get("keywords", ""))
        self.groups = self._parse_groups(config.get("groups", ""))
        self.cooldown = config.get("cooldown", 300)  # 5 minutes default
        self.db_path = config.get("db_path", "")
        self.api_url = config.get("api_url", "")

        # Track last alert time per keyword to prevent spam
        self.last_alert_time: Dict[str, datetime] = {}

        # Cache for group names
        self.group_name_cache: Dict[str, str] = {}

        if self.enabled:
            logger.info(f"Keyword monitoring enabled")
            logger.info(f"  Keywords: {', '.join(self.keywords)}")
            logger.info(f"  Groups: {'all' if self.monitor_all_groups else f'{len(self.groups)} specific groups'}")
            logger.info(f"  Recipient: {self.recipient}")
            logger.info(f"  Alert cooldown: {self.cooldown}s")

    def _parse_keywords(self, keywords_str: str) -> List[str]:
        """Parse comma-separated quoted keywords"""
        if not keywords_str:
            return []

        # Remove outer quotes and split by comma
        keywords_str = keywords_str.strip("'\"")
        if not keywords_str:
            return []

        # Split and clean each keyword
        keywords = [k.strip().strip("'\"").lower() for k in keywords_str.split(",")]
        return [k for k in keywords if k]

    def _parse_groups(self, groups_str: str) -> List[str]:
        """Parse comma-separated quoted group JIDs or 'all'"""
        if not groups_str:
            return []

        # Check for 'all' keyword
        groups_str_clean = groups_str.strip("'\"").lower()
        if groups_str_clean == "all":
            self.monitor_all_groups = True
            return []

        self.monitor_all_groups = False

        # Split and clean each JID
        groups = [g.strip().strip("'\"") for g in groups_str.split(",")]
        return [g for g in groups if g and g.endswith("@g.us")]

    def should_monitor_group(self, group_jid: str) -> bool:
        """
        Check if a group should be monitored

        Args:
            group_jid: WhatsApp group JID

        Returns:
            True if group should be monitored
        """
        if self.monitor_all_groups:
            return True

        return group_jid in self.groups

    def detect_keywords(self, message_text: str) -> List[str]:
        """
        Detect keywords in message text

        Args:
            message_text: Message content

        Returns:
            List of detected keywords
        """
        if not message_text:
            return []

        message_lower = message_text.lower()
        detected = []

        for keyword in self.keywords:
            # Use word boundary regex for accurate matching
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, message_lower):
                detected.append(keyword)

        return detected

    def can_send_alert(self, keyword: str) -> bool:
        """
        Check if an alert can be sent for a keyword (cooldown check)

        Args:
            keyword: The detected keyword

        Returns:
            True if alert can be sent (cooldown expired or first alert)
        """
        if keyword not in self.last_alert_time:
            return True

        time_since_last = datetime.now() - self.last_alert_time[keyword]
        return time_since_last.total_seconds() >= self.cooldown

    def mark_alert_sent(self, keyword: str):
        """
        Mark that an alert was sent for a keyword

        Args:
            keyword: The keyword that was alerted
        """
        self.last_alert_time[keyword] = datetime.now()

    def get_group_name(self, group_jid: str) -> str:
        """
        Get group name from JID with caching

        Args:
            group_jid: WhatsApp group JID

        Returns:
            Group name or JID if not found
        """
        # Check cache first
        if group_jid in self.group_name_cache:
            return self.group_name_cache[group_jid]

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM chats WHERE jid = ?", (group_jid,))
            result = cursor.fetchone()

            if result:
                name = result[0]
                self.group_name_cache[group_jid] = name
                return name

        except Exception as e:
            logger.error(f"Error getting group name for {group_jid}: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

        # Fallback to JID
        self.group_name_cache[group_jid] = group_jid
        return group_jid

    def format_alert(
        self,
        keyword: str,
        message: Dict[str, Any],
        group_name: str
    ) -> str:
        """
        Format keyword alert message

        Args:
            keyword: Detected keyword
            message: Message dictionary
            group_name: Group name

        Returns:
            Formatted alert message
        """
        lines = []
        lines.append(f"🚨 *Keyword Alert: '{keyword}'*")
        lines.append("")

        # Group info
        lines.append(f"📱 *Group:* {group_name}")

        # Sender info
        sender_name = message.get("sender_name", "Unknown")
        lines.append(f"👤 *Sender:* {sender_name}")

        # Timestamp
        timestamp_str = message.get("timestamp")
        if timestamp_str:
            try:
                if isinstance(timestamp_str, int):
                    msg_time = datetime.fromtimestamp(timestamp_str)
                else:
                    msg_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                time_formatted = msg_time.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"⏰ *Time:* {time_formatted}")
            except Exception:
                pass

        lines.append("")

        # Message content
        message_text = message.get("message", "")
        if message_text:
            # Truncate long messages
            if len(message_text) > 300:
                message_text = message_text[:300] + "..."

            lines.append("💬 *Message:*")
            lines.append(f'"{message_text}"')

        lines.append("")
        lines.append("=" * 40)
        lines.append("✨ _Keyword Monitoring Alert_")

        return "\n".join(lines)

    def send_alert(self, alert_text: str):
        """
        Send alert via WhatsApp

        Args:
            alert_text: Formatted alert message
        """
        try:
            if not self.recipient:
                logger.error("No recipient configured for keyword alerts")
                return

            logger.info(f"Sending keyword alert to {self.recipient}")

            payload = {
                "recipient": self.recipient,
                "message": alert_text
            }

            response = requests.post(self.api_url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info("Keyword alert sent successfully")
            else:
                logger.error(f"Failed to send keyword alert: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending keyword alert: {e}")

    def check_message(self, message: Dict[str, Any]) -> bool:
        """
        Check a message for keywords and send alert if found

        Args:
            message: Message dictionary

        Returns:
            True if alert was sent
        """
        try:
            # Get message details
            chat_jid = message.get("chat_jid", "")
            message_text = message.get("content", "") or message.get("message", "")

            # Check if we should monitor this group
            if not chat_jid.endswith("@g.us"):
                return False  # Only monitor groups

            if not self.should_monitor_group(chat_jid):
                return False

            # Detect keywords
            detected_keywords = self.detect_keywords(message_text)

            if not detected_keywords:
                return False

            # Check cooldown and send alerts
            alert_sent = False
            for keyword in detected_keywords:
                if self.can_send_alert(keyword):
                    # Get group name
                    group_name = self.get_group_name(chat_jid)

                    # Format alert
                    alert_text = self.format_alert(keyword, message, group_name)

                    # Send alert
                    self.send_alert(alert_text)

                    # Mark alert sent
                    self.mark_alert_sent(keyword)

                    alert_sent = True
                    logger.info(f"Alert sent for keyword '{keyword}' in group {group_name}")
                else:
                    cooldown_remaining = self.cooldown - (datetime.now() - self.last_alert_time[keyword]).total_seconds()
                    logger.debug(f"Skipping alert for '{keyword}' (cooldown: {int(cooldown_remaining)}s remaining)")

            return alert_sent

        except Exception as e:
            logger.error(f"Error checking message for keywords: {e}")
            return False

    def check_recent_messages(self, since: datetime) -> int:
        """
        Check recent messages for keywords

        Args:
            since: Check messages after this timestamp

        Returns:
            Number of alerts sent
        """
        try:
            alerts_sent = 0
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # If monitoring all groups, need to get all groups first
            if self.monitor_all_groups:
                cursor.execute("SELECT jid FROM chats WHERE jid LIKE '%@g.us'")
                groups_to_check = [row[0] for row in cursor.fetchall()]
            else:
                groups_to_check = self.groups

            # Convert since to string for SQL
            since_str = since.strftime("%Y-%m-%d %H:%M:%S")

            # Check messages in each group
            for group_jid in groups_to_check:
                messages = self._fetch_messages_since(cursor, group_jid, since_str)

                for message in messages:
                    if self.check_message(message):
                        alerts_sent += 1

            return alerts_sent

        except Exception as e:
            logger.error(f"Error checking recent messages: {e}")
            return 0
        finally:
            if 'conn' in locals():
                conn.close()

    def _fetch_messages_since(self, cursor, group_jid: str, since_str: str) -> List[Dict[str, Any]]:
        """
        Fetch messages from a group since a specific time

        Args:
            cursor: Database cursor
            group_jid: WhatsApp group JID
            since_str: Timestamp string in format YYYY-MM-DD HH:MM:SS

        Returns:
            List of message dictionaries
        """
        try:
            query = """
            SELECT
                m.timestamp,
                m.sender,
                m.content,
                m.chat_jid,
                m.id
            FROM messages m
            WHERE
                m.chat_jid = ?
                AND datetime(substr(m.timestamp, 1, 19)) > datetime(?)
            ORDER BY m.timestamp ASC
            LIMIT 100
            """

            cursor.execute(query, (group_jid, since_str))
            results = cursor.fetchall()

            messages = []
            for row in results:
                messages.append({
                    "timestamp": row[0],
                    "sender_name": row[1] or "Unknown",
                    "content": row[2],
                    "message": row[2],  # Add both for compatibility
                    "chat_jid": row[3],
                    "id": row[4]
                })

            return messages

        except Exception as e:
            logger.debug(f"Error fetching messages for {group_jid}: {e}")
            return []


def create_from_env() -> Optional[KeywordMonitor]:
    """
    Create KeywordMonitor from environment variables

    Returns:
        KeywordMonitor instance or None if disabled
    """
    config = {
        "enabled": os.environ.get("KEYWORD_MONITORING_ENABLED", "false").lower() == "true",
        "recipient": os.environ.get("KEYWORD_ALERT_RECIPIENT", ""),
        "keywords": os.environ.get("MONITORED_KEYWORDS", ""),
        "groups": os.environ.get("MONITORED_GROUPS", ""),
        "cooldown": int(os.environ.get("KEYWORD_ALERT_COOLDOWN", "300")),
        "db_path": os.environ.get("MESSAGES_DB_PATH", ""),
        "api_url": os.environ.get("WHATSAPP_API_URL", "http://localhost:8080/api/send")
    }

    return KeywordMonitor(config)
