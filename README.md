# 📰 ScoutAI — AI-Powered Personal News Curator

> Stop scrolling. Start knowing. ScoutAI curates personalized newsletters from 6 trusted sources — delivered to your inbox on your schedule.

## ✨ Features

- **💬 AI Chat Onboarding** — Tell our AI what you care about in plain language
- **📂 Category Picker** — Quick-select from 10 predefined news categories
- **⏰ Custom Schedules** — Set delivery times per topic (morning, evening, etc.)
- **📅 Expiration Control** — Topics auto-expire after events end (e.g., FIFA World Cup)
- **🔍 6 Trusted Sources** — AI selects 6 legitimate sources per topic
- **🕷️ Deep Scraping** — Full article content scraped and analyzed
- **📊 AI Analysis** — Each article scored for relevance, filtered for quality
- **📧 Auto-Delivered** — Beautiful HTML newsletters emailed automatically

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite |
| Styling | Vanilla CSS (dark glassmorphism) |
| Backend API | FastAPI (Python) |
| AI/LLM | LangChain + OpenAI GPT-4o-mini |
| Web Search | Tavily Search API |
| Database | MongoDB Atlas |
| Scheduling | Celery + Redis (local dev) / external cron + `/api/cron/tick` (production) |
| Email | Resend API |

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- MongoDB (Atlas or local)
- Redis (local or cloud)

### 1. Clone & Setup Backend

```bash
cd backend
cp .env.example .env
# Fill in your API keys in .env

python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Start the API
uvicorn app.main:app --reload --port 8000
```

### 2. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Trigger automated newsletters

Locally, run Celery Beat + worker as before:

```bash
cd backend
celery -A worker.celery_app worker --beat --loglevel=info
```

In production, no Celery/Redis process needs to run continuously. An
external free scheduler (e.g. [cron-job.org](https://cron-job.org)) hits
`POST /api/cron/tick` every 5 minutes with an `X-Cron-Secret` header
matching `CRON_SECRET` in `.env`. That endpoint runs the same curate/dispatch
check in-process — see `app/routes/cron.py`.

### 🔑 Required API Keys

| Key | Get it from |
|-----|------------|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) (1000 free searches/month) |
| `RESEND_API_KEY` | [resend.com](https://resend.com) (100 free emails/day) |
| `MONGO_URI` | [mongodb.com/atlas](https://mongodb.com/atlas) (free M0 cluster) |

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

- **Frontend** → Vercel (set `VITE_API_URL` env var)
- **Backend API** → Render free Web Service (sleeps when idle; the cron ping below wakes it)
- **Scheduling** → external free cron (e.g. cron-job.org) → `POST /api/cron/tick` every 5 min, with header `X-Cron-Secret: <CRON_SECRET>`
- No Redis or standalone worker needed in production
