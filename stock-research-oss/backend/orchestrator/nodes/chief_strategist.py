"""Chief Strategist node — final synthesis and investment recommendation."""
import logging
from ..state import AnalysisState, FinalReport
from ...agents.base import AgentBase, get_chief_model
from ...agents.prompts import CHIEF_STRATEGIST_PROMPT

logger = logging.getLogger(__name__)

agent = AgentBase("chief_strategist", CHIEF_STRATEGIST_PROMPT, temperature=0.3)  # Lower temp for consistency


async def run_chief_strategist(state: AnalysisState) -> AnalysisState:
    """Synthesize all reports, debate, and red team findings into a final recommendation."""
    state["status_message"] = "首席策略官正在进行最终综合研判..."
    state["current_phase"] = "phase3"
    logger.info("Running Chief Strategist synthesis...")

    context = {
        **state,
        "_task": "你是首席策略官。请综合所有分析报告、辩论记录和红队验证结果，做出最终投资决策。",
    }

    result = await agent.invoke(context, output_schema=FinalReport)
    state["final_report"] = result

    rec = result.get("recommendation", "N/A")
    score = result.get("composite_score", "N/A")
    state["status_message"] = f"分析完成 — 建议: {rec}，综合评分: {score}/10"
    state["current_phase"] = "complete"

    logger.info(f"Chief Strategist done. Recommendation: {rec}, Score: {score}")
    return state
