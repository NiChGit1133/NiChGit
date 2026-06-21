"""Agent package."""
from .base import AgentBase, get_model, get_analyst_model, get_red_team_model, get_chief_model
from .prompts import (
    TECHNICAL_ANALYST_PROMPT,
    FUNDAMENTAL_ANALYST_PROMPT,
    NEWS_ANALYST_PROMPT,
    SENTIMENT_ANALYST_PROMPT,
    BULL_DEBATER_PROMPT,
    BEAR_DEBATER_PROMPT,
    RED_TEAM_PROMPT,
    CHIEF_STRATEGIST_PROMPT,
)
