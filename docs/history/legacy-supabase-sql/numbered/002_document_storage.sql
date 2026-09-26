-- ============================================================
-- Migration 002: Employee Document Storage
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Create employee_documents table
CREATE TABLE IF NOT EXISTS employee_documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  employee_id   UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  document_type TEXT NOT NULL,           -- 'Visa', 'Passport', 'Emirates ID', etc.
  file_name     TEXT NOT NULL,           -- original filename for display
  file_size     INTEGER NOT NULL DEFAULT 0, -- bytes
  storage_path  TEXT NOT NULL DEFAULT '', -- path within the Supabase Storage bucket
  expiry_date   DATE,                    -- nullable — not all docs expire
  notes         TEXT NOT NULL DEFAULT '',
  uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Enable RLS
ALTER TABLE employee_documents ENABLE ROW LEVEL SECURITY;

-- 3. Grant access
GRANT ALL ON TABLE employee_documents TO authenticated;

-- 4. Admin RLS: company owner sees all their employees' documents
CREATE POLICY "employee_documents_admin"
  ON employee_documents
  FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- 5. Employee self-service: can read their own documents
CREATE POLICY "employee_documents_self_read"
  ON employee_documents
  FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- ============================================================
-- Supabase Storage setup (do this in the Supabase Dashboard):
--
-- 1. Go to Storage → Create new bucket
-- 2. Name: employee-documents
-- 3. Public: OFF (private bucket — signed URLs used for access)
-- 4. File size limit: 10 MB
-- 5. Allowed MIME types: image/jpeg, image/png, application/pdf
--
-- Then add a Storage policy allowing authenticated users to
-- upload/read files under their own user_id prefix:
--
-- INSERT policy:
--   (storage.foldername(name))[1] = auth.uid()::text
--
-- SELECT policy:
--   (storage.foldername(name))[1] = auth.uid()::text
--
-- DELETE policy:
--   (storage.foldername(name))[1] = auth.uid()::text
-- ============================================================
