-- Migration 002: Create eligibility_results table
-- VTK-104: Eligibility Rules Engine Against VTKL Profile

CREATE TABLE IF NOT EXISTS eligibility_results (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    opportunity_id          text        NOT NULL,
    is_eligible             boolean     NOT NULL,
    participation_path      text,
    entity_type_check       jsonb       NOT NULL,
    location_check          jsonb       NOT NULL,
    sam_active_check        jsonb       NOT NULL,
    naics_match_check       jsonb       NOT NULL,
    security_posture_check  jsonb       NOT NULL,
    certification_check     jsonb       NOT NULL,
    blockers                jsonb       NOT NULL DEFAULT '[]',
    assets                  jsonb       NOT NULL DEFAULT '[]',
    warnings                jsonb       NOT NULL DEFAULT '[]',
    evaluated_at            timestamptz NOT NULL DEFAULT now(),
    vtkl_profile_version    text        NOT NULL DEFAULT '1.0',
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_er_opportunity_id ON eligibility_results (opportunity_id);
CREATE INDEX IF NOT EXISTS idx_er_is_eligible ON eligibility_results (is_eligible);
