CREATE TABLE photolab.zip_product_bundles (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_batch_id bigint NOT NULL REFERENCES photolab.import_batches(id),
    source_stem text NOT NULL,
    metadata jsonb CHECK (metadata IS NULL OR jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (import_batch_id, source_stem)
);

CREATE TABLE photolab.zip_bundle_assets (
    bundle_id bigint NOT NULL REFERENCES photolab.zip_product_bundles(id),
    original_filename text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('ies', 'ldt', 'json', 'jpg', 'png')),
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    artifact_path text NOT NULL,
    photometry_file_id bigint REFERENCES photolab.photometry_files(id),
    PRIMARY KEY (bundle_id, original_filename)
);
