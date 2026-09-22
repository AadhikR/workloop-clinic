"""Add the Phase 11B file-security queue.

Revision ID: d8f0a2c4e6b1
Revises: c6e8a1b3d927
Created: 2026-09-22 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8f0a2c4e6b1"
down_revision: str | Sequence[str] | None = "c6e8a1b3d927"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCANNER_CONTEXT = """
current_user='workloop_file_scanner'
AND session_user='workloop_file_scanner'
AND public.workloop_actor_kind()='scheduled_job'
AND public.workloop_actor_key()='file_security_scan'
""".strip()


def _replace_actor_key_reader(*, include_scanner: bool) -> None:
    values = "'expiry_processing','storage_reconciliation'"
    if include_scanner:
        values += ",'file_security_scan'"
    op.execute(f"""
CREATE OR REPLACE FUNCTION public.workloop_actor_key()
RETURNS text
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path TO pg_catalog, pg_temp
AS $function$
  SELECT CASE WHEN value IN ({values}) THEN value ELSE NULL END
  FROM (VALUES (pg_catalog.current_setting('workloop.actor_key', true))) AS setting(value)
$function$
""")
    op.execute("ALTER FUNCTION public.workloop_actor_key() OWNER TO workloop_migration")
    op.execute("REVOKE ALL ON FUNCTION public.workloop_actor_key() FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.workloop_actor_key() "
        "TO workloop_runtime,workloop_expiry_processing,workloop_storage_reconciler"
    )
    if include_scanner:
        op.execute("GRANT EXECUTE ON FUNCTION public.workloop_actor_key() TO workloop_file_scanner")


def upgrade() -> None:
    _replace_actor_key_reader(include_scanner=True)
    op.create_table(
        "file_security_scans",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=True),
        sa.Column("created_by_app_user_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("scanner_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("scanner_definition", sa.Text(), nullable=False),
        sa.Column("result_signature", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error_code", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entity_type IN ('leave_attachment','expense_receipt','employee_document',"
            "'training_evidence','certification_evidence')",
            name="entity_type",
        ),
        sa.CheckConstraint(
            "octet_length(object_key) BETWEEN 1 AND 1024 "
            "AND object_key !~ '[[:cntrl:]\\\\]' AND left(object_key,1)<>'/' "
            "AND object_key NOT LIKE '%//%' AND ('/'||object_key||'/') NOT LIKE '%/./%' "
            "AND ('/'||object_key||'/') NOT LIKE '%/../%'",
            name="object_key",
        ),
        sa.CheckConstraint(
            "content_type IN ('application/pdf','image/png','image/jpeg')",
            name="content_type",
        ),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 10485760", name="size_bytes"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        sa.CheckConstraint(
            "scanner_definition ~ '^[a-z0-9][a-z0-9._-]{0,63}$'",
            name="scanner_definition",
        ),
        sa.CheckConstraint(
            "scanner_name='' OR scanner_name ~ '^[a-z0-9][a-z0-9._-]{0,63}$'",
            name="scanner_name",
        ),
        sa.CheckConstraint(
            "result_signature='' OR result_signature ~ '^[a-z0-9][a-z0-9._-]{0,63}$'",
            name="result_signature",
        ),
        sa.CheckConstraint(
            "last_error_code='' OR last_error_code ~ '^[a-z0-9][a-z0-9._-]{0,63}$'",
            name="last_error_code",
        ),
        sa.CheckConstraint(
            "status IN ('pending','claimed','clean','infected','failed')",
            name="status",
        ),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 8", name="attempt_count"),
        sa.CheckConstraint(
            "(status='pending' AND attempt_count=0 AND scanner_name='' "
            "AND result_signature='' AND last_error_code='' AND next_attempt_at IS NULL "
            "AND claimed_at IS NULL AND lease_expires_at IS NULL AND scanned_at IS NULL "
            "AND valid_until IS NULL) OR "
            "(status='claimed' AND attempt_count BETWEEN 1 AND 8 AND scanner_name='' "
            "AND result_signature='' AND last_error_code='' AND next_attempt_at IS NULL "
            "AND claimed_at IS NOT NULL AND lease_expires_at=claimed_at+interval '15 minutes' "
            "AND scanned_at IS NULL AND valid_until IS NULL) OR "
            "(status='clean' AND attempt_count BETWEEN 1 AND 8 AND scanner_name<>'' "
            "AND result_signature<>'' AND last_error_code='' AND next_attempt_at IS NULL "
            "AND claimed_at IS NULL AND lease_expires_at IS NULL AND scanned_at IS NOT NULL "
            "AND valid_until=scanned_at+interval '30 days') OR "
            "(status='infected' AND attempt_count BETWEEN 1 AND 8 AND scanner_name<>'' "
            "AND result_signature<>'' AND last_error_code='' AND next_attempt_at IS NULL "
            "AND claimed_at IS NULL AND lease_expires_at IS NULL AND scanned_at IS NOT NULL "
            "AND valid_until IS NULL) OR "
            "(status='failed' AND attempt_count BETWEEN 1 AND 8 AND scanner_name='' "
            "AND result_signature='' AND last_error_code<>'' AND claimed_at IS NULL "
            "AND lease_expires_at IS NULL AND scanned_at IS NULL AND valid_until IS NULL "
            "AND ((attempt_count<8 AND next_attempt_at IS NOT NULL) "
            "OR (attempt_count=8 AND next_attempt_at IS NULL)))",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "updated_at>=created_at AND (next_attempt_at IS NULL OR next_attempt_at>=created_at) "
            "AND (claimed_at IS NULL OR claimed_at>=created_at) "
            "AND (lease_expires_at IS NULL OR lease_expires_at>=created_at) "
            "AND (scanned_at IS NULL OR scanned_at>=created_at) "
            "AND (valid_until IS NULL OR valid_until>=created_at)",
            name="timestamps",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_file_security_scans"),
        sa.UniqueConstraint(
            "id",
            "company_id",
            "branch_id",
            name="uq_file_security_scans_id_company_id_branch_id",
        ),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_file_security_scans_entity"),
        sa.UniqueConstraint("object_key", name="uq_file_security_scans_object_key"),
    )
    op.create_index(
        "ix_file_security_scans_claim",
        "file_security_scans",
        ["status", "next_attempt_at", "lease_expires_at", "created_at", "id"],
    )
    op.create_index(
        "ix_file_security_scans_expiry",
        "file_security_scans",
        ["valid_until", "id"],
        postgresql_where=sa.text("status='clean'"),
    )
    op.create_index(
        "ix_file_security_scans_entity",
        "file_security_scans",
        ["entity_type", "entity_id"],
    )
    op.execute("ALTER TABLE public.file_security_scans OWNER TO workloop_migration")

    for table in ("leave_attachments", "expense_receipts"):
        op.add_column(table, sa.Column("file_security_scan_id", sa.UUID(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_file_security_scan_scope",
            table,
            "file_security_scans",
            ["file_security_scan_id", "company_id", "branch_id"],
            ["id", "company_id", "branch_id"],
            ondelete="RESTRICT",
        )
        op.execute(f"GRANT UPDATE(file_security_scan_id) ON public.{table} TO workloop_runtime")

    op.execute(r"""
CREATE FUNCTION public._file_security_scan_transition_phase11b()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF session_user<>'workloop_file_scanner'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'scheduled_job'
    OR public.workloop_actor_key() IS DISTINCT FROM 'file_security_scan' THEN
    RAISE EXCEPTION 'file security scan transition denied' USING ERRCODE='42501';
  END IF;
  IF NOT (
    (OLD.status='pending' AND OLD.attempt_count=0
     AND NEW.status='claimed' AND NEW.attempt_count=1
     AND NEW.claimed_at=statement_timestamp()
     AND NEW.lease_expires_at=NEW.claimed_at+interval '15 minutes')
    OR
    (OLD.status='clean' AND OLD.valid_until<=statement_timestamp()
     AND NEW.status='claimed' AND NEW.attempt_count=1
     AND NEW.scanner_name='' AND NEW.result_signature=''
     AND NEW.scanned_at IS NULL AND NEW.valid_until IS NULL
     AND NEW.claimed_at=statement_timestamp()
     AND NEW.lease_expires_at=NEW.claimed_at+interval '15 minutes')
    OR
    (OLD.status='failed' AND OLD.attempt_count BETWEEN 1 AND 7
     AND OLD.next_attempt_at<=statement_timestamp()
     AND NEW.status='claimed' AND NEW.attempt_count=OLD.attempt_count+1
     AND NEW.claimed_at=statement_timestamp()
     AND NEW.lease_expires_at=NEW.claimed_at+interval '15 minutes')
    OR
    (OLD.status='failed' AND OLD.attempt_count BETWEEN 1 AND 7
     AND NEW.status='failed' AND NEW.attempt_count=OLD.attempt_count
     AND NEW.last_error_code=OLD.last_error_code
     AND NEW.next_attempt_at=statement_timestamp())
    OR
    (OLD.status='claimed' AND OLD.attempt_count BETWEEN 1 AND 7
     AND OLD.lease_expires_at<=statement_timestamp()
     AND NEW.status='claimed' AND NEW.attempt_count=OLD.attempt_count+1
     AND NEW.claimed_at=statement_timestamp()
     AND NEW.lease_expires_at=NEW.claimed_at+interval '15 minutes')
    OR
    (OLD.status='claimed' AND NEW.attempt_count=OLD.attempt_count
     AND NEW.status IN ('clean','infected')
     AND NEW.scanned_at BETWEEN OLD.claimed_at AND statement_timestamp())
    OR
    (OLD.status='claimed' AND OLD.attempt_count BETWEEN 1 AND 7
     AND NEW.status='failed' AND NEW.attempt_count=OLD.attempt_count
     AND NEW.last_error_code<>''
     AND NEW.next_attempt_at=statement_timestamp()+CASE OLD.attempt_count
       WHEN 1 THEN interval '1 minute' WHEN 2 THEN interval '5 minutes'
       WHEN 3 THEN interval '15 minutes' WHEN 4 THEN interval '1 hour'
       WHEN 5 THEN interval '6 hours' WHEN 6 THEN interval '24 hours'
       WHEN 7 THEN interval '72 hours' END)
    OR
    (OLD.status='claimed' AND OLD.attempt_count=8 AND NEW.status='failed'
     AND NEW.attempt_count=8 AND NEW.next_attempt_at IS NULL
     AND NEW.last_error_code<>'')) THEN
    RAISE EXCEPTION 'file security scan transition denied' USING ERRCODE='42501';
  END IF;
  IF NEW.id<>OLD.id OR NEW.company_id<>OLD.company_id OR NEW.branch_id<>OLD.branch_id
    OR NEW.employee_id IS DISTINCT FROM OLD.employee_id
    OR NEW.created_by_app_user_id<>OLD.created_by_app_user_id
    OR NEW.entity_type<>OLD.entity_type OR NEW.entity_id<>OLD.entity_id
    OR NEW.object_key<>OLD.object_key OR NEW.content_type<>OLD.content_type
    OR NEW.size_bytes<>OLD.size_bytes OR NEW.sha256<>OLD.sha256
    OR NEW.scanner_definition<>OLD.scanner_definition OR NEW.created_at<>OLD.created_at THEN
    RAISE EXCEPTION 'file security scan identity is immutable' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END
$function$
""")
    op.execute(
        "ALTER FUNCTION public._file_security_scan_transition_phase11b() "
        "OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public._file_security_scan_transition_phase11b() FROM PUBLIC"
    )
    op.execute(
        "CREATE TRIGGER file_security_scan_transition_phase11b "
        "BEFORE UPDATE ON public.file_security_scans FOR EACH ROW "
        "EXECUTE FUNCTION public._file_security_scan_transition_phase11b()"
    )

    op.execute(r"""
CREATE FUNCTION public.append_file_security_audit(
  p_scan_id uuid, p_action text, p_error_code text DEFAULT ''
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  scan public.file_security_scans%ROWTYPE;
  event_id uuid;
BEGIN
  IF session_user<>'workloop_file_scanner'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'scheduled_job'
    OR public.workloop_actor_key() IS DISTINCT FROM 'file_security_scan'
    OR public.workloop_company_id() IS NULL OR public.workloop_branch_id() IS NULL THEN
    RAISE EXCEPTION 'file security audit denied' USING ERRCODE='42501';
  END IF;
  SELECT * INTO STRICT scan FROM public.file_security_scans
  WHERE id=p_scan_id AND company_id=public.workloop_company_id()
    AND branch_id=public.workloop_branch_id();
  IF NOT (
    (p_action='file_scan_clean' AND scan.status='clean' AND p_error_code='')
    OR (p_action='file_scan_infected' AND scan.status='infected' AND p_error_code='')
    OR (p_action='file_scan_retry_scheduled' AND scan.status='failed'
        AND scan.attempt_count<8 AND p_error_code=scan.last_error_code)
    OR (p_action='file_scan_terminal' AND scan.status='failed'
        AND scan.attempt_count=8 AND p_error_code=scan.last_error_code)
    OR (p_action='storage_manual_requeue' AND scan.status='failed'
        AND scan.attempt_count<8 AND scan.next_attempt_at<=statement_timestamp()
        AND p_error_code=scan.last_error_code)) THEN
    RAISE EXCEPTION 'file security audit denied' USING ERRCODE='42501';
  END IF;
  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(
    scan.company_id,scan.branch_id,'scheduled_job',NULL,'file_security_scan',NULL,
    p_action,scan.entity_type,scan.entity_id,ARRAY['scan_status']::text[],
    'File security scan state recorded',
    jsonb_build_object('scan_id',scan.id,'entity_type',scan.entity_type,
      'attempt_count',scan.attempt_count,'scanner_definition',scan.scanner_definition,
      'error_code',p_error_code))
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
""")
    op.execute(
        "ALTER FUNCTION public.append_file_security_audit(uuid,text,text) "
        "OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.append_file_security_audit(uuid,text,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.append_file_security_audit(uuid,text,text) "
        "TO workloop_file_scanner"
    )

    op.execute(r"""
CREATE FUNCTION public.requeue_file_security_scan(p_scan_id uuid)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  scan public.file_security_scans%ROWTYPE;
BEGIN
  IF session_user<>'workloop_file_scanner'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'scheduled_job'
    OR public.workloop_actor_key() IS DISTINCT FROM 'file_security_scan'
    OR public.workloop_company_id() IS NULL OR public.workloop_branch_id() IS NULL THEN
    RAISE EXCEPTION 'file security requeue denied' USING ERRCODE='42501';
  END IF;
  UPDATE public.file_security_scans
  SET next_attempt_at=statement_timestamp(),updated_at=statement_timestamp()
  WHERE id=p_scan_id AND company_id=public.workloop_company_id()
    AND branch_id=public.workloop_branch_id()
    AND status='failed' AND attempt_count BETWEEN 1 AND 7
  RETURNING * INTO scan;
  IF NOT FOUND THEN
    RETURN false;
  END IF;
  PERFORM public.append_file_security_audit(
    scan.id,'storage_manual_requeue',scan.last_error_code
  );
  RETURN true;
END
$function$
""")
    op.execute("ALTER FUNCTION public.requeue_file_security_scan(uuid) OWNER TO workloop_migration")
    op.execute("REVOKE ALL ON FUNCTION public.requeue_file_security_scan(uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.requeue_file_security_scan(uuid) TO workloop_file_scanner"
    )

    op.execute(r"""
CREATE FUNCTION public.append_storage_recovery_audit(
  p_company_id uuid, p_branch_id uuid, p_action text, p_event_id uuid,
  p_manifest_digest text DEFAULT ''
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  audit_id uuid;
BEGIN
  IF session_user<>'workloop_storage_reconciler'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'scheduled_job'
    OR public.workloop_actor_key() IS DISTINCT FROM 'storage_reconciliation'
    OR public.workloop_company_id() IS DISTINCT FROM p_company_id
    OR public.workloop_branch_id() IS DISTINCT FROM p_branch_id
    OR NOT EXISTS (
      SELECT 1 FROM public.branches
      WHERE id=p_branch_id AND company_id=p_company_id
    ) THEN
    RAISE EXCEPTION 'storage recovery audit denied' USING ERRCODE='42501';
  END IF;
  IF p_action NOT IN (
      'storage_backup_completed','storage_restore_verified','storage_credential_rotated'
    )
    OR (p_action IN ('storage_backup_completed','storage_restore_verified')
        AND p_manifest_digest !~ '^sha256:[0-9a-f]{64}$')
    OR (p_action='storage_credential_rotated' AND p_manifest_digest<>'') THEN
    RAISE EXCEPTION 'storage recovery audit denied' USING ERRCODE='42501';
  END IF;
  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(
    p_company_id,p_branch_id,'scheduled_job',NULL,'storage_reconciliation',NULL,
    p_action,'storage_recovery',p_event_id,ARRAY['recovery_state']::text[],
    'Storage recovery control recorded',
    jsonb_build_object('operation_id',p_event_id,'manifest_digest',p_manifest_digest))
  RETURNING id INTO audit_id;
  RETURN audit_id;
END
$function$
""")
    op.execute(
        "ALTER FUNCTION public.append_storage_recovery_audit(uuid,uuid,text,uuid,text) "
        "OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "public.append_storage_recovery_audit(uuid,uuid,text,uuid,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION "
        "public.append_storage_recovery_audit(uuid,uuid,text,uuid,text) "
        "TO workloop_storage_reconciler"
    )

    op.execute(r"""
CREATE FUNCTION public.file_security_scan_allows_download(
  p_scan_id uuid, p_entity_type text, p_entity_id uuid, p_object_key text,
  p_content_type text, p_size_bytes bigint, p_sha256 text, p_scanner_definition text
) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
  SELECT session_user='workloop_runtime'
    AND public.workloop_actor_kind()='human'
    AND public.workloop_actor_key() IS NULL
    AND public.workloop_app_user_id() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.file_security_scans AS scan
      WHERE scan.id=p_scan_id
        AND scan.company_id=public.workloop_company_id()
        AND scan.branch_id=public.workloop_branch_id()
        AND scan.entity_type=p_entity_type AND scan.entity_id=p_entity_id
        AND scan.object_key=p_object_key AND scan.content_type=p_content_type
        AND scan.size_bytes=p_size_bytes AND scan.sha256=p_sha256
        AND scan.scanner_definition=p_scanner_definition
        AND scan.status='clean' AND scan.valid_until>statement_timestamp()
    )
$function$
""")
    op.execute(
        "ALTER FUNCTION public.file_security_scan_allows_download"
        "(uuid,text,uuid,text,text,bigint,text,text) OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.file_security_scan_allows_download"
        "(uuid,text,uuid,text,text,bigint,text,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.file_security_scan_allows_download"
        "(uuid,text,uuid,text,text,bigint,text,text) TO workloop_runtime"
    )

    op.execute("ALTER TABLE public.file_security_scans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.file_security_scans FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.file_security_scans FROM PUBLIC")
    op.execute("REVOKE ALL ON TABLE public.file_security_scans FROM workloop_runtime")
    op.execute("REVOKE ALL ON TABLE public.file_security_scans FROM workloop_file_scanner")
    op.execute(
        "GRANT INSERT(company_id,branch_id,employee_id,created_by_app_user_id,entity_type,"
        "entity_id,object_key,content_type,size_bytes,sha256,scanner_definition) "
        "ON public.file_security_scans TO workloop_runtime"
    )
    op.execute(
        "GRANT SELECT(id,company_id,branch_id,entity_type,entity_id,status,scanner_definition,"
        "scanned_at,valid_until) ON public.file_security_scans TO workloop_runtime"
    )
    op.execute("GRANT SELECT ON public.file_security_scans TO workloop_file_scanner")
    op.execute(
        "GRANT UPDATE(status,scanner_name,result_signature,attempt_count,last_error_code,"
        "next_attempt_at,claimed_at,lease_expires_at,scanned_at,valid_until,updated_at) "
        "ON public.file_security_scans TO workloop_file_scanner"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO workloop_file_scanner")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.workloop_actor_kind(),public.workloop_actor_key(),"
        "public.workloop_company_id(),public.workloop_branch_id() TO workloop_file_scanner"
    )
    runtime = (
        "current_user='workloop_runtime' AND session_user='workloop_runtime' "
        "AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL "
        "AND public.workloop_app_user_id() IS NOT NULL "
        "AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()"
    )
    op.execute(
        "CREATE POLICY file_security_scans_runtime_select ON public.file_security_scans "
        f"FOR SELECT TO workloop_runtime USING ({runtime})"
    )
    op.execute(
        "CREATE POLICY file_security_scans_runtime_insert ON public.file_security_scans "
        f"FOR INSERT TO workloop_runtime WITH CHECK ({runtime} "
        "AND created_by_app_user_id=public.workloop_app_user_id() AND status='pending')"
    )
    op.execute(
        "CREATE POLICY file_security_scans_scanner_select ON public.file_security_scans "
        f"FOR SELECT TO workloop_file_scanner USING ({SCANNER_CONTEXT})"
    )
    op.execute(
        "CREATE POLICY file_security_scans_scanner_update ON public.file_security_scans "
        f"FOR UPDATE TO workloop_file_scanner USING ({SCANNER_CONTEXT}) "
        f"WITH CHECK ({SCANNER_CONTEXT})"
    )
    op.execute(
        "CREATE POLICY file_security_scans_migration_all ON public.file_security_scans "
        "FOR ALL TO workloop_migration USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.file_security_scan_allows_download"
        "(uuid,text,uuid,text,text,bigint,text,text) FROM workloop_runtime"
    )
    op.execute(
        "DROP FUNCTION public.file_security_scan_allows_download"
        "(uuid,text,uuid,text,text,bigint,text,text)"
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION "
        "public.append_storage_recovery_audit(uuid,uuid,text,uuid,text) "
        "FROM workloop_storage_reconciler"
    )
    op.execute("DROP FUNCTION public.append_storage_recovery_audit(uuid,uuid,text,uuid,text)")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.requeue_file_security_scan(uuid) "
        "FROM workloop_file_scanner"
    )
    op.execute("DROP FUNCTION public.requeue_file_security_scan(uuid)")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.append_file_security_audit(uuid,text,text) "
        "FROM workloop_file_scanner"
    )
    op.drop_constraint(
        "fk_expense_receipts_file_security_scan_scope", "expense_receipts", type_="foreignkey"
    )
    op.drop_column("expense_receipts", "file_security_scan_id")
    op.drop_constraint(
        "fk_leave_attachments_file_security_scan_scope", "leave_attachments", type_="foreignkey"
    )
    op.drop_column("leave_attachments", "file_security_scan_id")
    op.drop_table("file_security_scans")
    op.execute("DROP FUNCTION public.append_file_security_audit(uuid,text,text)")
    op.execute("DROP FUNCTION public._file_security_scan_transition_phase11b()")
    op.execute("REVOKE EXECUTE ON FUNCTION public.workloop_actor_key() FROM workloop_file_scanner")
    _replace_actor_key_reader(include_scanner=False)
