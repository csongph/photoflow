-- PhotoFlow / MomentLink schema for a new Supabase Postgres project.
-- Run this once in Supabase Dashboard > SQL Editor.
-- This creates the current application schema only; it does not restore deleted data.

BEGIN;

CREATE TABLE public.events (
    id VARCHAR(32) PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL,
    name VARCHAR(180) NOT NULL,
    event_date VARCHAR(20) NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    pin_hash VARCHAR(200) NOT NULL DEFAULT '',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE UNIQUE INDEX ix_events_public_id ON public.events (public_id);

CREATE TABLE public.gallery_settings (
    event_id VARCHAR(32) PRIMARY KEY REFERENCES public.events (id),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    allow_download BOOLEAN NOT NULL,
    find_my_photos BOOLEAN NOT NULL DEFAULT FALSE,
    auto_refresh BOOLEAN NOT NULL,
    credit_text VARCHAR(220) NOT NULL DEFAULT '',
    report_contact VARCHAR(220) NOT NULL DEFAULT ''
);

CREATE TABLE public.photos (
    id VARCHAR(32) PRIMARY KEY,
    event_id VARCHAR(32) NOT NULL REFERENCES public.events (id),
    local_photo_id VARCHAR(64) NOT NULL,
    filename VARCHAR(260) NOT NULL,
    capture_id VARCHAR(220) NOT NULL,
    storage_provider VARCHAR(60) NOT NULL,
    storage_object_id VARCHAR(300) NOT NULL DEFAULT '',
    published BOOLEAN NOT NULL DEFAULT FALSE,
    hidden BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT uq_photo_event_local UNIQUE (event_id, local_photo_id)
);
CREATE INDEX ix_photos_event_id ON public.photos (event_id);
CREATE INDEX ix_photos_local_photo_id ON public.photos (local_photo_id);
CREATE INDEX ix_photos_capture_id ON public.photos (capture_id);
CREATE INDEX ix_photos_published ON public.photos (published);

CREATE TABLE public.photo_variants (
    id VARCHAR(32) PRIMARY KEY,
    photo_id VARCHAR(32) NOT NULL REFERENCES public.photos (id),
    kind VARCHAR(30) NOT NULL,
    storage_provider VARCHAR(60) NOT NULL,
    storage_object_id VARCHAR(300) NOT NULL,
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_photo_variants_photo_id ON public.photo_variants (photo_id);
CREATE INDEX ix_photo_variants_kind ON public.photo_variants (kind);

CREATE TABLE public.sync_jobs (
    id VARCHAR(32) PRIMARY KEY,
    event_id VARCHAR(32) NOT NULL REFERENCES public.events (id),
    state VARCHAR(40) NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE INDEX ix_sync_jobs_event_id ON public.sync_jobs (event_id);
CREATE INDEX ix_sync_jobs_state ON public.sync_jobs (state);

CREATE TABLE public.photo_faces (
    id VARCHAR(32) PRIMARY KEY,
    event_id VARCHAR(32) NOT NULL REFERENCES public.events (id),
    photo_id VARCHAR(32) NOT NULL REFERENCES public.photos (id),
    embedding BYTEA NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    bounding_box VARCHAR(120) NOT NULL DEFAULT '',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE INDEX ix_photo_faces_event_id ON public.photo_faces (event_id);
CREATE INDEX ix_photo_faces_photo_id ON public.photo_faces (photo_id);
CREATE INDEX ix_photo_faces_event_photo ON public.photo_faces (event_id, photo_id);

CREATE TABLE public.face_search_sessions (
    id VARCHAR(48) PRIMARY KEY,
    event_id VARCHAR(32) NOT NULL REFERENCES public.events (id),
    status VARCHAR(40) NOT NULL DEFAULT 'CREATED',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE INDEX ix_face_search_sessions_event_id ON public.face_search_sessions (event_id);

-- Mark the existing Alembic migration chain as applied so the next Render deploy
-- does not try to recreate these tables.
CREATE TABLE public.alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);
INSERT INTO public.alembic_version (version_num)
VALUES ('0003_disable_face_search');

COMMIT;
