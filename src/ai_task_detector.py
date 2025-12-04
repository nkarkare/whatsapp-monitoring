#!/usr/bin/env python3
"""
AI-Powered Task Detection Module

Uses Claude API to intelligently detect action items, follow-ups, and pending tasks
from WhatsApp messages with mixed Marathi-English content.
"""

import os
import logging
import json
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import hashlib

logger = logging.getLogger("whatsapp_monitoring.ai_task_detector")


class AITaskDetector:
    """Intelligent task detection using Claude API with learning capabilities"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AI task detector

        Args:
            config: Configuration dictionary with:
                - enabled: bool
                - claude_api_key: str
                - claude_api_url: str
                - claude_model: str
                - confidence_threshold: int (0-100)
                - min_message_length: int
                - batch_analysis: bool
                - batch_size: int
                - daily_budget: int
                - learning_enabled: bool
                - learning_db_path: str
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        self.claude_api_key = config.get("claude_api_key", "")
        self.claude_api_url = config.get("claude_api_url", "https://api.anthropic.com/v1/messages")
        self.claude_model = config.get("claude_model", "claude-3-sonnet-20240229")
        self.confidence_threshold = config.get("confidence_threshold", 50)
        self.min_message_length = config.get("min_message_length", 10)
        self.batch_analysis = config.get("batch_analysis", True)
        self.batch_size = config.get("batch_size", 10)
        self.daily_budget = config.get("daily_budget", 500)
        self.learning_enabled = config.get("learning_enabled", True)
        self.learning_db_path = config.get("learning_db_path", "data/task_detection_history.db")

        # Tracking
        self.daily_api_calls = 0
        self.last_reset_date = datetime.now().date()
        self.analysis_cache = {}  # Message hash -> analysis result

        # Learning examples (will be loaded from database)
        self.positive_examples = []
        self.negative_examples = []

        if self.enabled:
            logger.info("AI Task Detection enabled")
            logger.info(f"  Model: {self.claude_model}")
            logger.info(f"  Confidence threshold: {self.confidence_threshold}%")
            logger.info(f"  Daily budget: {self.daily_budget} calls")
            logger.info(f"  Learning: {'enabled' if self.learning_enabled else 'disabled'}")

            # Initialize learning database
            if self.learning_enabled:
                from src.learning_engine import LearningEngine
                self.learning_engine = LearningEngine(self.learning_db_path)
                self._load_learning_examples()
            else:
                self.learning_engine = None

    def _load_learning_examples(self):
        """Load recent approved/rejected examples for few-shot learning"""
        if not self.learning_engine:
            return

        try:
            # Get top approved detections
            self.positive_examples = self.learning_engine.get_top_examples(
                approved=True,
                limit=5
            )

            # Get top rejected detections
            self.negative_examples = self.learning_engine.get_top_examples(
                approved=False,
                limit=3
            )

            if self.positive_examples or self.negative_examples:
                logger.info(f"Loaded {len(self.positive_examples)} positive and {len(self.negative_examples)} negative examples for learning")

        except Exception as e:
            logger.error(f"Error loading learning examples: {e}")

    def should_analyze_message(self, message: Dict[str, Any]) -> bool:
        """
        Pre-filter check: should this message be analyzed?

        Args:
            message: Message dictionary

        Returns:
            True if message should be analyzed
        """
        content = message.get("content", "") or message.get("message", "")

        # Length check
        if len(content) < self.min_message_length:
            return False

        # Skip pure greetings/acknowledgments
        greetings = ['hi', 'hello', 'ok', 'okay', 'thanks', 'thank you', 'bye', 'good morning', 'good night']
        if content.lower().strip() in greetings:
            return False

        # Skip media-only messages (no text)
        if not content.strip():
            return False

        # Budget check
        if not self._check_daily_budget():
            return False

        return True

    def _check_daily_budget(self) -> bool:
        """Check if we're within daily API call budget"""
        # Reset counter if new day
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_api_calls = 0
            self.last_reset_date = current_date
            logger.info("Daily API call counter reset")

        if self.daily_api_calls >= self.daily_budget:
            logger.warning(f"Daily API budget ({self.daily_budget}) exceeded. Pausing AI detection.")
            return False

        return True

    def _build_analysis_prompt(self, message: Dict[str, Any]) -> str:
        """
        Build AI prompt with learning examples

        Args:
            message: Message dictionary

        Returns:
            Formatted prompt string
        """
        content = message.get("content", "") or message.get("message", "")
        sender = message.get("sender_name", "Unknown")
        group = message.get("group_name", "Unknown Group")
        timestamp = message.get("timestamp", "")

        # Base prompt
        prompt = f"""Analyze this WhatsApp message for action items, follow-ups, or pending tasks.
The message may contain mixed Marathi and English (code-switching).

MESSAGE DETAILS:
Content: "{content}"
Sender: {sender}
Group: {group}
Time: {timestamp}

TASK DETECTION:
Determine if this message represents:
1. An action item that needs to be tracked
2. A follow-up question about pending work
3. A reminder or deadline mention
4. A request for status update

MIXED LANGUAGE UNDERSTANDING:
Common Marathi phrases to recognize:
- "ka" / "का" = question marker (was it done? is it complete?)
- "na" / "ना" = seeking confirmation (right? isn't it?)
- "kelas ka" / "kelas" = did you do it? have you done it?
- "sent ka" = was it sent?
- "pending" = pending/incomplete
- "cha" / "चा" = possessive (of/belonging to)
- "lakar" / "लाकड" = urgently
- "aaata" / "आत्ता" = now/immediately
- "udya" / "उद्या" = tomorrow"""

        # Add learning examples if available
        if self.positive_examples:
            prompt += "\n\n✅ EXAMPLES OF ACTION ITEMS (learn from these):\n"
            for i, example in enumerate(self.positive_examples[:3], 1):
                prompt += f"\n{i}. \"{example.get('message_content', '')}\" → Task created: {example.get('ai_subject', 'Task')}"

        if self.negative_examples:
            prompt += "\n\n❌ EXAMPLES OF NON-ACTION ITEMS (ignore messages like these):\n"
            for i, example in enumerate(self.negative_examples[:2], 1):
                prompt += f"\n{i}. \"{example.get('message_content', '')}\" → Correctly ignored"

        # Output format
        prompt += """

ANALYSIS OUTPUT:
Return ONLY valid JSON (no markdown, no extra text) in this exact format:
{
  "is_action_item": true or false,
  "confidence": 0-100 (how confident you are this needs tracking),
  "type": "follow-up" or "pending-task" or "deadline-reminder" or "status-request" or "general-chat",
  "subject": "Brief English task title (max 100 chars)",
  "description": "Keep original message text here",
  "assignee_mentions": ["List", "of", "names"] (extract @mentions or names from message),
  "due_date": "YYYY-MM-DD or null" (parse dates like 'dec 5', 'tomorrow', 'friday'),
  "priority": "Low" or "Medium" or "High" (based on urgency),
  "reasoning": "Brief explanation of your decision"
}

IMPORTANT:
- If this is just a greeting, acknowledgment, or casual chat → is_action_item: false, confidence: 10-30
- If this clearly asks about pending work or mentions a deadline → is_action_item: true, confidence: 70-95
- If uncertain → confidence: 40-60
- Keep subject in English but preserve original language in description
"""

        return prompt

    def analyze_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze a message with Claude API

        Args:
            message: Message dictionary

        Returns:
            Analysis result dict or None if should skip
        """
        # Pre-filter check
        if not self.should_analyze_message(message):
            return None

        content = message.get("content", "") or message.get("message", "")

        # Check cache
        message_hash = hashlib.md5(content.encode()).hexdigest()
        if message_hash in self.analysis_cache:
            logger.debug(f"Using cached analysis for message")
            return self.analysis_cache[message_hash]

        try:
            # Build prompt
            prompt = self._build_analysis_prompt(message)

            # Call Claude API
            logger.info(f"Analyzing message with AI: {content[:50]}...")
            result = self._call_claude_api(prompt)

            if result:
                # Parse JSON response
                analysis = self._parse_analysis_result(result, message)

                if analysis:
                    # Cache result
                    self.analysis_cache[message_hash] = analysis

                    # Log detection
                    logger.info(
                        f"AI Detection: is_action={analysis['is_action_item']}, "
                        f"confidence={analysis['confidence']}%, "
                        f"type={analysis.get('type', 'unknown')}"
                    )

                    return analysis

        except Exception as e:
            logger.error(f"Error analyzing message: {e}")

        return None

    def analyze_messages_batch(self, messages: List[Dict[str, Any]]) -> List[Optional[Dict[str, Any]]]:
        """
        Analyze multiple messages in a single API call (batch mode)

        Args:
            messages: List of message dictionaries

        Returns:
            List of analysis results (same order as input, None for skipped/failed)
        """
        if not messages:
            return []

        # Filter messages and track indices
        to_analyze = []
        results = [None] * len(messages)

        for idx, message in enumerate(messages):
            content = message.get("content", "") or message.get("message", "")

            # Check cache first
            message_hash = hashlib.md5(content.encode()).hexdigest()
            if message_hash in self.analysis_cache:
                logger.debug(f"Using cached analysis for message {idx}")
                results[idx] = self.analysis_cache[message_hash]
                continue

            # Pre-filter check (skip budget check - we do that once for batch)
            if len(content) < self.min_message_length:
                continue
            greetings = ['hi', 'hello', 'ok', 'okay', 'thanks', 'thank you', 'bye', 'good morning', 'good night']
            if content.lower().strip() in greetings:
                continue
            if not content.strip():
                continue

            to_analyze.append((idx, message))

        if not to_analyze:
            return results

        # Budget check for batch
        if not self._check_daily_budget():
            return results

        try:
            # Build batch prompt
            prompt = self._build_batch_analysis_prompt([m for _, m in to_analyze])

            # Call Claude API (increased max_tokens for batch)
            logger.info(f"Batch analyzing {len(to_analyze)} messages with AI...")
            result = self._call_claude_api(prompt, max_tokens=2000)

            if result:
                # Parse batch JSON response
                batch_results = self._parse_batch_analysis_result(result, [m for _, m in to_analyze])

                if batch_results:
                    for i, (orig_idx, message) in enumerate(to_analyze):
                        if i < len(batch_results) and batch_results[i]:
                            analysis = batch_results[i]
                            results[orig_idx] = analysis

                            # Cache result
                            content = message.get("content", "") or message.get("message", "")
                            message_hash = hashlib.md5(content.encode()).hexdigest()
                            self.analysis_cache[message_hash] = analysis

                            # Log detection
                            logger.info(
                                f"AI Batch Detection [{i+1}/{len(to_analyze)}]: "
                                f"is_action={analysis['is_action_item']}, "
                                f"confidence={analysis['confidence']}%, "
                                f"type={analysis.get('type', 'unknown')}"
                            )

        except Exception as e:
            logger.error(f"Error in batch analysis: {e}")

        return results

    def _build_batch_analysis_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """
        Build AI prompt for batch analysis of multiple messages

        Args:
            messages: List of message dictionaries

        Returns:
            Formatted prompt string
        """
        # Build message list
        message_list = []
        for idx, message in enumerate(messages, 1):
            content = message.get("content", "") or message.get("message", "")
            sender = message.get("sender_name", "Unknown")
            group = message.get("group_name", "Unknown Group")
            timestamp = message.get("timestamp", "")
            message_list.append(f"[{idx}] Sender: {sender} | Group: {group} | Time: {timestamp}\n    Content: \"{content}\"")

        messages_text = "\n\n".join(message_list)

        # Base prompt
        prompt = f"""Analyze these {len(messages)} WhatsApp messages for action items, follow-ups, or pending tasks.
Messages may contain mixed Marathi and English (code-switching).

MESSAGES TO ANALYZE:
{messages_text}

TASK DETECTION:
For each message, determine if it represents:
1. An action item that needs to be tracked
2. A follow-up question about pending work
3. A reminder or deadline mention
4. A request for status update

MIXED LANGUAGE UNDERSTANDING:
Common Marathi phrases to recognize:
- "ka" / "का" = question marker (was it done? is it complete?)
- "na" / "ना" = seeking confirmation (right? isn't it?)
- "kelas ka" / "kelas" = did you do it? have you done it?
- "sent ka" = was it sent?
- "pending" = pending/incomplete
- "lakar" / "लाकड" = urgently
- "aaata" / "आत्ता" = now/immediately
- "udya" / "उद्या" = tomorrow"""

        # Add learning examples if available
        if self.positive_examples:
            prompt += "\n\n✅ EXAMPLES OF ACTION ITEMS (learn from these):\n"
            for i, example in enumerate(self.positive_examples[:3], 1):
                prompt += f"\n{i}. \"{example.get('message_content', '')}\" → Task created: {example.get('ai_subject', 'Task')}"

        if self.negative_examples:
            prompt += "\n\n❌ EXAMPLES OF NON-ACTION ITEMS (ignore messages like these):\n"
            for i, example in enumerate(self.negative_examples[:2], 1):
                prompt += f"\n{i}. \"{example.get('message_content', '')}\" → Correctly ignored"

        # Output format for batch
        prompt += f"""

ANALYSIS OUTPUT:
Return ONLY a valid JSON array with {len(messages)} objects (one per message, in order).
No markdown, no extra text - just the JSON array.

[
  {{
    "message_num": 1,
    "is_action_item": true or false,
    "confidence": 0-100,
    "type": "follow-up" or "pending-task" or "deadline-reminder" or "status-request" or "general-chat",
    "subject": "Brief English task title (max 100 chars)",
    "description": "Keep original message text here",
    "assignee_mentions": ["List", "of", "names"],
    "due_date": "YYYY-MM-DD or null",
    "priority": "Low" or "Medium" or "High",
    "reasoning": "Brief explanation"
  }},
  ... (one object for each message)
]

IMPORTANT:
- Return exactly {len(messages)} objects in the array, matching message order
- If a message is just a greeting or casual chat → is_action_item: false, confidence: 10-30
- If a message clearly asks about pending work or mentions a deadline → is_action_item: true, confidence: 70-95
"""

        return prompt

    def _parse_batch_analysis_result(self, response_text: str, original_messages: List[Dict[str, Any]]) -> List[Optional[Dict[str, Any]]]:
        """
        Parse Claude API batch response into structured analysis list

        Args:
            response_text: Raw API response
            original_messages: List of original message dicts

        Returns:
            List of parsed analysis dicts or None for failures
        """
        results = [None] * len(original_messages)

        try:
            # Try to extract JSON array from response
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON array
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response_text

            # Parse JSON array
            analyses = json.loads(json_str)

            if not isinstance(analyses, list):
                logger.error("Batch response is not a JSON array")
                return results

            # Map results back to original messages
            for analysis in analyses:
                # Get message number (1-indexed in prompt)
                msg_num = analysis.get('message_num', 0)
                if msg_num < 1 or msg_num > len(original_messages):
                    continue

                idx = msg_num - 1
                original_message = original_messages[idx]

                # Add original message metadata
                analysis['original_message'] = original_message
                analysis['message_id'] = original_message.get('id', '')
                analysis['sender_name'] = original_message.get('sender_name', 'Unknown')
                analysis['group_name'] = original_message.get('group_name', 'Unknown Group')
                analysis['timestamp'] = original_message.get('timestamp', '')

                # Validate required fields
                required_fields = ['is_action_item', 'confidence', 'type']
                if all(field in analysis for field in required_fields):
                    # Ensure confidence is an integer
                    analysis['confidence'] = int(analysis.get('confidence', 0))
                    results[idx] = analysis

            logger.info(f"Parsed {sum(1 for r in results if r)} of {len(original_messages)} batch results")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse batch JSON from Claude response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
        except Exception as e:
            logger.error(f"Error parsing batch analysis result: {e}")

        return results

    def _call_claude_api(self, prompt: str, max_tokens: int = 1000) -> Optional[str]:
        """
        Call Claude API with the analysis prompt

        Args:
            prompt: Formatted prompt
            max_tokens: Maximum tokens in response (default 1000, use more for batch)

        Returns:
            API response text or None
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.claude_api_key,
                "anthropic-version": "2023-06-01"
            }

            payload = {
                "model": self.claude_model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }

            logger.debug(f"Sending request to Claude API (model: {self.claude_model})")

            response = requests.post(
                self.claude_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            # Increment API call counter
            self.daily_api_calls += 1

            if response.status_code == 200:
                response_data = response.json()
                if "content" in response_data and len(response_data["content"]) > 0:
                    return response_data["content"][0]["text"]
                else:
                    logger.error(f"Invalid response format from Claude API: {response_data}")
                    return None
            else:
                logger.error(f"Error from Claude API: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Request error with Claude API: {e}")
            return None
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            return None

    def _parse_analysis_result(self, response_text: str, original_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Claude API response into structured analysis

        Args:
            response_text: Raw API response
            original_message: Original message dict

        Returns:
            Parsed analysis dict or None
        """
        try:
            # Try to extract JSON from response
            # Sometimes Claude wraps JSON in markdown code blocks
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response_text

            # Parse JSON
            analysis = json.loads(json_str)

            # Add original message metadata
            analysis['original_message'] = original_message
            analysis['message_id'] = original_message.get('id', '')
            analysis['sender_name'] = original_message.get('sender_name', 'Unknown')
            analysis['group_name'] = original_message.get('group_name', 'Unknown Group')
            analysis['timestamp'] = original_message.get('timestamp', '')

            # Validate required fields
            required_fields = ['is_action_item', 'confidence', 'type']
            for field in required_fields:
                if field not in analysis:
                    logger.error(f"Missing required field '{field}' in AI response")
                    return None

            # Ensure confidence is an integer
            analysis['confidence'] = int(analysis.get('confidence', 0))

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Claude response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing analysis result: {e}")
            return None

    def record_feedback(self, detection: Dict[str, Any], user_approved: bool, user_feedback: str = ""):
        """
        Record user feedback for learning

        Args:
            detection: Original detection dict
            user_approved: True if user approved the task creation
            user_feedback: Optional feedback text
        """
        if not self.learning_engine:
            return

        try:
            self.learning_engine.record_feedback(
                detection=detection,
                user_approved=user_approved,
                user_feedback=user_feedback
            )

            # Reload learning examples periodically
            if self.learning_engine.get_feedback_count() % 5 == 0:
                logger.info("Reloading learning examples after 5 new feedbacks")
                self._load_learning_examples()

        except Exception as e:
            logger.error(f"Error recording feedback: {e}")

    def get_daily_stats(self) -> Dict[str, Any]:
        """
        Get daily statistics for AI detection

        Returns:
            Stats dictionary
        """
        return {
            'api_calls_today': self.daily_api_calls,
            'budget': self.daily_budget,
            'budget_remaining': max(0, self.daily_budget - self.daily_api_calls),
            'budget_used_percent': round((self.daily_api_calls / self.daily_budget) * 100, 1),
            'cache_size': len(self.analysis_cache),
            'positive_examples': len(self.positive_examples),
            'negative_examples': len(self.negative_examples)
        }


def create_from_env() -> Optional[AITaskDetector]:
    """
    Create AITaskDetector from environment variables

    Returns:
        AITaskDetector instance or None if disabled
    """
    config = {
        "enabled": os.environ.get("AI_TASK_DETECTION_ENABLED", "false").lower() == "true",
        "claude_api_key": os.environ.get("CLAUDE_API_KEY", ""),
        "claude_api_url": os.environ.get("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages"),
        "claude_model": os.environ.get("CLAUDE_MODEL", "claude-3-sonnet-20240229"),
        "confidence_threshold": int(os.environ.get("AI_CONFIDENCE_THRESHOLD", "50")),
        "min_message_length": int(os.environ.get("AI_MIN_MESSAGE_LENGTH", "10")),
        "batch_analysis": os.environ.get("AI_BATCH_ANALYSIS", "true").lower() == "true",
        "batch_size": int(os.environ.get("AI_BATCH_SIZE", "10")),
        "daily_budget": int(os.environ.get("AI_DAILY_BUDGET", "500")),
        "learning_enabled": os.environ.get("AI_LEARNING_ENABLED", "true").lower() == "true",
        "learning_db_path": os.environ.get("AI_LEARNING_DB_PATH", "data/task_detection_history.db")
    }

    return AITaskDetector(config)
