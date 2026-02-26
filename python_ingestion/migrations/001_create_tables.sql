-- Migration 001: Create grant_opportunities and pipeline_runs tables
-- VTK-99: REQ-4 Implement Supabase Client

-- =============================================================================
-- grant_opportunities
-- =============================================================================
CREATE TABLE IF NOT EXISTS grant_opportunities (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source          text        NOT NULL,
    source_opportunity_id text  NOT NULL,
    dedup_hash      text        NOT NULL UNIQUE,

    title           text        NOT NULL,
    agency          text        NOT NULL,
    opportunity_number text,

    posted_date     timestamptz,
    response_deadline timestamptz,
    archive_date    timestamptz,

    award_amount_min     double precision,
    award_amount_max     double precision,
    estimated_total_program_funding double precision,

    naics_codes     text[]      DEFAULT '{}',
    set_aside_type  text,
    opportunity_type text,

    description     text,
    raw_text        text,

    source_url      text        NOT NULL,

    first_detected_at timestamptz NOT NULL DEFAULT now(),
    last_updated_at   timestamptz NOT NULL DEFAULT now(),
    status          text        NOT NULL DEFAULT 'new',

    sbir_program_active boolean NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_go_dedup_hash ON grant_opportunities (dedup_hash);
CREATE INDEX IF NOT EXISTS idx_go_source     ON grant_opportunities (source);
CREATE INDEX IF NOT EXISTS idx_go_status     ON grant_opportunities (status);

-- =============================================================================
-- pipeline_runs
-- =============================================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at        timestamptz NOT NULL,
    completed_at      timestamptz NOT NULL,
    grants_processed  integer     NOT NULL DEFAULT 0,
    grants_new        integer     NOT NULL DEFAULT 0,
    grants_updated    integer     NOT NULL DEFAULT 0,
    errors            jsonb       NOT NULL DEFAULT '[]',
    status            text        NOT NULL DEFAULT 'completed'
);
