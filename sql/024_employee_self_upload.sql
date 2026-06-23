-- ============================================================
-- Migration 024: Employee Self-Service Document Uploads (Feature 1.2)
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Add status, document_number, rejection_reason columns to employee_documents
ALTER TABLE employee_documents
  ADD COLUMN IF NOT EXISTS document_number   TEXT    NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS status            TEXT    NOT NULL DEFAULT 'verified',
  ADD COLUMN IF NOT EXISTS rejection_reason  TEXT    NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS submitted_by      TEXT    NOT NULL DEFAULT 'hr'; -- 'hr' | 'employee'

-- 2. RPC: employee submits a document (SECURITY DEFINER so it writes using the admin's user_id)
CREATE OR REPLACE FUNCTION employee_submit_document(
  p_document_type  TEXT,
  p_document_number TEXT,
  p_expiry_date    DATE,
  p_notes          TEXT,
  p_storage_path   TEXT,
  p_file_name      TEXT,
  p_file_size      INTEGER
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_employee_id UUID;
  v_admin_uid   UUID;
  v_doc_id      UUID;
BEGIN
  -- Resolve caller's employee record
  SELECT id, user_id
    INTO v_employee_id, v_admin_uid
    FROM employees
   WHERE auth_user_id = auth.uid()
     AND active = true
   LIMIT 1;

  IF v_employee_id IS NULL THEN
    RAISE EXCEPTION 'No active employee account linked to this user';
  END IF;

  INSERT INTO employee_documents (
    user_id, employee_id, document_type, document_number,
    file_name, file_size, storage_path, expiry_date,
    notes, status, submitted_by
  ) VALUES (
    v_admin_uid, v_employee_id, p_document_type, COALESCE(p_document_number, ''),
    p_file_name, COALESCE(p_file_size, 0), p_storage_path, p_expiry_date,
    COALESCE(p_notes, ''), 'pending_verification', 'employee'
  )
  RETURNING id INTO v_doc_id;

  RETURN v_doc_id;
END;
$$;

GRANT EXECUTE ON FUNCTION employee_submit_document(TEXT, TEXT, DATE, TEXT, TEXT, TEXT, INTEGER) TO authenticated;

-- 3. Employee can update their own pending document (e.g. to replace file before HR reviews)
DROP POLICY IF EXISTS "employee_documents_self_update_pending" ON employee_documents;
CREATE POLICY "employee_documents_self_update_pending"
  ON employee_documents
  FOR UPDATE
  USING (
    submitted_by = 'employee'
    AND status = 'pending_verification'
    AND employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- ============================================================
-- Storage policies (run in Supabase Dashboard → SQL Editor)
-- These allow employees to upload files into their employer's
-- folder: {admin_user_id}/{employee_id}/{filename}
-- ============================================================

-- INSERT: employee can upload to the folder matching their employment record
DROP POLICY IF EXISTS "employee_documents_employee_upload" ON storage.objects;
CREATE POLICY "employee_documents_employee_upload"
  ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'employee-documents'
    AND EXISTS (
      SELECT 1 FROM public.employees e
       WHERE e.auth_user_id = auth.uid()
         AND e.user_id::text  = (storage.foldername(name))[1]
         AND e.id::text       = (storage.foldername(name))[2]
    )
  );

-- SELECT: employee can generate signed URLs for files in their folder
DROP POLICY IF EXISTS "employee_documents_employee_read_own" ON storage.objects;
CREATE POLICY "employee_documents_employee_read_own"
  ON storage.objects
  FOR SELECT TO authenticated
  USING (
    bucket_id = 'employee-documents'
    AND EXISTS (
      SELECT 1 FROM public.employees e
       WHERE e.auth_user_id = auth.uid()
         AND e.user_id::text  = (storage.foldername(name))[1]
         AND e.id::text       = (storage.foldername(name))[2]
    )
  );

-- ============================================================
-- After running, also run:
--   GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
-- ============================================================
