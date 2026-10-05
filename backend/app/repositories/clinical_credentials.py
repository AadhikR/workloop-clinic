CLINICAL_CREDENTIALS = """
  SELECT 'document:'||document.id::text id,document.employee_id,
    document.document_type source_type,document.expiry_date
  FROM public.employee_documents document
  WHERE document.company_id=:company_id AND document.branch_id=:branch_id
    AND document.document_type=ANY(:clinical_types) AND document.status='verified'
    AND document.content_type IS NOT NULL AND document.cleanup_requested_at IS NULL
    AND public.file_security_scan_allows_download(
      document.file_security_scan_id,'employee_document',document.id,document.storage_path,
      document.content_type,document.file_size,document.sha256,:scanner_definition)
  UNION ALL
  SELECT 'certification:'||certification.id::text id,certification.employee_id,
    certification.certification_name source_type,certification.expiry_date
  FROM public.certifications certification
  WHERE certification.company_id=:company_id AND certification.branch_id=:branch_id
    AND certification.status='verified' AND certification.content_type IS NOT NULL
    AND public.file_security_scan_allows_download(
      certification.file_security_scan_id,'certification_evidence',certification.id,
      certification.storage_path,certification.content_type,certification.size_bytes,
      certification.sha256,:scanner_definition)
"""
