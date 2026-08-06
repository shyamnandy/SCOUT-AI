# 📰 ScoutAI — AI-Powered Personal News Curator

> Stop scrolling. Start knowing. Tell ScoutAI what you care about in plain English — it finds the sources, reads the articles, drops the noise, and emails you a newsletter on your schedule.

**[🔗 Live demo](https://scout-ai-peach-five.vercel.app/)** · [Engineering challenges](CHALLENGES.md)

---

## ✨ Features

- **💬 AI chat onboarding** — Describe your interests in plain language; the LLM turns them into a topic with keywords
- **📂 Category picker** — Or quick-select from 10 predefined news categories
- **⏰ Per-topic schedules** — Any delivery time, in your own timezone
- **📅 Expiration control** — Topics auto-retire after an event ends (e.g. the FIFA World Cup)
- **🔍 Source discovery** — The LLM shortlists legitimate outlets per topic, anchored to reputable names in that category
- **🕷️ Deep scraping** — Full article text, not just headlines or RSS blurbs
- **📊 Relevance filtering** — Every article is scored 0–1; anything below the floor is dropped rather than padding the issue
- **🔑 Bring your own keys** — Users can supply their own Groq/Tavily keys, encrypted at rest
- **📧 Auto-delivered** — Clean HTML newsletters, sent without you doing anything

## 🔬 How curation works

Each delivery slot runs one pipeline, shared by the scheduler and the manual
"send now" trigger so the two can't drift apart ([`app/services/pipeline.py`](backend/app/services/pipeline.py)):

```
Topic keywords
   ↓  Tavily news search (last 24h, up to 3 query angles × 20 results)
   ↓  LLM groups results by event and shortlists 16 distinct stories
   ↓  Full-text scrape of each source
   ↓  LLM scores relevance + importance; drops anything below 0.4
   ↓  5–10 surviving articles rendered into an HTML newsletter
   ↓  Resend delivers to the inbox
```

Issue length adapts to the news. Five articles are guaranteed when the topic
has them; past that, a story only earns a slot if its importance clears 0.6 —
so a busy week can run to ten, while a quiet one stops at five rather than
padding with routine follow-ups.

The shortlist is deliberately larger than what ships, so duplicate coverage of
the same story — which often only becomes visible in the full text — can be
dropped without leaving gaps.

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite |
| Styling | Vanilla CSS (dark glassmorphism) |
| Backend API | FastAPI (Python) |
| AI/LLM | LangChain + Groq (Llama 3.3 70B) |
| Web Search | Tavily Search API |
| Database | MongoDB Atlas |
| Auth | JWT |
| Scheduling | External cron → `/api/cron/tick` (production) · Celery + Redis (local dev) |
| Email | Resend API |

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- MongoDB (Atlas free tier or local)
- Redis — **optional**, only if you want to run the Celery scheduler locally

### 1. Backend

```bash
cd backend
cp .env.example .env
# Fill in your API keys in .env

python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Automated delivery

Locally, run Celery Beat + worker:

```bash
cd backend
celery -A worker.celery_app worker --beat --loglevel=info
```

In production nothing runs continuously. A free external scheduler
(e.g. [cron-job.org](https://cron-job.org)) sends `POST /api/cron/tick` every
5 minutes with an `X-Cron-Secret` header matching `CRON_SECRET`. That endpoint
runs the same curate/dispatch check in-process — see
[`app/routes/cron.py`](backend/app/routes/cron.py). No Redis, no worker.

Why it's built this way: [CHALLENGES.md § 1](CHALLENGES.md).

### 🔑 Environment variables

| Key | Purpose | Get it from |
|-----|---------|------------|
| `MONGO_URI` | Database | [mongodb.com/atlas](https://mongodb.com/atlas) (free M0) |
| `GROQ_API_KEY` | LLM — chat onboarding + curation | [console.groq.com](https://console.groq.com/keys) (free) |
| `TAVILY_API_KEY` | News search | [tavily.com](https://tavily.com) (1000 free searches/mo) |
| `RESEND_API_KEY` | Email delivery | [resend.com](https://resend.com) (100 free emails/day) |
| `JWT_SECRET` | Session signing — use a long random string | — |
| `CRON_SECRET` | Shared secret for `/api/cron/tick` | — |
| `FROM_EMAIL` | Newsletter sender address | Resend |
| `FRONTEND_URL` | CORS origin | — |

See [`backend/.env.example`](backend/.env.example) for the full list.

## 📁 Project Structure

```
ScoutAI/
├── frontend/          # React + Vite SPA
│   └── src/
│       ├── components/  # Reusable UI components
│       ├── pages/       # Route pages
│       ├── context/     # Auth state management
│       └── services/    # API client
├── backend/           # FastAPI + Celery
│   ├── app/
│   │   ├── routes/      # API endpoints
│   │   ├── services/    # AI pipeline services
│   │   ├── models/      # MongoDB document factories
│   │   └── schemas/     # Pydantic validation
│   ├── worker/          # Celery tasks + scheduler
│   └── templates/       # Email HTML templates
```

## 🌐 Deployment

- **Frontend** → Vercel (set `VITE_API_URL`)
- **Backend API** → Render free web service (sleeps when idle; the cron ping wakes it)
- **Scheduling** → free external cron → `POST /api/cron/tick` every 5 min, header `X-Cron-Secret: <CRON_SECRET>`
- **Infra cost** → $0. No Redis, no standalone worker, nothing running 24/7.

## 🧠 Engineering notes

Problems worth reading about — always-on infra cost, double-send prevention,
timezone-correct scheduling: **[CHALLENGES.md](CHALLENGES.md)**
