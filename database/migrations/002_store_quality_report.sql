ALTER TABLE photolab.photometry_files
    ADD COLUMN quality_report jsonb NOT NULL DEFAULT '{}'::jsonb;
