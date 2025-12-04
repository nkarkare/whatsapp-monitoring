#!/usr/bin/env python3
"""
Daily Summary Module

Generates and sends daily summaries of WhatsApp group activity.
Scheduled using APScheduler with timezone support.
"""

import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    import pytz
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    logging.warning("APScheduler or pytz not available. Install with: pip install APScheduler pytz")

logger = logging.getLogger("whatsapp_monitoring.daily_summary")


class DailySummaryGenerator:
    """Generates daily summaries of WhatsApp group activity"""

    def __init__(self, whatsapp_client, config: Dict[str, Any]):
        """
        Initialize daily summary generator

        Args:
            whatsapp_client: WhatsApp MCP client session
            config: Configuration dictionary with:
                - enabled: bool
                - recipient: str (phone number)
                - groups: List[str] (group JIDs)
                - schedule_time: str (HH:MM format)
                - timezone: str
        """
        self.whatsapp_client = whatsapp_client
        self.config = config
        self.scheduler = None

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

    async def fetch_all_groups(self) -> List[str]:
        """
        Fetch all available group JIDs

        Returns:
            List of group JIDs
        """
        try:
            logger.info("Fetching all available groups...")

            result = await self.whatsapp_client.call_tool(
                "list_chats",
                {
                    "limit": 100,
                    "include_last_message": False
                }
            )

            if not result or not result.content:
                logger.warning("No chats found")
                return []

            groups = []
            for content in result.content:
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    chats = data.get("chats", [])
                    for chat in chats:
                        jid = chat.get("jid", "")
                        if jid.endswith("@g.us"):
                            groups.append(jid)
                            logger.debug(f"Found group: {chat.get('name', jid)}")

            logger.info(f"Found {len(groups)} groups")
            return groups

        except Exception as e:
            logger.error(f"Error fetching all groups: {e}")
            return []

    async def fetch_messages_last_24h(self, group_jid: str) -> List[Dict[str, Any]]:
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
            after_timestamp = yesterday.isoformat()

            logger.debug(f"Fetching messages for {group_jid} after {after_timestamp}")

            # Call WhatsApp MCP to get messages
            result = await self.whatsapp_client.call_tool(
                "list_messages",
                {
                    "chat_jid": group_jid,
                    "after": after_timestamp,
                    "limit": 1000,
                    "include_context": False
                }
            )

            if not result or not result.content:
                logger.warning(f"No response for group {group_jid}")
                return []

            # Parse response
            for content in result.content:
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    messages = data.get("messages", [])
                    logger.debug(f"Found {len(messages)} messages for {group_jid}")
                    return messages

            return []

        except Exception as e:
            logger.error(f"Error fetching messages for {group_jid}: {e}")
            return []

    async def get_group_name(self, group_jid: str) -> str:
        """
        Get group name from JID

        Args:
            group_jid: WhatsApp group JID

        Returns:
            Group name or JID if not found
        """
        try:
            result = await self.whatsapp_client.call_tool(
                "get_chat",
                {"chat_jid": group_jid}
            )

            if result and result.content:
                for content in result.content:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        return data.get("name", group_jid)

            return group_jid

        except Exception as e:
            logger.error(f"Error getting group name for {group_jid}: {e}")
            return group_jid

    def analyze_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze messages and generate statistics

        Args:
            messages: List of message dictionaries

        Returns:
            Dictionary with analysis results
        """
        if not messages:
            return {
                "total_count": 0,
                "top_senders": [],
                "time_distribution": {},
                "sample_messages": []
            }

        # Count messages per sender
        senders = [msg.get("sender_name", "Unknown") for msg in messages if msg.get("sender_name")]
        sender_counts = Counter(senders)
        top_senders = sender_counts.most_common(5)

        # Time distribution (morning, afternoon, evening, night)
        time_distribution = {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}

        for msg in messages:
            timestamp_str = msg.get("timestamp")
            if timestamp_str:
                try:
                    # Parse timestamp
                    if isinstance(timestamp_str, int):
                        msg_time = datetime.fromtimestamp(timestamp_str)
                    else:
                        msg_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                    hour = msg_time.hour

                    if 5 <= hour < 12:
                        time_distribution["morning"] += 1
                    elif 12 <= hour < 17:
                        time_distribution["afternoon"] += 1
                    elif 17 <= hour < 21:
                        time_distribution["evening"] += 1
                    else:
                        time_distribution["night"] += 1

                except Exception as e:
                    logger.debug(f"Error parsing timestamp {timestamp_str}: {e}")

        # Get sample of recent messages (last 3)
        sample_messages = messages[-3:] if len(messages) >= 3 else messages

        return {
            "total_count": len(messages),
            "top_senders": top_senders,
            "time_distribution": time_distribution,
            "sample_messages": sample_messages
        }

    def format_summary(self, group_summaries: List[Dict[str, Any]]) -> str:
        """
        Format the summary message

        Args:
            group_summaries: List of group summary dictionaries

        Returns:
            Formatted summary message
        """
        lines = []
        lines.append("📊 *Daily WhatsApp Summary*")
        lines.append(f"📅 {datetime.now().strftime('%B %d, %Y')}")
        lines.append("")
        lines.append("=" * 40)
        lines.append("")

        total_messages = sum(gs["stats"]["total_count"] for gs in group_summaries)
        lines.append(f"📬 *Total Messages:* {total_messages}")
        lines.append(f"👥 *Groups Monitored:* {len(group_summaries)}")
        lines.append("")

        for group_summary in group_summaries:
            group_name = group_summary["name"]
            stats = group_summary["stats"]

            lines.append(f"📱 *{group_name}*")
            lines.append(f"   💬 Messages: {stats['total_count']}")

            if stats["top_senders"]:
                lines.append(f"   👤 Top Senders:")
                for sender, count in stats["top_senders"][:3]:
                    lines.append(f"      • {sender}: {count} msgs")

            # Time distribution
            time_dist = stats["time_distribution"]
            if sum(time_dist.values()) > 0:
                lines.append(f"   ⏰ Activity:")
                if time_dist["morning"] > 0:
                    lines.append(f"      • Morning: {time_dist['morning']}")
                if time_dist["afternoon"] > 0:
                    lines.append(f"      • Afternoon: {time_dist['afternoon']}")
                if time_dist["evening"] > 0:
                    lines.append(f"      • Evening: {time_dist['evening']}")
                if time_dist["night"] > 0:
                    lines.append(f"      • Night: {time_dist['night']}")

            lines.append("")

        lines.append("=" * 40)
        lines.append("")
        lines.append("✨ _Generated by WhatsApp Monitoring_")

        return "\n".join(lines)

    async def send_summary(self, summary_text: str):
        """
        Send summary via WhatsApp

        Args:
            summary_text: Formatted summary message
        """
        try:
            if not self.recipient:
                logger.error("No recipient configured for daily summary")
                return

            logger.info(f"Sending daily summary to {self.recipient}")

            result = await self.whatsapp_client.call_tool(
                "send_message",
                {
                    "recipient": self.recipient,
                    "message": summary_text
                }
            )

            if result:
                logger.info("Daily summary sent successfully")
            else:
                logger.error("Failed to send daily summary")

        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")

    async def generate_and_send_summary(self):
        """Generate and send the daily summary"""
        try:
            logger.info("Generating daily summary...")

            if not self.groups:
                logger.warning("No groups configured for daily summary")
                return

            # Resolve 'all' keyword to actual group JIDs
            groups_to_process = self.groups
            if self.groups == ['all']:
                logger.info("Resolving 'all' to actual group list...")
                groups_to_process = await self.fetch_all_groups()
                if not groups_to_process:
                    logger.warning("No groups found when resolving 'all'")
                    return
                logger.info(f"Found {len(groups_to_process)} groups to summarize")

            group_summaries = []

            for group_jid in groups_to_process:
                # Fetch messages
                messages = await self.fetch_messages_last_24h(group_jid)

                # Get group name
                group_name = await self.get_group_name(group_jid)

                # Analyze messages
                stats = self.analyze_messages(messages)

                group_summaries.append({
                    "jid": group_jid,
                    "name": group_name,
                    "stats": stats
                })

            # Format summary
            summary_text = self.format_summary(group_summaries)

            # Send summary
            await self.send_summary(summary_text)

            logger.info("Daily summary completed")

        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")

    def _job_wrapper(self):
        """Wrapper to run async job in scheduler"""
        logger.info("Daily summary job triggered")
        asyncio.run(self.generate_and_send_summary())

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
            hour, minute = map(int, self.schedule_time.split(":"))

            # Get timezone
            tz = pytz.timezone(self.timezone_str)

            # Create scheduler
            self.scheduler = BackgroundScheduler(timezone=tz)

            # Add job
            trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
            self.scheduler.add_job(
                self._job_wrapper,
                trigger=trigger,
                id="daily_summary_job",
                name="Daily WhatsApp Summary",
                replace_existing=True
            )

            # Start scheduler
            self.scheduler.start()

            logger.info(f"✓ Daily summary scheduler started")
            logger.info(f"  Schedule: {self.schedule_time} {self.timezone_str}")
            logger.info(f"  Next run: {self.scheduler.get_job('daily_summary_job').next_run_time}")

        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")

    def stop_scheduler(self):
        """Stop the daily summary scheduler"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Daily summary scheduler stopped")


def create_from_env(whatsapp_client) -> Optional[DailySummaryGenerator]:
    """
    Create DailySummaryGenerator from environment variables

    Args:
        whatsapp_client: WhatsApp MCP client session

    Returns:
        DailySummaryGenerator instance or None if disabled
    """
    config = {
        "enabled": os.environ.get("DAILY_SUMMARY_ENABLED", "false").lower() == "true",
        "recipient": os.environ.get("DAILY_SUMMARY_RECIPIENT", ""),
        "groups": os.environ.get("DAILY_SUMMARY_GROUPS", ""),
        "schedule_time": os.environ.get("DAILY_SUMMARY_TIME", "09:00"),
        "timezone": os.environ.get("DAILY_SUMMARY_TIMEZONE", "Asia/Kolkata")
    }

    return DailySummaryGenerator(whatsapp_client, config)
