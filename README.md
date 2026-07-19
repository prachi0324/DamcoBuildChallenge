# 🗓️ Week Planner Bot — Damco Builder Challenge

> AI-powered Telegram bot that plans your week, remembers past weeks via RAG, and responds to natural language — built for the Damco Builder Challenge.

---

## Problem

Tasks scattered across WhatsApp, notes, and memory. No structure. By Wednesday everything's chaos. Existing tools like Notion or Google Calendar require manual input and give zero intelligence — they're just storage.

---

## Solution

A Telegram bot that:
- Takes weekly tasks in plain English
- Remembers past weeks via RAG to carry forward incomplete tasks
- Generates a structured day-by-day plan using Groq LLaMA 3.1
- Responds to natural language: *"What do I have tomorrow?"*, *"Reschedule standup to 12pm"*
- Supports full month planning — plan multiple weeks, view monthly overview
- Gets smarter every week as history builds up
- Loads plan from RAG automatically even after session restart

---

## Architecture

```
User (Telegram)
      │
      ▼
bot.py (Interface Layer)
  7 commands + natural language fallback
  RAG fallback when session is empty
      │
      ▼
agent.py (Chain Layer)
  7 LangChain chains → Groq LLaMA 3.1 8B
  Retry: exponential backoff (3 attempts)
      │
      ▼
rag_store.py (Memory Layer)
  FAISS + HuggingFace all-MiniLM-L6-v2
  Per-user, per-week indexed storage
  Persistent on Google Drive
```

---

## 7 LangChain Chains

| Chain | Purpose |
|-------|---------|
| PlannerChain | Generate structured weekly plan with RAG context |
| ModifyChain | Flexible plan modification — no hardcoded rules |
| TodayChain | Extract today's focus using actual system date |
| SummaryChain | Summarize past weeks from RAG memory |
| InsightsChain | Productivity pattern analysis |
| MonthChain | Full month overview across all saved weeks |
| NaturalChain | Handle any query or update via intent detection |

---

## Commands

| Command | Description |
|---------|-------------|
| `/plan` | Create week plan — pick this/next/week3/week4 |
| `/modify` | Modify anything in current plan |
| `/today` | Today's focus (actual system date aware) |
| `/summary` | Past weeks summary from RAG memory |
| `/insights` | AI productivity pattern analysis |
| `/month` | Full month overview |
| `/help` | All commands |

---

## Natural Language

Just type anything:
- *"What do I have today?"* → shows actual today's tasks
- *"What's tomorrow looking like?"* → shows actual tomorrow
- *"Reschedule standup to 12pm"* → auto-detects update, modifies plan
- *"Am I free Wednesday?"* → checks and answers
- *"What's pending this week?"* → analyzes and summarizes

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Groq LLaMA 3.1 8B Instant (free, 14,400 req/day) |
| Chain Orchestration | LangChain (7 chains) |
| Embeddings | HuggingFace all-MiniLM-L6-v2 (local, free) |
| Vector Store | FAISS (Google Drive persistent) |
| Bot Interface | python-telegram-bot v21 |
| Testing | unittest (15 test cases) |
| Runtime | Google Colab |

---

## File Structure

```
DamcoBuildChallenge/
├── bot.py              # Telegram handlers + RAG session fallback
├── agent.py            # 7 LangChain chains + retry logic
├── rag_store.py        # FAISS RAG — save/retrieve/month plans
├── config.py           # All constants centralized
├── requirements.txt    # Pinned dependencies
├── run.ipynb           # Colab notebook — clone and run in 7 cells
├── tests/
│   └── test_agent.py  # 15 unit tests
└── docs/
    └── architecture.md # Full system design doc
```

---

## Setup on Google Colab

1. Open `run.ipynb` in Colab
2. Add Colab Secrets: `TELEGRAM_BOT_TOKEN` and `GROQ_API_KEY`
3. Run all cells top to bottom
4. Open your bot in Telegram and send `/start`

---

## Get API Keys (both free, no card needed)

- **Telegram**: Message @BotFather → `/newbot` → copy token
- **Groq**: [console.groq.com](https://console.groq.com) → Create API Key

---

## Run Tests

```bash
python -m pytest tests/test_agent.py -v
```

15 tests covering intent detection, RAG fallback, config validation, and week key generation.

---

## Key Design Decisions

**Groq over OpenAI/Gemini**: Gemini free tier has 0 quota in India. OpenAI requires billing. Groq gives 14,400 free requests/day with LLaMA 3.1 quality — right tool for the job.

**FAISS over Weaviate**: Zero infrastructure, runs on Google Drive, no cost. Tradeoff: no metadata filtering — retrieves by similarity not exact week key. At scale, swap to Weaviate for metadata-filtered retrieval.

**7 chains over 1 prompt**: Each chain has a narrow, focused responsibility — independently testable and debuggable. Failure in one chain doesn't break others.

**RAG session fallback**: If Colab restarts and session is lost, bot automatically reloads the latest plan from FAISS — no data loss, seamless continuity.

---

## Failure Modes

| Failure | Mitigation |
|---------|-----------|
| Groq rate limit | Exponential backoff retry (3 attempts) |
| Colab session dies | Plan reloaded from FAISS/Drive automatically |
| Wrong day inference | System date explicitly injected into every prompt |
| No past history | Graceful fallback message, plan generated fresh |

---

## What I'd Add Next

- Google Calendar sync (auto-block time slots)
- Daily 8am priority reminder with top 3 tasks
- Voice message support (Whisper STT → text → plan)
- Swap FAISS → Weaviate for exact week-key metadata retrieval
- Deploy on Railway for always-on production hosting
