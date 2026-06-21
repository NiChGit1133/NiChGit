"""AkShare client for Chinese A-share market data with caching and fallback.

Data source priority: Futu OpenAPI → AkShare → efinance → Baostock → Demo
"""
import asyncio
import time
import logging
import pandas as pd
from typing import Optional
from .cache import cache
from .baostock_client import BaostockClient
from .futu_client import futu as futu_client
from .demo_data import (
    generate_demo_quote, generate_demo_kline, generate_demo_financial,
    generate_demo_news, generate_demo_fund_flows, DEMO_STOCKS
)
from ..config import CACHE_TTL_QUOTE, CACHE_TTL_FINANCIAL, API_RATE_LIMIT

logger = logging.getLogger(__name__)

# Circuit breaker: once a source fails, skip it for subsequent calls
_circuit_breaker = {"akshare": True, "efinance": True, "baostock": True}


class AkShareClient:
    """Wraps AkShare API calls with caching, rate limiting, and fallback."""

    def __init__(self):
        self.baostock = BaostockClient()
        self._last_request_time = 0.0

    async def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / API_RATE_LIMIT
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    async def _try_akshare(self, func, *args, **kwargs):
        """Try an AkShare call. Circuit breaker: skip if previously failed."""
        if not _circuit_breaker.get("akshare", True):
            return None
        try:
            await self._rate_limit()
            result = await asyncio.wait_for(
                asyncio.to_thread(func, *args, **kwargs),
                timeout=1.5  # Short timeout — Futu is our primary source
            )
            if result is not None and not (isinstance(result, pd.DataFrame) and result.empty):
                return result
        except (asyncio.TimeoutError, Exception):
            _circuit_breaker["akshare"] = False  # Don't try again
        return None

    # ─── Real-Time & Quote Data ───────────────────────────────────────

    async def get_realtime_quote(self, code: str) -> dict | None:
        """Get real-time stock quote.

        Priority: Futu (instant) → efinance (2s timeout) → demo (instant)
        """
        cache_key = f"quote_{code}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 1. Try Futu OpenAPI (instant when available — the real solution)
        result = futu_client.get_realtime_quote(code)
        if result:
            cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
            return result

        # 2. Try efinance with 2-second timeout
        try:
            result = await asyncio.wait_for(
                self._get_quote_efinance(code), timeout=2.0
            )
            if result:
                cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
                logger.info(f"Got quote via efinance for {code}")
                return result
        except (asyncio.TimeoutError, Exception):
            pass

        # 3. Demo data (instant)
        logger.info(f"Using demo data for {code}")
        result = generate_demo_quote(code)
        if result:
            cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
        return result

    async def _get_quote_efinance(self, code: str) -> dict | None:
        """Get real-time quote via efinance (internal, circuit-breaker protected)."""
        if not _circuit_breaker.get("efinance", True):
            return None
        try:
            import efinance as ef
            await self._rate_limit()
            df = await asyncio.wait_for(
                asyncio.to_thread(ef.stock.get_realtime_quotes),
                timeout=1.5
            )
            if df is None or df.empty:
                return None
            row = df[df["股票代码"] == code]
            if row.empty:
                row = df[df["股票代码"] == code.zfill(6)]
            if row.empty:
                return None
            r = row.iloc[0]
            return {
                "code": str(r.get("股票代码", code)),
                "name": str(r.get("股票名称", "")),
                "price": float(r.get("最新价", 0)),
                "change_pct": float(r.get("涨跌幅", 0)),
                "change_amount": float(r.get("涨跌额", 0)),
                "volume": float(r.get("成交量", 0)),
                "amount": float(r.get("成交额", 0)),
                "high": float(r.get("最高", 0)),
                "low": float(r.get("最低", 0)),
                "open": float(r.get("今开", 0)),
                "pre_close": float(r.get("昨收", 0)),
                "turnover": float(r.get("换手率", 0)) if "换手率" in r.index else 0,
                "pe": float(r.get("市盈率-动态", 0)) if "市盈率-动态" in r.index else 0,
                "pb": float(r.get("市净率", 0)) if "市净率" in r.index else 0,
                "total_mv": float(r.get("总市值", 0)) if "总市值" in r.index else 0,
                "circ_mv": float(r.get("流通市值", 0)) if "流通市值" in r.index else 0,
            }
        except (asyncio.TimeoutError, Exception):
            _circuit_breaker["efinance"] = False
            return None

    # ─── K-Line History ───────────────────────────────────────────────

    async def get_kline_history(self, code: str, period: str = "daily", days: int = 250) -> dict | None:
        """Get K-line history data.

        Priority: Futu → AkShare → Baostock → demo
        """
        cache_key = f"kline_{code}_{period}_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 1. Try Futu OpenAPI
        result = futu_client.get_kline_history(code, days)
        if result:
            cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
            return result

        # 2. Try AkShare
        try:
            import akshare as ak

            df = await self._try_akshare(
                ak.stock_zh_a_hist,
                symbol=code,
                period=period,
                start_date=(pd.Timestamp.now() - pd.Timedelta(days=days + 30)).strftime("%Y%m%d"),
                end_date=pd.Timestamp.now().strftime("%Y%m%d"),
                adjust="qfq",
            )

            if df is not None and not df.empty:
                df = df.tail(days)
                result = self._process_kline_df(df, days)
                if result:
                    cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
                    logger.info(f"Got K-line via AkShare for {code}: {result['data_points']} points")
                    return result
        except Exception as e:
            logger.warning(f"AkShare K-line failed for {code}: {e}")

        # Try Baostock
        logger.info(f"Trying Baostock K-line for {code}...")
        result = self.baostock.get_kline_history(code, days)
        if result:
            cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
            return result

        # Fallback: demo data
        logger.info(f"Using demo K-line data for {code}")
        result = generate_demo_kline(code, days)
        if result:
            cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
        return result

    def _process_kline_df(self, df: pd.DataFrame, days: int) -> dict | None:
        """Process raw AkShare K-line dataframe into standard format."""
        try:
            df = df.tail(days)
            close = df["收盘"].astype(float)
            high = df["最高"].astype(float)
            low = df["最低"].astype(float)
            vol = df["成交量"].astype(float)

            ma5 = close.rolling(5).mean()
            ma10 = close.rolling(10).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()

            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9).mean()
            macd = 2 * (dif - dea)

            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1 / 14).mean()
            avg_loss = loss.ewm(alpha=1 / 14).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-9)
            rsi14 = 100 - (100 / (1 + rs))

            vol_ma5 = vol.rolling(5).mean()
            vol_ma20 = vol.rolling(20).mean()

            tr1 = high - low
            tr2 = (high - close.shift()).abs()
            tr3 = (low - close.shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr14 = tr.ewm(alpha=1 / 14).mean()

            return {
                "dates": df["日期"].tolist(),
                "open": df["开盘"].astype(float).tolist(),
                "high": high.tolist(),
                "low": low.tolist(),
                "close": close.tolist(),
                "volume": vol.tolist(),
                "amount": df.get("成交额", pd.Series([0] * len(df))).astype(float).tolist(),
                "ma5": ma5.tolist(),
                "ma10": ma10.tolist(),
                "ma20": ma20.tolist(),
                "ma60": ma60.tolist(),
                "dif": dif.tolist(),
                "dea": dea.tolist(),
                "macd": macd.tolist(),
                "rsi14": rsi14.tolist(),
                "vol_ma5": vol_ma5.tolist(),
                "vol_ma20": vol_ma20.tolist(),
                "atr14": atr14.tolist(),
                "latest_close": float(close.iloc[-1]),
                "data_points": len(df),
            }
        except Exception as e:
            logger.error(f"Failed to process K-line dataframe: {e}")
            return None

    # ─── Financial Statements ────────────────────────────────────────

    async def get_financial_data(self, code: str) -> dict | None:
        """Get financial statements (instant demo data)."""
        cache_key = f"financial_{code}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        result = generate_demo_financial(code)
        if result:
            cache.set(cache_key, result, ttl=CACHE_TTL_FINANCIAL)
        return result

    # ─── News ─────────────────────────────────────────────────────────

    async def get_stock_news(self, code: str, limit: int = 20) -> list[dict]:
        """Get recent news for a stock (instant demo data)."""
        cache_key = f"news_{code}_{limit}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        news = generate_demo_news(code, limit)
        cache.set(cache_key, news, ttl=CACHE_TTL_QUOTE)
        return news

    # ─── Fund Flows ───────────────────────────────────────────────────

    async def get_fund_flows(self, code: str) -> dict | None:
        """Get fund flow data (instant demo data)."""
        cache_key = f"fundflow_{code}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        result = generate_demo_fund_flows(code)
        if result:
            cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
        return result

    # ─── Industry Comparison ──────────────────────────────────────────

    async def get_industry_data(self, code: str) -> dict | None:
        """Get industry/sector data (instant)."""
        return None  # Skip for speed — not critical for analysis

    # ─── Composite Data Fetch ────────────────────────────────────────

    async def fetch_all(self, code: str) -> dict:
        """Fetch all data for a stock in parallel. Returns a combined dict."""
        quote, kline, financial, news, fund_flows, industry = await asyncio.gather(
            self.get_realtime_quote(code),
            self.get_kline_history(code),
            self.get_financial_data(code),
            self.get_stock_news(code),
            self.get_fund_flows(code),
            self.get_industry_data(code),
            return_exceptions=True,
        )

        result = {
            "stock_code": code,
            "stock_name": quote.get("name", code) if isinstance(quote, dict) else code,
            "quote": quote if isinstance(quote, dict) else None,
            "kline": kline if isinstance(kline, dict) else None,
            "financial": financial if isinstance(financial, dict) else None,
            "news": news if isinstance(news, list) else [],
            "fund_flows": fund_flows if isinstance(fund_flows, dict) else None,
            "industry": industry if isinstance(industry, dict) else None,
        }

        # Count failures
        failures = sum(1 for v in [result["quote"], result["kline"], result["financial"]] if v is None)
        if failures > 0:
            logger.warning(f"Data fetch for {code}: {failures} sources failed")

        return result


# Global client instance
akshare = AkShareClient()
