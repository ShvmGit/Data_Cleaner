# DataCleaner AI

**AI-powered data cleaning and exploratory data analysis** — Upload CSV, TXT, or Excel files and let an AI pipeline clean, analyze, and generate insights in seconds.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Next.js-16-000?style=flat-square&logo=next.js" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi" />
  <img src="https://img.shields.io/badge/Groq-LLM-FF6F00?style=flat-square" />
  <img src="https://img.shields.io/badge/Google_ADK-Orchestration-4285F4?style=flat-square&logo=google" />
</p>

---

## ✨ Features

- 🤖 **AI-Powered Cleaning** — Groq LLM selects optimal tools via Google ADK orchestration
- 📊 **Interactive EDA** — Plotly visualizations: heatmaps, distributions, box plots, scatter plots
- ⚡ **Real-Time Progress** — Server-Sent Events stream pipeline stages live to the UI
- 🛡️ **Fault-Tolerant** — 3-model LLM fallback chain + rule-based fallback if AI is unavailable
- 📋 **Comprehensive Reports** — HTML reports, cleaned CSV/Excel exports, audit trail
- 🎨 **Premium UI** — Dark glassmorphism design with Tailwind CSS

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Next.js 16     │────▶│  FastAPI Backend  │────▶│  ADK + Groq LLM │
│  (Tailwind UI)  │◀────│  (SSE Stream)    │◀────│  (Tool Calling)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │                        │
                        ┌─────┴─────┐            ┌─────┴─────┐
                        │  Profiler  │            │  7 Clean   │
                        │  Engine    │            │  Tools     │
                        └───────────┘            └───────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Groq API Key](https://console.groq.com/)

### 1. Clone & Setup
```bash
git clone <repo-url>
cd csv_cleaner

# Backend
cd backend
cp .env.example .env  # Add your GROQ_API_KEY
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Run
```bash
# Terminal 1: Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

### 3. Open
Visit **http://localhost:3000** and upload a file!

## 📁 Project Structure

```
csv_cleaner/
├── backend/
│   ├── main.py              # FastAPI app entry
│   ├── api/routes.py         # REST + SSE endpoints
│   ├── agents/orchestrator.py # ADK agent pipeline
│   ├── core/
│   │   ├── config.py         # Pydantic settings
│   │   ├── file_loader.py    # Multi-format parser
│   │   ├── state_manager.py  # Session management
│   │   ├── llm_client.py     # Groq API + fallback
│   │   └── circuit_breaker.py
│   └── tools/
│       ├── profiler.py       # Statistical analysis
│       ├── cleaning.py       # 7 cleaning functions
│       ├── eda.py            # 5 Plotly generators
│       ├── fallback.py       # Rule-based backup
│       └── reporter.py       # HTML/CSV/Excel output
├── frontend/
│   └── src/
│       ├── app/              # Next.js pages
│       ├── hooks/useSSE.ts   # SSE streaming hook
│       └── lib/              # API client, types
├── shared/schemas.py         # Pydantic data contracts
├── render.yaml               # Render deployment
└── README.md
```

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ | — | Groq API key for LLM |
| `CORS_ORIGINS` | — | `http://localhost:3000` | Comma-separated CORS origins |
| `MAX_FILE_SIZE_MB` | — | `100` | Max upload size |
| `SESSION_TTL_MINUTES` | — | `30` | Session expiry time |
| `LOG_LEVEL` | — | `INFO` | Logging level |

## 📊 Pipeline Stages

1. **Parse** → Multi-format loading with encoding detection
2. **Profile** → Statistical analysis, outlier/duplicate detection
3. **Clean** → AI-selected tools: missing values, outliers, duplicates, dtypes, whitespace, column names
4. **Analyze** → Plotly charts + AI-generated insights
5. **Report** → HTML report + CSV/Excel exports

## 🚢 Deploy to Render

1. Push to GitHub
2. Connect repo in [Render Dashboard](https://dashboard.render.com)
3. Select **Blueprint** and choose `render.yaml`
4. Set `GROQ_API_KEY` environment variable
5. Deploy!

## 📄 License

MIT
