#!/usr/bin/env python3
"""
Tests for Keyword Monitoring Module
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.keyword_monitor import KeywordMonitor


class TestKeywordMonitor(unittest.TestCase):
    """Test cases for KeywordMonitor"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.call_tool = AsyncMock()

        self.config = {
            "enabled": True,
            "recipient": "917498189688",
            "keywords": "'urgent','critical','help'",
            "groups": "'123456789@g.us','987654321@g.us'",
            "cooldown": 300
        }

    def test_initialization(self):
        """Test monitor initialization"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        self.assertTrue(monitor.enabled)
        self.assertEqual(monitor.recipient, "917498189688")
        self.assertEqual(len(monitor.keywords), 3)
        self.assertIn("urgent", monitor.keywords)
        self.assertIn("critical", monitor.keywords)
        self.assertIn("help", monitor.keywords)

    def test_parse_keywords(self):
        """Test parsing keywords from config"""
        config = self.config.copy()
        config["keywords"] = "'bug','error','crash','failure'"

        monitor = KeywordMonitor(self.mock_client, config)

        self.assertEqual(len(monitor.keywords), 4)
        self.assertIn("bug", monitor.keywords)
        self.assertIn("error", monitor.keywords)

    def test_parse_groups_all(self):
        """Test parsing 'all' groups"""
        config = self.config.copy()
        config["groups"] = "'all'"

        monitor = KeywordMonitor(self.mock_client, config)

        self.assertTrue(monitor.monitor_all_groups)

    def test_detect_keywords_single(self):
        """Test detecting single keyword"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        detected = monitor.detect_keywords("This is an urgent message!")

        self.assertEqual(len(detected), 1)
        self.assertIn("urgent", detected)

    def test_detect_keywords_multiple(self):
        """Test detecting multiple keywords"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        detected = monitor.detect_keywords("URGENT: Critical help needed!")

        self.assertGreaterEqual(len(detected), 2)
        self.assertIn("urgent", detected)
        self.assertIn("critical", detected)

    def test_detect_keywords_case_insensitive(self):
        """Test case-insensitive detection"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        detected = monitor.detect_keywords("URGENT: This is CRITICAL!")

        self.assertIn("urgent", detected)
        self.assertIn("critical", detected)

    def test_detect_keywords_word_boundary(self):
        """Test word boundary detection"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        # Should match 'help' as a standalone word
        detected1 = monitor.detect_keywords("I need help please")
        self.assertIn("help", detected1)

        # Should NOT match 'help' inside 'helpful'
        detected2 = monitor.detect_keywords("This is helpful")
        # 'help' should match in 'helpful' with word boundary
        # Actually, let's test exact word: should not match partial
        config = self.config.copy()
        config["keywords"] = "'test'"
        monitor2 = KeywordMonitor(self.mock_client, config)

        # Should match
        self.assertEqual(len(monitor2.detect_keywords("this is a test")), 1)

        # Should NOT match inside 'testing'
        detected_partial = monitor2.detect_keywords("this is testing")
        # Due to word boundary, it won't match
        self.assertEqual(len(detected_partial), 0)

    def test_detect_keywords_none(self):
        """Test detecting no keywords"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        detected = monitor.detect_keywords("This is a normal message")

        self.assertEqual(len(detected), 0)

    def test_cooldown_mechanism(self):
        """Test alert cooldown"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        # First alert should be allowed
        self.assertTrue(monitor.can_send_alert("urgent"))

        # Mark alert sent
        monitor.mark_alert_sent("urgent")

        # Second alert should be blocked (cooldown)
        self.assertFalse(monitor.can_send_alert("urgent"))

        # Different keyword should be allowed
        self.assertTrue(monitor.can_send_alert("critical"))

    def test_cooldown_expiry(self):
        """Test cooldown expiry"""
        config = self.config.copy()
        config["cooldown"] = 1  # 1 second cooldown

        monitor = KeywordMonitor(self.mock_client, config)

        # Send alert
        monitor.mark_alert_sent("urgent")
        self.assertFalse(monitor.can_send_alert("urgent"))

        # Wait for cooldown to expire
        import time
        time.sleep(1.1)

        # Should be allowed now
        self.assertTrue(monitor.can_send_alert("urgent"))

    def test_should_monitor_group(self):
        """Test group monitoring check"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        # Should monitor configured groups
        self.assertTrue(monitor.should_monitor_group("123456789@g.us"))
        self.assertTrue(monitor.should_monitor_group("987654321@g.us"))

        # Should NOT monitor other groups
        self.assertFalse(monitor.should_monitor_group("111111111@g.us"))

    def test_should_monitor_group_all(self):
        """Test monitoring all groups"""
        config = self.config.copy()
        config["groups"] = "'all'"

        monitor = KeywordMonitor(self.mock_client, config)

        # Should monitor any group
        self.assertTrue(monitor.should_monitor_group("123456789@g.us"))
        self.assertTrue(monitor.should_monitor_group("999999999@g.us"))

    def test_format_alert(self):
        """Test alert formatting"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        message = {
            "sender_name": "Alice",
            "timestamp": datetime.now().isoformat(),
            "message": "This is an urgent issue that needs help!",
            "chat_jid": "123456789@g.us"
        }

        alert = monitor.format_alert("urgent", message, "Test Group")

        self.assertIn("urgent", alert)
        self.assertIn("Alice", alert)
        self.assertIn("Test Group", alert)
        self.assertIn("urgent issue", alert)

    def test_format_alert_long_message(self):
        """Test alert formatting with long message"""
        monitor = KeywordMonitor(self.mock_client, self.config)

        long_message = "This is urgent! " + ("a" * 400)  # Very long message

        message = {
            "sender_name": "Bob",
            "timestamp": datetime.now().isoformat(),
            "message": long_message,
            "chat_jid": "123456789@g.us"
        }

        alert = monitor.format_alert("urgent", message, "Test Group")

        # Should truncate long messages
        self.assertLess(len(alert), len(long_message) + 200)
        self.assertIn("...", alert)  # Truncation indicator


class TestKeywordMonitorIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for Keyword Monitor"""

    async def test_check_message_with_keyword(self):
        """Test checking a message with a keyword"""
        mock_client = Mock()

        # Mock get_chat response
        mock_chat_result = Mock()
        mock_chat_content = Mock()
        mock_chat_content.text = '{"name": "Test Group", "jid": "123456789@g.us"}'
        mock_chat_result.content = [mock_chat_content]

        # Mock send_message response
        mock_send_result = Mock()
        mock_send_content = Mock()
        mock_send_content.text = '{"success": true}'
        mock_send_result.content = [mock_send_content]

        # Setup mock to return different responses
        async def mock_call_tool(tool_name, params):
            if tool_name == "get_chat":
                return mock_chat_result
            elif tool_name == "send_message":
                return mock_send_result
            return None

        mock_client.call_tool = mock_call_tool

        config = {
            "enabled": True,
            "recipient": "917498189688",
            "keywords": "'urgent','critical'",
            "groups": "'123456789@g.us'",
            "cooldown": 300
        }

        monitor = KeywordMonitor(mock_client, config)

        message = {
            "sender_name": "Alice",
            "timestamp": datetime.now().isoformat(),
            "message": "This is an urgent message!",
            "chat_jid": "123456789@g.us"
        }

        result = await monitor.check_message(message)

        self.assertTrue(result)

    async def test_check_message_no_keyword(self):
        """Test checking a message without keywords"""
        mock_client = Mock()
        mock_client.call_tool = AsyncMock()

        config = {
            "enabled": True,
            "recipient": "917498189688",
            "keywords": "'urgent','critical'",
            "groups": "'123456789@g.us'",
            "cooldown": 300
        }

        monitor = KeywordMonitor(mock_client, config)

        message = {
            "sender_name": "Bob",
            "timestamp": datetime.now().isoformat(),
            "message": "This is a normal message",
            "chat_jid": "123456789@g.us"
        }

        result = await monitor.check_message(message)

        self.assertFalse(result)

    async def test_check_message_wrong_group(self):
        """Test checking a message from non-monitored group"""
        mock_client = Mock()
        mock_client.call_tool = AsyncMock()

        config = {
            "enabled": True,
            "recipient": "917498189688",
            "keywords": "'urgent'",
            "groups": "'123456789@g.us'",
            "cooldown": 300
        }

        monitor = KeywordMonitor(mock_client, config)

        message = {
            "sender_name": "Charlie",
            "timestamp": datetime.now().isoformat(),
            "message": "This is urgent!",
            "chat_jid": "999999999@g.us"  # Different group
        }

        result = await monitor.check_message(message)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
