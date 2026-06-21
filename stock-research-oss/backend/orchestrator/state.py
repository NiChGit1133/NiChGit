"""LangGraph state definition for the multi-analyst workflow.

Uses Annotated keys with reducers to support parallel node fan-out in LangGraph 1.x.
"""
from typing import Optional, Any, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
import operator


# ── Reducer helpers ──────────────────────────────────────────────────

def _keep_latest(current, update):
    """Reducer: always take the latest update, fall back to current."""
    return update if update is not None else current


def _merge_dict(current: dict, update: dict) -> dict:
    """Reducer: merge dicts (update wins on conflicts)."""
    merged = {**current, **update}
    return merged


# ── Pydantic Schemas ─────────────────────────────────────────────────

class AnalystReport(BaseModel):
    """Standardized report from each analyst agent."""
    agent: str = Field(default="unknown", description="Agent name: technical/fundamental/news/sentiment")
    score: float = Field(ge=0, le=10, description="Rating score 0-10")
    summary: str = Field(description="One-line summary of the analysis")
    report: str = Field(description="Full analysis report in markdown")
    key_points: list[str] = Field(default_factory=list, description="3-5 key bullet points")
    risks: list[str] = Field(default_factory=list, description="Key risks identified")
    catalysts: list[str] = Field(default_factory=list, description="Positive catalysts")


class RedTeamClaim(BaseModel):
    """A single claim verified by the Red Team."""
    claim: str = Field(description="The claim being verified")
    source_agent: str = Field(default="unknown", description="Which agent made this claim")
    verdict: str = Field(description="VERIFIED, UNVERIFIED, or REFUTED")
    reasoning: str = Field(description="Why this verdict was reached")


class RedTeamReport(BaseModel):
    """Red Team verification report."""
    verified_claims: list[RedTeamClaim] = Field(default_factory=list)
    logical_fallacies: list[str] = Field(default_factory=list)
    missing_risks: list[str] = Field(default_factory=list)
    overall_credibility: float = Field(ge=0, le=10, description="How credible is the overall analysis")
    notes: str = Field(default="")


class FinalReport(BaseModel):
    """Chief Strategist's final synthesis."""
    recommendation: str = Field(description="买入 (BUY), 持有 (HOLD), or 卖出 (SELL)")
    conviction: str = Field(description="高 (HIGH), 中 (MEDIUM), or 低 (LOW)")
    composite_score: float = Field(ge=0, le=10)
    score_breakdown: dict = Field(default_factory=dict, description="Individual agent scores")
    core_logic: list[str] = Field(default_factory=list, description="3-5 core investment thesis points")
    risk_warning: str = Field(description="Key risk warning summary")
    key_prices: dict = Field(default_factory=dict, description="Support/resistance/target prices")
    report: str = Field(description="Full final report in markdown")


# ── LangGraph State with Reducers ────────────────────────────────────

class AnalysisState(TypedDict, total=False):
    """Full state for the multi-analyst stock analysis workflow.

    All keys use Annotated with reducers to support parallel node fan-out
    in LangGraph 1.x. Each key must specify how to merge concurrent updates.
    """

    # ── Input (scalar — last writer wins) ──
    stock_code: Annotated[str, _keep_latest]
    stock_name: Annotated[str, _keep_latest]

    # ── Pre-fetched data ──
    market_data: Annotated[dict[str, Any], _merge_dict]
    financial_data: Annotated[Optional[dict[str, Any]], _keep_latest]
    news_data: Annotated[list[dict[str, Any]], operator.add]
    sentiment_data: Annotated[Optional[dict[str, Any]], _keep_latest]
    industry_data: Annotated[Optional[dict[str, Any]], _keep_latest]

    # ── Phase 1: Analyst outputs (each key only written by ONE node — safe) ──
    technical_report: Annotated[Optional[dict], _keep_latest]
    fundamental_report: Annotated[Optional[dict], _keep_latest]
    news_report: Annotated[Optional[dict], _keep_latest]
    sentiment_report: Annotated[Optional[dict], _keep_latest]

    # ── Phase 2: Debate ──
    bull_thesis: Annotated[Optional[str], _keep_latest]
    bear_thesis: Annotated[Optional[str], _keep_latest]
    bull_rebuttal: Annotated[Optional[str], _keep_latest]
    bear_rebuttal: Annotated[Optional[str], _keep_latest]
    debate_transcript: Annotated[Optional[str], _keep_latest]
    red_team_findings: Annotated[Optional[dict], _keep_latest]

    # ── Phase 3: Synthesis ──
    final_report: Annotated[Optional[dict], _keep_latest]

    # ── Streaming metadata ──
    current_phase: Annotated[str, _keep_latest]
    status_message: Annotated[str, _keep_latest]
    error: Annotated[Optional[str], _keep_latest]
    analysis_id: Annotated[Optional[str], _keep_latest]
