"""Configuration management for the stock research system."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory (sibling of this config file)
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)

# LLM Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# Default model for all agents (user only has DeepSeek V4 Pro)
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek/deepseek-chat")
CHIEF_MODEL = os.getenv("CHIEF_MODEL", "deepseek/deepseek-chat")
RED_TEAM_MODEL = os.getenv("RED_TEAM_MODEL", "deepseek/deepseek-chat")

# Agent temperature settings (differentiation via temperature + prompt)
ANALYST_TEMPERATURE = float(os.getenv("ANALYST_TEMPERATURE", "0.7"))
RED_TEAM_TEMPERATURE = float(os.getenv("RED_TEAM_TEMPERATURE", "1.0"))
CHIEF_TEMPERATURE = float(os.getenv("CHIEF_TEMPERATURE", "0.3"))

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Data cache
CACHE_DIR = os.getenv("CACHE_DIR", "./cache")
CACHE_TTL_QUOTE = int(os.getenv("CACHE_TTL_QUOTE", "300"))  # 5 min for quotes
CACHE_TTL_FINANCIAL = int(os.getenv("CACHE_TTL_FINANCIAL", "86400"))  # 24h for financials

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./stock_research.db")

# Rate limiting
API_RATE_LIMIT = float(os.getenv("API_RATE_LIMIT", "2.0"))  # requests per second
