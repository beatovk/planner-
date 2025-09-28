-- Entertainment Planner - Materialized View DDL
-- Creates epx.places_search_mv with derived flags for chill/romantic/cinema

CREATE SCHEMA IF NOT EXISTS epx;

DROP MATERIALIZED VIEW IF EXISTS epx.places_search_mv;

CREATE MATERIALIZED VIEW epx.places_search_mv AS
WITH base AS (
  SELECT
    p.id,
    p.name,
    COALESCE(p.category,'') AS category,
    to_jsonb(p)->>'summary' AS summary,
    to_jsonb(p)->>'description' AS description,
    COALESCE(to_jsonb(p)->>'tags_csv', '') AS tags_csv,
    COALESCE(p.signals, '{}'::jsonb) AS signals,
    COALESCE(p.processing_status,'published') AS processing_status,
    p.lat,
    p.lng,
    p.picture_url,
    p.gmaps_place_id,
    p.gmaps_url,
    p.rating,
    trim(both ' ' FROM CONCAT_WS(' ',
      p.name, 
      to_jsonb(p)->>'summary', 
      to_jsonb(p)->>'description',
      COALESCE(to_jsonb(p)->>'tags_csv', '')
    )) AS text_blob
  FROM public.places p
)
SELECT
  b.*,
  (
    setweight(to_tsvector('simple', COALESCE(b.name,'')), 'A') ||
    setweight(to_tsvector('simple', COALESCE(b.summary,'')), 'B') ||
    setweight(to_tsvector('simple', COALESCE(b.description,'')), 'B') ||
    setweight(to_tsvector('simple', COALESCE(b.tags_csv,'')), 'C')
  ) AS fts,
  -- derived flags
  (
    lower(b.category) IN ('cinema','movie_theater') OR
    b.text_blob ILIKE '%cinema%' OR b.text_blob ILIKE '%movie%' OR
    (b.signals ? 'cinema')
  ) AS is_cinema,
  (
    (b.signals->>'dateworthy')::boolean IS TRUE OR
    (b.signals ? 'romantic') OR
    b.text_blob ILIKE '%romantic%' OR
    b.text_blob ILIKE '%couple%' OR
    b.text_blob ILIKE '%rooftop%' OR
    b.text_blob ILIKE '%sunset%'
  ) AS is_romantic,
  (
    (b.signals ? 'spa' OR b.signals ? 'massage' OR b.signals ? 'onsen' OR
     b.signals ? 'sauna' OR b.signals ? 'hammam' OR
     b.signals ? 'yoga' OR b.signals ? 'meditation' OR
     b.signals ? 'tea' OR b.signals ? 'park' OR b.signals ? 'garden' OR
     b.signals ? 'lounge' OR b.signals ? 'ambient')
    OR b.text_blob ILIKE '%spa%' OR b.text_blob ILIKE '%sauna%' OR
       b.text_blob ILIKE '%yoga%' OR b.text_blob ILIKE '%park%'  OR
       b.text_blob ILIKE '%lounge%' OR b.text_blob ILIKE '%ambient%'
  ) AS is_chill
FROM base b;

-- Create indexes
CREATE UNIQUE INDEX IF NOT EXISTS pk_places_search_mv ON epx.places_search_mv (id);
CREATE INDEX IF NOT EXISTS idx_places_search_mv_fts ON epx.places_search_mv USING GIN (fts);
CREATE INDEX IF NOT EXISTS idx_places_search_mv_isflags ON epx.places_search_mv (is_cinema, is_romantic, is_chill);

-- Refresh data
REFRESH MATERIALIZED VIEW epx.places_search_mv;
