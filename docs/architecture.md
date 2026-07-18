# Week Planner Bot — Architecture

## Overview

An AI-powered Telegram bot that plans your week, remembers past weeks via RAG, and responds to natural language queries and updates.

---

## System Architecture

```
User (Telegram)
      │
      ▼
┌─────────────────────────────────────────────┐
│              bot.py (Interface Layer)        │
│  Commands: /plan /modify /today /summary    │
│            /insights /month /help           │
│  Natural language → auto-routed             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│            agent.py (Chain Layer)            │
│                                             │
│  Chain 1: PlannerChain                      │
│  Chain 2: ModifyChain                       │
│  Chain 3: TodayChain                        │
│  Chain 4: SummaryChain                      │
│  Chain 5: InsightsChain                     │
│  Chain 6: MonthChain                        │
│  Chain 7: NaturalChain (query/update router)│
│                                             │
│  All chains: Groq LLaMA 3.1 8B             │
│  Retry: exponential backoff (3 attempts)    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           rag_store.py (Memory Layer)        │
│                                             │
│  Embeddings: HuggingFace all-MiniLM-L6-v2  │
│  Vector Store: FAISS (local/Google Drive)   │
│  Indexed by: user_id + week_key             │
│  Operations: save_plan, retrieve_context,   │
│              retrieve_all_month_plans        │
└─────────────────────────────────────────────┘
```

---

## Data Flow

### Plan Generation
```
User input (tasks list)
    → retrieve_past_context() [RAG: similar past weeks]
    → PlannerChain [Groq LLaMA 3.1]
    → Structured week plan
    → save_plan() [FAISS store with week_key]
    → Return to user
```

### Natural Language Query
```
User message
    → intent detection (UPDATE_KEYWORDS match?)
    │
    ├── YES (update intent)
    │   → ModifyChain
    │   → Updated plan saved to session
    │
    └── NO (query intent)
        → NaturalChain [with today/tomorrow injected]
        → Direct answer from plan
```

### Monthly Planning
```
/plan → Week selector (This/Next/Week3/Week4)
    → week_offset parameter
    → generate_plan(week_offset=N)
    → save_plan(week_key=YYYY-WNN)

/month → retrieve_all_month_plans()
    → deduplicate by week_key
    → MonthChain generates overview
```

---

## Key Design Decisions

### Why Groq over OpenAI/Gemini?
- Gemini free tier has 0 quota in India (RESOURCE_EXHAUSTED on first call)
- OpenAI requires billing ($5 minimum)
- Groq: 14,400 free requests/day, LLaMA 3.1 quality, no billing required

### Why FAISS over Weaviate/Pinecone?
- Zero infrastructure — runs locally or on Google Drive
- No API key, no cost, no external dependency
- Tradeoff: no metadata filtering (retrieves by similarity, not exact week key)
- At scale: swap to Weaviate for metadata-filtered week-exact retrieval

### Why Telegram over web app?
- Zero friction — no new app to download or login to create
- Users are already in Telegram daily
- Bot lives where the user is

### Why 7 separate chains over one prompt?
- Each chain has a focused, narrow responsibility
- Independent testability and debugability
- Easier to swap models per chain (e.g., smaller model for Today vs Insights)
- Failure in one chain doesn't break others

---

## Retry Strategy

All LLM calls use `invoke_with_retry()`:
```
Attempt 1 → fail → wait 2s
Attempt 2 → fail → wait 4s
Attempt 3 → fail → raise Exception
```

FAISS operations use flat retry (no backoff):
```
Attempt 1 → fail → wait 2s
Attempt 2 → fail → wait 2s
Attempt 3 → fail → return False/empty string
```

---

## Failure Modes

| Failure | Behaviour | Fix |
|---------|-----------|-----|
| Groq rate limit | Retry x3, then user-friendly error | Exponential backoff |
| Colab session dies | Bot goes offline, data safe in Drive | Deploy on Railway/Render |
| FAISS no history | Graceful fallback message | No plan generated without history |
| Wrong day inference | Explicit date injection in all prompts | System date always passed |
| Empty user input | Telegram validator catches before LLM | Input length check |

---

## File Structure

```
weekplanner/
├── bot.py              # Telegram handlers + conversation flows
├── agent.py            # 7 LangChain chains + retry logic
├── rag_store.py        # FAISS RAG — save, retrieve, month plans
├── config.py           # All constants — models, keys, retry params
├── requirements.txt    # Pinned dependencies
├── .env.example        # Environment variable template
├── tests/
│   └── test_agent.py  # Unit tests — 15 test cases
└── docs/
    └── architecture.md # This document
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `GROQ_API_KEY` | From console.groq.com (free) |
| `STORE_DIR` | Path to FAISS store (default: ./faiss_store) |
