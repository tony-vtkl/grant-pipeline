-- Migration: Create eligibility_results table
-- Issue: VTK-104
-- Date: 2026-02-27

CREATE TABLE IF NOT EXISTS eligibility_results (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    opportunity_id  TEXT NOT NULL UNIQUE,
    is_eligible     BOOLEAN NOT NULL,
    participation_path TEXT,  -- 'prime', 'subawardee', or NULL

    -- Individual constraint check results (JSONB)
    entity_type_check       JSONB NOT NULL,
    location_check          JSONB NOT NULL,
    sam_active_check        JSONB NOT NULL,
    naics_match_check       JSONB NOT NULL,
    security_posture_check  JSONB NOT NULL,
    certification_check     JSONB NOT NULL,

    -- Categorized findings
    blockers    JSONB DEFAULT '[]'::jsonb,
    assets      JSONB DEFAULT '[]'::jsonb,
    warnings    JSONB DEFAULT '[]'::jsonb,

    evaluated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    vtkl_profile_version  TEXT NOT NULL DEFAULT '1.0',

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_opportunity
        FOREIGN KEY (opportunity_id)
        REFERENCES grant_opportunities(source_opportunity_id)
        ON DELETE CASCADE
);

-- Index for lookups by eligibility
CREATE INDEX IF NOT EXISTS idx_eligibility_results_eligible
    ON eligibility_results (is_eligible);

-- Index for path-based queries
CREATE INDEX IF NOT EXISTS idx_eligibility_results_path
    ON eligibility_results (participation_path);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_eligibility_results_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_eligibility_results_updated_at ON eligibility_results;
CREATE TRIGGER trg_eligibility_results_updated_at
    BEFORE UPDATE ON eligibility_results
    FOR EACH ROW
    EXECUTE FUNCTION update_eligibility_results_updated_at();
