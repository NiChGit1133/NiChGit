# AI Multi-Analyst Stock Research System

AI-driven multi-analyst collaborative stock research platform. 5 specialized AI analysts work in parallel, followed by bull-bear debate with red team verification, culminating in a final investment recommendation.

## How It Works

```
Phase 1: Data Fetch (Futu real-time, ~0.3s)
    ↓
Phase 1: 4 Analysts in Parallel (DeepSeek, ~10-30s)
    ├── 📊 Technical Analyst (K-line, MA, MACD, RSI, ATR, BOLL)
    ├── 📈 Fundamental Analyst (Margins, CapEx, PE, ROE, Cash Flow)
    ├── 📰 News Analyst (Policy, Industry, Institutions, Catalysts)
    └── 😊 Sentiment Analyst (Fund Flows, Turnover, Market Mood)
    ↓
Phase 2: Bull-Bear Debate + Red Team
    ├── 🐂 Bull Debater (maximizes optimistic interpretation)
    ├── 🐻 Bear Debater (maximizes pessimistic interpretation)
    └── 🔴 Red Team (independent claim verification: VERIFIED/UNVERIFIED/REFUTED)
    ↓
Phase 3: 👑 Chief Strategist → BUY / HOLD / SELL + Conviction + Price Targets
```

## Quick Start

### Prerequisites

- Python 3.10+
- [DeepSeek API Key](https://platform.deepseek.com) (or any OpenAI-compatible LLM)
- [FutuOpenD](https://www.futunn.com/download/OpenAPI) + Futu account (for real-time data)
- Windows / macOS / Linux

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/stock-research-system.git
cd stock-research-system
pip install -r backend/requirements.txt
```

### 2. Configure

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — add your DeepSeek API key:
#   DEEPSEEK_API_KEY=sk-your-key-here
```

### 3. Start FutuOpenD (for live data)

Download FutuOpenD from https://www.futunn.com/download/OpenAPI, launch it, and log in with your Futu account. It runs on `127.0.0.1:11111`.

> If you don't have Futu, the system falls back to demo data automatically.

### 4. Run

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** — enter a stock code like `AAPL` and press Enter.

## Supported Markets

| Market | Format | Examples | Data Source |
|--------|--------|----------|-------------|
| 🇺🇸 US Stocks | 1-5 letters | AAPL, NVDA, TSLA, MSFT | Futu LV3 (real-time) |
| 🇨🇳 A-Shares | 6 digits | 000837, 600519 | Demo (needs Futu A-share permission) |
| 🇭🇰 HK Stocks | 5 digits | 00700 | Demo (needs Futu HK permission) |

## Architecture

```
Frontend (pure HTML, served by FastAPI)
    ↓ SSE streaming
FastAPI Backend
    ↓
LangGraph StateGraph (9 nodes)
    ├── fetch_data → [technical ‖ fundamental ‖ news ‖ sentiment]
    ├── bull_debater → bear_debater → red_team
    └── chief_strategist
    ↓
Data Sources: Futu OpenAPI → efinance → Demo
AI: DeepSeek V4 Pro (via langchain-deepseek)
DB: SQLite (watchlist + history)
```

## Configuration

All configurable in `backend/.env`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEEPSEEK_API_KEY` | (required) | Your DeepSeek API key |
| `ANALYST_TEMPERATURE` | 0.7 | Higher = more creative, lower = more consistent |
| `RED_TEAM_TEMPERATURE` | 1.0 | Higher = more aggressive verification |
| `CHIEF_TEMPERATURE` | 0.3 | Lower = more stable judgment |
| `PORT` | 8000 | Server port |
| `CACHE_TTL_QUOTE` | 300 | Quote cache (seconds) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Frontend UI |
| GET | `/api/health` | Health check |
| GET | `/api/stock/{code}/quote` | Real-time quote |
| GET | `/api/stock/{code}` | Full stock data |
| GET | `/api/stock/search?q=` | Stock search |
| GET | `/api/analyze/stream?code=&temperature=&source=` | SSE streaming analysis |
| GET | `/api/futu/news/{code}` | Stock news |
| GET | `/api/futu/sentiment/{code}` | Community sentiment |
| GET | `/api/futu/anomaly/{code}` | Anomaly detection |
| GET/POST/DELETE | `/api/watchlist` | Watchlist CRUD |
| GET | `/api/history` | Analysis history |

## Project Structure

```
backend/
├── main.py                    # FastAPI app + all routes
├── config.py                  # Environment configuration
├── requirements.txt           # Python dependencies
├── agents/
│   ├── base.py                # LLM agent base class
│   └── prompts.py             # 7 Chinese system prompts
├── data/
│   ├── akshare_client.py      # Data orchestrator (Futu→AkShare→efinance→demo)
│   ├── futu_client.py         # Futu OpenAPI wrapper
│   ├── baostock_client.py     # Baostock fallback (A-shares)
│   ├── demo_data.py           # Demo data generator
│   └── cache.py               # JSON file cache
├── db/
│   ├── database.py            # SQLite async connection
│   └── models.py              # Watchlist + Analysis models
├── orchestrator/
│   ├── graph.py               # LangGraph StateGraph + SSE streaming
│   ├── state.py               # Pydantic state models
│   └── nodes/                 # 9 analysis nodes
└── frontend/
    └── index.html             # Single-file frontend
```

## Troubleshooting

**"FutuOpenD not reachable"** — FutuOpenD isn't running. The system will use demo data. Install and launch FutuOpenD for real-time quotes.

**"Stock not found"** — Check the code format (AAPL, not AAPL.US). The system auto-detects market from code pattern.

**Analysis takes too long** — The DeepSeek API may be slow. First request takes ~30s; subsequent requests are faster due to caching.

**Scores vary between runs** — This is normal LLM behavior with temperature=0.7. Lower it to 0.3 for more consistent results.

## License

MIT — use freely, modify, share.

---

Built with DeepSeek V4 Pro, Futu OpenAPI, LangGraph, and FastAPI.
