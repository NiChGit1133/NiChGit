"""Bear debater node — constructs the strongest bearish thesis."""
import logging
from ..state import AnalysisState
from ...agents.base import AgentBase
from ...agents.prompts import BEAR_DEBATER_PROMPT

logger = logging.getLogger(__name__)

agent = AgentBase("bear_debater", BEAR_DEBATER_PROMPT, temperature=0.8)


async def run_bear_debater(state: AnalysisState) -> AnalysisState:
    """Build the bearish investment thesis and rebut the bull."""
    state["status_message"] = "空头辩论手正在构建看空论点并反驳多头..."
    logger.info("Running Bear Debater...")

    context = {
        **state,
        "_task": "你是空头辩论手。请基于分析师报告和多头论点构建最强看空论点，并逐条反驳多头观点。",
    }

    result = await agent.invoke(context)
    thesis = result.get("report", result.get("raw_text", str(result)))
    state["bear_thesis"] = thesis
    state["status_message"] = "空头辩论完成"

    logger.info(f"Bear Debater done. Thesis length: {len(thesis)}")
    return state
