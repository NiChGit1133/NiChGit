"""Technical analyst node."""
import logging
from ..state import AnalysisState, AnalystReport
from ...agents.base import AgentBase, get_analyst_model
from ...agents.prompts import TECHNICAL_ANALYST_PROMPT

logger = logging.getLogger(__name__)

agent = AgentBase("technical", TECHNICAL_ANALYST_PROMPT, temperature=0.7)


async def run_technical_analyst(state: AnalysisState) -> AnalysisState:
    """Run technical analysis on the stock data."""
    state["status_message"] = "技术分析师正在分析K线形态和指标..."
    logger.info("Running Technical Analyst...")

    result = await agent.invoke(state, output_schema=AnalystReport)
    state["technical_report"] = result
    state["status_message"] = f"技术分析师完成，评分: {result.get('score', 'N/A')}/10"

    logger.info(f"Technical Analyst done. Score: {result.get('score')}")
    return state
