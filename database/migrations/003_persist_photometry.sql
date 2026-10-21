CREATE TABLE photolab.photometries (
    file_id bigint PRIMARY KEY REFERENCES photolab.photometry_files(id),
    schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    application_version text NOT NULL,
    data jsonb NOT NULL CHECK (jsonb_typeof(data) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
