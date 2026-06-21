"""News analyst node."""
import logging
from ..state import AnalysisState, AnalystReport
from ...agents.base import AgentBase, get_analyst_model
from ...agents.prompts import NEWS_ANALYST_PROMPT

logger = logging.getLogger(__name__)

agent = AgentBase("news", NEWS_ANALYST_PROMPT, temperature=0.7)


async def run_news_analyst(state: AnalysisState) -> AnalysisState:
    """Run news analysis on the stock data."""
    state["status_message"] = "新闻分析师正在梳理近期新闻和催化因素..."
    logger.info("Running News Analyst...")

    result = await agent.invoke(state, output_schema=AnalystReport)
    state["news_report"] = result
    state["status_message"] = f"新闻分析师完成，评分: {result.get('score', 'N/A')}/10"

    logger.info(f"News Analyst done. Score: {result.get('score')}")
    return state
