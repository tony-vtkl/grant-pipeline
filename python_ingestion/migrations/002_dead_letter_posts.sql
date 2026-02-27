-- Migration 002: dead_letter_posts + posted_to_slack_at tracking
-- VTK-107: Slack Block Kit Delivery + Daily Digest Cron

-- =============================================================================
-- dead_letter_posts — stores failed Slack post attempts
-- =============================================================================
CREATE TABLE IF NOT EXISTS dead_letter_posts (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    opportunity_id      text        NOT NULL,
    verdict             text        NOT NULL,
    payload             jsonb       NOT NULL DEFAULT '{}',
    error_message       text,
    attempts            integer     NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now(),
    last_attempted_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dlp_opportunity ON dead_letter_posts (opportunity_id);
CREATE INDEX IF NOT EXISTS idx_dlp_created     ON dead_letter_posts (created_at);

-- =============================================================================
-- Add posted_to_slack_at to verdict_reports (if table exists)
-- =============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'verdict_reports') THEN
        ALTER TABLE verdict_reports ADD COLUMN IF NOT EXISTS posted_to_slack_at timestamptz;
    END IF;
END $$;
