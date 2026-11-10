CREATE TABLE photolab.archive_assets (
    batch_id bigint NOT NULL REFERENCES photolab.import_batches(id),
    member_name text NOT NULL,
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    private_artifact_path text NOT NULL,
    PRIMARY KEY (batch_id, member_name)
);

CREATE INDEX archive_assets_sha256_idx ON photolab.archive_assets (sha256);
