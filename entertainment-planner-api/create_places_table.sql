-- Create places table with full schema matching source database
DROP TABLE IF EXISTS public.places CASCADE;

CREATE TABLE public.places (
    id integer NOT NULL DEFAULT nextval('places_id_seq'::regclass),
    source text,
    source_url text,
    raw_payload text,
    scraped_at timestamp without time zone,
    lat double precision,
    lng double precision,
    address text,
    gmaps_place_id text,
    gmaps_url text,
    business_status text,
    utc_offset_minutes integer,
    name text,
    category text,
    description_full text,
    summary text,
    tags_csv text,
    price_level integer,
    rating double precision,
    hours_json text,
    picture_url text,
    website text,
    phone text,
    processing_status text,
    last_error text,
    published_at timestamp without time zone,
    updated_at timestamp without time zone,
    summary_source text,
    summary_version integer,
    ai_verified text,
    ai_verification_date timestamp without time zone,
    ai_verification_data text,
    interest_signals json,
    attempts text,
    quality_flags text,
    tag_bitset integer,
    category_id integer,
    sig_hash character varying,
    signals jsonb DEFAULT '{}'::jsonb,
    search_vector tsvector,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT places_pkey PRIMARY KEY (id)
);

-- Create sequence for id
CREATE SEQUENCE IF NOT EXISTS places_id_seq;
ALTER TABLE public.places ALTER COLUMN id SET DEFAULT nextval('places_id_seq'::regclass);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_places_processing_status ON public.places (processing_status);
CREATE INDEX IF NOT EXISTS idx_places_category ON public.places (category);
CREATE INDEX IF NOT EXISTS idx_places_rating ON public.places (rating);
CREATE INDEX IF NOT EXISTS idx_places_signals ON public.places USING GIN (signals);
CREATE INDEX IF NOT EXISTS idx_places_search_vector ON public.places USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_places_location ON public.places (lat, lng);

-- Grant permissions
GRANT ALL ON TABLE public.places TO postgres;
GRANT ALL ON SEQUENCE places_id_seq TO postgres;
