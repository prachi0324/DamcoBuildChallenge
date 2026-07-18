# 🗓️ Week Planner Bot

> AI-powered Telegram bot that plans your week, remembers past weeks, and responds to natural language — built for the Damco Builder Challenge.

---

## Problem

People start every week with zero structure. Tasks are scattered across WhatsApp, notes, and memory. By Wednesday priorities are lost and deadlines missed. Existing tools (Notion, Google Calendar) require manual input and give zero intelligence — they're just storage.

---

## Solution

A Telegram bot that:
- Takes weekly tasks in plain English
- Retrieves past weeks via **RAG** to carry forward incomplete tasks
- Generates a structured day-by-day plan using **Groq LLaMA 3.1**
- Responds to natural language: *"What do I have tomorrow?"*, *"Reschedule standup to 12pm"*
- Supports **full month planning** — plan multiple weeks, view monthly overview
- Gets smarter every week as it builds up your history

---

## Architecture

```
User (Telegram)
      │
      ▼
bot.py (Interface Layer)
  7 commands + natural language fallback
      │
      ▼
agent.py (Chain Layer)
  7 LangChain chains → Groq LLaMA 3.1 8B
  Retry: exponential backoff (3 attempts)
      │
      ▼
rag_store.py (Memory Layer)
  FAISS + HuggingFace embeddings
  Per-user, per-week indexed storage
```

See [docs/architecture.md](docs/architecture.md) for full design doc.

---

## Features

| Command | Description |
|---------|-------------|
| `/plan` | Create week plan — pick this week / next week / week 3 / week 4 |
| `/modify` | Modify anything in current plan |
| `/today` | Today's focus (uses actual system date) |
| `/summary` | Summary of past weeks from RAG memory |
| `/insights` | AI productivity pattern analysis |
| `/month` | Full month overview across all saved weeks |
| `/help` | All commands |

**Natural language** — just type anything:
- *"What do I have today?"* → shows actual today's tasks
- *"What's tomorrow looking like?"* → shows actual tomorrow
- *"Am I free on Wednesday?"* → checks plan and answers
- *"Reschedule my standup to 12pm"* → auto-detects update, modifies plan
- *"What's pending this week?"* → summarizes unfinished items

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Groq LLaMA 3.1 8B Instant |
| Chain Orchestration | LangChain (7 chains) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector Store | FAISS (local) |
| Bot Interface | python-telegram-bot v21 |
| Config | python-dotenv |
| Testing | unittest (15 test cases) |

---

## Setup

### 1. Clone
```bash
git clone https://github.com/prachi0324/DamcoBuildChallenge.git
cd DamcoBuildChallenge
```

### 2. Install
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
# Edit .env and add:
# TELEGRAM_BOT_TOKEN — from @BotFather on Telegram
# GROQ_API_KEY — from console.groq.com (free, no card needed)
```

### 4. Run
```bash
python bot.py
```

### 5. Test
```bash
python -m pytest tests/ -v
```

---

## Running on Google Colab

If running on Colab (no persistent server):
```python
import nest_asyncio
nest_asyncio.apply()

import asyncio
from bot import build_app

app = build_app()
await app.run_polling(drop_pending_updates=True)
```

Set secrets in Colab: `TELEGRAM_BOT_TOKEN` and `GROQ_API_KEY`

For persistence, mount Google Drive and set:
```
STORE_DIR=/content/drive/MyDrive/week-planner/faiss_store
```

---

## Testing

```bash
python -m pytest tests/ -v
```

15 test cases covering:
- Week key/label generation
- Update intent detection (8 cases)
- Config validation
- RAG store graceful fallback

---

## Key Design Decisions

**Groq over OpenAI/Gemini**: Gemini free tier has 0 quota in India. OpenAI requires billing. Groq gives 14,400 free requests/day with LLaMA 3.1 quality.

**FAISS over Weaviate**: Zero infrastructure, runs locally. Tradeoff: no metadata filtering. At scale, swap to Weaviate for exact week-key retrieval.

**7 chains over 1 prompt**: Each chain has narrow responsibility — independently testable, debuggable, and swappable. Failure in one doesn't break others.

**Telegram over web app**: Zero friction. Users are already there daily.

---

## Failure Modes & Mitigations

| Failure | Mitigation |
|---------|-----------|
| Groq rate limit | Exponential backoff retry (3 attempts) |
| Colab session dies | Data safe in FAISS/Drive; redeploy on Railway for production |
| No past history | Graceful fallback — plan generated without RAG context |
| Wrong day inference | System date explicitly injected into every prompt |

---

## What I'd Add Next

- Google Calendar sync (auto-block time slots)
- Daily 8am reminder with top 3 priorities
- Voice message support (Whisper STT → text → plan)
- Swap FAISS → Weaviate for metadata-filtered week retrieval
- Deploy on Railway for always-on production hosting
