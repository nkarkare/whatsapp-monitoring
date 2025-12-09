#!/usr/bin/env python3
"""
Daily Summary Module

Generates and sends daily summaries of WhatsApp group activity.
Scheduled using APScheduler with timezone support.
Uses direct SQLite access for reliability (no async MCP issues).
"""

import os
import logging
import sqlite3
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter
from pathlib import Path

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    import pytz
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    logging.warning("APScheduler or pytz not available. Install with: pip install APScheduler pytz")

logger = logging.getLogger("whatsapp_monitoring.daily_summary")

# Default database path
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = os.path.join(os.path.dirname(BASE_DIR), 'whatsapp-mcp', 'whatsapp-bridge', 'store', 'messages.db')


class DailySummaryGenerator:
    """Generates daily summaries of WhatsApp group activity"""

    def __init__(self, whatsapp_client, config: Dict[str, Any]):
        """
        Initialize daily summary generator

        Args:
            whatsapp_client: WhatsApp MCP client session (not used, kept for compatibility)
            config: Configuration dictionary with:
                - enabled: bool
                - recipient: str (phone number)
                - groups: List[str] (group JIDs)
                - schedule_time: str (HH:MM format)
                - timezone: str
        """
        self.whatsapp_client = whatsapp_client  # Kept for compatibility
        self.config = config
        self.scheduler = None

        # Database path
        self.db_path = os.environ.get("MESSAGES_DB_PATH", DEFAULT_DB_PATH)

        # WhatsApp API URL
        self.whatsapp_api_url = os.environ.get("WHATSAPP_API_URL", "http://localhost:8080/api/send")

        # Validate configuration
        self.enabled = config.get("enabled", False)
        self.recipient = config.get("recipient", "").strip("'\"")
        self.groups = self._parse_groups(config.get("groups", ""))
        self.schedule_time = config.get("schedule_time", "09:00")
        self.timezone_str = config.get("timezone", "Asia/Kolkata")

        if self.enabled:
            logger.info(f"Daily summary enabled for {len(self.groups)} groups")
            logger.info(f"Scheduled at {self.schedule_time} {self.timezone_str}")
            logger.info(f"Recipient: {self.recipient}")

    def _parse_groups(self, groups_str: str) -> List[str]:
        """Parse comma-separated quoted group JIDs or 'all' for all groups"""
        if not groups_str:
            return []

        # Remove outer quotes and strip
        groups_str = groups_str.strip("'\"").strip().lower()
        if not groups_str:
            return []

        # Check for 'all' keyword - will be resolved at runtime
        if groups_str == 'all':
            return ['all']

        # Split and clean each JID
        groups = [g.strip().strip("'\"") for g in groups_str.split(",")]
        return [g for g in groups if g and g.endswith("@g.us")]

    def fetch_all_groups(self) -> List[Dict[str, str]]:
        """
        Fetch all available groups from database

        Returns:
            List of dicts with 'jid' and 'name'
        """
        try:
            logger.info("Fetching all available groups from database...")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT jid, name FROM chats
                WHERE jid LIKE '%@g.us'
                ORDER BY last_message_time DESC
            """)

            groups = []
            for row in cursor.fetchall():
                groups.append({
                    'jid': row[0],
                    'name': row[1] or row[0]
                })

            conn.close()
            logger.info(f"Found {len(groups)} groups")
            return groups

        except Exception as e:
            logger.error(f"Error fetching all groups: {e}")
            return []

    def fetch_messages_last_24h(self, group_jid: str) -> List[Dict[str, Any]]:
        """
        Fetch messages from last 24 hours for a specific group

        Args:
            group_jid: WhatsApp group JID

        Returns:
            List of message dictionaries
        """
        try:
            # Calculate timestamp for 24 hours ago
            yesterday = datetime.now() - timedelta(days=1)
            after_timestamp = yesterday.strftime("%Y-%m-%d %H:%M:%S")

            logger.debug(f"Fetching messages for {group_jid} after {after_timestamp}")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, sender, content, timestamp, is_from_me
                FROM messages
                WHERE chat_jid = ?
                AND datetime(substr(timestamp, 1, 19)) > datetime(?)
                ORDER BY timestamp ASC
            """, (group_jid, after_timestamp))

            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row[0],
                    'sender': row[1],
                    'content': row[2],
                    'timestamp': row[3],
                    'is_from_me': row[4]
                })

            conn.close()
            logger.debug(f"Found {len(messages)} messages for {group_jid}")
            return messages

        except Exception as e:
            logger.error(f"Error fetching messages for {group_jid}: {e}")
            return []

    def get_group_name(self, group_jid: str) -> str:
        """
        Get group name from JID

        Args:
            group_jid: WhatsApp group JID

        Returns:
            Group name or JID if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM chats WHERE jid = ?", (group_jid,))
            result = cursor.fetchone()
            conn.close()

            return result[0] if result and result[0] else group_jid

        except Exception as e:
            logger.error(f"Error getting group name for {group_jid}: {e}")
            return group_jid

    def analyze_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze messages and generate statistics

        Args:
            messages: List of message dictionaries

        Returns:
            Statistics dictionary
        """
        if not messages:
            return {
                "total_messages": 0,
                "unique_senders": 0,
                "top_senders": [],
                "hourly_distribution": {},
                "keywords": []
            }

        # Count messages per sender
        sender_counts = Counter()
        hourly_counts = Counter()

        for msg in messages:
            sender = msg.get("sender", "Unknown")
            sender_counts[sender] += 1

            # Extract hour from timestamp
            timestamp = msg.get("timestamp", "")
            if timestamp:
                try:
                    # Handle various timestamp formats
                    ts = timestamp[:19]  # Get YYYY-MM-DD HH:MM:SS part
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    hourly_counts[dt.hour] += 1
                except:
                    pass

        # Get top senders
        top_senders = sender_counts.most_common(5)

        return {
            "total_messages": len(messages),
            "unique_senders": len(sender_counts),
            "top_senders": [{"sender": s, "count": c} for s, c in top_senders],
            "hourly_distribution": dict(hourly_counts),
            "keywords": []  # Could be enhanced with keyword extraction
        }

    def format_summary(self, group_summaries: List[Dict[str, Any]]) -> str:
        """
        Format summary for WhatsApp message

        Args:
            group_summaries: List of group summary dictionaries

        Returns:
            Formatted summary string
        """
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")

        summary_parts = [
            f"📊 *Daily WhatsApp Summary*",
            f"📅 {date_str}",
            "",
        ]

        total_messages = 0
        for group_data in group_summaries:
            stats = group_data.get("stats", {})
            msg_count = stats.get("total_messages", 0)
            total_messages += msg_count

            if msg_count == 0:
                continue

            group_name = group_data.get("name", "Unknown Group")
            unique_senders = stats.get("unique_senders", 0)
            top_senders = stats.get("top_senders", [])

            summary_parts.append(f"*{group_name}*")
            summary_parts.append(f"💬 {msg_count} messages from {unique_senders} participants")

            if top_senders:
                top_list = ", ".join([f"{s['sender'].split('@')[0][:10]}({s['count']})" for s in top_senders[:3]])
                summary_parts.append(f"👥 Top: {top_list}")

            summary_parts.append("")

        if total_messages == 0:
            summary_parts.append("No activity in the last 24 hours.")
        else:
            summary_parts.append(f"📈 *Total: {total_messages} messages across {len([g for g in group_summaries if g['stats']['total_messages'] > 0])} active groups*")

        return "\n".join(summary_parts)

    def send_summary(self, summary_text: str) -> bool:
        """
        Send summary via WhatsApp

        Args:
            summary_text: Summary text to send

        Returns:
            True if sent successfully
        """
        try:
            if not self.recipient:
                logger.error("No recipient configured for daily summary")
                return False

            logger.info(f"Sending daily summary to {self.recipient}")

            payload = {
                "recipient": self.recipient,
                "message": summary_text
            }

            response = requests.post(self.whatsapp_api_url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info("Daily summary sent successfully")
                return True
            else:
                logger.error(f"Failed to send daily summary: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
            return False

    def generate_and_send_summary(self):
        """Generate and send the daily summary (synchronous version)"""
        try:
            logger.info("Generating daily summary...")

            if not self.groups:
                logger.warning("No groups configured for daily summary")
                return

            # Resolve 'all' keyword to actual group JIDs
            if self.groups == ['all']:
                logger.info("Resolving 'all' to actual group list...")
                groups_data = self.fetch_all_groups()
                if not groups_data:
                    logger.warning("No groups found when resolving 'all'")
                    return
                logger.info(f"Found {len(groups_data)} groups to summarize")
            else:
                groups_data = [{'jid': g, 'name': self.get_group_name(g)} for g in self.groups]

            group_summaries = []

            for group_info in groups_data:
                group_jid = group_info['jid']

                # Fetch messages
                messages = self.fetch_messages_last_24h(group_jid)

                # Analyze messages
                stats = self.analyze_messages(messages)

                group_summaries.append({
                    "jid": group_jid,
                    "name": group_info['name'],
                    "stats": stats
                })

            # Format summary
            summary_text = self.format_summary(group_summaries)

            # Send summary
            self.send_summary(summary_text)

            logger.info("Daily summary completed")

        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            import traceback
            traceback.print_exc()

    def _job_wrapper(self):
        """Wrapper to run job in scheduler"""
        logger.info("Daily summary job triggered")
        self.generate_and_send_summary()

    def start_scheduler(self):
        """Start the daily summary scheduler"""
        if not self.enabled:
            logger.info("Daily summary disabled in configuration")
            return

        if not SCHEDULER_AVAILABLE:
            logger.error("Cannot start scheduler: APScheduler or pytz not installed")
            return

        if not self.recipient:
            logger.error("Cannot start scheduler: No recipient configured")
            return

        if not self.groups:
            logger.error("Cannot start scheduler: No groups configured (use 'all' for all groups)")
            return

        if self.groups == ['all']:
            logger.info("Daily summary configured for ALL groups")

        try:
            # Parse schedule time
            hour, minute = self.schedule_time.split(":")
            hour = int(hour)
            minute = int(minute)

            # Get timezone
            tz = pytz.timezone(self.timezone_str)

            # Create scheduler
            self.scheduler = BackgroundScheduler(timezone=tz)

            # Add job
            trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
            self.scheduler.add_job(
                self._job_wrapper,
                trigger=trigger,
                id="daily_whatsapp_summary",
                name="Daily WhatsApp Summary",
                replace_existing=True
            )

            # Start scheduler
            self.scheduler.start()

            # Get next run time
            job = self.scheduler.get_job("daily_whatsapp_summary")
            next_run = job.next_run_time if job else "Unknown"

            logger.info("✓ Daily summary scheduler started")
            logger.info(f"  Schedule: {self.schedule_time} {self.timezone_str}")
            logger.info(f"  Next run: {next_run}")

        except Exception as e:
            logger.error(f"Failed to start daily summary scheduler: {e}")

    def stop_scheduler(self):
        """Stop the daily summary scheduler"""
        if self.scheduler:
            logger.info("Stopping daily summary scheduler...")
            self.scheduler.shutdown(wait=False)
            self.scheduler = None
            logger.info("✓ Daily summary scheduler stopped")

    def run_now(self):
        """Manually trigger the daily summary"""
        logger.info("Manually triggering daily summary...")
        self.generate_and_send_summary()


def create_from_env(whatsapp_client=None) -> Optional[DailySummaryGenerator]:
    """
    Create DailySummaryGenerator from environment variables

    Environment variables:
        DAILY_SUMMARY_ENABLED: "true" to enable
        DAILY_SUMMARY_RECIPIENT: Phone number to send summary to
        DAILY_SUMMARY_GROUPS: Comma-separated group JIDs or 'all'
        DAILY_SUMMARY_TIME: Time in HH:MM format (default: 09:00)
        DAILY_SUMMARY_TIMEZONE: Timezone (default: Asia/Kolkata)

    Returns:
        DailySummaryGenerator instance or None if disabled
    """
    config = {
        "enabled": os.environ.get("DAILY_SUMMARY_ENABLED", "").lower() == "true",
        "recipient": os.environ.get("DAILY_SUMMARY_RECIPIENT", ""),
        "groups": os.environ.get("DAILY_SUMMARY_GROUPS", ""),
        "schedule_time": os.environ.get("DAILY_SUMMARY_TIME", "19:00"),
        "timezone": os.environ.get("DAILY_SUMMARY_TIMEZONE", "Asia/Kolkata")
    }

    if not config["enabled"]:
        logger.info("Daily summary feature disabled")
        return None

    return DailySummaryGenerator(whatsapp_client, config)
