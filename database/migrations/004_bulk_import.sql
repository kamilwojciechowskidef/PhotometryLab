ALTER TABLE photolab.import_batches
    ADD COLUMN status text NOT NULL DEFAULT 'legacy',
    ADD COLUMN report jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN expected_files integer,
    ADD COLUMN finished_at timestamptz;
