"""
bot.py — Telegram bot handlers for Week Planner Bot.

Commands:
    /start   — Welcome message + command list
    /plan    — Create weekly plan (with week selector)
    /modify  — Modify current plan
    /today   — Today's focus (date-aware)
    /summary — Past weeks summary from RAG
    /insights — Productivity pattern analysis
    /month   — Full month overview
    /help    — Show all commands

Natural language:
    Anything typed is handled by the NaturalChain —
    queries ("what do I have tomorrow?") and updates
    ("reschedule standup to 12pm") are auto-detected.
"""

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from agent import (
    generate_plan,
    modify_plan,
    get_today_focus,
    get_summary,
    get_insights,
    get_month_overview,
    answer_natural_query
)
from rag_store import get_week_label
from config import (
    TELEGRAM_BOT_TOKEN,
    WAITING_FOR_TASKS,
    WAITING_FOR_MODIFICATION,
    WAITING_FOR_WEEK_TASKS
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)

# In-memory session store: user_id → current plan text
user_sessions: dict[str, str] = {}

# Track selected week offset per user
user_week_offset: dict[str, int] = {}


# ── /start and /help ───────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Week Planner Bot!\n\n"
        "I plan your week using AI and get smarter every week by remembering your history!\n\n"
        "🚀 Commands:\n"
        "/plan — Create a week plan\n"
        "/modify — Modify current plan\n"
        "/today — Today's focus (date-aware)\n"
        "/summary — Past weeks summary\n"
        "/insights — AI productivity insights\n"
        "/month — Full month overview\n"
        "/help — Show this message\n\n"
        "💬 Or just type anything:\n"
        "• What do I have tomorrow?\n"
        "• Reschedule my standup to 12pm\n"
        "• Am I free on Wednesday?\n"
        "• What's pending this week?"
    )


# ── /plan ──────────────────────────────────────────────────────────────────

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 This Week", callback_data="week_0")],
        [InlineKeyboardButton("📅 Next Week", callback_data="week_1")],
        [InlineKeyboardButton("📅 Week After Next", callback_data="week_2")],
        [InlineKeyboardButton("📅 Week 4 of Month", callback_data="week_3")]
    ]
    await update.message.reply_text(
        "Which week would you like to plan?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def week_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    week_offset = int(query.data.split("_")[1])
    user_week_offset[user_id] = week_offset

    target_date = datetime.now() + timedelta(weeks=week_offset)
    week_label = get_week_label(target_date)

    await query.edit_message_text(
        f"📅 Planning for: {week_label}\n\n"
        "Tell me your tasks, meetings and deadlines:\n\n"
        "Example: Presentation Monday 2pm, dentist Tuesday, "
        "project deadline Friday, gym Tuesday and Friday"
    )
    return WAITING_FOR_WEEK_TASKS


async def receive_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_input = update.message.text
    week_offset = user_week_offset.get(user_id, 0)
    target_date = datetime.now() + timedelta(weeks=week_offset)
    week_label = get_week_label(target_date)

    await update.message.reply_text(
        f"⚙️ Building plan for {week_label}...\n"
        "Checking your past weeks for context..."
    )

    try:
        plan, label = generate_plan(user_id, user_input, week_offset)
        user_sessions[user_id] = plan
        await update.message.reply_text(plan)
        await update.message.reply_text(
            f"✅ Plan for {label} saved to memory!\n\n"
            "Try:\n"
            "• /plan again to add another week\n"
            "• /month to see all your weeks\n"
            "• Just ask: What do I have today?"
        )
    except Exception as e:
        logger.error(f"Plan generation failed for {user_id}: {e}")
        await update.message.reply_text(
            f"❌ Sorry, something went wrong. Please try again.\nError: {str(e)}"
        )

    return ConversationHandler.END


# ── /modify ────────────────────────────────────────────────────────────────

async def modify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in user_sessions:
        await update.message.reply_text(
            "⚠️ No plan found in current session.\n"
            "Use /plan to create one first."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "✏️ What would you like to change?\n\n"
        "Examples:\n"
        "• Reschedule standup to 12pm tomorrow\n"
        "• Move dentist to Thursday\n"
        "• Add gym Wednesday 7am\n"
        "• Cancel Friday deployment\n"
        "• Remove all weekend tasks"
    )
    return WAITING_FOR_MODIFICATION


async def receive_modification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    modification = update.message.text
    current_plan = user_sessions.get(user_id, "")

    await update.message.reply_text("⚙️ Updating your plan...")

    try:
        updated_plan = modify_plan(current_plan, modification)
        user_sessions[user_id] = updated_plan
        await update.message.reply_text(updated_plan)
        await update.message.reply_text(
            "✅ Plan updated!\nUse /modify again for more changes."
        )
    except Exception as e:
        logger.error(f"Modification failed for {user_id}: {e}")
        await update.message.reply_text(f"❌ Could not update plan. Please try again.")

    return ConversationHandler.END


# ── /today ─────────────────────────────────────────────────────────────────

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await update.message.reply_text("🔍 Finding today's focus...")

    try:
        current_plan = user_sessions.get(user_id, None)
        today_focus = get_today_focus(user_id, current_plan)
        await update.message.reply_text(
            f"📅 TODAY — {datetime.now().strftime('%A, %B %d')}\n\n{today_focus}"
        )
    except Exception as e:
        logger.error(f"Today focus failed for {user_id}: {e}")
        await update.message.reply_text("❌ Could not retrieve today's focus. Please try again.")


# ── /summary ───────────────────────────────────────────────────────────────

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await update.message.reply_text("🔍 Checking your past weeks from memory...")

    try:
        summary = get_summary(user_id)
        await update.message.reply_text(f"📚 YOUR PAST WEEKS SUMMARY\n\n{summary}")
    except Exception as e:
        logger.error(f"Summary failed for {user_id}: {e}")
        await update.message.reply_text("❌ Could not retrieve summary. Please try again.")


# ── /insights ──────────────────────────────────────────────────────────────

async def insights_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await update.message.reply_text("🧠 Analyzing your productivity patterns...")

    try:
        insights = get_insights(user_id)
        await update.message.reply_text(insights)
    except Exception as e:
        logger.error(f"Insights failed for {user_id}: {e}")
        await update.message.reply_text("❌ Could not generate insights. Please try again.")


# ── /month ─────────────────────────────────────────────────────────────────

async def month_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await update.message.reply_text("📆 Building your monthly overview from memory...")

    try:
        overview = get_month_overview(user_id)
        await update.message.reply_text(f"📆 MONTHLY OVERVIEW\n\n{overview}")
    except Exception as e:
        logger.error(f"Month overview failed for {user_id}: {e}")
        await update.message.reply_text("❌ Could not retrieve monthly overview. Please try again.")


# ── Natural language fallback ──────────────────────────────────────────────

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text
    await update.message.reply_text("🤔 Let me check your plan...")

    try:
        response = answer_natural_query(user_id, user_message, user_sessions)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Natural query failed for {user_id}: {e}")
        await update.message.reply_text(
            "❌ Sorry, I couldn't process that. Try /help to see available commands."
        )


# ── Build application ──────────────────────────────────────────────────────

def build_app() -> Application:
    """Build and configure the Telegram bot application."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    plan_conv = ConversationHandler(
        entry_points=[CommandHandler("plan", plan_command)],
        states={
            WAITING_FOR_WEEK_TASKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tasks)
            ]
        },
        fallbacks=[CommandHandler("help", start)]
    )

    modify_conv = ConversationHandler(
        entry_points=[CommandHandler("modify", modify_command)],
        states={
            WAITING_FOR_MODIFICATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_modification)
            ]
        },
        fallbacks=[CommandHandler("help", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("summary", summary_command))
    app.add_handler(CommandHandler("insights", insights_command))
    app.add_handler(CommandHandler("month", month_command))
    app.add_handler(CallbackQueryHandler(week_selected, pattern="^week_"))
    app.add_handler(plan_conv)
    app.add_handler(modify_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    return app


if __name__ == "__main__":
    logger.info("Starting Week Planner Bot...")
    app = build_app()
    app.run_polling(drop_pending_updates=True)
