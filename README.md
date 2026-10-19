# 🌍 EcoPulse AI

**Autonomous Urban Climate Intelligence & Decision Engine**: a full-stack platform that ingests air-quality data, forecasts pollution 24-72 hours ahead, analyses satellite imagery with a CNN, runs a multi-agent LangGraph pipeline for health risk and policy recommendations, and answers questions through a RAG-powered streaming chatbot.

## 👤 About the Builder
**NIKHIL CHARY SRIRAMOJU**, B.Tech Final Year, Computer Science & Engineering

- 🔗 LinkedIn: [nikhil-chary-sriramoju](https://in.linkedin.com/in/nikhil-chary-sriramoju-95041b38a)
- 💻 GitHub: [Nikhil-creat](https://github.com/Nikhil-creat)
- 📧 Email: sriramojunikhil66@gmail.com

## ✨ Features
- **Multi-pollutant forecasting**: PM2.5, PM10, NO₂, AQI and temperature at +6/12/24/48/72 h. Holt-Winters, damped-trend and seasonal-naive models are compared on a 24 h hold-out; the best is used. Retrained every 3 hours and when drift is detected.
- **CNN spatial analysis**: ResNet-style PyTorch network producing a Smog Severity Index and Green Canopy Density, rendered as a 3D heatmap (heuristic scoring until trained on labelled imagery).
- **Agentic AI (LangGraph)**: Data Integrity Agent → Forecast & Health Risk Agent → Policy & Mitigation Agent. Works deterministically without an LLM; Groq / Gemini add narrative text.
- **Hybrid RAG chatbot**: pgvector + full-text search fused with reciprocal-rank fusion over WHO / CPCB guidelines, combined with live sensor and forecast context, streamed over SSE with session memory.
- **MLOps drift monitor**: KS-test and Wasserstein distance against a reference window, triggering retraining.
- **Live dashboard**: Next.js, Tailwind, Recharts, deck.gl 3D map, WebSocket live metrics, one-click Executive Health & Policy Report (PDF).
- **Security basics**: API-key protection on write/admin endpoints, per-IP rate limits.

## 🏗️ Architecture
```
Browser ─▶ Nginx ─┬─▶ Next.js dashboard
                  ├─▶ FastAPI ──▶ TimescaleDB + pgvector
                  │      │ ▲            ▲
                  │      ▼ │            │
                  │    Redis ◀──▶ Celery worker + beat
                  │                (ingest · CNN · forecasts · drift)
                  └─▶ WebSocket /ws/live-metrics, SSE /api/v1/chat
```

## 🧰 Tech Stack
FastAPI · Python 3.11 · SQLAlchemy 2 · TimescaleDB · pgvector · Celery · Redis · PyTorch · statsmodels · LangChain / LangGraph · Groq · Gemini · sentence-transformers (all-MiniLM-L6-v2) · Next.js 14 · Tailwind · Recharts · deck.gl · ReportLab · Docker Compose · Nginx · GitHub Actions

## 🚀 Getting Started
Requires Docker + Docker Compose (a Linux VM or GitHub Codespaces works).

1. Clone this repo.
2. `cp .env.example .env` and set `POSTGRES_PASSWORD`, `SECRET_KEY`, `API_KEYS` (optional: `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENWEATHER_API_KEY`, `CPCB_API_KEY`, `STATIONS_JSON`).
3. `make up`
4. `./scripts/bootstrap.sh http://localhost YOUR_API_KEY` (seeds the knowledge base, backfills simulated history, trains forecasts)
5. Open `http://localhost` (dashboard) and `http://localhost/docs` (API).

See [`docs/DEPLOY.md`](docs/DEPLOY.md) for the deployment checklist.

## 🔌 Key Endpoints
| Endpoint | Purpose |
|---|---|
| `GET /api/v1/stats/summary` | Latest readings and mean AQI |
| `GET /api/v1/forecasts` | Station forecast |
| `POST /api/v1/agents/run` | Run the 3-agent pipeline |
| `POST /api/v1/chat` | Streaming RAG chat (SSE) |
| `GET /api/v1/reports/executive` | Executive PDF report |
| `POST /api/v1/satellite/analyze` | Queue CNN analysis of an image |
| `GET /api/v1/mlops/drift` | Latest drift report |
| `WS /ws/live-metrics` | Live readings |

## ⚠️ Honest Limitations
- Without API keys the platform uses clearly tagged **simulated** data.
- The CNN uses heuristic scoring until trained on real labelled imagery.
- Seed WHO/CPCB documents are summaries; upload the official PDFs for production use.
- Decision-support only: not medical advice; policy actions need official approval.
- No user accounts yet; dashboard reads are public.
