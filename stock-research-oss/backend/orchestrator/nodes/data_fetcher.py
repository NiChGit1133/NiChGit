"""Data fetching node — pre-fetches all data before analysis begins."""
import logging
from ..state import AnalysisState
from ...data.akshare_client import akshare

logger = logging.getLogger(__name__)


async def fetch_stock_data(state: AnalysisState) -> AnalysisState:
    """Fetch all required data for a stock and populate the state."""
    code = state["stock_code"]
    state["current_phase"] = "data_fetching"
    state["status_message"] = f"正在获取{state.get('stock_name', code)}的实时数据..."

    logger.info(f"Fetching all data for {code}...")

    data = await akshare.fetch_all(code)

    # Update stock name if we got it
    stock_name = data.get("stock_name", code)
    if stock_name and stock_name != code:
        state["stock_name"] = stock_name

    # Populate state fields
    # Merge quote and kline into market_data for backward compatibility
    market_data = {}
    if data.get("quote"):
        market_data.update(data["quote"])
    if data.get("kline"):
        market_data.update(data["kline"])
    state["market_data"] = market_data

    state["financial_data"] = data.get("financial")
    state["news_data"] = data.get("news", [])
    state["sentiment_data"] = data.get("fund_flows")
    state["industry_data"] = data.get("industry")

    data_sources = sum(1 for v in [data.get("quote"), data.get("kline"), data.get("financial"),
                                   data.get("news"), data.get("fund_flows")] if v)
    state["status_message"] = f"数据获取完成，共获取{data_sources}个数据源"

    logger.info(f"Data fetch complete for {code}: {data_sources} sources")
    return state
