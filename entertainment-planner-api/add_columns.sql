-- Добавляем колонки для full-text search и signals
ALTER TABLE places ADD COLUMN IF NOT EXISTS search_vector tsvector;
ALTER TABLE places ADD COLUMN IF NOT EXISTS signals JSONB;

-- Создаем индексы
CREATE INDEX IF NOT EXISTS places_search_gin_idx ON places USING gin (search_vector);
CREATE INDEX IF NOT EXISTS places_signals_idx ON places USING gin (signals);

-- Заполняем search_vector для существующих записей
UPDATE places
SET search_vector = to_tsvector(
  'simple',
  unaccent(coalesce(name,'') || ' ' || coalesce(category,'') || ' ' ||
           coalesce(tags_csv,'') || ' ' || coalesce(summary,''))
);
