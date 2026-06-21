"""Futu OpenAPI client for real-time A-share market data.

Requires FutuOpenD gateway running locally (default: 127.0.0.1:11111).
Download: https://www.futunn.com/download/OpenAPI

A-share code format: SH.600519 (Shanghai) or SZ.000837 (Shenzhen)
"""
import logging
from typing import Optional
from .cache import cache
from ..config import CACHE_TTL_QUOTE, CACHE_TTL_FINANCIAL

logger = logging.getLogger(__name__)

FUTU_HOST = "127.0.0.1"
FUTU_PORT = 11111


def detect_market(code: str) -> str:
    """Auto-detect market from code format and return (futu_code, market).

    Rules:
      - Pure letters (1-5 chars): US stock → US.XXXX
      - 5 digits: HK stock → HK.XXXXX
      - 6 digits starting with 6/9: Shanghai A-share → SH.XXXXXX
      - 6 digits starting with 0/3/2: Shenzhen A-share → SZ.XXXXXX
    """
    code = code.strip().upper()

    # Already in Futu format
    if "." in code:
        return code

    # US stock: pure letters
    if code.isalpha() and len(code) <= 5:
        return f"US.{code}"

    # Numeric codes
    if code.isdigit():
        if len(code) == 5:
            return f"HK.{code}"
        if len(code) == 6:
            if code[0] in ("6", "9"):
                return f"SH.{code}"
            else:
                return f"SZ.{code}"

    # Default: treat as US
    return f"US.{code}"


def _to_futu_code(code: str) -> str:
    """Convert any stock code to Futu format. (backward compat)"""
    return detect_market(code)


class FutuClient:
    """Futu OpenAPI client for real-time and historical A-share data."""

    def __init__(self):
        self._quote_ctx = None
        self._available = None  # None = unchecked, True/False after check

    def _connect(self) -> bool:
        """Lazily connect to FutuOpenD. Returns True if connected.

        Uses a short timeout to avoid blocking when FutuOpenD is not running.
        """
        if self._available is False:
            return False
        if self._quote_ctx is not None:
            return True

        try:
            import socket
            # Quick pre-check: is port 11111 even open?
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex((FUTU_HOST, FUTU_PORT))
            sock.close()
            if result != 0:
                logger.info(f"FutuOpenD not reachable on {FUTU_HOST}:{FUTU_PORT}")
                self._available = False
                return False

            from futu import OpenQuoteContext, RET_OK

            self._quote_ctx = OpenQuoteContext(host=FUTU_HOST, port=FUTU_PORT)
            # Test connection
            ret, data = self._quote_ctx.get_global_state()
            if ret == RET_OK:
                self._available = True
                logger.info(f"FutuOpenD connected: {FUTU_HOST}:{FUTU_PORT}")
                return True
            else:
                logger.warning(f"FutuOpenD connection failed: {data}")
                self._quote_ctx.close()
                self._quote_ctx = None
                self._available = False
                return False
        except Exception as e:
            logger.info(f"FutuOpenD not available: {e}")
            self._quote_ctx = None
            self._available = False
            return False

    def _disconnect(self):
        """Close the Futu connection."""
        if self._quote_ctx:
            try:
                self._quote_ctx.close()
            except Exception:
                pass
            self._quote_ctx = None
            self._available = None

    @property
    def is_available(self) -> bool:
        """Check if FutuOpenD is reachable."""
        if self._available is None:
            return self._connect()
        return self._available

    # ─── Real-Time Quote ──────────────────────────────────────────

    def get_realtime_quote(self, code: str) -> Optional[dict]:
        """Get real-time stock quote via Futu OpenAPI."""
        if not self.is_available:
            return None

        cache_key = f"futu_quote_{code}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            from futu import RET_OK

            futu_code = _to_futu_code(code)
            ret, data = self._quote_ctx.get_market_snapshot([futu_code])

            if ret != RET_OK or data.empty:
                logger.warning(f"Futu snapshot failed for {futu_code}: {data}")
                return None

            row = data.iloc[0]
            result = {
                "code": code,
                "name": str(row.get("stock_name", row.get("name", ""))),
                "price": float(row.get("last_price", 0)),
                "change_pct": float(row.get("change_rate", 0)) * 100 if "change_rate" in row else float(row.get("pct_chg", 0)),
                "change_amount": float(row.get("change_val", 0)),
                "volume": float(row.get("volume", 0)),
                "amount": float(row.get("turnover", 0)),
                "high": float(row.get("high_price", 0)),
                "low": float(row.get("low_price", 0)),
                "open": float(row.get("open_price", 0)),
                "pre_close": float(row.get("prev_close_price", 0)),
                "turnover": float(row.get("turnover_rate", 0)) if "turnover_rate" in row else 0,
                "pe": float(row.get("pe_ttm", 0)) if "pe_ttm" in row else 0,
                "pb": float(row.get("pb_rate", 0)) if "pb_rate" in row else 0,
                "total_mv": float(row.get("total_market_val", 0)) if "total_market_val" in row else 0,
                "circ_mv": float(row.get("circular_market_val", 0)) if "circular_market_val" in row else 0,
            }

            cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
            logger.info(f"Futu quote for {code}: ¥{result['price']} ({result['change_pct']:+.2f}%)")
            return result

        except Exception as e:
            logger.error(f"Futu quote error for {code}: {e}")
            return None

    # ─── K-Line History ───────────────────────────────────────────

    def get_kline_history(self, code: str, days: int = 250) -> Optional[dict]:
        """Get daily K-line history via Futu."""
        if not self.is_available:
            return None

        cache_key = f"futu_kline_{code}_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            from futu import RET_OK, KLType, AuType
            import pandas as pd
            import numpy as np

            futu_code = _to_futu_code(code)

            ret, data, _ = self._quote_ctx.request_history_kline(
                futu_code,
                max_count=min(days + 50, 1000),
                ktype=KLType.K_DAY,
                autype=AuType.QFQ,  # 前复权
            )

            if ret != RET_OK or data.empty:
                logger.warning(f"Futu K-line failed for {futu_code}")
                return None

            df = data.tail(days)

            # Compute indicators
            close = df["close"].astype(float)
            high = df["high"].astype(float)
            low = df["low"].astype(float)
            vol = df["volume"].astype(float)
            amount = df["turnover"].astype(float)

            # MA
            ma5 = close.rolling(5).mean()
            ma10 = close.rolling(10).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()

            # MACD
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9).mean()
            macd = 2 * (dif - dea)

            # RSI(14)
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1 / 14).mean()
            avg_loss = loss.ewm(alpha=1 / 14).mean()
            rs_val = avg_gain / avg_loss.replace(0, 1e-9)
            rsi14 = 100 - (100 / (1 + rs_val))

            # Volume MA
            vol_ma5 = vol.rolling(5).mean()
            vol_ma20 = vol.rolling(20).mean()

            # ATR(14)
            tr1 = high - low
            tr2 = (high - close.shift()).abs()
            tr3 = (low - close.shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr14 = tr.ewm(alpha=1 / 14).mean()

            result = {
                "dates": df.index.astype(str).tolist() if hasattr(df.index, "astype") else [str(d) for d in df["time_key"]] if "time_key" in df.columns else [],
                "open": df["open"].astype(float).tolist(),
                "high": high.tolist(),
                "low": low.tolist(),
                "close": close.tolist(),
                "volume": vol.tolist(),
                "amount": amount.tolist(),
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

            cache.set(cache_key, result, ttl=CACHE_TTL_QUOTE)
            logger.info(f"Futu K-line for {code}: {len(df)} points")
            return result

        except Exception as e:
            logger.error(f"Futu K-line error for {code}: {e}")
            return None

    # ─── Batch Fetch ──────────────────────────────────────────────

    def fetch_quote_and_kline(self, code: str, days: int = 250) -> tuple[Optional[dict], Optional[dict]]:
        """Fetch both quote and K-line in one connection session."""
        if not self.is_available:
            return None, None

        quote = self.get_realtime_quote(code)
        kline = self.get_kline_history(code, days)
        return quote, kline


# Global instance
futu = FutuClient()
