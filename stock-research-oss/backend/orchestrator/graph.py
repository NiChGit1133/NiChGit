"""LangGraph StateGraph definition for the multi-analyst stock research workflow.

Workflow:
    Phase 1: fetch_data -> [technical || fundamental || news || sentiment] (parallel)
    Phase 2: bull_debater -> bear_debater -> red_team
    Phase 3: chief_strategist -> END
"""
import logging
from langgraph.graph import StateGraph, END
from .state import AnalysisState
from .nodes import (
    fetch_stock_data,
    run_technical_analyst,
    run_fundamental_analyst,
    run_news_analyst,
    run_sentiment_analyst,
    run_bull_debater,
    run_bear_debater,
    run_red_team,
    run_chief_strategist,
)

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build and return the LangGraph StateGraph for the analysis workflow."""

    builder = StateGraph(AnalysisState)

    # ── Nodes ──
    builder.add_node("fetch_data", fetch_stock_data)
    builder.add_node("technical_analyst", run_technical_analyst)
    builder.add_node("fundamental_analyst", run_fundamental_analyst)
    builder.add_node("news_analyst", run_news_analyst)
    builder.add_node("sentiment_analyst", run_sentiment_analyst)
    builder.add_node("bull_debater", run_bull_debater)
    builder.add_node("bear_debater", run_bear_debater)
    builder.add_node("red_team", run_red_team)
    builder.add_node("chief_strategist", run_chief_strategist)

    # ── Edges ──

    # Entry: fetch data first
    builder.set_entry_point("fetch_data")

    # Phase 1: Fan out to 4 parallel analysts after data fetch
    builder.add_edge("fetch_data", "technical_analyst")
    builder.add_edge("fetch_data", "fundamental_analyst")
    builder.add_edge("fetch_data", "news_analyst")
    builder.add_edge("fetch_data", "sentiment_analyst")

    # Phase 2: Sequential debate (bull -> bear -> red_team)
    # All 4 analysts must complete before debate starts
    # We use the LAST analyst to trigger the debate chain
    builder.add_edge("technical_analyst", "bull_debater")
    builder.add_edge("fundamental_analyst", "bull_debater")
    builder.add_edge("news_analyst", "bull_debater")
    builder.add_edge("sentiment_analyst", "bull_debater")

    # Debate chain: bull -> bear -> red_team
    builder.add_edge("bull_debater", "bear_debater")
    builder.add_edge("bear_debater", "red_team")

    # Phase 3: Chief strategist synthesizes everything
    builder.add_edge("red_team", "chief_strategist")

    # End
    builder.add_edge("chief_strategist", END)

    return builder


# Singleton compiled graph
_compiled_graph = None


def get_graph():
    """Get or compile the analysis workflow graph."""
    global _compiled_graph
    if _compiled_graph is None:
        builder = build_graph()
        _compiled_graph = builder.compile()
        logger.info("LangGraph analysis workflow compiled")
    return _compiled_graph


async def run_analysis(stock_code: str) -> dict:
    """Run the full analysis pipeline for a given stock code.

    Returns the final state dict.
    """
    graph = get_graph()

    initial_state: AnalysisState = {
        "stock_code": stock_code,
        "stock_name": stock_code,
        "market_data": {},
        "financial_data": None,
        "news_data": [],
        "sentiment_data": None,
        "industry_data": None,
        "technical_report": None,
        "fundamental_report": None,
        "news_report": None,
        "sentiment_report": None,
        "bull_thesis": None,
        "bear_thesis": None,
        "bull_rebuttal": None,
        "bear_rebuttal": None,
        "debate_transcript": None,
        "red_team_findings": None,
        "final_report": None,
        "current_phase": "starting",
        "status_message": "开始分析...",
        "error": None,
    }

    logger.info(f"Starting analysis for {stock_code}")
    final_state = await graph.ainvoke(initial_state)
    logger.info(f"Analysis complete for {stock_code}")

    return final_state


async def run_analysis_streaming(stock_code: str, temperature: float = 0.7, source: str = "auto"):
    """Run the analysis pipeline with streaming events for SSE.

    Args:
        stock_code: Stock ticker (e.g. AAPL, 000837)
        temperature: LLM temperature for analysts (0.1-1.5)
        source: Data source mode - 'auto', 'futu', or 'demo'
    """
    graph = get_graph()

    # Apply temperature to config (agents read this in their base class)
    import backend.config as cfg
    original_temp = cfg.ANALYST_TEMPERATURE
    original_source = cfg.DEFAULT_MODEL  # not changing model, just temp
    cfg.ANALYST_TEMPERATURE = temperature
    cfg.RED_TEAM_TEMPERATURE = min(temperature + 0.3, 1.5)
    cfg.CHIEF_TEMPERATURE = max(temperature - 0.4, 0.1)

    # Apply source mode
    if source == "demo":
        from backend.data.akshare_client import _circuit_breaker
        _circuit_breaker["akshare"] = False
        _circuit_breaker["efinance"] = False
    elif source == "futu":
        from backend.data.akshare_client import _circuit_breaker
        _circuit_breaker["akshare"] = False
        _circuit_breaker["efinance"] = False

    initial_state: AnalysisState = {
        "stock_code": stock_code,
        "stock_name": stock_code,
        "market_data": {},
        "financial_data": None,
        "news_data": [],
        "sentiment_data": None,
        "industry_data": None,
        "technical_report": None,
        "fundamental_report": None,
        "news_report": None,
        "sentiment_report": None,
        "bull_thesis": None,
        "bear_thesis": None,
        "bull_rebuttal": None,
        "bear_rebuttal": None,
        "debate_transcript": None,
        "red_team_findings": None,
        "final_report": None,
        "current_phase": "starting",
        "status_message": "正在连接数据源...",
        "error": None,
    }

    logger.info(f"Starting streaming analysis for {stock_code} (temp={temperature}, source={source})")

    agent_map = {
        "technical_analyst": "technical",
        "fundamental_analyst": "fundamental",
        "news_analyst": "news",
        "sentiment_analyst": "sentiment",
    }

    completed = set()

    try:
        async for chunk in graph.astream(initial_state):
            for node_name, state_update in chunk.items():
                if node_name in completed:
                    continue
                completed.add(node_name)

                logger.info(f"Node completed: {node_name}")

                if node_name == "fetch_data":
                    stock_name = state_update.get("stock_name", stock_code)
                    yield {
                        "event": "phase",
                        "data": {"phase": "phase1", "message": f"数据获取完成 - {stock_name}"},
                    }

                elif node_name in agent_map:
                    agent = agent_map[node_name]
                    yield {"event": "analyst_start", "data": {"agent": agent}}

                    report = state_update.get(f"{agent}_report", {}) or {}
                    if report:
                        yield {
                            "event": "analyst_complete",
                            "data": {
                                "agent": agent,
                                "score": report.get("score"),
                                "summary": report.get("summary", ""),
                                "report": report.get("report", ""),
                                "key_points": report.get("key_points", []),
                                "risks": report.get("risks", []),
                                "catalysts": report.get("catalysts", []),
                            },
                        }

                elif node_name == "bull_debater":
                    yield {"event": "phase", "data": {"phase": "phase2", "message": "多头辩论完成，空头准备反驳..."}}
                    thesis = state_update.get("bull_thesis", "")
                    yield {"event": "debate_round", "data": {"round": 1, "speaker": "bull", "content": thesis}}

                elif node_name == "bear_debater":
                    yield {"event": "phase", "data": {"phase": "phase2", "message": "空头辩论完成，红队开始证伪..."}}
                    thesis = state_update.get("bear_thesis", "")
                    yield {"event": "debate_round", "data": {"round": 2, "speaker": "bear", "content": thesis}}

                elif node_name == "red_team":
                    findings = state_update.get("red_team_findings", {}) or {}
                    yield {
                        "event": "red_team_complete",
                        "data": {
                            "verified_claims": findings.get("verified_claims", []),
                            "logical_fallacies": findings.get("logical_fallacies", []),
                            "missing_risks": findings.get("missing_risks", []),
                            "overall_credibility": findings.get("overall_credibility"),
                        },
                    }
                    yield {"event": "phase", "data": {"phase": "phase3", "message": "首席策略官最终研判中..."}}

                elif node_name == "chief_strategist":
                    final = state_update.get("final_report", {}) or {}
                    yield {
                        "event": "final_report",
                        "data": {
                            "recommendation": final.get("recommendation"),
                            "conviction": final.get("conviction"),
                            "composite_score": final.get("composite_score"),
                            "score_breakdown": final.get("score_breakdown", {}),
                            "core_logic": final.get("core_logic", []),
                            "risk_warning": final.get("risk_warning", ""),
                            "key_prices": final.get("key_prices", {}),
                            "report": final.get("report", ""),
                        },
                    }
                    yield {"event": "complete", "data": {"status": "success"}}
    finally:
        # Restore original config
        cfg.ANALYST_TEMPERATURE = original_temp
        cfg.RED_TEAM_TEMPERATURE = original_temp + 0.3 if original_temp == 0.7 else 1.0
        cfg.CHIEF_TEMPERATURE = max(original_temp - 0.4, 0.1)
