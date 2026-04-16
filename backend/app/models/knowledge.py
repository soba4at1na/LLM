from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text, func

from app.core.database import Base


class SourceReference(Base):
    __tablename__ = "source_references"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    section = Column(String(128), nullable=True)
    reference_code = Column(String(128), nullable=True)
    url_or_local_path = Column(String(1024), nullable=True)
    note = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    term = Column(String(255), nullable=False, index=True)
    normalized_term = Column(String(255), nullable=False, index=True)
    canonical_definition = Column(Text, nullable=False)
    allowed_variants = Column(JSON, nullable=False, default=list)
    forbidden_variants = Column(JSON, nullable=False, default=list)
    category = Column(String(64), nullable=True)
    severity_default = Column(String(16), nullable=False, default="medium")
    source_ref_id = Column(BigInteger, ForeignKey("source_references.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class RulePattern(Base):
    __tablename__ = "rule_patterns"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    rule_type = Column(String(32), nullable=False, default="regex")  # regex|lemma|triplet
    pattern = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False, default="medium")
    suggestion_template = Column(Text, nullable=True)
    source_ref_id = Column(BigInteger, ForeignKey("source_references.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class KnowledgePolicySnapshot(Base):
    __tablename__ = "knowledge_policy_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    label = Column(String(255), nullable=True)
    policy_hash = Column(String(64), nullable=False, index=True)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KnowledgeImportCandidate(Base):
    __tablename__ = "knowledge_import_candidates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_ref_id = Column(BigInteger, ForeignKey("source_references.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    term = Column(String(255), nullable=False, index=True)
    normalized_term = Column(String(255), nullable=False, index=True)
    canonical_definition = Column(Text, nullable=False)
    confidence = Column(String(16), nullable=False, default="medium")
    status = Column(String(16), nullable=False, default="pending")  # pending|approved|rejected
    reviewed_by = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
