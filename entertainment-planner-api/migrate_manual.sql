-- ============================================
-- МИГРАЦИЯ SIGNALS - ВЫПОЛНИТЬ В PSQL
-- ============================================

-- 1. Добавляем поле signals в таблицу places
ALTER TABLE places ADD COLUMN IF NOT EXISTS signals jsonb DEFAULT '{}'::jsonb;

-- 2. Переносим данные из interest_signals в signals
UPDATE places SET signals = interest_signals WHERE interest_signals IS NOT NULL;

-- 3. Создаем схему epx
CREATE SCHEMA IF NOT EXISTS epx AUTHORIZATION postgres;

-- 4. Создаем материализованное представление
DROP MATERIALIZED VIEW IF EXISTS epx.places_search_mv;
CREATE MATERIALIZED VIEW epx.places_search_mv AS
SELECT 
  p.id, p.name, p.category, p.summary, p.tags_csv, p.lat, p.lng,
  p.picture_url, p.gmaps_place_id, p.gmaps_url, p.rating, p.processing_status,
  to_tsvector('simple', 
    coalesce(p.name,'') || ' ' || 
    coalesce(p.category,'') || ' ' || 
    coalesce(p.tags_csv,'') || ' ' || 
    coalesce(p.summary,'')
  ) AS search_vector,
  COALESCE(p.signals, '{}'::jsonb) AS signals
FROM public.places p;

-- 5. Создаем индексы
CREATE UNIQUE INDEX IF NOT EXISTS places_search_mv_pk ON epx.places_search_mv (id);
CREATE INDEX IF NOT EXISTS places_search_mv_gin ON epx.places_search_mv USING gin (search_vector);
CREATE INDEX IF NOT EXISTS places_search_mv_signals_gin ON epx.places_search_mv USING gin (signals);

-- 6. Обновляем материализованное представление
REFRESH MATERIALIZED VIEW epx.places_search_mv;

-- 7. Проверяем результат
SELECT 'Поле signals добавлено' as status WHERE EXISTS (
  SELECT 1 FROM information_schema.columns 
  WHERE table_name = 'places' AND column_name = 'signals'
);

SELECT 'MV создано' as status WHERE EXISTS (
  SELECT 1 FROM pg_matviews WHERE matviewname = 'places_search_mv'
);

SELECT COUNT(*) as records_with_signals FROM places 
WHERE signals IS NOT NULL AND signals != '{}'::jsonb;
