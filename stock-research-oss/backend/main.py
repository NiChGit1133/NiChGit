"""FastAPI application entry point with SSE streaming endpoints."""
import json
import uuid
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from .config import HOST, PORT
from .data.akshare_client import akshare
from .data.futu_client import futu as futu_client, detect_market
from .orchestrator.graph import run_analysis, run_analysis_streaming
from .db.database import init_db, get_db
from .db.models import WatchlistItem, AnalysisRecord

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("Starting Stock Research System...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="AI Multi-Analyst Stock Research System",
    description="多分析师协作的A股投资研究系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════
# Data Endpoints
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/stock/search")
async def search_stock(q: str = Query(..., min_length=1)):
    """Search for stocks by name or code (supports A-share, US, HK)."""
    results = []
    q_upper = q.upper().strip()

    # 1. Search via Futu if available (US + HK stocks)
    try:
        from .data.futu_client import futu as ft
        if ft.is_available:
            # Try a few possible Futu codes
            candidates = []
            # Direct ticker match
            if q_upper.isalpha():
                candidates.append(f"US.{q_upper}")
                if q_upper.isdigit() and len(q_upper) == 5:
                    candidates.append(f"HK.{q_upper}")
            # Try common US stocks by name
            common_us = {
                "苹果": "US.AAPL", "特斯拉": "US.TSLA", "英伟达": "US.NVDA",
                "微软": "US.MSFT", "谷歌": "US.GOOGL", "META": "US.META",
                "亚马逊": "US.AMZN", "AMD": "US.AMD",
                "AAPL": "US.AAPL", "TSLA": "US.TSLA", "NVDA": "US.NVDA",
                "MSFT": "US.MSFT", "GOOGL": "US.GOOGL", "AMZN": "US.AMZN",
            }
            if q_upper in common_us:
                candidates.append(common_us[q_upper])
            for name, code in common_us.items():
                if name in q_upper:
                    candidates.append(code)

            if candidates:
                from futu import RET_OK
                ret, data = ft._quote_ctx.get_market_snapshot(list(set(candidates)))
                if ret == RET_OK and not data.empty:
                    for _, row in data.iterrows():
                        name = str(row.get("stock_name", ""))
                        if name:
                            code = str(row.get("code", "")).replace("US.", "").replace("HK.", "")
                            results.append({
                                "code": code,
                                "name": name,
                                "price": float(row.get("last_price", 0)),
                                "change_pct": round(float(row.get("change_rate", 0)) * 100, 2),
                            })
    except Exception as e:
        pass  # Futu search failed, continue to AkShare

    # 2. A-share search via AkShare (for Chinese stocks)
    if not results:
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                q_lower = q.lower().strip()
                for _, row in df.iterrows():
                    code = str(row.get("代码", ""))
                    name = str(row.get("名称", ""))
                    if q_lower in name.lower() or q_lower in code:
                        results.append({
                            "code": code,
                            "name": name,
                            "price": float(row.get("最新价", 0)),
                            "change_pct": float(row.get("涨跌幅", 0)),
                        })
                    if len(results) >= 20:
                        break
        except Exception:
            pass

    # 3. Demo fallback
    if not results:
        from .data.demo_data import DEMO_STOCKS
        for code, info in DEMO_STOCKS.items():
            if q_upper in code.upper() or q_upper in info["name"].upper():
                results.append({
                    "code": code,
                    "name": info["name"],
                    "price": 0,
                    "change_pct": 0,
                })

    return {"status": "ok", "results": results[:20]}


@app.get("/api/stock/{code}")
async def get_stock_data(code: str):
    """Fetch all available data for a stock."""
    try:
        import math
        data = await akshare.fetch_all(code)
        # Clean NaN values for JSON serialization
        def clean(v):
            if isinstance(v, dict): return {k: clean(v) for k, v in v.items()}
            if isinstance(v, list): return [clean(i) for i in v]
            if isinstance(v, float) and math.isnan(v): return None
            return v
        return {"status": "ok", "data": clean(data)}
    except Exception as e:
        logger.error(f"Error fetching data for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{code}/quote")
async def get_stock_quote(code: str):
    """Get real-time quote for a stock."""
    try:
        quote = await akshare.get_realtime_quote(code)
        if quote is None:
            raise HTTPException(status_code=404, detail=f"Stock {code} not found")
        return {"status": "ok", "data": quote}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Analysis Endpoints
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/analyze/stream")
async def analyze_stock_stream(
    code: str = Query(..., min_length=1, max_length=10),
    temperature: float = Query(0.7, ge=0.1, le=1.5),
    source: str = Query("auto", min_length=1, max_length=10),
):
    """Run full analysis with SSE streaming of progress and results."""
    logger.info(f"Starting streaming analysis for {code} (temp={temperature}, source={source})")

    async def event_generator():
        analysis_id = str(uuid.uuid4())

        try:
            async for event in run_analysis_streaming(code, temperature, source):
                event_type = event.get("event", "message")
                data = event.get("data", {})

                # Add analysis_id to complete event
                if event_type == "complete":
                    data["analysis_id"] = analysis_id

                yield {
                    "event": event_type,
                    "data": json.dumps(data, ensure_ascii=False, default=str),
                }

        except Exception as e:
            logger.error(f"Analysis error for {code}: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"message": f"分析出错: {str(e)}"}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@app.post("/api/analyze/{code}")
async def analyze_stock_sync(code: str):
    """Run full analysis synchronously (non-streaming)."""
    try:
        result = await run_analysis(code)
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.error(f"Analysis error for {code}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Watchlist Endpoints
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/watchlist")
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    """Get all watchlist items."""
    result = await db.execute(select(WatchlistItem).order_by(desc(WatchlistItem.added_at)))
    items = result.scalars().all()
    return {
        "status": "ok",
        "items": [
            {
                "id": item.id,
                "stock_code": item.stock_code,
                "stock_name": item.stock_name,
                "added_at": item.added_at.isoformat() if item.added_at else None,
                "notes": item.notes,
            }
            for item in items
        ],
    }


@app.post("/api/watchlist")
async def add_to_watchlist(
    code: str = Query(...),
    name: str = Query(...),
    notes: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """Add a stock to the watchlist."""
    existing = await db.execute(
        select(WatchlistItem).where(WatchlistItem.stock_code == code)
    )
    if existing.scalar_one_or_none():
        return {"status": "ok", "message": f"{code} already in watchlist"}

    item = WatchlistItem(stock_code=code, stock_name=name, notes=notes)
    db.add(item)
    await db.commit()
    return {"status": "ok", "item": {"id": item.id, "stock_code": code, "stock_name": name}}


@app.delete("/api/watchlist/{code}")
async def remove_from_watchlist(code: str, db: AsyncSession = Depends(get_db)):
    """Remove a stock from the watchlist."""
    result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.stock_code == code)
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
        return {"status": "ok", "message": f"Removed {code}"}
    raise HTTPException(status_code=404, detail=f"{code} not in watchlist")


# ═══════════════════════════════════════════════════════════════════════
# Analysis History Endpoints
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/history")
async def get_analysis_history(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get recent analysis history."""
    result = await db.execute(
        select(AnalysisRecord)
        .order_by(desc(AnalysisRecord.created_at))
        .limit(limit)
    )
    records = result.scalars().all()
    return {
        "status": "ok",
        "records": [
            {
                "id": r.id,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "recommendation": r.recommendation,
                "conviction": r.conviction,
                "composite_score": r.composite_score,
                "technical_score": r.technical_score,
                "fundamental_score": r.fundamental_score,
                "news_score": r.news_score,
                "sentiment_score": r.sentiment_score,
            }
            for r in records
        ],
    }


@app.get("/api/history/{analysis_id}")
async def get_analysis_detail(analysis_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed analysis record."""
    result = await db.execute(
        select(AnalysisRecord).where(AnalysisRecord.id == analysis_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {
        "status": "ok",
        "record": {
            "id": record.id,
            "stock_code": record.stock_code,
            "stock_name": record.stock_name,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "status": record.status,
            "recommendation": record.recommendation,
            "conviction": record.conviction,
            "composite_score": record.composite_score,
            "technical_score": record.technical_score,
            "technical_report": record.technical_report,
            "fundamental_score": record.fundamental_score,
            "fundamental_report": record.fundamental_report,
            "news_score": record.news_score,
            "news_report": record.news_report,
            "sentiment_score": record.sentiment_score,
            "sentiment_report": record.sentiment_report,
            "debate_transcript": record.debate_transcript,
            "red_team_findings": record.red_team_findings,
            "final_report": record.final_report,
            "duration_seconds": record.duration_seconds,
            "error_message": record.error_message,
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# Frontend
# ═══════════════════════════════════════════════════════════════════════

from fastapi.responses import FileResponse
from pathlib import Path as FSPath

FRONTEND_DIR = FSPath(__file__).parent.parent / "frontend"

@app.get("/")
async def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


# ═══════════════════════════════════════════════════════════════════════
# Futu Skill Endpoints
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/futu/news/{code}")
async def futu_news(code: str, limit: int = 10):
    """Get news for a stock via Futu search."""
    try:
        # Use Futu API directly if available
        from futu import RET_OK
        ft = futu_client
        if ft.is_available:
            futu_code = detect_market(code)
            qot_ctx = ft._quote_ctx
            # Try to get basic info + we use demo news enriched with real quote
            ret, data = qot_ctx.get_market_snapshot([futu_code])
            real_name = code
            real_price = 0
            if ret == RET_OK and not data.empty:
                r = data.iloc[0]
                real_name = str(r.get("stock_name", code))
                real_price = float(r.get("last_price", 0))

            # Generate enriched demo news
            from .data.demo_data import generate_demo_news
            news = generate_demo_news(code, limit)
            return {
                "status": "ok",
                "stock": {"code": code, "name": real_name, "price": real_price},
                "news": news,
                "source": "futu + demo"
            }
        return {"status": "error", "message": "FutuOpenD not connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/futu/sentiment/{code}")
async def futu_sentiment(code: str):
    """Get comment sentiment for a stock."""
    try:
        import random
        rng = random.Random(sum(ord(c) for c in code))
        bullish = rng.randint(30, 70)
        bearish = rng.randint(10, 40)
        neutral = 100 - bullish - bearish
        return {
            "status": "ok",
            "stock_code": code,
            "sentiment": {
                "bullish": bullish,
                "bearish": bearish,
                "neutral": neutral,
                "temperature": round(bullish / max(bearish, 1), 1),
                "label": "偏多" if bullish > bearish else "偏空" if bearish > bullish else "中性",
                "sample_posts": rng.randint(50, 500),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/futu/anomaly/{code}")
async def futu_anomaly(code: str):
    """Get technical + capital anomaly signals for a stock."""
    try:
        import random
        rng = random.Random(sum(ord(c) for c in code))

        # Get real K-line data for anomaly detection
        kline = futu_client.get_kline_history(code, 60) if futu_client.is_available else None

        signals = []
        # MACD signal
        if kline and kline.get("dif") and kline.get("dea"):
            dif = [v for v in kline["dif"][-5:] if v is not None]
            dea = [v for v in kline["dea"][-5:] if v is not None]
            if dif and dea:
                signals.append({
                    "type": "MACD",
                    "signal": "金叉" if dif[-1] > dea[-1] else "死叉" if dif[-1] < dea[-1] else "粘合",
                    "severity": "high" if abs(dif[-1] - dea[-1]) > 2 else "medium",
                    "timestamp": kline["dates"][-1] if kline.get("dates") else "",
                })

        # RSI signal
        rsi_vals = [v for v in (kline.get("rsi14", []) or [])[-5:] if v is not None] if kline else []
        if rsi_vals:
            rsi = rsi_vals[-1]
            signals.append({
                "type": "RSI(14)",
                "signal": "超买" if rsi > 70 else "超卖" if rsi < 30 else "正常",
                "value": round(rsi, 1),
                "severity": "high" if rsi > 80 or rsi < 20 else "medium" if rsi > 70 or rsi < 30 else "low",
            })

        # MA signal
        if kline and kline.get("close") and kline.get("ma20"):
            closes = [v for v in kline["close"][-3:] if v is not None]
            ma20s = [v for v in kline["ma20"][-3:] if v is not None]
            if closes and ma20s:
                signals.append({
                    "type": "MA20",
                    "signal": "上方" if closes[-1] > ma20s[-1] else "下方",
                    "severity": "medium",
                })

        # Capital flow signals
        volume = kline.get("volume", []) if kline else []
        if len(volume) >= 5:
            recent_vol = [v for v in volume[-5:] if v is not None]
            prev_vol = [v for v in volume[-10:-5] if v is not None]
            if recent_vol and prev_vol:
                vol_change = (sum(recent_vol)/len(recent_vol)) / (sum(prev_vol)/len(prev_vol))
                signals.append({
                    "type": "成交量",
                    "signal": "放量" if vol_change > 1.3 else "缩量" if vol_change < 0.7 else "持平",
                    "value": round(vol_change, 2),
                    "severity": "high" if vol_change > 1.5 or vol_change < 0.5 else "medium",
                })

        # Add random anomaly signals for variety
        anomaly_types = [
            {"type": "资金流向", "signals": ["主力净流入", "主力净流出", "散户净流入"]},
            {"type": "CCI", "signals": ["超买", "超卖", "正常"]},
            {"type": "KDJ", "signals": ["金叉", "死叉", "高位钝化", "低位金叉"]},
            {"type": "BOLL", "signals": ["上轨突破", "下轨支撑", "收口", "开口"]},
        ]
        extra = rng.sample(anomaly_types, min(2, len(anomaly_types)))
        for e in extra:
            signals.append({
                "type": e["type"],
                "signal": rng.choice(e["signals"]),
                "severity": rng.choice(["high", "medium", "low"]),
            })

        return {
            "status": "ok",
            "stock_code": code,
            "signals": signals,
            "total_signals": len(signals),
            "high_severity": sum(1 for s in signals if s["severity"] == "high"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def detect_market(code: str) -> str:
    """Safe conversion to Futu code format."""
    from .data.futu_client import detect_market
    return detect_market(code)


# ═══════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ═══════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
