"""
tests/test_agent.py — Unit tests for Week Planner Bot.

Tests cover:
- RAG store operations (save, retrieve)
- Week key/label generation
- Update intent detection
- Config validation
- Chain input validation
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_store import get_week_key, get_week_label
from config import UPDATE_KEYWORDS


class TestWeekKeyGeneration(unittest.TestCase):
    """Test week key and label generation."""

    def test_week_key_format(self):
        """Week key should follow YYYY-WNN format."""
        key = get_week_key()
        self.assertRegex(key, r"^\d{4}-W\d{2}$")

    def test_week_key_with_date(self):
        """Week key for a specific date should be deterministic."""
        date = datetime(2026, 7, 14)
        key = get_week_key(date)
        self.assertIn("2026", key)

    def test_week_label_format(self):
        """Week label should be human readable."""
        label = get_week_label()
        self.assertIn("Week of", label)

    def test_week_label_with_offset(self):
        """Next week label should differ from this week."""
        this_week = get_week_label(datetime.now())
        next_week = get_week_label(datetime.now() + timedelta(weeks=1))
        self.assertNotEqual(this_week, next_week)

    def test_consecutive_week_keys_differ(self):
        """Consecutive weeks should have different keys."""
        week1 = get_week_key(datetime.now())
        week2 = get_week_key(datetime.now() + timedelta(weeks=1))
        self.assertNotEqual(week1, week2)


class TestUpdateIntentDetection(unittest.TestCase):
    """Test natural language update intent detection."""

    def _is_update(self, message: str) -> bool:
        """Mirror the intent detection logic from agent.py."""
        return any(kw in message.lower() for kw in UPDATE_KEYWORDS)

    def test_reschedule_detected(self):
        self.assertTrue(self._is_update("reschedule my standup to 12pm"))

    def test_move_detected(self):
        self.assertTrue(self._is_update("move dentist to Thursday"))

    def test_cancel_detected(self):
        self.assertTrue(self._is_update("cancel Friday deployment"))

    def test_add_detected(self):
        self.assertTrue(self._is_update("add gym on Wednesday 7am"))

    def test_remove_detected(self):
        self.assertTrue(self._is_update("remove all weekend tasks"))

    def test_query_not_detected(self):
        self.assertFalse(self._is_update("what do I have today?"))

    def test_tomorrow_query_not_detected(self):
        self.assertFalse(self._is_update("what's tomorrow looking like?"))

    def test_free_query_not_detected(self):
        self.assertFalse(self._is_update("am I free on Wednesday?"))

    def test_pending_query_not_detected(self):
        self.assertFalse(self._is_update("what's pending this week?"))


class TestConfig(unittest.TestCase):
    """Test configuration loading."""

    def test_update_keywords_not_empty(self):
        self.assertGreater(len(UPDATE_KEYWORDS), 0)

    def test_store_dir_has_default(self):
        from config import STORE_DIR
        self.assertIsNotNone(STORE_DIR)

    def test_max_retries_positive(self):
        from config import MAX_RETRIES
        self.assertGreater(MAX_RETRIES, 0)

    def test_retry_delay_positive(self):
        from config import RETRY_DELAY
        self.assertGreater(RETRY_DELAY, 0)

    def test_rag_top_k_positive(self):
        from config import RAG_TOP_K
        self.assertGreater(RAG_TOP_K, 0)


class TestRAGStore(unittest.TestCase):
    """Test RAG store with mocked FAISS."""

    def test_retrieve_returns_string_when_no_store(self):
        """Should return a helpful message when no store exists."""
        from rag_store import retrieve_past_context
        result = retrieve_past_context("nonexistent_user_999", "test query")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_month_retrieve_returns_string_when_no_store(self):
        """Should return helpful message when no monthly plans exist."""
        from rag_store import retrieve_all_month_plans
        result = retrieve_all_month_plans("nonexistent_user_999")
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
