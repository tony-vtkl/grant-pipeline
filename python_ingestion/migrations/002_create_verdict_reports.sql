CREATE TABLE IF NOT EXISTS verdict_reports (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    opportunity_id  text NOT NULL,
    verdict         text NOT NULL,
    composite_score double precision NOT NULL,
    verdict_rationale text NOT NULL,
    executive_summary text NOT NULL,
    risk_assessment text NOT NULL,
    strategic_roadmap jsonb,
    one_pager_pitch text,
    generated_at    timestamptz NOT NULL DEFAULT now(),
    status          text NOT NULL DEFAULT 'awaiting_human_approval',
    CONSTRAINT fk_opportunity FOREIGN KEY (opportunity_id) 
        REFERENCES grant_opportunities(source_opportunity_id)
);

CREATE INDEX IF NOT EXISTS idx_vr_opportunity ON verdict_reports(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_vr_status ON verdict_reports(status);
