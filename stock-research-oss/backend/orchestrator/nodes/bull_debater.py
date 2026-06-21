"""Bull debater node — constructs the strongest bullish thesis."""
import logging
from ..state import AnalysisState
from ...agents.base import AgentBase
from ...agents.prompts import BULL_DEBATER_PROMPT

logger = logging.getLogger(__name__)

agent = AgentBase("bull_debater", BULL_DEBATER_PROMPT, temperature=0.8)


async def run_bull_debater(state: AnalysisState) -> AnalysisState:
    """Build the bullish investment thesis from analyst reports."""
    state["status_message"] = "多头辩论手正在构建看多论点..."
    state["current_phase"] = "phase2"
    logger.info("Running Bull Debater...")

    # Prepare context: all 4 analyst reports
    context = {
        **state,
        "_task": "你是多头辩论手。请基于以下四位分析师的报告构建最强看多论点。",
    }

    result = await agent.invoke(context)
    thesis = result.get("report", result.get("raw_text", str(result)))
    state["bull_thesis"] = thesis
    state["status_message"] = "多头辩论完成"

    logger.info(f"Bull Debater done. Thesis length: {len(thesis)}")
    return state
