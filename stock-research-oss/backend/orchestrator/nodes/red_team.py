"""Red Team node — adversarial verification of all claims."""
import logging
from ..state import AnalysisState, RedTeamReport
from ...agents.base import AgentBase, get_red_team_model
from ...agents.prompts import RED_TEAM_PROMPT

logger = logging.getLogger(__name__)

agent = AgentBase("red_team", RED_TEAM_PROMPT, temperature=1.0)  # Higher temp for creative skepticism


async def run_red_team(state: AnalysisState) -> AnalysisState:
    """Adversarially verify all analyst claims and debate arguments."""
    state["status_message"] = "🔴 AI红队正在进行独立证伪验证..."
    logger.info("Running Red Team verification...")

    # Build debate transcript
    debate_parts = []
    if state.get("bull_thesis"):
        debate_parts.append(f"## 多头论点\n\n{state['bull_thesis']}")
    if state.get("bear_thesis"):
        debate_parts.append(f"## 空头论点\n\n{state['bear_thesis']}")
    state["debate_transcript"] = "\n\n---\n\n".join(debate_parts)

    context = {
        **state,
        "_task": "你是红队证伪分析师。请验证所有关键论断并找出逻辑漏洞。",
    }

    result = await agent.invoke(context, output_schema=RedTeamReport)
    state["red_team_findings"] = result
    state["status_message"] = f"红队证伪完成，整体可信度: {result.get('overall_credibility', 'N/A')}/10"

    logger.info(f"Red Team done. Credibility: {result.get('overall_credibility')}")
    return state
