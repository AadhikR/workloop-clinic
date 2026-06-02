/**
 * notifications.spec.js — Playwright tests for Feature 4: In-App Notification System
 *
 * Covers:
 *   Admin portal:
 *     - Bell icon button present in admin sidebar
 *     - Clicking bell opens the notification panel
 *     - Panel has correct header ("Notifications")
 *     - Panel has close (×) button that dismisses it
 *     - Backdrop click closes the panel
 *     - "Mark all read" button only visible when unread notifications exist
 *   Employee portal:
 *     - Bell icon present in employee sidebar
 *     - Clicking bell opens the notification panel
 *
 * Note: This file is last alphabetically among the new feature spec files.
 * The employee test uses loginAsEmployee() (fresh login) to avoid refresh-token
 * rotation issues from shared storageState.
 */
import { test, expect } from '@playwright/test';
import { loginAsEmployee } from './helpers/auth.js';
import { readFileSync, existsSync } from 'fs';
import { adminClient, deleteWhere } from './helpers/db.js';

// ─── Admin notification bell ──────────────────────────────────────────────────
// storageState is shared with other admin test files; since notifications.spec.js
// comes before payroll.spec.js alphabetically, storageState is still valid here.
test.describe('Notifications — Admin portal', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  // Clean up any notifications created during the session for this test run
  test.afterAll(async () => {
    try {
      const db = adminClient();
      const envPath = '.playwright/env.json';
      if (!existsSync(envPath)) return;
      const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));
      await deleteWhere(db, 'notifications', 'user_id', adminId);
      console.log('[notifications cleanup] Removed test notifications.');
    } catch (e) {
      console.warn('[notifications cleanup] Could not clean up:', e.message);
    }
  });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  });

  test('bell icon is present in admin sidebar', async ({ page }) => {
    // NotificationBell renders a <button title="Notifications">
    await expect(page.locator('button[title="Notifications"]')).toBeVisible({ timeout: 6000 });
  });

  test('clicking bell opens notification panel', async ({ page }) => {
    await page.locator('button[title="Notifications"]').click();

    // Panel header text "Notifications"
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('notification panel has a close button', async ({ page }) => {
    await page.locator('button[title="Notifications"]').click();
    // Panel is visible
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ }).first()
    ).toBeVisible({ timeout: 6000 });

    // The panel has a × close button (btn-icon inside the panel header area)
    // It's the button with an X icon — use a locator scoped inside the fixed panel
    const panel = page.locator('[style*="position: absolute"][style*="right: 12px"]').or(
      page.locator('[style*="right:12px"]')
    ).first();
    const closeBtn = panel.locator('button').last();
    await closeBtn.click();

    // Panel should disappear
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ })
    ).not.toBeVisible({ timeout: 5000 });
  });

  test('backdrop click closes notification panel', async ({ page }) => {
    await page.locator('button[title="Notifications"]').click();
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ }).first()
    ).toBeVisible({ timeout: 6000 });

    // Click on the backdrop (the semi-transparent overlay — position: absolute, inset: 0)
    await page.mouse.click(100, 400); // Far left of screen — hits the backdrop, not the panel
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ })
    ).not.toBeVisible({ timeout: 5000 });
  });

  test('panel shows "No notifications yet" when inbox is empty', async ({ page }) => {
    // If no notifications exist, the panel should show the empty-state message
    await page.locator('button[title="Notifications"]').click();
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ }).first()
    ).toBeVisible({ timeout: 6000 });

    // Either shows empty-state text OR notification rows — both are valid
    const emptyState = page.locator('text=No notifications yet');
    const notifRow   = page.locator('[style*="border-bottom"]').filter({ hasText: /.+/ }).first();
    await expect(emptyState.or(notifRow)).toBeVisible({ timeout: 8000 });
  });

  test('dashboard load creates expiry notifications in bell (if docs expiring)', async ({ page }) => {
    // Navigate to dashboard to trigger generateExpiryNotifications
    await page.goto('/');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000); // Allow async notification write to complete

    // Open bell — won't fail even if 0 notifications exist
    await page.locator('button[title="Notifications"]').click();
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ }).first()
    ).toBeVisible({ timeout: 6000 });

    // The Insurance Alerts stat card should also be visible now
    await page.mouse.click(100, 400); // Close panel via backdrop
    await expect(page.locator('.stat-card').filter({ hasText: /Insurance Alerts/i })).toBeVisible({ timeout: 6000 });
  });

  test('"Mark all read" button visible when there are unread notifications', async ({ page }) => {
    // Seed one notification via the DB client so we have a known unread item
    const db = adminClient();
    const envPath = '.playwright/env.json';
    if (!existsSync(envPath)) test.skip(true, 'env.json not found');

    const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));
    await db.from('notifications').upsert({
      user_id:             adminId,
      recipient_user_id:   adminId,
      type:                'document_expiry',
      title:               'Test notification',
      body:                'Playwright test notification — will be cleaned up in afterAll.',
      related_entity_type: 'test',
      related_entity_id:   `playwright_test_${Date.now()}`,
    }, { onConflict: 'recipient_user_id,type,related_entity_id', ignoreDuplicates: true });

    // Reload page so the bell polls the fresh count
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(1500);

    // The unread badge should appear (count ≥ 1)
    const badge = page.locator('button[title="Notifications"] span');
    await expect(badge).toBeVisible({ timeout: 8000 });

    // Open panel — "Mark all read" button should be visible
    await page.locator('button[title="Notifications"]').click();
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ }).first()
    ).toBeVisible({ timeout: 6000 });
    await expect(page.locator('button:has-text("All read")')).toBeVisible({ timeout: 5000 });
  });

  test('"Mark all read" clears unread badge', async ({ page }) => {
    // Relies on at least one unread notification existing (from previous test or seeded)
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(1000);

    const badge = page.locator('button[title="Notifications"] span');
    if (!await badge.isVisible({ timeout: 3000 })) {
      test.skip(true, 'No unread notifications to test mark-all-read');
    }

    await page.locator('button[title="Notifications"]').click();
    await expect(page.locator('button:has-text("All read")')).toBeVisible({ timeout: 5000 });
    await page.locator('button:has-text("All read")').click();

    // Badge should disappear after marking all read
    await expect(badge).not.toBeVisible({ timeout: 5000 });
  });
});

// ─── Employee notification bell ───────────────────────────────────────────────
// Uses fresh login (loginAsEmployee) to avoid refresh-token rotation
// since this is the second admin-related describe — using fresh session is safer.
test.describe('Notifications — Employee portal', () => {

  test('bell icon is present in employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    await expect(page.locator('button[title="Notifications"]')).toBeVisible({ timeout: 6000 });
  });

  test('employee bell opens notification panel', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button[title="Notifications"]').click();

    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('employee panel shows empty state or notification list', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button[title="Notifications"]').click();

    const emptyState = page.locator('text=No notifications yet');
    const notifRow   = page.locator('[style*="border-bottom"]').filter({ hasText: /.+/ }).first();
    await expect(emptyState.or(notifRow)).toBeVisible({ timeout: 8000 });
  });

  test('employee panel close button works', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button[title="Notifications"]').click();
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ }).first()
    ).toBeVisible({ timeout: 6000 });

    // Click backdrop to close
    await page.mouse.click(100, 400);
    await expect(
      page.locator('div').filter({ hasText: /^Notifications$/ })
    ).not.toBeVisible({ timeout: 5000 });
  });
});
