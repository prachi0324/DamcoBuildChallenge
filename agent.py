"""
agent.py — LangChain + Groq chains for Week Planner Bot.

7 chains:
1. PlannerChain     — Generate structured weekly plan
2. ModifyChain      — Flexible plan modification
3. TodayChain       — Extract today's focus from plan
4. SummaryChain     — Summarize past weeks from RAG
5. InsightsChain    — Productivity pattern analysis
6. MonthChain       — Full month overview
7. NaturalChain     — Handle any natural language query or update

All chains use retry logic for resilience.
"""

import logging
import time
from datetime import datetime, timedelta
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag_store import (
    retrieve_past_context,
    retrieve_all_month_plans,
    save_plan,
    get_week_key,
    get_week_label
)
from config import (
    GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE,
    MAX_RETRIES, RETRY_DELAY, UPDATE_KEYWORDS
)

logger = logging.getLogger(__name__)


def get_llm() -> ChatGroq:
    """Initialize Groq LLM."""
    return ChatGroq(
        model=LLM_MODEL,
        api_key=GROQ_API_KEY,
        temperature=LLM_TEMPERATURE
    )


def invoke_with_retry(chain, inputs: dict) -> str:
    """Invoke a LangChain chain with exponential backoff retry."""
    for attempt in range(MAX_RETRIES):
        try:
            return chain.invoke(inputs)
        except Exception as e:
            logger.warning(f"Chain invoke attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)
    raise Exception(f"Chain failed after {MAX_RETRIES} attempts.")


# ── Chain 1: Weekly Plan Generator ────────────────────────────────────────

PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a smart weekly planner assistant.
Create a structured realistic week plan.
Today is {today} ({weekday}).
This plan is for: {week_label}

PAST CONTEXT (RAG memory from previous weeks):
{past_context}

Carry forward any incomplete tasks from past context.

USE THIS EXACT FORMAT:
━━━━━━━━━━━━━━━━━━━━━━
📅 WEEK PLAN — {week_label}
━━━━━━━━━━━━━━━━━━━━━━

📌 Monday
  ⏰ [time if known] — [task] [🔴 if high priority]
  ⏰ [time] — [task]

📌 Tuesday
  ⏰ [time] — [task]

📌 Wednesday
  ⏰ [time] — [task]

📌 Thursday
  ⏰ [time] — [task]

📌 Friday
  ⏰ [time] — [task]

📌 Weekend 🌿
  • [task or Rest and recharge]

━━━━━━━━━━━━━━━━━━━━━━
🎯 TOP PRIORITIES
  1️⃣ [priority]
  2️⃣ [priority]
  3️⃣ [priority]

💡 TIP: [one specific productivity tip based on their schedule]
━━━━━━━━━━━━━━━━━━━━━━
"""),
    ("human", "My tasks for {week_label}:\n{user_input}")
])


def generate_plan(user_id: str, user_input: str, week_offset: int = 0) -> tuple[str, str]:
    """
    Generate a weekly plan using RAG context from past weeks.

    Args:
        user_id: Telegram user ID
        user_input: Raw task list from user
        week_offset: 0=this week, 1=next week, 2=week after, etc.

    Returns:
        Tuple of (plan_text, week_label)
    """
    target_date = datetime.now() + timedelta(weeks=week_offset)
    week_key = get_week_key(target_date)
    week_label = get_week_label(target_date)
    past_context = retrieve_past_context(user_id, user_input)

    chain = PLANNER_PROMPT | get_llm() | StrOutputParser()
    result = invoke_with_retry(chain, {
        "user_input": user_input,
        "past_context": past_context,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "weekday": datetime.now().strftime("%A"),
        "week_label": week_label
    })

    save_plan(user_id, result, user_input, week_key)
    return result, week_label


# ── Chain 2: Plan Modifier ─────────────────────────────────────────────────

MODIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a planner assistant.
Apply EXACTLY what the user asks — reschedule, add, remove, rename, move anything.
Do NOT restrict what changes are allowed.
Return the FULL updated week plan in the same format.
At the end add one line: ✅ Updated: [brief summary of change]
"""),
    ("human", "Current plan:\n{current_plan}\n\nUser request: {modification}\n\nReturn complete updated plan.")
])


def modify_plan(current_plan: str, modification: str) -> str:
    """Apply any modification to an existing plan."""
    chain = MODIFY_PROMPT | get_llm() | StrOutputParser()
    return invoke_with_retry(chain, {
        "current_plan": current_plan,
        "modification": modification
    })


# ── Chain 3: Today Focus ───────────────────────────────────────────────────

TODAY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a daily focus assistant.
Extract only today's tasks from the week plan.
Today is {today} ({weekday}).
Show tasks in priority order. Be concise and motivating. Use emojis.
If no tasks found for today, say so clearly.
"""),
    ("human", "Full week plan:\n{current_plan}\n\nWhat should I focus on today?")
])


def get_today_focus(user_id: str, current_plan: str = None) -> str:
    """Get today's tasks — falls back to RAG if no session plan."""
    if not current_plan:
        current_plan = retrieve_past_context(user_id, "week plan tasks schedule", k=1)
        if "No past plans" in current_plan:
            return "No plan found. Use /plan first to create your week plan!"

    chain = TODAY_PROMPT | get_llm() | StrOutputParser()
    return invoke_with_retry(chain, {
        "current_plan": current_plan,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "weekday": datetime.now().strftime("%A")
    })


# ── Chain 4: Past Weeks Summary ────────────────────────────────────────────

SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a weekly review assistant.
Based on the user's past week plans, provide:
- What they typically work on
- Recurring commitments
- Tasks that kept appearing (likely incomplete/blocked)
Keep it under 6 bullet points. Be specific. Use emojis.
"""),
    ("human", "Past plans from memory:\n{past_context}")
])


def get_summary(user_id: str) -> str:
    """Summarize past weeks from RAG store."""
    past_context = retrieve_past_context(user_id, "weekly tasks summary history recurring", k=4)
    if "No past plans" in past_context:
        return "📭 No past plans found yet. Use /plan first to start building your history!"

    chain = SUMMARY_PROMPT | get_llm() | StrOutputParser()
    return invoke_with_retry(chain, {"past_context": past_context})


# ── Chain 5: Productivity Insights ────────────────────────────────────────

INSIGHTS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a productivity coach.
Analyze the user's past weekly plans and provide 3-4 specific insights:
- Days consistently overloaded
- Tasks that repeat every week (habits or blockers?)
- What keeps getting pushed/delayed
- Scheduling patterns worth fixing
Format:
🔍 PRODUCTIVITY INSIGHTS

📊 Pattern 1: [observation]
→ Recommendation: [action]

📊 Pattern 2: [observation]
→ Recommendation: [action]

Be direct, specific and actionable.
"""),
    ("human", "Past weekly plans:\n{past_context}")
])


def get_insights(user_id: str) -> str:
    """Analyze productivity patterns from RAG history."""
    past_context = retrieve_past_context(
        user_id, "weekly patterns productivity habits recurring tasks", k=5
    )
    if "No past plans" in past_context:
        return "📭 Not enough history yet. Use /plan for a few weeks first — then I can spot your patterns!"

    chain = INSIGHTS_PROMPT | get_llm() | StrOutputParser()
    return invoke_with_retry(chain, {"past_context": past_context})


# ── Chain 6: Monthly Overview ──────────────────────────────────────────────

MONTH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a monthly planner assistant.
The user has plans stored for multiple weeks.
Create a clean monthly overview showing:
- Each week and its key tasks/highlights
- Overall priorities across the month
- Any patterns or overloaded periods
Format cleanly with week separators. Use emojis.
"""),
    ("human", "All week plans this month:\n{all_plans}")
])


def get_month_overview(user_id: str) -> str:
    """Build a monthly overview from all stored week plans."""
    all_plans = retrieve_all_month_plans(user_id)
    if "No plans" in all_plans:
        return "📭 No plans found yet. Use /plan to start planning your weeks!"

    chain = MONTH_PROMPT | get_llm() | StrOutputParser()
    return invoke_with_retry(chain, {"all_plans": all_plans})


# ── Chain 7: Natural Language Handler ─────────────────────────────────────

NATURAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a smart week planner assistant.
Today is {today} — {weekday}.
Tomorrow is {tomorrow} — {tomorrow_day}.

User's week plan:
{current_plan}

Rules:
- NEVER assume any default day — always use dates provided above
- If asked about today → show {weekday} tasks only
- If asked about tomorrow → show {tomorrow_day} tasks only
- If asked about a specific day → show only that day's tasks
- If asked what's pending → summarize unfinished items
- If asked if free on a day → check plan and answer honestly
- Be conversational, concise and use emojis
"""),
    ("human", "{user_message}")
])


def answer_natural_query(user_id: str, user_message: str, user_sessions: dict) -> str:
    """
    Handle any natural language query or update request.

    Automatically detects:
    - Update intent → routes to modify_plan
    - Query intent → routes to natural language chain
    """
    current_plan = user_sessions.get(user_id, None)
    if not current_plan:
        current_plan = retrieve_past_context(user_id, user_message, k=1)
        if "No past plans" in current_plan:
            return "📭 No plan found yet! Use /plan to create your week plan first."

    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    is_update = any(kw in user_message.lower() for kw in UPDATE_KEYWORDS)

    if is_update:
        updated_plan = modify_plan(current_plan, user_message)
        user_sessions[user_id] = updated_plan
        return updated_plan
    else:
        chain = NATURAL_PROMPT | get_llm() | StrOutputParser()
        return invoke_with_retry(chain, {
            "user_message": user_message,
            "current_plan": current_plan,
            "today": today.strftime("%Y-%m-%d"),
            "weekday": today.strftime("%A"),
            "tomorrow": tomorrow.strftime("%Y-%m-%d"),
            "tomorrow_day": tomorrow.strftime("%A")
        })
