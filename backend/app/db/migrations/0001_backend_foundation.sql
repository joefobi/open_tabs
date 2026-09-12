CREATE TABLE owners (
  id UUID PRIMARY KEY,
  installation_credential_hash TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE images (
  id UUID PRIMARY KEY,
  owner_id UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  storage_key TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sources (
  id UUID PRIMARY KEY,
  owner_id UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  source_key TEXT NOT NULL,
  latest_observation_id UUID,
  latest_revision INTEGER NOT NULL DEFAULT 0,
  observed_at TIMESTAMPTZ,
  UNIQUE (owner_id, source_key)
);

CREATE TABLE observations (
  id UUID PRIMARY KEY,
  owner_id UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  revision INTEGER NOT NULL,
  client_observation_id TEXT NOT NULL,
  source_url TEXT NOT NULL,
  title TEXT NOT NULL,
  text TEXT NOT NULL,
  extraction_state TEXT NOT NULL,
  truncated BOOLEAN NOT NULL DEFAULT false,
  content_hash TEXT NOT NULL,
  screenshot_id UUID REFERENCES images(id),
  captured_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_id, client_observation_id)
);

ALTER TABLE sources
  ADD CONSTRAINT sources_latest_observation_id_fkey
  FOREIGN KEY (latest_observation_id)
  REFERENCES observations(id)
  ON DELETE SET NULL;

CREATE TABLE tasks (
  id UUID PRIMARY KEY,
  owner_id UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  origin TEXT NOT NULL,
  source_key TEXT,
  source_url TEXT,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  status_reason TEXT,
  summary TEXT,
  processing_state TEXT NOT NULL,
  processing_error_code TEXT,
  detection_revision INTEGER,
  summary_revision INTEGER,
  observed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_id, source_key)
);

CREATE TABLE scans (
  id UUID PRIMARY KEY,
  owner_id UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  client_request_id TEXT NOT NULL,
  state TEXT NOT NULL,
  item_count INTEGER NOT NULL DEFAULT 0,
  completed_count INTEGER NOT NULL DEFAULT 0,
  error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_id, client_request_id)
);

CREATE TABLE scan_items (
  id UUID PRIMARY KEY,
  scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
  observation_id UUID NOT NULL REFERENCES observations(id) ON DELETE CASCADE,
  task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
  processing_state TEXT NOT NULL,
  detection_outcome TEXT,
  error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX owners_installation_credential_hash_idx
  ON owners (installation_credential_hash);

CREATE INDEX tasks_owner_updated_at_idx
  ON tasks (owner_id, updated_at DESC);
