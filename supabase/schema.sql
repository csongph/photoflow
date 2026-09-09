-- MomentLink Cloud schema for Supabase
-- Run this in Supabase SQL Editor if you want to create tables manually.

create table if not exists events (
  id varchar(32) primary key,
  public_id varchar(64) not null unique,
  name varchar(180) not null,
  event_date varchar(20) not null default '',
  description text not null default '',
  pin_hash varchar(200) not null default '',
  created_at timestamp,
  updated_at timestamp
);

create index if not exists ix_events_public_id on events (public_id);

create table if not exists gallery_settings (
  event_id varchar(32) primary key references events(id) on delete cascade,
  enabled boolean not null default true,
  allow_download boolean not null default true,
  find_my_photos boolean not null default false,
  auto_refresh boolean not null default true,
  credit_text varchar(220) not null default '',
  report_contact varchar(220) not null default ''
);

create table if not exists photos (
  id varchar(32) primary key,
  event_id varchar(32) references events(id) on delete cascade,
  local_photo_id varchar(64),
  filename varchar(260),
  capture_id varchar(220),
  storage_provider varchar(60),
  storage_object_id varchar(300),
  published boolean default false,
  hidden boolean default false,
  created_at timestamp,
  constraint uq_photo_event_local unique (event_id, local_photo_id)
);

create index if not exists ix_photos_event_id on photos (event_id);
create index if not exists ix_photos_local_photo_id on photos (local_photo_id);
create index if not exists ix_photos_capture_id on photos (capture_id);
create index if not exists ix_photos_published on photos (published);

create table if not exists photo_variants (
  id varchar(32) primary key,
  photo_id varchar(32) references photos(id) on delete cascade,
  kind varchar(30),
  storage_provider varchar(60),
  storage_object_id varchar(300),
  width integer default 0,
  height integer default 0
);

create index if not exists ix_photo_variants_photo_id on photo_variants (photo_id);
create index if not exists ix_photo_variants_kind on photo_variants (kind);

create table if not exists sync_jobs (
  id varchar(32) primary key,
  event_id varchar(32) references events(id) on delete cascade,
  state varchar(40),
  payload_json text default '{}',
  created_at timestamp
);

create index if not exists ix_sync_jobs_event_id on sync_jobs (event_id);
create index if not exists ix_sync_jobs_state on sync_jobs (state);

create table if not exists photo_faces (
  id varchar(32) primary key,
  event_id varchar(32) references events(id) on delete cascade,
  photo_id varchar(32) references photos(id) on delete cascade,
  embedding bytea,
  confidence double precision default 0,
  bounding_box varchar(120) default '',
  created_at timestamp
);

create index if not exists ix_photo_faces_event_photo on photo_faces (event_id, photo_id);

create table if not exists face_search_sessions (
  id varchar(48) primary key,
  event_id varchar(32) references events(id) on delete cascade,
  status varchar(40) default 'CREATED',
  created_at timestamp
);

create index if not exists ix_face_search_sessions_event_id on face_search_sessions (event_id);
