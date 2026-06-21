"""Baostock client for historical A-share data (reliable fallback)."""
import baostock as bs
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BaostockClient:
    """Provides historical A-share data via Baostock as a fallback source."""

    def __init__(self):
        self._logged_in = False

    def _ensure_login(self):
        if not self._logged_in:
            lg = bs.login()
            if lg.error_code != "0":
                logger.error(f"Baostock login failed: {lg.error_msg}")
                raise ConnectionError(f"Baostock login failed: {lg.error_msg}")
            self._logged_in = True
            logger.info("Baostock logged in")

    def _logout(self):
        if self._logged_in:
            bs.logout()
            self._logged_in = False

    def _format_code(self, code: str) -> str:
        """Convert stock code to Baostock format (sh.000837 or sz.000837)."""
        code = code.replace(".SZ", "").replace(".SH", "").strip()
        if code.startswith(("6", "9")):
            return f"sh.{code}"
        elif code.startswith(("0", "3", "2")):
            return f"sz.{code}"
        else:
            return f"sz.{code}"  # Default to Shenzhen

    def get_kline_history(self, code: str, days: int = 250) -> dict | None:
        """Get daily K-line history data.

        Returns dict with keys: dates, open, high, low, close, volume, amounts
        """
        try:
            self._ensure_login()
            bs_code = self._format_code(code)
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days + 30)).strftime("%Y-%m-%d")

            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2"  # 前复权
            )

            if rs.error_code != "0":
                logger.error(f"Baostock query failed: {rs.error_msg}")
                return None

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return None

            df = pd.DataFrame(data_list, columns=rs.fields)

            # Convert types
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Take only the last N days
            df = df.tail(days)

            result = {
                "dates": df["date"].tolist(),
                "open": df["open"].tolist(),
                "high": df["high"].tolist(),
                "low": df["low"].tolist(),
                "close": df["close"].tolist(),
                "volume": df["volume"].tolist(),
                "amount": df["amount"].tolist(),
                "latest_close": float(df["close"].iloc[-1]) if len(df) > 0 else None,
                "data_points": len(df),
            }

            logger.info(f"Baostock: got {len(df)} K-line records for {code}")
            return result

        except Exception as e:
            logger.error(f"Baostock K-line error for {code}: {e}")
            return None

    def get_stock_basic_info(self, code: str) -> dict | None:
        """Get basic stock information."""
        try:
            self._ensure_login()
            bs_code = self._format_code(code)

            rs = bs.query_stock_basic(code=bs_code)
            if rs.error_code != "0":
                return None

            data = []
            while rs.next():
                data.append(rs.get_row_data())

            if not data:
                return None

            row = data[0]
            return {
                "code": row[0] if len(row) > 0 else code,
                "name": row[1] if len(row) > 1 else "",
                "ipo_date": row[2] if len(row) > 2 else "",
                "type": row[3] if len(row) > 3 else "",
            }
        except Exception as e:
            logger.error(f"Baostock basic info error for {code}: {e}")
            return None
