-- Create materialized view for entertainment planner
CREATE MATERIALIZED VIEW epx.places_search_mv AS
WITH base AS (
  SELECT
    p.id,
    p.name,
    COALESCE(p.category,'') AS category,
    p.summary,
    p.description,
    p.tags_csv,
    p.lat, p.lng,
    p.picture_url,
    p.gmaps_place_id,
    p.gmaps_url,
    p.rating,
    COALESCE(p.signals, '{}'::jsonb) AS signals,
    COALESCE(p.processing_status,'published') AS processing_status,
    trim(both ' ' FROM CONCAT_WS(' ',
      p.name, p.summary, p.description, p.tags_csv
    )) AS text_blob
  FROM public.places p
  WHERE COALESCE(p.processing_status,'published') IN ('published','summarized','new')
)
SELECT
  b.*,
  -- FTS (на простом конфиге; при желании поменяй словарь)
  (
    setweight(to_tsvector('simple', COALESCE(b.name,'')), 'A') ||
    setweight(to_tsvector('simple', COALESCE(b.summary,'')), 'B') ||
    setweight(to_tsvector('simple', COALESCE(b.description,'')), 'B') ||
    setweight(to_tsvector('simple', COALESCE(b.tags_csv,'')), 'C')
  ) AS fts,
  -- derived-флаги
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
FROM base b
WITH NO DATA;