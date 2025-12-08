#!/usr/bin/env python3
"""
Learning Engine for AI Task Detection

Tracks user feedback (approvals/rejections) and uses it to improve
AI detection accuracy over time through few-shot learning.
"""

import os
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger("whatsapp_monitoring.learning_engine")


class LearningEngine:
    """Manages learning database and feedback tracking"""

    def __init__(self, db_path: str):
        """
        Initialize learning engine

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"Learning engine initialized with database: {db_path}")

    def _init_database(self):
        """Create database tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Detection history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detection_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT,
                    message_content TEXT,
                    sender_name TEXT,
                    group_name TEXT,
                    timestamp TEXT,

                    -- AI Detection
                    ai_detected BOOLEAN,
                    ai_confidence INTEGER,
                    ai_subject TEXT,
                    ai_type TEXT,
                    ai_assignee TEXT,
                    ai_due_date TEXT,
                    ai_priority TEXT,
                    ai_reasoning TEXT,

                    -- User Feedback
                    user_approved BOOLEAN,
                    user_action TEXT,
                    user_feedback TEXT,
                    final_task_id TEXT,

                    -- Learning
                    was_correct BOOLEAN,
                    learned_from BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Learned patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT,
                    pattern TEXT,
                    action TEXT,
                    examples INTEGER DEFAULT 1,
                    accuracy REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Assignee mappings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assignee_mappings (
                    whatsapp_name TEXT PRIMARY KEY,
                    erpnext_email TEXT,
                    confidence INTEGER,
                    confirmed_count INTEGER DEFAULT 1,
                    last_confirmed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_stats (
                    date TEXT PRIMARY KEY,
                    total_detections INTEGER DEFAULT 0,
                    approved INTEGER DEFAULT 0,
                    rejected INTEGER DEFAULT 0,
                    accuracy REAL,
                    avg_confidence REAL
                )
            """)

            # Pending suggestions table (persists across sessions)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_num INTEGER NOT NULL,
                    message_id TEXT UNIQUE,
                    message_content TEXT,
                    sender_name TEXT,
                    sender_id TEXT,
                    group_name TEXT,
                    group_jid TEXT,
                    message_timestamp TEXT,

                    -- AI Detection results
                    ai_subject TEXT,
                    ai_type TEXT,
                    ai_confidence INTEGER,
                    ai_priority TEXT,
                    ai_due_date TEXT,
                    ai_assignee_mentions TEXT,
                    ai_reasoning TEXT,

                    -- Status tracking
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    responded_at TIMESTAMP,
                    final_task_id TEXT
                )
            """)

            # Task number counter table (persists the daily counter)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_counter (
                    date TEXT PRIMARY KEY,
                    last_num INTEGER DEFAULT 0
                )
            """)

            conn.commit()
            logger.info("Database tables initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

        finally:
            if 'conn' in locals():
                conn.close()

    def record_feedback(self, detection: Dict[str, Any], user_approved: bool,
                       user_feedback: str = "", final_task_id: str = ""):
        """
        Record user feedback for a detection

        Args:
            detection: Original detection dictionary
            user_approved: True if user approved task creation
            user_feedback: Optional user feedback text
            final_task_id: ERPNext task ID if created
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Extract detection details
            message_content = detection.get('original_message', {}).get('content', '')
            sender_name = detection.get('sender_name', 'Unknown')
            group_name = detection.get('group_name', 'Unknown')
            timestamp = detection.get('timestamp', '')

            ai_detected = detection.get('is_action_item', False)
            ai_confidence = detection.get('confidence', 0)
            ai_subject = detection.get('subject', '')
            ai_type = detection.get('type', '')
            ai_assignee = ','.join(detection.get('assignee_mentions', []))
            ai_due_date = detection.get('due_date', '')
            ai_priority = detection.get('priority', '')
            ai_reasoning = detection.get('reasoning', '')

            # Determine if AI was correct
            was_correct = ai_detected == user_approved

            # Insert into database
            cursor.execute("""
                INSERT INTO detection_history (
                    message_id, message_content, sender_name, group_name, timestamp,
                    ai_detected, ai_confidence, ai_subject, ai_type, ai_assignee,
                    ai_due_date, ai_priority, ai_reasoning,
                    user_approved, user_action, user_feedback, final_task_id, was_correct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                detection.get('message_id', ''),
                message_content,
                sender_name,
                group_name,
                timestamp,
                ai_detected,
                ai_confidence,
                ai_subject,
                ai_type,
                ai_assignee,
                ai_due_date,
                ai_priority,
                ai_reasoning,
                user_approved,
                'approved' if user_approved else 'rejected',
                user_feedback,
                final_task_id,
                was_correct
            ))

            conn.commit()

            # Update daily stats
            self._update_daily_stats(user_approved, ai_confidence)

            logger.info(
                f"Recorded feedback: approved={user_approved}, "
                f"was_correct={was_correct}, confidence={ai_confidence}%"
            )

            # Learn from feedback
            if user_approved:
                self._learn_positive_pattern(message_content, ai_type)
            else:
                self._learn_negative_pattern(message_content, ai_type)

        except Exception as e:
            logger.error(f"Error recording feedback: {e}")

        finally:
            if 'conn' in locals():
                conn.close()

    def _update_daily_stats(self, approved: bool, confidence: int):
        """Update daily statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')

            # Get current stats
            cursor.execute("SELECT * FROM learning_stats WHERE date = ?", (today,))
            result = cursor.fetchone()

            if result:
                # Update existing
                total = result[1] + 1
                approved_count = result[2] + (1 if approved else 0)
                rejected_count = result[3] + (0 if approved else 1)
                accuracy = (approved_count / total) * 100
                avg_conf = ((result[5] * (total - 1)) + confidence) / total

                cursor.execute("""
                    UPDATE learning_stats
                    SET total_detections = ?,
                        approved = ?,
                        rejected = ?,
                        accuracy = ?,
                        avg_confidence = ?
                    WHERE date = ?
                """, (total, approved_count, rejected_count, accuracy, avg_conf, today))
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO learning_stats (date, total_detections, approved, rejected, accuracy, avg_confidence)
                    VALUES (?, 1, ?, ?, 100.0, ?)
                """, (today, 1 if approved else 0, 0 if approved else 1, confidence))

            conn.commit()

        except Exception as e:
            logger.error(f"Error updating daily stats: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    def _learn_positive_pattern(self, message_content: str, msg_type: str):
        """Learn from approved detection"""
        # Extract patterns from approved messages
        # This is a simplified version - can be enhanced with NLP
        pass

    def _learn_negative_pattern(self, message_content: str, msg_type: str):
        """Learn from rejected detection"""
        # Extract patterns from rejected messages
        pass

    def get_top_examples(self, approved: bool, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top examples for few-shot learning

        Args:
            approved: True for approved examples, False for rejected
            limit: Maximum number of examples

        Returns:
            List of example dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get high-confidence examples
            cursor.execute("""
                SELECT
                    message_content, sender_name, group_name,
                    ai_confidence, ai_subject, ai_type, ai_reasoning
                FROM detection_history
                WHERE user_approved = ? AND was_correct = 1
                ORDER BY ai_confidence DESC, created_at DESC
                LIMIT ?
            """, (approved, limit))

            results = cursor.fetchall()

            examples = []
            for row in results:
                examples.append({
                    'message_content': row[0],
                    'sender_name': row[1],
                    'group_name': row[2],
                    'ai_confidence': row[3],
                    'ai_subject': row[4],
                    'ai_type': row[5],
                    'ai_reasoning': row[6]
                })

            return examples

        except Exception as e:
            logger.error(f"Error getting examples: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()

    def get_accuracy_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get accuracy statistics for the last N days

        Args:
            days: Number of days to include

        Returns:
            Statistics dictionary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Overall accuracy
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct,
                    AVG(ai_confidence) as avg_confidence,
                    SUM(CASE WHEN user_approved THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN NOT user_approved THEN 1 ELSE 0 END) as rejected
                FROM detection_history
                WHERE created_at >= datetime('now', '-' || ? || ' days')
            """, (days,))

            result = cursor.fetchone()

            if result and result[0] > 0:
                total = result[0]
                correct = result[1] or 0
                accuracy = (correct / total) * 100

                return {
                    'total_detections': total,
                    'correct_predictions': correct,
                    'accuracy': round(accuracy, 1),
                    'avg_confidence': round(result[2] or 0, 1),
                    'approved': result[3] or 0,
                    'rejected': result[4] or 0,
                    'approval_rate': round((result[3] or 0) / total * 100, 1)
                }
            else:
                return {
                    'total_detections': 0,
                    'correct_predictions': 0,
                    'accuracy': 0,
                    'avg_confidence': 0,
                    'approved': 0,
                    'rejected': 0,
                    'approval_rate': 0
                }

        except Exception as e:
            logger.error(f"Error getting accuracy stats: {e}")
            return {}
        finally:
            if 'conn' in locals():
                conn.close()

    def get_feedback_count(self) -> int:
        """Get total number of feedback entries"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM detection_history")
            result = cursor.fetchone()

            return result[0] if result else 0

        except Exception as e:
            logger.error(f"Error getting feedback count: {e}")
            return 0
        finally:
            if 'conn' in locals():
                conn.close()

    def save_assignee_mapping(self, whatsapp_name: str, erpnext_email: str):
        """
        Save confirmed assignee mapping

        Args:
            whatsapp_name: WhatsApp display name
            erpnext_email: ERPNext user email
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO assignee_mappings (whatsapp_name, erpnext_email, confidence, confirmed_count)
                VALUES (?, ?, 100, 1)
                ON CONFLICT(whatsapp_name) DO UPDATE SET
                    confirmed_count = confirmed_count + 1,
                    last_confirmed = CURRENT_TIMESTAMP
            """, (whatsapp_name, erpnext_email))

            conn.commit()
            logger.info(f"Saved assignee mapping: {whatsapp_name} -> {erpnext_email}")

        except Exception as e:
            logger.error(f"Error saving assignee mapping: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    def get_assignee_mapping(self, whatsapp_name: str) -> Optional[str]:
        """
        Get ERPNext email for a WhatsApp name

        Args:
            whatsapp_name: WhatsApp display name

        Returns:
            ERPNext email or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT erpnext_email
                FROM assignee_mappings
                WHERE whatsapp_name = ?
            """, (whatsapp_name,))

            result = cursor.fetchone()
            return result[0] if result else None

        except Exception as e:
            logger.error(f"Error getting assignee mapping: {e}")
            return None
        finally:
            if 'conn' in locals():
                conn.close()

    # =========================================================================
    # Pending Suggestions Management (persists across sessions)
    # =========================================================================

    def get_next_task_num(self) -> int:
        """
        Get next task number for this month (persists across sessions)
        Task numbers reset at the start of each month.

        Returns:
            Next task number
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Use monthly key format (YYYY-MM) instead of daily
            this_month = datetime.now().strftime("%Y-%m")

            # Get or create counter for this month
            cursor.execute("""
                INSERT INTO task_counter (date, last_num)
                VALUES (?, 0)
                ON CONFLICT(date) DO UPDATE SET last_num = last_num + 1
                RETURNING last_num
            """, (this_month,))

            result = cursor.fetchone()
            if result:
                task_num = result[0] + 1
            else:
                # Fallback for older SQLite without RETURNING
                cursor.execute("""
                    UPDATE task_counter SET last_num = last_num + 1 WHERE date = ?
                """, (this_month,))
                cursor.execute("SELECT last_num FROM task_counter WHERE date = ?", (this_month,))
                result = cursor.fetchone()
                task_num = result[0] if result else 1

            conn.commit()
            return task_num

        except Exception as e:
            logger.error(f"Error getting next task num: {e}")
            return 1
        finally:
            if 'conn' in locals():
                conn.close()

    def save_pending_suggestion(self, task_num: int, detection: Dict[str, Any]) -> bool:
        """
        Save a pending task suggestion to database

        Args:
            task_num: Task number for this suggestion
            detection: AI detection result dict

        Returns:
            True if saved successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            original_msg = detection.get('original_message', {})

            cursor.execute("""
                INSERT OR REPLACE INTO pending_suggestions (
                    task_num, message_id, message_content,
                    sender_name, sender_id, group_name, group_jid, message_timestamp,
                    ai_subject, ai_type, ai_confidence, ai_priority,
                    ai_due_date, ai_assignee_mentions, ai_reasoning,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                task_num,
                detection.get('message_id', ''),
                original_msg.get('content', ''),
                detection.get('sender_name', ''),
                detection.get('sender_id', ''),
                detection.get('group_name', ''),
                detection.get('group_jid', ''),
                detection.get('timestamp', ''),
                detection.get('subject', ''),
                detection.get('type', ''),
                detection.get('confidence', 0),
                detection.get('priority', 'Medium'),
                detection.get('due_date', ''),
                ','.join(detection.get('assignee_mentions', [])),
                detection.get('reasoning', '')
            ))

            conn.commit()
            logger.info(f"Saved pending suggestion #{task_num}")
            return True

        except Exception as e:
            logger.error(f"Error saving pending suggestion: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def get_pending_suggestions(self) -> List[Dict[str, Any]]:
        """
        Get all pending suggestions from database

        Returns:
            List of pending suggestion dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM pending_suggestions
                WHERE status = 'pending'
                ORDER BY task_num ASC
            """)

            rows = cursor.fetchall()
            suggestions = []

            for row in rows:
                suggestions.append({
                    'task_num': row['task_num'],
                    'message_id': row['message_id'],
                    'detection': {
                        'message_id': row['message_id'],
                        'subject': row['ai_subject'],
                        'type': row['ai_type'],
                        'confidence': row['ai_confidence'],
                        'priority': row['ai_priority'],
                        'due_date': row['ai_due_date'],
                        'assignee_mentions': row['ai_assignee_mentions'].split(',') if row['ai_assignee_mentions'] else [],
                        'reasoning': row['ai_reasoning'],
                        'sender_name': row['sender_name'],
                        'sender_id': row['sender_id'],
                        'group_name': row['group_name'],
                        'group_jid': row['group_jid'],
                        'timestamp': row['message_timestamp'],
                        'original_message': {
                            'content': row['message_content']
                        },
                        'is_action_item': True
                    },
                    'created_at': row['created_at']
                })

            return suggestions

        except Exception as e:
            logger.error(f"Error getting pending suggestions: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()

    def update_suggestion_status(self, message_id: str, status: str,
                                  final_task_id: str = None) -> bool:
        """
        Update status of a pending suggestion

        Args:
            message_id: Message ID of the suggestion
            status: New status ('approved', 'rejected', 'expired')
            final_task_id: ERPNext task ID if created

        Returns:
            True if updated successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE pending_suggestions
                SET status = ?, responded_at = CURRENT_TIMESTAMP, final_task_id = ?
                WHERE message_id = ?
            """, (status, final_task_id, message_id))

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating suggestion status: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def get_suggestion_by_task_num(self, task_num: int) -> Optional[Dict[str, Any]]:
        """
        Get a pending suggestion by task number

        Args:
            task_num: Task number to look up

        Returns:
            Suggestion dict or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM pending_suggestions
                WHERE task_num = ? AND status = 'pending'
            """, (task_num,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'task_num': row['task_num'],
                'message_id': row['message_id'],
                'detection': {
                    'message_id': row['message_id'],
                    'subject': row['ai_subject'],
                    'type': row['ai_type'],
                    'confidence': row['ai_confidence'],
                    'priority': row['ai_priority'],
                    'due_date': row['ai_due_date'],
                    'assignee_mentions': row['ai_assignee_mentions'].split(',') if row['ai_assignee_mentions'] else [],
                    'reasoning': row['ai_reasoning'],
                    'sender_name': row['sender_name'],
                    'sender_id': row['sender_id'],
                    'group_name': row['group_name'],
                    'group_jid': row['group_jid'],
                    'timestamp': row['message_timestamp'],
                    'original_message': {
                        'content': row['message_content']
                    },
                    'is_action_item': True
                },
                'created_at': row['created_at']
            }

        except Exception as e:
            logger.error(f"Error getting suggestion by task num: {e}")
            return None
        finally:
            if 'conn' in locals():
                conn.close()

    def get_all_suggestions_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all suggestions (pending and processed) for review

        Args:
            limit: Maximum number of suggestions to return

        Returns:
            List of suggestion dicts with status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM pending_suggestions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting suggestions history: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()

    def purge_old_pending_suggestions(self, hours: int = 24) -> int:
        """
        Purge pending suggestions older than specified hours.
        These are suggestions that were never responded to (ignored).
        They are marked as 'expired' - NO learning happens from these.

        Args:
            hours: Age threshold in hours (default 24)

        Returns:
            Number of suggestions purged
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Mark old pending suggestions as expired (not rejected - no learning)
            cursor.execute("""
                UPDATE pending_suggestions
                SET status = 'expired', responded_at = CURRENT_TIMESTAMP
                WHERE status = 'pending'
                AND datetime(created_at, '+' || ? || ' hours') < datetime('now')
            """, (hours,))

            purged_count = cursor.rowcount
            conn.commit()

            if purged_count > 0:
                logger.info(f"Purged {purged_count} expired suggestions (older than {hours}h)")

            return purged_count

        except Exception as e:
            logger.error(f"Error purging old suggestions: {e}")
            return 0
        finally:
            if 'conn' in locals():
                conn.close()

    def get_pending_count(self) -> int:
        """Get count of pending suggestions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pending_suggestions WHERE status = 'pending'")
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting pending count: {e}")
            return 0
        finally:
            if 'conn' in locals():
                conn.close()
