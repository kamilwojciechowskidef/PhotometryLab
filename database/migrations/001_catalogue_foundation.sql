CREATE TABLE photolab.import_batches (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    imported_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_description text,
    application_version text NOT NULL
);

CREATE TABLE photolab.photometry_files (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256 char(64) NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    format text,
    quality_status text NOT NULL,
    private_artifact_path text,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE photolab.file_aliases (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_id bigint NOT NULL REFERENCES photolab.photometry_files(id),
    import_batch_id bigint NOT NULL REFERENCES photolab.import_batches(id),
    original_filename text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (import_batch_id, original_filename)
);

CREATE INDEX file_aliases_file_id_idx ON photolab.file_aliases (file_id);
