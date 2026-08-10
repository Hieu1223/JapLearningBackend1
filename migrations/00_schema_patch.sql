-- ============================================================================
-- Migration step 00: bring the CURRENT public schema up to date with the
-- columns the transform step (01_transform.sql) expects to write into.
--
-- The application models added these columns after the migration was written,
-- but the live target database may still be on the older schema. Add them
-- here (NULLable, idempotent) so 01_transform.sql can run.
-- ============================================================================

ALTER TABLE public.transcript
    ADD COLUMN IF NOT EXISTS individual_settings JSONB;

ALTER TABLE public.transcriptionhistory
    ADD COLUMN IF NOT EXISTS resource_id TEXT,
    ADD COLUMN IF NOT EXISTS original_source TEXT,
    ADD COLUMN IF NOT EXISTS name TEXT,
    ADD COLUMN IF NOT EXISTS thumbnail_url TEXT,
    ADD COLUMN IF NOT EXISTS resource_url TEXT;
