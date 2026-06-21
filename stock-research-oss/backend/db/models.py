"""SQLAlchemy models for watchlist and analysis history."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, JSON
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stock_code = Column(String(10), nullable=False, unique=True, index=True)
    stock_name = Column(String(50), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, default="")


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="running")  # running, completed, failed

    # Scores
    technical_score = Column(Float, nullable=True)
    fundamental_score = Column(Float, nullable=True)
    news_score = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    composite_score = Column(Float, nullable=True)

    # Reports (JSON)
    technical_report = Column(JSON, nullable=True)
    fundamental_report = Column(JSON, nullable=True)
    news_report = Column(JSON, nullable=True)
    sentiment_report = Column(JSON, nullable=True)

    # Debate
    debate_transcript = Column(JSON, nullable=True)
    red_team_findings = Column(JSON, nullable=True)

    # Final
    recommendation = Column(String(20), nullable=True)  # BUY, HOLD, SELL
    conviction = Column(String(10), nullable=True)  # HIGH, MEDIUM, LOW
    final_report = Column(JSON, nullable=True)

    # Metadata
    duration_seconds = Column(Float, nullable=True)
    model_used = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
