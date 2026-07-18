"""
config.py — Central configuration for Week Planner Bot.
All constants, model names, paths, and settings in one place.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Model Config ───────────────────────────────────────
LLM_MODEL = "llama-3.1-8b-instant"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
LLM_TEMPERATURE = 0.7

# ── RAG Config ─────────────────────────────────────────
STORE_DIR = os.getenv("STORE_DIR", "./faiss_store")
RAG_TOP_K = 3
RAG_MONTH_TOP_K = 8

# ── Retry Config ───────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries

# ── Bot Conversation States ────────────────────────────
WAITING_FOR_TASKS = 1
WAITING_FOR_MODIFICATION = 2
WAITING_FOR_WEEK_TASKS = 3

# ── Update intent keywords ─────────────────────────────
UPDATE_KEYWORDS = [
    "update", "reschedule", "change", "move", "shift",
    "cancel", "add", "remove", "delete", "postpone",
    "push", "bring forward", "set", "modify", "swap",
    "replace", "edit", "adjust", "rebook"
]
