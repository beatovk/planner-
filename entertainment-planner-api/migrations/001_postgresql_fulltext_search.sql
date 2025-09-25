-- Migration: PostgreSQL Full-Text Search Setup
-- Description: Adds full-text search capabilities to PostgreSQL with tsvector column and indexes

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS cube;
CREATE EXTENSION IF NOT EXISTS earthdistance;

-- Add search_vector column to places table
ALTER TABLE places ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Create function to update search_vector
CREATE OR REPLACE FUNCTION places_search_vector_update()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_vector := to_tsvector(
    'simple',
    unaccent(coalesce(NEW.name,'') || ' ' || coalesce(NEW.category,'') || ' ' ||
             coalesce(NEW.tags_csv,'') || ' ' || coalesce(NEW.summary,'') || ' ' ||
             coalesce(NEW.description_full,''))
  );
  RETURN NEW;
END $$;

-- Create trigger to automatically update search_vector
DROP TRIGGER IF EXISTS trg_places_search_vector ON places;
CREATE TRIGGER trg_places_search_vector
BEFORE INSERT OR UPDATE OF name, category, tags_csv, summary, description_full
ON places FOR EACH ROW EXECUTE FUNCTION places_search_vector_update();

-- Update existing records with search_vector
UPDATE places
SET search_vector = to_tsvector(
  'simple',
  unaccent(coalesce(name,'') || ' ' || coalesce(category,'') || ' ' ||
           coalesce(tags_csv,'') || ' ' || coalesce(summary,'') || ' ' ||
           coalesce(description_full,''))
);

-- Create indexes for full-text search
CREATE INDEX IF NOT EXISTS places_search_gin_idx ON places USING gin (search_vector);
CREATE INDEX IF NOT EXISTS places_loc_gist_idx ON places USING gist (ll_to_earth(lat, lng));
CREATE INDEX IF NOT EXISTS places_status_idx ON places (processing_status);
CREATE INDEX IF NOT EXISTS places_updated_idx ON places (updated_at DESC);
CREATE INDEX IF NOT EXISTS places_rating_idx ON places (rating DESC);

-- Create index for signals column (for surprise me feature)
CREATE INDEX IF NOT EXISTS places_signals_idx ON places USING gin (signals);

-- Add comment for documentation
COMMENT ON COLUMN places.search_vector IS 'Full-text search vector for PostgreSQL tsvector search';
COMMENT ON COLUMN places.signals IS 'JSON signals for surprise me feature and special place marking';
