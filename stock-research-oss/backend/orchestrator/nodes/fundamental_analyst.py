"""Fundamental analyst node."""
import logging
from ..state import AnalysisState, AnalystReport
from ...agents.base import AgentBase, get_analyst_model
from ...agents.prompts import FUNDAMENTAL_ANALYST_PROMPT

logger = logging.getLogger(__name__)

agent = AgentBase("fundamental", FUNDAMENTAL_ANALYST_PROMPT, temperature=0.7)


async def run_fundamental_analyst(state: AnalysisState) -> AnalysisState:
    """Run fundamental analysis on the stock data."""
    state["status_message"] = "基本面分析师正在分析财务报表..."
    logger.info("Running Fundamental Analyst...")

    result = await agent.invoke(state, output_schema=AnalystReport)
    state["fundamental_report"] = result
    state["status_message"] = f"基本面分析师完成，评分: {result.get('score', 'N/A')}/10"

    logger.info(f"Fundamental Analyst done. Score: {result.get('score')}")
    return state
