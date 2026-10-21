CREATE TABLE photolab.feature_sets (
    file_id bigint NOT NULL REFERENCES photolab.photometry_files(id),
    algorithm_version text NOT NULL,
    dimensions smallint NOT NULL CHECK (dimensions = 684),
    vector real[] NOT NULL CHECK (cardinality(vector) = 684),
    l2_norm real NOT NULL CHECK (l2_norm > 0),
    canonical_rotation smallint NOT NULL CHECK (canonical_rotation >= 0 AND canonical_rotation < 360),
    feature_digest char(64) NOT NULL CHECK (feature_digest ~ '^[0-9a-f]{64}$'),
    bucket_0 smallint NOT NULL CHECK (bucket_0 BETWEEN 0 AND 4095),
    bucket_1 smallint NOT NULL CHECK (bucket_1 BETWEEN 0 AND 4095),
    bucket_2 smallint NOT NULL CHECK (bucket_2 BETWEEN 0 AND 4095),
    bucket_3 smallint NOT NULL CHECK (bucket_3 BETWEEN 0 AND 4095),
    bucket_4 smallint NOT NULL CHECK (bucket_4 BETWEEN 0 AND 4095),
    bucket_5 smallint NOT NULL CHECK (bucket_5 BETWEEN 0 AND 4095),
    bucket_6 smallint NOT NULL CHECK (bucket_6 BETWEEN 0 AND 4095),
    bucket_7 smallint NOT NULL CHECK (bucket_7 BETWEEN 0 AND 4095),
    generated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (file_id, algorithm_version)
);

CREATE INDEX feature_sets_bucket_0_idx ON photolab.feature_sets (algorithm_version, bucket_0);
CREATE INDEX feature_sets_bucket_1_idx ON photolab.feature_sets (algorithm_version, bucket_1);
CREATE INDEX feature_sets_bucket_2_idx ON photolab.feature_sets (algorithm_version, bucket_2);
CREATE INDEX feature_sets_bucket_3_idx ON photolab.feature_sets (algorithm_version, bucket_3);
CREATE INDEX feature_sets_bucket_4_idx ON photolab.feature_sets (algorithm_version, bucket_4);
CREATE INDEX feature_sets_bucket_5_idx ON photolab.feature_sets (algorithm_version, bucket_5);
CREATE INDEX feature_sets_bucket_6_idx ON photolab.feature_sets (algorithm_version, bucket_6);
CREATE INDEX feature_sets_bucket_7_idx ON photolab.feature_sets (algorithm_version, bucket_7);

CREATE TABLE photolab.feature_generation_errors (
    file_id bigint NOT NULL REFERENCES photolab.photometry_files(id),
    algorithm_version text NOT NULL,
    message text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (file_id, algorithm_version)
);
