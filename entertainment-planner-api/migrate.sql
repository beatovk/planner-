-- Миграция signals
ALTER TABLE places ADD COLUMN IF NOT EXISTS signals jsonb DEFAULT '{}'::jsonb;
UPDATE places SET signals = interest_signals WHERE interest_signals IS NOT NULL;

-- Создание схемы
CREATE SCHEMA IF NOT EXISTS epx AUTHORIZATION postgres;

-- Создание материализованного представления
DROP MATERIALIZED VIEW IF EXISTS epx.places_search_mv;
CREATE MATERIALIZED VIEW epx.places_search_mv AS
SELECT p.id, p.name, p.category, p.summary, p.tags_csv, p.lat, p.lng,
       p.picture_url, p.gmaps_place_id, p.gmaps_url, p.rating, p.processing_status,
       to_tsvector('simple', coalesce(p.name,'') || ' ' || coalesce(p.category,'') || ' ' || coalesce(p.tags_csv,'') || ' ' || coalesce(p.summary,'')) AS search_vector,
       COALESCE(p.signals, '{}'::jsonb) AS signals
FROM public.places p;

-- Создание индексов
CREATE UNIQUE INDEX IF NOT EXISTS places_search_mv_pk ON epx.places_search_mv (id);
CREATE INDEX IF NOT EXISTS places_search_mv_gin ON epx.places_search_mv USING gin (search_vector);
CREATE INDEX IF NOT EXISTS places_search_mv_signals_gin ON epx.places_search_mv USING gin (signals);

-- Обновление MV
REFRESH MATERIALIZED VIEW epx.places_search_mv;
