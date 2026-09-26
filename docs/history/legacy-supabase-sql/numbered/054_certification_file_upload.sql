-- 054: Add file upload support to certifications and training_records
-- Allows certificate files to be uploaded to Supabase Storage instead of pasting URLs.
-- Idempotent — safe to re-run.

-- certifications: storage_path for uploaded certificate file
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'certifications' AND column_name = 'storage_path'
  ) THEN
    ALTER TABLE certifications ADD COLUMN storage_path TEXT DEFAULT '';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'certifications' AND column_name = 'file_name'
  ) THEN
    ALTER TABLE certifications ADD COLUMN file_name TEXT DEFAULT '';
  END IF;
END $$;

-- training_records: storage_path for uploaded certificate/completion file
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'training_records' AND column_name = 'storage_path'
  ) THEN
    ALTER TABLE training_records ADD COLUMN storage_path TEXT DEFAULT '';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'training_records' AND column_name = 'file_name'
  ) THEN
    ALTER TABLE training_records ADD COLUMN file_name TEXT DEFAULT '';
  END IF;
END $$;
