CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) DEFAULT 'user';
UPDATE users SET role = 'user' WHERE role IS NULL;
UPDATE users SET role = 'admin' WHERE is_admin IS TRUE AND role <> 'admin';

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(127) NOT NULL DEFAULT 'application/octet-stream',
    extension VARCHAR(16),
    source_type VARCHAR(20) NOT NULL DEFAULT 'upload',
    purpose VARCHAR(20) NOT NULL DEFAULT 'check',
    confidentiality_level VARCHAR(20) NOT NULL DEFAULT 'confidential',
    file_size INTEGER NOT NULL DEFAULT 0,
    file_hash VARCHAR(64),
    file_content BYTEA,
    extracted_text TEXT NOT NULL DEFAULT '',
    text_hash VARCHAR(64),
    word_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'processed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ
);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS purpose VARCHAR(20) DEFAULT 'check';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS confidentiality_level VARCHAR(20) DEFAULT 'confidential';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS text_hash VARCHAR(64);
UPDATE documents SET confidentiality_level = 'confidential' WHERE confidentiality_level IS NULL;

CREATE INDEX IF NOT EXISTS idx_documents_owner_id ON documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_purpose ON documents(purpose);
CREATE INDEX IF NOT EXISTS idx_documents_confidentiality_level ON documents(confidentiality_level);
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_text_hash ON documents(text_hash);

CREATE TABLE IF NOT EXISTS source_references (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    section VARCHAR(128),
    reference_code VARCHAR(128),
    url_or_local_path VARCHAR(1024),
    note TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_source_references_active ON source_references(is_active);

CREATE TABLE IF NOT EXISTS glossary_terms (
    id BIGSERIAL PRIMARY KEY,
    term VARCHAR(255) NOT NULL,
    normalized_term VARCHAR(255) NOT NULL,
    canonical_definition TEXT NOT NULL,
    allowed_variants JSONB NOT NULL DEFAULT '[]'::jsonb,
    forbidden_variants JSONB NOT NULL DEFAULT '[]'::jsonb,
    category VARCHAR(64),
    severity_default VARCHAR(16) NOT NULL DEFAULT 'medium',
    source_ref_id BIGINT REFERENCES source_references(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_glossary_terms_term ON glossary_terms(term);
CREATE INDEX IF NOT EXISTS idx_glossary_terms_normalized_term ON glossary_terms(normalized_term);
CREATE INDEX IF NOT EXISTS idx_glossary_terms_active ON glossary_terms(is_active);
CREATE INDEX IF NOT EXISTS idx_glossary_terms_source_ref_id ON glossary_terms(source_ref_id);

CREATE TABLE IF NOT EXISTS rule_patterns (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(32) NOT NULL DEFAULT 'regex',
    pattern TEXT NOT NULL,
    description TEXT,
    severity VARCHAR(16) NOT NULL DEFAULT 'medium',
    suggestion_template TEXT,
    source_ref_id BIGINT REFERENCES source_references(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_rule_patterns_rule_type ON rule_patterns(rule_type);
CREATE INDEX IF NOT EXISTS idx_rule_patterns_active ON rule_patterns(is_active);
CREATE INDEX IF NOT EXISTS idx_rule_patterns_source_ref_id ON rule_patterns(source_ref_id);

CREATE TABLE IF NOT EXISTS knowledge_policy_snapshots (
    id BIGSERIAL PRIMARY KEY,
    label VARCHAR(255),
    policy_hash VARCHAR(64) NOT NULL,
    snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledge_policy_snapshots_hash ON knowledge_policy_snapshots(policy_hash);
CREATE INDEX IF NOT EXISTS idx_knowledge_policy_snapshots_created_at ON knowledge_policy_snapshots(created_at DESC);

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    char_count INTEGER NOT NULL DEFAULT 0,
    word_count INTEGER NOT NULL DEFAULT 0,
    sentence_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    overall_score INTEGER NOT NULL,
    readability_score INTEGER NOT NULL,
    grammar_score INTEGER NOT NULL,
    structure_score INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    raw_response JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_mode TEXT NOT NULL DEFAULT 'mock',
    policy_hash TEXT,
    processing_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS policy_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_analysis_runs_document_id ON analysis_runs(document_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_user_id ON analysis_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at ON analysis_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS analysis_issues (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    issue_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_issues_run_id ON analysis_issues(run_id);

CREATE TABLE IF NOT EXISTS analysis_recommendations (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    recommendation_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_recommendations_run_id ON analysis_recommendations(run_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64),
    resource_id VARCHAR(128),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS chat_threads (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Новый чат',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id BIGINT REFERENCES chat_threads(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    context_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS thread_id BIGINT REFERENCES chat_threads(id) ON DELETE SET NULL;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS context_used BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_id ON chat_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_chat_threads_user_id ON chat_threads(user_id);
