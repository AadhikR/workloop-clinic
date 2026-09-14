"""Add leave attachment metadata and protected audit actions.

Revision ID: a83d5e7c1b29
Revises: 4d8a7c2e9f31
Created: 2026-09-14 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a83d5e7c1b29"
down_revision: str | Sequence[str] | None = "4d8a7c2e9f31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
PRIOR_SIGNATURE = "public._append_audit_event_phase8d_prior(text,text,uuid,text[],text,jsonb)"

HUMAN_CONTEXT = """
current_user='workloop_runtime' AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
""".strip()


def _create_table() -> None:
    metadata_complete = (
        "file_name IS NOT NULL AND content_type IS NOT NULL AND size_bytes IS NOT NULL "
        "AND sha256 IS NOT NULL AND object_key IS NOT NULL"
    )
    metadata_empty = (
        "file_name IS NULL AND content_type IS NULL AND size_bytes IS NULL "
        "AND sha256 IS NULL AND object_key IS NULL"
    )
    op.create_table(
        "leave_attachments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("leave_request_id", sa.UUID(), nullable=True),
        sa.Column("created_by_app_user_id", sa.UUID(), nullable=False),
        sa.Column("submission_token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
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
            "octet_length(submission_token_digest)=32",
            name="submission_token_digest",
        ),
        sa.CheckConstraint(
            "status IN ('pending','uploading','staged','attached','cleanup_pending','removed')",
            name="status",
        ),
        sa.CheckConstraint(
            f"(({metadata_empty}) OR ({metadata_complete}))",
            name="metadata_completeness",
        ),
        sa.CheckConstraint(
            "file_name IS NULL OR octet_length(file_name) BETWEEN 1 AND 180",
            name="file_name",
        ),
        sa.CheckConstraint(
            "content_type IS NULL OR content_type IN ('application/pdf','image/png','image/jpeg')",
            name="content_type",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes BETWEEN 1 AND 10485760",
            name="size_bytes",
        ),
        sa.CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'",
            name="sha256",
        ),
        sa.CheckConstraint(
            "object_key IS NULL OR (octet_length(object_key) BETWEEN 1 AND 1024 "
            "AND object_key !~ '[[:cntrl:]\\\\]' AND left(object_key,1)<>'/' "
            "AND object_key NOT LIKE '%//%' AND ('/'||object_key||'/') NOT LIKE '%/./%' "
            "AND ('/'||object_key||'/') NOT LIKE '%/../%')",
            name="object_key",
        ),
        sa.CheckConstraint(
            f"(status='pending' AND {metadata_empty} AND token_consumed_at IS NULL "
            "AND expires_at=created_at+interval '15 minutes' AND uploaded_at IS NULL "
            "AND attached_at IS NULL AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            f"(status='uploading' AND {metadata_empty} AND token_consumed_at IS NOT NULL "
            "AND expires_at IS NOT NULL AND uploaded_at IS NULL AND attached_at IS NULL "
            "AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            f"(status='staged' AND {metadata_complete} AND token_consumed_at IS NOT NULL "
            "AND uploaded_at IS NOT NULL AND expires_at=uploaded_at+interval '24 hours' "
            "AND leave_request_id IS NULL AND attached_at IS NULL "
            "AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            f"(status='attached' AND {metadata_complete} AND token_consumed_at IS NOT NULL "
            "AND uploaded_at IS NOT NULL AND expires_at IS NULL AND leave_request_id IS NOT NULL "
            "AND attached_at IS NOT NULL AND cleanup_requested_at IS NULL AND removed_at IS NULL) "
            "OR "
            f"(status='cleanup_pending' AND {metadata_complete} "
            "AND cleanup_requested_at IS NOT NULL AND removed_at IS NULL) OR "
            f"(status='removed' AND {metadata_complete} AND removed_at IS NOT NULL)",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "updated_at>=created_at AND (expires_at IS NULL OR expires_at>=created_at) "
            "AND (token_consumed_at IS NULL OR token_consumed_at>=created_at) "
            "AND (uploaded_at IS NULL OR uploaded_at>=created_at) "
            "AND (attached_at IS NULL OR attached_at>=created_at) "
            "AND (cleanup_requested_at IS NULL OR cleanup_requested_at>=created_at) "
            "AND (removed_at IS NULL OR removed_at>=created_at)",
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
        sa.ForeignKeyConstraint(
            ["leave_request_id", "company_id", "branch_id"],
            ["leave_requests.id", "leave_requests.company_id", "leave_requests.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_leave_attachments"),
        sa.UniqueConstraint("leave_request_id", name="uq_leave_attachments_leave_request_id"),
        sa.UniqueConstraint(
            "submission_token_digest", name="uq_leave_attachments_submission_token_digest"
        ),
    )
    op.create_index(
        "ix_leave_attachments_scope",
        "leave_attachments",
        ["company_id", "branch_id", "employee_id"],
    )
    op.execute("ALTER TABLE public.leave_attachments OWNER TO workloop_migration")


def _rls_and_grants() -> None:
    op.execute("ALTER TABLE public.leave_attachments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.leave_attachments FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.leave_attachments FROM PUBLIC")
    op.execute("REVOKE ALL ON TABLE public.leave_attachments FROM workloop_runtime")
    op.execute("REVOKE ALL ON TABLE public.leave_attachments FROM workloop_storage_reconciler")
    op.execute("GRANT SELECT ON public.leave_attachments TO workloop_runtime")
    op.execute(
        "GRANT INSERT(id,company_id,branch_id,employee_id,leave_request_id,"
        "created_by_app_user_id,submission_token_digest,expires_at) "
        "ON public.leave_attachments TO workloop_runtime"
    )
    op.execute(
        "GRANT UPDATE(leave_request_id,file_name,content_type,size_bytes,sha256,object_key,status,"
        "expires_at,token_consumed_at,uploaded_at,attached_at,cleanup_requested_at,removed_at,"
        "updated_at) ON public.leave_attachments TO workloop_runtime"
    )
    visible = f"""{HUMAN_CONTEXT}
AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
AND (
  employee_id=public.workloop_employee_id()
  OR (public.workloop_role()='admin' AND public.workloop_employee_id() IS NULL)
  OR (leave_request_id IS NOT NULL AND public.workloop_role() IN ('manager','employee')
      AND EXISTS (
        SELECT 1 FROM public.leave_requests AS request
        WHERE request.id=leave_attachments.leave_request_id
          AND request.company_id=leave_attachments.company_id
          AND request.branch_id=leave_attachments.branch_id
          AND request.status IN ('Pending','ManagerApproved')
      ))
)"""
    mutable = f"""{HUMAN_CONTEXT}
AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
AND ((employee_id=public.workloop_employee_id()
      AND created_by_app_user_id=public.workloop_app_user_id())
     OR (public.workloop_role()='admin' AND public.workloop_employee_id() IS NULL))"""
    op.execute(
        "CREATE POLICY leave_attachments_migration_all ON public.leave_attachments "
        "FOR ALL TO workloop_migration USING (true) WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY leave_attachments_runtime_select ON public.leave_attachments "
        f"FOR SELECT TO workloop_runtime USING ({visible})"
    )
    op.execute(
        "CREATE POLICY leave_attachments_runtime_insert ON public.leave_attachments "
        f"FOR INSERT TO workloop_runtime WITH CHECK ({mutable} AND status='pending')"
    )
    op.execute(
        "CREATE POLICY leave_attachments_runtime_update ON public.leave_attachments "
        f"FOR UPDATE TO workloop_runtime USING ({mutable}) WITH CHECK ({mutable})"
    )


def _wrap_audit() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase8d_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_SIGNATURE} FROM workloop_runtime")
    op.execute(r"""
CREATE FUNCTION public.append_audit_event(
  p_action text,p_entity_type text,p_entity_id uuid,p_changed_fields text[],
  p_reason text,p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE event_id uuid;
BEGIN
  IF p_action NOT IN ('leave_attachment_uploaded','leave_attachment_cleanup_requested') THEN
    RETURN public._append_audit_event_phase8d_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF session_user<>'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL OR public.workloop_business_date() IS NULL
    OR public.workloop_app_user_id() IS NULL OR public.workloop_company_id() IS NULL
    OR public.workloop_branch_id() IS NULL OR p_entity_type<>'leave_attachment'
    OR jsonb_typeof(p_metadata) IS DISTINCT FROM 'object' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action='leave_attachment_uploaded' THEN
    IF p_changed_fields IS DISTINCT FROM
      ARRAY['file_name','content_type','size_bytes','sha256','status']::text[]
      OR p_reason<>'Leave attachment uploaded'
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>1
      OR NOT (p_metadata ? 'storage_operation_id')
      OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'storage_operation_id','uuid')
      OR NOT EXISTS (
        SELECT 1 FROM public.leave_attachments AS attachment
        JOIN public.storage_operations AS operation
          ON operation.id=(p_metadata->>'storage_operation_id')::uuid
         AND operation.entity_type='leave_attachment' AND operation.entity_id=attachment.id
         AND operation.company_id=attachment.company_id
         AND operation.branch_id=attachment.branch_id
        WHERE attachment.id=p_entity_id
          AND attachment.company_id=public.workloop_company_id()
          AND attachment.branch_id=public.workloop_branch_id()
          AND attachment.created_by_app_user_id=public.workloop_app_user_id()
          AND attachment.status IN ('staged','attached')
          AND operation.operation='upload' AND operation.status='succeeded') THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    IF p_changed_fields IS DISTINCT FROM ARRAY['status']::text[]
      OR p_reason<>'Leave attachment cleanup requested'
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>2
      OR p_metadata->>'trigger' NOT IN
        ('failed_submission','request_cancelled','staged_expired','missing_object')
      OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'storage_operation_id','uuid')
      OR NOT EXISTS (
        SELECT 1 FROM public.leave_attachments AS attachment
        JOIN public.storage_operations AS operation
          ON operation.id=(p_metadata->>'storage_operation_id')::uuid
         AND operation.entity_type='leave_attachment' AND operation.entity_id=attachment.id
         AND operation.company_id=attachment.company_id
         AND operation.branch_id=attachment.branch_id
        WHERE attachment.id=p_entity_id
          AND attachment.company_id=public.workloop_company_id()
          AND attachment.branch_id=public.workloop_branch_id()
          AND attachment.status='cleanup_pending'
          AND operation.operation='delete') THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END IF;
  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
    public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,
    p_changed_fields,p_reason,p_metadata)
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
""")
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def upgrade() -> None:
    _create_table()
    _rls_and_grants()
    _wrap_audit()


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase8d_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.drop_table("leave_attachments")
