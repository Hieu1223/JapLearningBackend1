-- ============================================================================
-- Migration step 01: transform the OLD (legacy_2026) public schema into the
-- CURRENT application schema, then load it into the live `public` schema.
--
-- The staging copy of the old dump lives in schema :staging (legacy_2026).
-- This script reads from :staging and writes into the real public schema.
-- The runner replaces every `:staging` token with the configured staging
-- schema name before executing, so this file is plain SQL (no psql variables).
-- All staging references use :staging."table" so table names are quoted.
--
-- Idempotency: every INSERT is guarded by a "WHERE NOT EXISTS" check so the
-- script can be re-run safely.
--
-- Scope:
--   * Carried over (have an equivalent table in the current schema):
--       user, authuser, usersettings, refreshtoken,
--       manga, chapter, ocr_result, readhistory,
--       transcript, transcriptionhistory, videoprogress
--   * Excluded - flashcard data (per request):
--       deck, card, srscard, reviewlog
--   * Excluded - no current model / unused in the app:
--       word, kanji, wordkanjireading
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Identity / account tables (1:1 copy)
-- ----------------------------------------------------------------------------

INSERT INTO public."user" (id, display_name, created_at, updated_at)
SELECT id, display_name, created_at, updated_at
FROM :staging."user" s
WHERE NOT EXISTS (SELECT 1 FROM public."user" u WHERE u.id = s.id);

INSERT INTO public.authuser (id, username, hashed_password, user_id)
SELECT id, username, hashed_password, user_id
FROM :staging.authuser s
WHERE NOT EXISTS (SELECT 1 FROM public.authuser a WHERE a.id = s.id);

INSERT INTO public.usersettings (id, user_id, settings, updated_at)
SELECT id, user_id, settings, updated_at
FROM :staging.usersettings s
WHERE NOT EXISTS (SELECT 1 FROM public.usersettings x WHERE x.id = s.id);

INSERT INTO public.refreshtoken (id, user_id, token, expires_at, created_at, revoked)
SELECT id, user_id, token, expires_at, created_at, revoked
FROM :staging.refreshtoken s
WHERE NOT EXISTS (SELECT 1 FROM public.refreshtoken x WHERE x.id = s.id);

-- ----------------------------------------------------------------------------
-- 2. Manga reader tables (1:1 copy)
-- ----------------------------------------------------------------------------

INSERT INTO public.manga (id, url, slug, title, description, cover, status, genres, created_at, updated_at)
SELECT id, url, slug, title, description, cover, status, genres, created_at, updated_at
FROM :staging.manga s
WHERE NOT EXISTS (SELECT 1 FROM public.manga x WHERE x.id = s.id);

INSERT INTO public.chapter (id, manga_id, title, url, chapter_index, date, created_at, pages)
SELECT id, manga_id, title, url, chapter_index, date, created_at, pages
FROM :staging.chapter s
WHERE NOT EXISTS (SELECT 1 FROM public.chapter x WHERE x.id = s.id);

INSERT INTO public.ocr_result (id, chapter_id, ocr_by, ocr_data, ocr_date)
SELECT id, chapter_id, ocr_by, ocr_data, ocr_date
FROM :staging.ocr_result s
WHERE NOT EXISTS (SELECT 1 FROM public.ocr_result x WHERE x.id = s.id);

INSERT INTO public.readhistory (id, user_id, manga_id, chapter_id, current_page, updated_at)
SELECT id, user_id, manga_id, chapter_id, current_page, updated_at
FROM :staging.readhistory s
WHERE NOT EXISTS (SELECT 1 FROM public.readhistory x WHERE x.id = s.id);

-- ----------------------------------------------------------------------------
-- 3. Transcription tables
--    transcript gained `individual_settings` (nullable) -> backfilled with NULL.
-- ----------------------------------------------------------------------------

INSERT INTO public.transcript (id, original_source, resource_id, resource_url, thumnail_url, name, date_created, data, status, public, individual_settings)
SELECT id, original_source, resource_id, resource_url, thumnail_url, name, date_created, data, status, public, NULL
FROM :staging.transcript s
WHERE NOT EXISTS (SELECT 1 FROM public.transcript x WHERE x.id = s.id);

-- transcriptionhistory gained resource_id, original_source, name,
-- thumbnail_url, resource_url. Backfill from the related transcript.
INSERT INTO public.transcriptionhistory (
    id, user_id, transcript_id, resource_id, original_source, name, thumbnail_url, resource_url, date_created
)
SELECT
    h.id,
    h.user_id,
    h.transcript_id,
    COALESCE(t.resource_id, ''),
    COALESCE(t.original_source, 'Youtube'),
    COALESCE(t.name, ''),
    COALESCE(t.thumnail_url, ''),
    COALESCE(t.resource_url, ''),
    h.date_created
FROM :staging.transcriptionhistory h
LEFT JOIN :staging.transcript t ON t.id = h.transcript_id
WHERE NOT EXISTS (SELECT 1 FROM public.transcriptionhistory x WHERE x.id = h.id);

-- videoprogress gained original_source -> default to 'Youtube'.
INSERT INTO public.videoprogress (id, user_id, resource_id, original_source, current_page, updated_at)
SELECT id, user_id, resource_id, 'Youtube', current_page, updated_at
FROM :staging.videoprogress s
WHERE NOT EXISTS (SELECT 1 FROM public.videoprogress x WHERE x.id = s.id);
