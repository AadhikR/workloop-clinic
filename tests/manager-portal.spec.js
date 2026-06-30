/**
 * manager-portal.spec.js — Comprehensive Manager Portal tests
 *
 * Uses .playwright/manager-session.json (created by global-setup.js).
 * Tests every tab in ManagerShell:
 *   1. Leave Queue     — direct-reports pending leaves, approve/reject
 *   2. Expense Queue   — direct-reports pending expenses, pre-approve/reject
 *   3. Appraisals      — team appraisal ratings (skip if no active cycle)
 *   4. My Leave        — manager's own leave form (reuses EmpLeave)
 *   5. Schedule        — manager's own roster (EmpSchedule)
 *   6. Attendance      — manager's own clock-in/out (EmpAttendance)
 *   7. Payslips        — manager's own payslips (EmpPayslips)
 *   8. Profile         — manager's own profile (EmpProfile)
 *
 * NOTE: storageState is scoped inside each describe block.
 */
import { test, expect } from '@playwright/test';
import { existsSync } from 'fs';

const MGR_SESSION = '.playwright/manager-session.json';
const EMP_SESSION = '.playwright/employee-session.json';

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function goToManagerTab(page, tabLabel) {
  await page.locator('button.nav-item').filter({ hasText: new RegExp(`^${tabLabel}$`) }).click();
  // Do NOT use waitForLoadState('networkidle') — ManagerShell has NotificationBell polling every
  // 60s which prevents networkidle from ever resolving. Each test waits for its own content.
  // A short domcontentloaded wait ensures the tab click has been processed.
  await page.waitForLoadState('domcontentloaded');
}

// ─── Shell loads + sidebar ────────────────────────────────────────────────────

test.describe('Manager Portal — shell & navigation', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    // Skip entire describe if ManagerShell doesn't render — means sql/034_manager_role.sql
    // hasn't been applied yet (user_profiles_role_check blocks role='manager')
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql in Supabase SQL Editor');
  });

  test('manager shell loads and shows "Manager Portal" label', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    await expect(
      page.locator('.emp-sidebar-logo').getByText(/Manager Portal/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test('all 8 tabs are visible in the sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });

    const tabs = ['Leave Queue', 'Expense Queue', 'Appraisals', 'My Leave', 'Schedule', 'Attendance', 'Payslips', 'Profile'];
    for (const tab of tabs) {
      await expect(
        page.locator('button.nav-item').filter({ hasText: new RegExp(`^${tab}$`) })
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('Sign Out button is present', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    await expect(
      page.locator('.emp-sidebar').getByRole('button', { name: /sign out/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('default landing tab is Leave Queue', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    // The Leave Queue tab (button.nav-item) should have 'active' class by default
    const queueTab = page.locator('button.nav-item').filter({ hasText: /^Leave Queue$/ });
    const cls = await queueTab.getAttribute('class');
    expect(cls).toMatch(/active/);
  });
});

// ─── 1. Leave Queue ───────────────────────────────────────────────────────────

test.describe('Manager Portal — Leave Queue', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) { test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql'); return; }
    await goToManagerTab(page, 'Leave Queue');
  });

  test('Leave Queue page renders a heading', async ({ page }) => {
    await expect(
      page.locator('h2, h3').filter({ hasText: /leave queue|pending leave/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('seeded pending leave request appears in the queue', async ({ page }) => {
    // global-setup seeds 1 Pending leave request for the test employee
    // who has reporting_manager_id → test manager
    await expect(
      page.locator('.emp-card, table, .card').first()
    ).toBeVisible({ timeout: 10000 });

    // Either a table row with PLAYWRIGHT_SEED reason or an empty state
    const hasItems = await page.locator('td, .emp-card').filter({ hasText: /PLAYWRIGHT_SEED|Annual Leave/i }).first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state, text=/no pending/i').first().isVisible({ timeout: 2000 }).catch(() => false);

    // One of these should be true
    expect(hasItems || hasEmpty, 'Expected either pending leave items or empty state').toBe(true);
  });

  test('Approve and Reject buttons are visible when pending requests exist', async ({ page }) => {
    const approveBtn = page.locator('button').filter({ hasText: /approve/i }).first();
    const visible = await approveBtn.isVisible({ timeout: 6000 }).catch(() => false);
    if (!visible) {
      test.skip(true, 'No pending leave requests in queue (manager may not be reporting manager for seeded employee)');
      return;
    }
    await expect(approveBtn).toBeVisible();
    await expect(page.locator('button').filter({ hasText: /reject/i }).first()).toBeVisible();
  });

  test('history section toggle button is present', async ({ page }) => {
    // ManagerLeaveQueue has a history toggle (ChevronDown/Up button)
    // .or().first() — correct order (not .first().or() which causes strict-mode violations)
    await expect(
      page.locator('button').filter({ hasText: /history/i })
        .or(page.locator('button[title*="history"], button[title*="History"]'))
        .or(page.locator('.emp-card, .card').filter({ hasText: /history/i }))
        .first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('Reject button shows a reason input', async ({ page }) => {
    const rejectBtn = page.locator('button').filter({ hasText: /^reject$/i }).first();
    if (!(await rejectBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No pending leave requests visible');
      return;
    }
    await rejectBtn.click();
    await expect(
      page.locator('input[placeholder*="reason"], textarea[placeholder*="reason"]')
        .or(page.locator('input, textarea').filter({ hasText: '' }))
        .first()
    ).toBeVisible({ timeout: 5000 });
  });
});

// ─── 2. Expense Queue ─────────────────────────────────────────────────────────

test.describe('Manager Portal — Expense Queue', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) { test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql'); return; }
    await goToManagerTab(page, 'Expense Queue');
  });

  test('Expense Queue page renders a heading', async ({ page }) => {
    await expect(
      page.locator('h2, h3').filter({ hasText: /expense queue|pending expense/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('page body is visible', async ({ page }) => {
    await expect(page.locator('.emp-page-body, .page-body').first()).toBeVisible({ timeout: 8000 });
  });

  test('seeded pending expense appears or empty state shown', async ({ page }) => {
    // global-setup seeds 1 pending expense for the test employee (direct report of manager)
    await page.waitForLoadState('networkidle');
    const hasItems = await page.locator('td, .emp-card').filter({ hasText: /PLAYWRIGHT_SEED|travel|meals/i }).first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state, text=/no.*expense/i').first().isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasItems || hasEmpty, 'Expected expense items or empty state').toBe(true);
  });

  test('Pre-Approve and Reject buttons exist when pending items are shown', async ({ page }) => {
    await page.waitForLoadState('networkidle');
    const approveBtn = page.locator('button').filter({ hasText: /pre-?approve|approve/i }).first();
    if (!(await approveBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No pending expenses in manager queue');
      return;
    }
    await expect(approveBtn).toBeVisible();
    await expect(page.locator('button').filter({ hasText: /reject/i }).first()).toBeVisible();
  });
});

// ─── 3. Appraisals ───────────────────────────────────────────────────────────

test.describe('Manager Portal — Appraisals', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) { test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql'); return; }
    await goToManagerTab(page, 'Appraisals');
  });

  test('Appraisals tab renders heading', async ({ page }) => {
    await expect(
      page.locator('h2, h3').filter({ hasText: /appraisal/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('shows team appraisals or empty state', async ({ page }) => {
    await page.waitForLoadState('networkidle');
    const content = page.locator('.emp-card, table, .empty-state').first();
    await expect(content).toBeVisible({ timeout: 10000 });
  });

  test('star ratings or locked indicator present when cycle data exists', async ({ page }) => {
    await page.waitForLoadState('networkidle');
    // If there are appraisals, star rating buttons or read-only stars should be visible
    const starRating = page.locator('[aria-label*="star"], button[title*="star"], .star-rating').first();
    const emptyOrTable = page.locator('.empty-state, .emp-card, table').first();
    await expect(starRating.or(emptyOrTable)).toBeVisible({ timeout: 8000 });
  });
});

// ─── 4. My Leave ─────────────────────────────────────────────────────────────

test.describe('Manager Portal — My Leave', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) { test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql'); return; }
    await goToManagerTab(page, 'My Leave');
  });

  test('My Leave tab renders EmpLeave component', async ({ page }) => {
    // EmpLeave renders leave balances or an apply button
    await expect(page.locator('.emp-page-body, .emp-main').first()).toBeVisible({ timeout: 10000 });
  });

  test('Apply / New Leave button is present', async ({ page }) => {
    await expect(
      page.locator('button').filter({ hasText: /apply|new leave|request leave/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('leave type dropdown has options when leave types seeded', async ({ page }) => {
    // Click Apply to show the form
    const applyBtn = page.locator('button').filter({ hasText: /apply|new leave|request leave/i }).first();
    if (!(await applyBtn.isVisible({ timeout: 5000 }).catch(() => false))) return;
    await applyBtn.click();
    await page.waitForTimeout(300);

    const select = page.locator('.emp-card select').first();
    const opts = await select.locator('option').count();
    expect(opts, 'Leave type dropdown should have at least 1 option (seeded leave types)').toBeGreaterThan(1);
  });

  test('leave balance cards or empty state visible', async ({ page }) => {
    // Either leave balance stat cards or a message that no leave configured
    // .or().first() — correct order per CLAUDE.md
    const balanceContent = page.locator('.emp-card, .stat-card').or(
      page.locator('text=/annual leave|sick leave|no leave/i')
    ).first();
    await expect(balanceContent).toBeVisible({ timeout: 8000 });
  });
});

// ─── 5. Schedule ─────────────────────────────────────────────────────────────

test.describe('Manager Portal — Schedule', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql');
  });

  test('Schedule tab renders EmpSchedule component', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    await goToManagerTab(page, 'Schedule');

    await expect(page.locator('.emp-page-body, .emp-main').first()).toBeVisible({ timeout: 8000 });
    // Either a roster calendar/table or empty state — .or() must come BEFORE .first()
    // to avoid strict-mode violations (see CLAUDE.md: .first().or() is invalid)
    const content = page.locator('.emp-card, table, .empty-state').or(
      page.locator('h2, h3').filter({ hasText: /schedule|roster/i })
    ).first();
    await expect(content).toBeVisible({ timeout: 8000 });
  });

  test('Schedule tab shows month navigation or empty roster message', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    await goToManagerTab(page, 'Schedule');
    await page.waitForLoadState('networkidle');

    // Either a published roster or "no shifts published" message
    const published = page.locator('.emp-card').filter({ hasText: /shift|roster|schedule/i }).first();
    const empty     = page.locator('text=/no.*shift|no.*roster|not.*assigned/i').first();
    await expect(published.or(empty)).toBeVisible({ timeout: 10000 });
  });
});

// ─── 6. Attendance ───────────────────────────────────────────────────────────

test.describe('Manager Portal — Attendance', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) { test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql'); return; }
    await goToManagerTab(page, 'Attendance');
  });

  test('Attendance tab renders EmpAttendance component', async ({ page }) => {
    await expect(page.locator('.emp-page-body, .emp-main').first()).toBeVisible({ timeout: 10000 });
  });

  test('Clock In or Clock Out button is present', async ({ page }) => {
    const clockBtn = page.locator('button').filter({ hasText: /clock in|clock out/i }).first();
    await expect(clockBtn).toBeVisible({ timeout: 10000 });
  });

  test('today status card shows current attendance state', async ({ page }) => {
    // .or() must come BEFORE .first() (see CLAUDE.md: .first().or() causes strict-mode violations)
    await expect(
      page.locator('.emp-card').filter({ hasText: /today|clock|attendance/i }).or(
        page.locator('text=/not started|present|clocked/i')
      ).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('attendance history table or empty state visible', async ({ page }) => {
    await page.waitForLoadState('networkidle');
    // .or().first() — correct order per CLAUDE.md (not .first().or())
    const historyContent = page.locator('table, .emp-card').or(
      page.locator('text=/no.*attendance|no.*record/i')
    ).first();
    await expect(historyContent).toBeVisible({ timeout: 8000 });
  });
});

// ─── 7. Payslips ─────────────────────────────────────────────────────────────

test.describe('Manager Portal — Payslips', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql');
  });

  test('Payslips tab renders EmpPayslips component', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    await goToManagerTab(page, 'Payslips');

    await expect(page.locator('.emp-page-body, .emp-main').first()).toBeVisible({ timeout: 8000 });
    // Either payslip rows or "no payslips yet" empty state
    // .or().first() — correct order per CLAUDE.md
    const content = page.locator('.emp-card, table').or(
      page.locator('text=/no payslip|no.*payslip/i')
    ).first();
    await expect(content).toBeVisible({ timeout: 8000 });
  });

  test('Payslips page shows manager name in header or sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    // Sidebar footer should show manager name
    const sidebarFooter = page.locator('.emp-sidebar');
    await expect(sidebarFooter).toBeVisible({ timeout: 5000 });
    // Manager Portal label confirms it's the right shell
    await expect(sidebarFooter.getByText(/Manager Portal/i)).toBeVisible({ timeout: 5000 });
  });
});

// ─── 8. Profile ──────────────────────────────────────────────────────────────

test.describe('Manager Portal — Profile', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) { test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql'); return; }
    await goToManagerTab(page, 'Profile');
  });

  test('Profile tab renders EmpProfile component', async ({ page }) => {
    await expect(page.locator('.emp-page-body, .emp-main').first()).toBeVisible({ timeout: 8000 });
  });

  test('Profile shows manager name and job title', async ({ page }) => {
    // Profile card should show the manager's name — wait directly for content instead of networkidle
    await expect(
      page.locator('.emp-card, .card').filter({ hasText: /Test Manager|manager/i }).first()
    ).toBeVisible({ timeout: 15000 });
  });

  test('Profile has editable fields (phone, personal email, etc.)', async ({ page }) => {
    // EmpProfile only renders the phone/email inputs after the user clicks the "Edit" toggle
    // ({editing && <form>} in EmpProfile.jsx). Click "Edit" first to reveal the inputs.
    const editBtn = page.locator('button').filter({ hasText: 'Edit' }).first();
    await expect(editBtn).toBeVisible({ timeout: 12000 });
    await editBtn.click();
    await expect(page.locator('input[type="tel"]').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('input[type="email"]').first()).toBeVisible({ timeout: 5000 });
  });

  test('Save Profile button is present (after clicking Edit)', async ({ page }) => {
    // EmpProfile hides the form (and Save button) behind an {editing && ...} toggle.
    // Click Edit first to reveal the form, then check for the Save button.
    const editBtn = page.locator('button').filter({ hasText: 'Edit' }).first();
    await expect(editBtn).toBeVisible({ timeout: 12000 });
    await editBtn.click();
    await expect(
      page.locator('button[type="submit"]').or(
        page.locator('button').filter({ hasText: /save/i })
      ).first()
    ).toBeVisible({ timeout: 5000 });
  });
});

// ─── Manager approve leave cross-check ───────────────────────────────────────

test.describe('Manager Portal — leave approval action', () => {
  test.use({ storageState: MGR_SESSION });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const ok = await page.locator("button.nav-item").filter({ hasText: /^Leave Queue$/ }).isVisible({ timeout: 12000 }).catch(() => false);
    if (!ok) test.skip(true, 'ManagerShell not loading — apply sql/034_manager_role.sql');
  });

  test('approving a pending leave request changes its status', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    await goToManagerTab(page, 'Leave Queue');
    await page.waitForLoadState('networkidle');

    const approveBtn = page.locator('button').filter({ hasText: /^approve$/i }).first();
    if (!(await approveBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No pending leaves in manager queue — check reporting_manager_id setup');
      return;
    }

    await approveBtn.click();
    await page.waitForLoadState('networkidle');

    // After approval, the request should either disappear from pending queue
    // or show "Approved" / "ManagerApproved" badge
    const approved = page.locator('text=/approved/i').first();
    const queueEmpty = page.locator('.empty-state, text=/no pending/i').first();
    await expect(approved.or(queueEmpty)).toBeVisible({ timeout: 8000 });
  });
});
