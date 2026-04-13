from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    overall_score = Column(Integer, nullable=False)
    readability_score = Column(Integer, nullable=False)
    grammar_score = Column(Integer, nullable=False)
    structure_score = Column(Integer, nullable=False)
    summary = Column(Text, nullable=False, default="")
    raw_response = Column(JSON, nullable=False, default=dict)
    model_mode = Column(Text, nullable=False, default="mock")  # mock | llm
    policy_hash = Column(Text, nullable=True)
    processing_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnalysisIssueRecord(Base):
    __tablename__ = "analysis_issues"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(BigInteger, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnalysisRecommendationRecord(Base):
    __tablename__ = "analysis_recommendations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(BigInteger, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
