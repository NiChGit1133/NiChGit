"""Sentiment analyst node."""
import logging
from ..state import AnalysisState, AnalystReport
from ...agents.base import AgentBase, get_analyst_model
from ...agents.prompts import SENTIMENT_ANALYST_PROMPT

logger = logging.getLogger(__name__)

agent = AgentBase("sentiment", SENTIMENT_ANALYST_PROMPT, temperature=0.7)


async def run_sentiment_analyst(state: AnalysisState) -> AnalysisState:
    """Run sentiment analysis on the stock data."""
    state["status_message"] = "情绪分析师正在分析资金流向和市场情绪..."
    logger.info("Running Sentiment Analyst...")

    result = await agent.invoke(state, output_schema=AnalystReport)
    state["sentiment_report"] = result
    state["status_message"] = f"情绪分析师完成，评分: {result.get('score', 'N/A')}/10"

    logger.info(f"Sentiment Analyst done. Score: {result.get('score')}")
    return state
