-- ============================================================
-- Migration 004: In-App Notification System
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

CREATE TABLE IF NOT EXISTS notifications (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE, -- admin who created the notification
  recipient_user_id   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE, -- who receives it (admin or employee)
  type                TEXT NOT NULL,    -- 'document_expiry','wps_deadline','insurance_expiry','policy_renewal',
                                        -- 'leave_approved','leave_rejected','leave_submitted','payslip_available'
  title               TEXT NOT NULL DEFAULT '',
  body                TEXT NOT NULL DEFAULT '',
  related_entity_type TEXT NOT NULL DEFAULT '',  -- 'employee', 'leave_request', 'payroll_run', etc.
  related_entity_id   TEXT NOT NULL DEFAULT '',  -- deduplication key (see below)
  read_at             TIMESTAMPTZ,               -- NULL = unread
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Deduplication: one notification per recipient per type per entity.
  -- Expiry alerts use threshold suffixes (e.g. uuid_visa_30d) so 60d and 30d
  -- alerts are separate entries.
  UNIQUE (recipient_user_id, type, related_entity_id)
);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE notifications TO authenticated;

-- Recipients can read their own notifications
CREATE POLICY "notifications_select"
  ON notifications FOR SELECT
  USING (recipient_user_id = auth.uid());

-- Admins (and employees with portal) can insert notifications they own
CREATE POLICY "notifications_insert"
  ON notifications FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- Recipients can mark their own notifications as read
CREATE POLICY "notifications_update"
  ON notifications FOR UPDATE
  USING  (recipient_user_id = auth.uid())
  WITH CHECK (recipient_user_id = auth.uid());

-- Admins can delete notifications they created
CREATE POLICY "notifications_delete"
  ON notifications FOR DELETE
  USING (user_id = auth.uid());

-- ============================================================
-- After running this migration also run:
--   GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
-- ============================================================
