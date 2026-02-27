-- Migration 002: Create scoring_results table for LLM-based scoring
-- VTK-105: Replace rule-based scoring with LLM-based scoring

CREATE TABLE IF NOT EXISTS scoring_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    mission_fit_score NUMERIC(5,2) NOT NULL,
    mission_fit_citations JSONB NOT NULL DEFAULT '[]',
    eligibility_score NUMERIC(5,2) NOT NULL,
    eligibility_citations JSONB NOT NULL DEFAULT '[]',
    technical_alignment_score NUMERIC(5,2) NOT NULL,
    technical_alignment_citations JSONB NOT NULL DEFAULT '[]',
    financial_viability_score NUMERIC(5,2) NOT NULL,
    financial_viability_citations JSONB NOT NULL DEFAULT '[]',
    strategic_value_score NUMERIC(5,2) NOT NULL,
    strategic_value_citations JSONB NOT NULL DEFAULT '[]',
    composite_score NUMERIC(5,2) NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('GO','SHAPE','MONITOR','NO-GO')),
    scoring_weights_version TEXT NOT NULL DEFAULT '1.0',
    llm_model TEXT NOT NULL,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scoring_results_opportunity ON scoring_results(opportunity_id);
CREATE INDEX idx_scoring_results_verdict ON scoring_results(verdict);
