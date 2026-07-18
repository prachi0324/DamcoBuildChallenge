"""
rag_store.py — FAISS-based RAG memory store.

Responsibilities:
- Embed and store weekly plans per user
- Retrieve relevant past context by semantic similarity
- Support week-keyed storage for monthly planning
- Persist to local disk (or Google Drive in Colab)
"""

import os
import logging
import time
from datetime import datetime, timedelta
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from config import STORE_DIR, EMBEDDING_MODEL, RAG_TOP_K, RAG_MONTH_TOP_K, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


def get_embeddings() -> HuggingFaceEmbeddings:
    """Initialize HuggingFace embeddings — local, free, no API key needed."""
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def get_week_key(date: datetime = None) -> str:
    """Return ISO week key e.g. '2026-W29'"""
    if date is None:
        date = datetime.now()
    return date.strftime("%Y-W%W")


def get_week_label(date: datetime = None) -> str:
    """Return human-readable week label e.g. 'Week of July 14, 2026'"""
    if date is None:
        date = datetime.now()
    return date.strftime("Week of %B %d, %Y")


def save_plan(user_id: str, plan_text: str, raw_input: str, week_key: str = None) -> bool:
    """
    Save a weekly plan to FAISS vector store.
    
    Args:
        user_id: Telegram user ID
        plan_text: Generated plan text
        raw_input: Original user input (tasks list)
        week_key: Optional week identifier e.g. '2026-W29'
    
    Returns:
        True if saved successfully, False otherwise
    """
    if week_key is None:
        week_key = get_week_key()

    for attempt in range(MAX_RETRIES):
        try:
            embeddings = get_embeddings()
            doc = Document(
                page_content=f"Week: {week_key}\nUser tasks: {raw_input}\nGenerated plan:\n{plan_text}",
                metadata={
                    "user_id": user_id,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "week_key": week_key
                }
            )
            store_path = os.path.join(STORE_DIR, user_id)

            if os.path.exists(os.path.join(store_path, "index.faiss")):
                db = FAISS.load_local(store_path, embeddings, allow_dangerous_deserialization=True)
                db.add_documents([doc])
            else:
                os.makedirs(store_path, exist_ok=True)
                db = FAISS.from_documents([doc], embeddings)

            db.save_local(store_path)
            logger.info(f"Plan saved for user {user_id}, week {week_key}")
            return True

        except Exception as e:
            logger.warning(f"Save attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    logger.error(f"Failed to save plan for user {user_id} after {MAX_RETRIES} attempts")
    return False


def retrieve_past_context(user_id: str, query: str, k: int = RAG_TOP_K) -> str:
    """
    Retrieve relevant past plans for a user via semantic similarity search.

    Args:
        user_id: Telegram user ID
        query: Search query (current week's tasks or question)
        k: Number of results to retrieve

    Returns:
        Formatted string of past plan excerpts with metadata
    """
    store_path = os.path.join(STORE_DIR, user_id)

    if not os.path.exists(os.path.join(store_path, "index.faiss")):
        return "No past plans found — this is the user's first plan."

    for attempt in range(MAX_RETRIES):
        try:
            embeddings = get_embeddings()
            db = FAISS.load_local(store_path, embeddings, allow_dangerous_deserialization=True)
            docs = db.similarity_search(query, k=k)

            if not docs:
                return "No relevant past context found."

            return "\n\n---\n\n".join([
                f"[Week: {doc.metadata.get('week_key')} | Date: {doc.metadata.get('date')}]\n{doc.page_content}"
                for doc in docs
            ])

        except Exception as e:
            logger.warning(f"Retrieve attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    return "Could not retrieve past context."


def retrieve_all_month_plans(user_id: str) -> str:
    """
    Retrieve all plans for a user (up to RAG_MONTH_TOP_K), deduplicated by week.

    Args:
        user_id: Telegram user ID

    Returns:
        Formatted string of all unique weekly plans
    """
    store_path = os.path.join(STORE_DIR, user_id)

    if not os.path.exists(os.path.join(store_path, "index.faiss")):
        return "No plans found yet."

    try:
        embeddings = get_embeddings()
        db = FAISS.load_local(store_path, embeddings, allow_dangerous_deserialization=True)
        docs = db.similarity_search("week plan schedule tasks", k=RAG_MONTH_TOP_K)

        seen = set()
        result = []
        for doc in docs:
            wk = doc.metadata.get("week_key", "unknown")
            if wk not in seen:
                seen.add(wk)
                result.append(f"[{wk}]\n{doc.page_content}")

        return "\n\n━━━━━━━━━━━━━━━\n\n".join(result) if result else "No plans found."

    except Exception as e:
        logger.error(f"Month retrieval failed: {e}")
        return f"Could not retrieve monthly plans: {str(e)}"
