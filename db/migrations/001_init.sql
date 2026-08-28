-- Voice Agent VPS (Vapi edition) — core schema. Requires pgvector.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS businesses (
    id                  SERIAL PRIMARY KEY,
    phone_number        TEXT UNIQUE NOT NULL,
    business_id         TEXT UNIQUE NOT NULL,
    business_name       TEXT NOT NULL,
    system_prompt       TEXT NOT NULL,
    knowledge_namespace TEXT NOT NULL,
    tools               JSONB NOT NULL DEFAULT '[]',
    llm_tier            TEXT NOT NULL DEFAULT 'hybrid',
    vapi_assistant_id   TEXT,                          -- filled in after first provision run
    vapi_voice_provider TEXT NOT NULL DEFAULT '11labs',
    vapi_voice_id       TEXT NOT NULL DEFAULT 'burt',
    vapi_model_label    TEXT NOT NULL DEFAULT 'gpt-4o',
    vapi_first_message  TEXT NOT NULL DEFAULT 'Hello, thanks for calling! How can I help you today?',
    active              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id            BIGSERIAL PRIMARY KEY,
    namespace     TEXT NOT NULL,
    content       TEXT NOT NULL,
    embedding     VECTOR(768) NOT NULL,        -- dims must match your embed model
    source_file   TEXT,
    source_type   TEXT NOT NULL DEFAULT 'doc',  -- doc | faq | live_call_correction | manual
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_knowledge_namespace ON knowledge_chunks (namespace);
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS calls (
    id                    BIGSERIAL PRIMARY KEY,
    call_id               TEXT UNIQUE NOT NULL,       -- Vapi's call.id
    business_id           TEXT NOT NULL,
    agent_id              TEXT,                       -- Vapi's assistantId
    started_at            TIMESTAMPTZ,
    ended_at              TIMESTAMPTZ,
    transcript            JSONB NOT NULL,
    call_successful        BOOLEAN,                    -- from Vapi's analysis.successEvaluation
    custom_analysis_data   JSONB NOT NULL DEFAULT '{}', -- Vapi's analysis.structuredData
    auto_score            REAL,                        -- our own scorecard (shared w/ simulation)
    flagged_for_review     BOOLEAN NOT NULL DEFAULT false,
    flag_reason            TEXT,
    reviewed_at            TIMESTAMPTZ,
    corrected_answer       TEXT,
    outcome                TEXT
);
CREATE INDEX IF NOT EXISTS idx_calls_business ON calls (business_id);
CREATE INDEX IF NOT EXISTS idx_calls_flagged ON calls (flagged_for_review) WHERE flagged_for_review;

CREATE TABLE IF NOT EXISTS simulation_runs (
    id            BIGSERIAL PRIMARY KEY,
    business_id   TEXT NOT NULL,
    run_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    calls_run     INT NOT NULL,
    avg_score     REAL NOT NULL,
    failing_calls INT NOT NULL,
    results_file  TEXT
);
