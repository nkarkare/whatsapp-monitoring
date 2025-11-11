#!/usr/bin/env python3
"""
Tests for Daily Summary Module
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.daily_summary import DailySummaryGenerator


class TestDailySummaryGenerator(unittest.TestCase):
    """Test cases for DailySummaryGenerator"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.call_tool = AsyncMock()

        self.config = {
            "enabled": True,
            "recipient": "917498189688",
            "groups": "'123456789@g.us','987654321@g.us'",
            "schedule_time": "09:00",
            "timezone": "Asia/Kolkata"
        }

    def test_initialization(self):
        """Test generator initialization"""
        generator = DailySummaryGenerator(self.mock_client, self.config)

        self.assertTrue(generator.enabled)
        self.assertEqual(generator.recipient, "917498189688")
        self.assertEqual(len(generator.groups), 2)
        self.assertIn("123456789@g.us", generator.groups)
        self.assertIn("987654321@g.us", generator.groups)

    def test_parse_groups_empty(self):
        """Test parsing empty groups string"""
        config = self.config.copy()
        config["groups"] = ""

        generator = DailySummaryGenerator(self.mock_client, config)
        self.assertEqual(len(generator.groups), 0)

    def test_parse_groups_single_quotes(self):
        """Test parsing groups with single quotes"""
        config = self.config.copy()
        config["groups"] = "'111@g.us','222@g.us','333@g.us'"

        generator = DailySummaryGenerator(self.mock_client, config)
        self.assertEqual(len(generator.groups), 3)

    def test_analyze_messages_empty(self):
        """Test analyzing empty message list"""
        generator = DailySummaryGenerator(self.mock_client, self.config)

        stats = generator.analyze_messages([])

        self.assertEqual(stats["total_count"], 0)
        self.assertEqual(len(stats["top_senders"]), 0)

    def test_analyze_messages_with_data(self):
        """Test analyzing messages with data"""
        generator = DailySummaryGenerator(self.mock_client, self.config)

        messages = [
            {"sender_name": "Alice", "timestamp": datetime.now().isoformat(), "message": "Hello"},
            {"sender_name": "Bob", "timestamp": datetime.now().isoformat(), "message": "Hi"},
            {"sender_name": "Alice", "timestamp": datetime.now().isoformat(), "message": "How are you?"},
            {"sender_name": "Alice", "timestamp": datetime.now().isoformat(), "message": "Good"},
        ]

        stats = generator.analyze_messages(messages)

        self.assertEqual(stats["total_count"], 4)
        self.assertEqual(len(stats["top_senders"]), 2)
        # Alice should be top sender with 3 messages
        self.assertEqual(stats["top_senders"][0][0], "Alice")
        self.assertEqual(stats["top_senders"][0][1], 3)

    def test_time_distribution(self):
        """Test time distribution calculation"""
        generator = DailySummaryGenerator(self.mock_client, self.config)

        messages = [
            {"sender_name": "Alice", "timestamp": datetime(2025, 1, 1, 8, 0).isoformat(), "message": "Morning"},
            {"sender_name": "Bob", "timestamp": datetime(2025, 1, 1, 14, 0).isoformat(), "message": "Afternoon"},
            {"sender_name": "Charlie", "timestamp": datetime(2025, 1, 1, 19, 0).isoformat(), "message": "Evening"},
            {"sender_name": "Dave", "timestamp": datetime(2025, 1, 1, 23, 0).isoformat(), "message": "Night"},
        ]

        stats = generator.analyze_messages(messages)

        self.assertEqual(stats["time_distribution"]["morning"], 1)
        self.assertEqual(stats["time_distribution"]["afternoon"], 1)
        self.assertEqual(stats["time_distribution"]["evening"], 1)
        self.assertEqual(stats["time_distribution"]["night"], 1)

    def test_format_summary(self):
        """Test summary formatting"""
        generator = DailySummaryGenerator(self.mock_client, self.config)

        group_summaries = [
            {
                "name": "Test Group",
                "jid": "123456789@g.us",
                "stats": {
                    "total_count": 10,
                    "top_senders": [("Alice", 5), ("Bob", 3)],
                    "time_distribution": {"morning": 2, "afternoon": 5, "evening": 3, "night": 0},
                    "sample_messages": []
                }
            }
        ]

        summary = generator.format_summary(group_summaries)

        self.assertIn("Daily WhatsApp Summary", summary)
        self.assertIn("Test Group", summary)
        self.assertIn("10", summary)  # Message count
        self.assertIn("Alice", summary)
        self.assertIn("Bob", summary)

    @patch('src.daily_summary.BackgroundScheduler')
    @patch('src.daily_summary.pytz')
    def test_start_scheduler(self, mock_pytz, mock_scheduler_class):
        """Test scheduler startup"""
        generator = DailySummaryGenerator(self.mock_client, self.config)

        mock_tz = Mock()
        mock_pytz.timezone.return_value = mock_tz

        mock_scheduler = Mock()
        mock_scheduler_class.return_value = mock_scheduler

        generator.start_scheduler()

        # Verify scheduler was created and started
        mock_scheduler_class.assert_called_once()
        mock_scheduler.add_job.assert_called_once()
        mock_scheduler.start.assert_called_once()

    def test_disabled_feature(self):
        """Test that disabled feature doesn't initialize scheduler"""
        config = self.config.copy()
        config["enabled"] = False

        generator = DailySummaryGenerator(self.mock_client, config)
        generator.start_scheduler()

        # Should not crash, but also shouldn't create scheduler
        self.assertIsNone(generator.scheduler)


class TestDailySummaryIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for Daily Summary"""

    async def test_fetch_messages(self):
        """Test fetching messages from WhatsApp MCP"""
        mock_client = Mock()
        mock_result = Mock()
        mock_content = Mock()
        mock_content.text = '{"messages": [{"id": "1", "message": "Test"}]}'
        mock_result.content = [mock_content]
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        config = {
            "enabled": True,
            "recipient": "917498189688",
            "groups": "'123456789@g.us'",
            "schedule_time": "09:00",
            "timezone": "Asia/Kolkata"
        }

        generator = DailySummaryGenerator(mock_client, config)

        messages = await generator.fetch_messages_last_24h("123456789@g.us")

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["message"], "Test")

    async def test_get_group_name(self):
        """Test getting group name"""
        mock_client = Mock()
        mock_result = Mock()
        mock_content = Mock()
        mock_content.text = '{"name": "Test Group", "jid": "123456789@g.us"}'
        mock_result.content = [mock_content]
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        config = {
            "enabled": True,
            "recipient": "917498189688",
            "groups": "'123456789@g.us'",
            "schedule_time": "09:00",
            "timezone": "Asia/Kolkata"
        }

        generator = DailySummaryGenerator(mock_client, config)

        name = await generator.get_group_name("123456789@g.us")

        self.assertEqual(name, "Test Group")


if __name__ == "__main__":
    unittest.main()
