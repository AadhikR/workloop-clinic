-- Add rejection_reason column to salary_advances so admins can record why they rejected/cancelled an advance.
ALTER TABLE salary_advances ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
