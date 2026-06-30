"""
Generate the Workloop Clinic HRMS Feature List PDF.
Run: python generate_feature_list.py
Output: Workloop_Clinic_HRMS_Feature_List.pdf (in the same directory)
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ── Colour palette ─────────────────────────────────────────────────────────────
NAVY       = colors.HexColor('#08122e')
BLUE       = colors.HexColor('#2563EB')
CYAN       = colors.HexColor('#06B6D4')
LIGHT_BLUE = colors.HexColor('#EFF6FF')
AMBER      = colors.HexColor('#FEF3C7')
GREEN      = colors.HexColor('#DCFCE7')
PURPLE     = colors.HexColor('#EDE9FE')
GRAY_BG    = colors.HexColor('#F1F5F9')
GRAY_TEXT  = colors.HexColor('#475569')
GRAY_LIGHT = colors.HexColor('#E2E8F0')
WHITE      = colors.white
BLACK      = colors.HexColor('#1E293B')

W, H = A4
MARGIN = 18 * mm
CONTENT_W = W - 2 * MARGIN   # 174 mm

# ── Styles ─────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def s(name, **kw):
    return ParagraphStyle(name, parent=base['Normal'], **kw)

styles = {
    'doc_title':    s('doc_title',  fontSize=22, textColor=WHITE, fontName='Helvetica-Bold',
                      alignment=TA_CENTER, spaceAfter=2),
    'doc_sub':      s('doc_sub',    fontSize=11, textColor=colors.HexColor('#BFDBFE'),
                      alignment=TA_CENTER, spaceAfter=0),
    'sec_title':    s('sec_title',  fontSize=12, textColor=WHITE, fontName='Helvetica-Bold'),
    'feat_title':   s('feat_title', fontSize=11, textColor=BLUE,  fontName='Helvetica-Bold',
                      spaceBefore=6, spaceAfter=3),
    'body':         s('body',       fontSize=9,  textColor=BLACK, leading=14, spaceAfter=3),
    'bullet':       s('bullet',     fontSize=9,  textColor=BLACK, leading=13,
                      leftIndent=10, spaceAfter=2),
    'lbl':          s('lbl',        fontSize=8,  textColor=GRAY_TEXT, fontName='Helvetica-Bold'),
    'th':           s('th',         fontSize=8,  textColor=WHITE,  fontName='Helvetica-Bold',
                      alignment=TA_CENTER),
    'tc':           s('tc',         fontSize=8,  textColor=BLACK,  alignment=TA_CENTER),
    'tc_l':         s('tc_l',       fontSize=8,  textColor=BLACK,  alignment=TA_LEFT),
    'footer':       s('footer',     fontSize=7,  textColor=GRAY_TEXT, alignment=TA_CENTER),
    'lgnd_k':       s('lgnd_k',     fontSize=8,  fontName='Helvetica-Bold', textColor=BLUE),
    'lgnd_v':       s('lgnd_v',     fontSize=8,  textColor=GRAY_TEXT),
}

# ── Badge helpers ──────────────────────────────────────────────────────────────
BADGE_BG  = {'EXISTS': colors.HexColor('#DCFCE7'),
             'EXTEND': colors.HexColor('#FEF3C7'),
             'NEW':    colors.HexColor('#EDE9FE')}
BADGE_FG  = {'EXISTS': colors.HexColor('#166534'),
             'EXTEND': colors.HexColor('#92400E'),
             'NEW':    colors.HexColor('#5B21B6')}

def badge_style(tag, extra=None):
    kw = dict(fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER,
              textColor=BADGE_FG.get(tag, GRAY_TEXT))
    if extra:
        kw.update(extra)
    return ParagraphStyle(f'badge_{tag}_{id(tag)}', parent=base['Normal'], **kw)

# ── Page callback (header + footer) ───────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 8*mm, W, 8*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor('#BFDBFE'))
    canvas.setFont('Helvetica', 7)
    canvas.drawString(MARGIN, H - 5.5*mm, 'Workloop Clinic HRMS — Feature Specification')
    canvas.drawRightString(W - MARGIN, H - 5.5*mm, 'For Internal Use')
    canvas.setFillColor(GRAY_LIGHT)
    canvas.rect(0, 0, W, 8*mm, fill=1, stroke=0)
    canvas.setFillColor(GRAY_TEXT)
    canvas.setFont('Helvetica', 7)
    canvas.drawCentredString(W / 2, 3*mm, f'Page {doc.page}')
    canvas.restoreState()

# ── Section header ────────────────────────────────────────────────────────────
def section_header(title):
    t = Table([[Paragraph(title, styles['sec_title'])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
    ]))
    return t

# ── Feature block ──────────────────────────────────────────────────────────────
def feature_block(number, title, status, sources,
                  what_is, affects, impl, extras=None):

    src_str = '  '.join(f'[{x}]' for x in sources)

    # Header row
    hdr = Table([[
        Paragraph(f'<b>{number}</b>',
                  ParagraphStyle('_n', fontSize=10, textColor=WHITE,
                                 fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph(title,
                  ParagraphStyle('_t', fontSize=10, textColor=BLACK,
                                 fontName='Helvetica-Bold')),
        Paragraph(status, badge_style(status)),
        Paragraph(src_str,
                  ParagraphStyle('_s', fontSize=8, textColor=GRAY_TEXT,
                                 alignment=TA_CENTER)),
    ]], colWidths=[10*mm, 107*mm, 22*mm, 35*mm])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, 0), NAVY),
        ('BACKGROUND',    (1, 0), (1, 0), LIGHT_BLUE),
        ('BACKGROUND',    (2, 0), (2, 0), BADGE_BG.get(status, GRAY_BG)),
        ('BACKGROUND',    (3, 0), (3, 0), GRAY_BG),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('GRID',          (0, 0), (-1, -1), 0.3, GRAY_LIGHT),
    ]))

    def field(label, paras):
        rows = [[Paragraph(label, styles['lbl'])]] + [[p] for p in paras]
        t = Table(rows, colWidths=[CONTENT_W - 8*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), GRAY_BG),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
            ('LINEBELOW',     (0, 0), (-1, 0), 0.3, GRAY_LIGHT),
        ]))
        return t

    def bullets(lines):
        return [Paragraph(f'&#8226;  {l}', styles['bullet']) for l in lines]

    elems = [
        hdr,
        field('WHAT IT IS',       [Paragraph(what_is, styles['body'])]),
        field('WHAT IT AFFECTS',   bullets(affects)),
        field('IMPLEMENTATION',    bullets(impl)),
    ]
    if extras:
        for e in extras:
            elems.append(e)
    elems.append(Spacer(1, 7))
    return KeepTogether(elems)

# ══════════════════════════════════════════════════════════════════════════════
# BUILD STORY
# ══════════════════════════════════════════════════════════════════════════════
story = []

# ── Cover ─────────────────────────────────────────────────────────────────────
cover = Table([
    [Paragraph('Workloop Clinic HRMS', styles['doc_title'])],
    [Paragraph('Feature Specification — UAE Healthcare', styles['doc_sub'])],
    [Paragraph('Gap Analysis &amp; Implementation Guide', styles['doc_sub'])],
], colWidths=[CONTENT_W])
cover.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
    ('TOPPADDING',    (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
]))
story.append(cover)
story.append(Spacer(1, 8))

# Legend
def mini_badge(tag, text):
    return Paragraph(text, ParagraphStyle(f'mb_{tag}', fontSize=8,
        fontName='Helvetica-Bold', textColor=BADGE_FG[tag], alignment=TA_CENTER))

lg = Table([[
    mini_badge('EXISTS', 'EXISTS'),
    Paragraph('Already built in current codebase', styles['lgnd_v']),
    mini_badge('EXTEND', 'EXTEND'),
    Paragraph('Feature exists, needs clinic-specific additions', styles['lgnd_v']),
    mini_badge('NEW', 'NEW'),
    Paragraph('Net-new feature not yet built', styles['lgnd_v']),
]], colWidths=[16*mm, 44*mm, 16*mm, 58*mm, 12*mm, 28*mm])
lg.setStyle(TableStyle([
    ('BACKGROUND',    (0,0),(0,0), BADGE_BG['EXISTS']),
    ('BACKGROUND',    (2,0),(2,0), BADGE_BG['EXTEND']),
    ('BACKGROUND',    (4,0),(4,0), BADGE_BG['NEW']),
    ('BACKGROUND',    (1,0),(1,0), GRAY_BG),
    ('BACKGROUND',    (3,0),(3,0), GRAY_BG),
    ('BACKGROUND',    (5,0),(5,0), GRAY_BG),
    ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ('TOPPADDING',    (0,0),(-1,-1), 5),
    ('BOTTOMPADDING', (0,0),(-1,-1), 5),
    ('LEFTPADDING',   (0,0),(-1,-1), 6),
    ('RIGHTPADDING',  (0,0),(-1,-1), 6),
    ('GRID',          (0,0),(-1,-1), 0.3, GRAY_LIGHT),
]))
story.append(lg)
story.append(Spacer(1, 5))

src = Table([[
    Paragraph('[PDF]', styles['lgnd_k']),
    Paragraph('Hospital requirements document provided by client', styles['lgnd_v']),
    Paragraph('[CSV]', styles['lgnd_k']),
    Paragraph('Duty rota template — Dubai Medical University Hospital', styles['lgnd_v']),
    Paragraph('[UAE]', styles['lgnd_k']),
    Paragraph('UAE Federal Labour Law / DHA regulation', styles['lgnd_v']),
]], colWidths=[10*mm, 56*mm, 10*mm, 64*mm, 10*mm, 24*mm])
src.setStyle(TableStyle([
    ('TOPPADDING',    (0,0),(-1,-1), 3),
    ('BOTTOMPADDING', (0,0),(-1,-1), 3),
    ('LEFTPADDING',   (0,0),(-1,-1), 4),
    ('RIGHTPADDING',  (0,0),(-1,-1), 4),
]))
story.append(src)
story.append(Spacer(1, 12))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Employee & Document Management
# ══════════════════════════════════════════════════════════════════════════════
story.append(section_header('SECTION 1 — Employee & Document Management'))
story.append(Spacer(1, 6))

story.append(feature_block(
    '1.1', 'Clinical Credential & Licence Tracking', 'EXTEND',
    ['PDF #2', 'PDF #3'],
    'The current system tracks passport, visa, and Emirates ID. For UAE healthcare, staff must '
    'also hold and renew clinical credentials (BLS, ACLS, PALS, NRP, CME certificates) with '
    'specific expiry dates. HR must be notified at least 1 month before any credential expires '
    '(per client requirement #3) — via email AND in-app notification.',
    [
        'EmployeeModal.jsx — UAE Compliance tab: add "Clinical Credentials" section below existing docs',
        'employee_documents table — extend document_type values to include: BLS, ACLS, PALS, NRP, CME-Certificate, DHA-Licence, DOH-Licence, MOH-Licence',
        'notificationStorage.js — generateExpiryNotifications(): add 30-day threshold for clinical docs (minimum per PDF #3); 60d and 90d are optional early warnings',
        'Email integration — Supabase Edge Function triggered when expiry_date - NOW() <= 30 days (currently only in-app notifications exist)',
        'NOTE: DHA/MOH/DOH professional licences are stored here as documents; compliance gating (blocking payroll for expired licences) is handled separately in Feature 7.1',
    ],
    [
        'Add clinical document types to the upload form dropdown in EmployeeModal Documents tab',
        'Employee self-upload of these same documents covered separately in Feature 1.2',
        'Expiry threshold: fire notification at 30 days (mandatory per client); optionally also at 60 days and 90 days for advance warning',
        'Email trigger: new Supabase Edge Function "notify-expiry" — reads documents expiring within 30 days, sends email to HR_EMAIL env variable',
        'Notification row: use type = clinical_credential_expiry with relatedEntityId = {docId}_{thr}d for deduplication',
    ],
))

story.append(feature_block(
    '1.2', 'Employee Self-Service Document Uploads', 'NEW',
    ['PDF #2'],
    'Requirement #2 asks employees to add their own documents from the portal: date of birth, '
    'passport (number, validity, scan), visa (number, validity, scan), Emirates ID, BLS, ACLS, '
    'PALS, NRP, and CME certificate. Currently the portal is read-only for documents — only HR '
    'can upload via the admin panel.',
    [
        'EmployeeShell.jsx — add 10th tab "Documents" (currently 9 tabs: Home through Profile)',
        'New EmpDocuments.jsx — form: document type selector, number field, validity date, file upload',
        'employee_documents RLS — add INSERT policy for auth_user_id = auth.uid() (currently HR-only)',
        'New RPC employee_submit_document(p_type, p_number, p_expiry, p_storage_path) — SECURITY DEFINER',
        'employees table — add date_of_birth DATE column (currently absent; needed for birthday dashboard card in Feature 4.1 too)',
    ],
    [
        'Employee picks document type, enters number and expiry, uploads file to Supabase Storage under a pending/ path prefix',
        'RPC writes the employee_documents row with status = pending_verification',
        'HR sees "Pending" badge in EmployeeModal Documents tab; clicks Approve (moves file, sets verified_at) or Reject (notifies employee with reason)',
        'Approved documents are then subject to the same expiry notifications as HR-uploaded ones',
        'DOB entered once in the employee portal profile; stored in employees.date_of_birth and surfaced in the HR dashboard birthday card',
    ],
))

story.append(feature_block(
    '1.3', 'Letter & Certificate Request System', 'NEW',
    ['PDF #4'],
    'Requirement #4: employees must be able to request standard HR letters from the portal '
    '(salary certificate, NOC, experience letter, employment certificate, salary transfer letter). '
    'HR must receive an email notification for each request, then generate and return the letter.',
    [
        'New DB table: letter_requests (id, employee_id, type, purpose, status, requested_at, completed_at, download_path, user_id)',
        'EmployeeShell.jsx — request form in Profile tab or a new "Requests" tab',
        'notificationStorage.js — fire letter_request in-app notification to HR admin on submission',
        'Email: Supabase Edge Function sends email to HR when a new letter request is created [PDF #4]',
        'AppShell Dashboard — "Pending Letter Requests" count badge visible to HR',
    ],
    [
        'Standard letter types: Salary Certificate (bank / embassy / personal), NOC, Experience Letter, Employment Certificate, Salary Transfer Letter',
        'Employee selects type + purpose → letter_requests row with status = pending created via RPC',
        'HR sees the queue, clicks "Generate" → opens print template (same window.open() pattern as EndOfServiceScreen)',
        'Status → completed; employee sees "Ready — Download" in their portal',
        'Edge Function: POST to HR email with employee name, letter type, request date on each new submission',
    ],
))

story.append(Spacer(1, 8))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Attendance & Scheduling
# ══════════════════════════════════════════════════════════════════════════════
story.append(section_header('SECTION 2 — Attendance & Scheduling'))
story.append(Spacer(1, 6))

# Shift code table from CSV — use plain strings; Paragraph wrapper applied uniformly below
shift_rows = [
    ['Code', 'Timing',         'Category',  'Hrs'],
    ['D',    '08:00-16:00',    'Morning',   '8h'],
    ['D1',   '09:00-17:00',    'Morning',   '8h'],
    ['D2',   '10:00-18:00',    'Morning',   '8h'],
    ['M',    '07:30-20:00',    'Long Day',  '12.5h'],
    ['M1',   '07:45-20:00',    'Long Day',  '12.25h'],
    ['N',    '17:30-08:00',    'Night',     '14.5h'],
    ['N1',   '17:45-08:00',    'Night',     '14.25h'],
    ['A',    '11:00-20:00',    'Afternoon', '9h'],
    ['A1',   '12:00-21:00',    'Afternoon', '9h'],
    ['O',    '-',              'Off',       '-'],
]
shift_t = Table(
    [[Paragraph(c, styles['th'] if r == 0 else styles['tc']) for c in row]
     for r, row in enumerate(shift_rows)],
    colWidths=[12*mm, 34*mm, 24*mm, 14*mm]
)
shift_t.setStyle(TableStyle([
    ('BACKGROUND',    (0,0),(-1,0), NAVY),
    ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, GRAY_BG]),
    ('GRID',          (0,0),(-1,-1), 0.3, GRAY_LIGHT),
    ('TOPPADDING',    (0,0),(-1,-1), 3),
    ('BOTTOMPADDING', (0,0),(-1,-1), 3),
    ('LEFTPADDING',   (0,0),(-1,-1), 4),
    ('RIGHTPADDING',  (0,0),(-1,-1), 4),
    ('FONTSIZE',      (0,0),(-1,-1), 8),
    ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
]))

# Leave code table from CSV
leave_rows = [
    ['Code', 'Meaning'],
    ['AL',   'Annual Leave'],
    ['SL',   'Sick Leave'],
    ['ML',   'Maternity Leave'],
    ['UL',   'Unpaid Leave'],
    ['PH',   'Public Holiday'],
    ['O',    'Off / Rest Day'],
]
leave_t = Table(
    [[Paragraph(c, styles['th'] if r == 0 else styles['tc']) for c in row]
     for r, row in enumerate(leave_rows)],
    colWidths=[12*mm, 34*mm]
)
leave_t.setStyle(TableStyle([
    ('BACKGROUND',    (0,0),(-1,0), NAVY),
    ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, GRAY_BG]),
    ('GRID',          (0,0),(-1,-1), 0.3, GRAY_LIGHT),
    ('TOPPADDING',    (0,0),(-1,-1), 3),
    ('BOTTOMPADDING', (0,0),(-1,-1), 3),
    ('LEFTPADDING',   (0,0),(-1,-1), 5),
    ('FONTSIZE',      (0,0),(-1,-1), 8),
    ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
]))

# Combined table — inner tables are 84mm and 46mm; outer cells match exactly
code_tables = Table([[shift_t, leave_t]], colWidths=[86*mm, 50*mm])
code_tables.setStyle(TableStyle([
    ('LEFTPADDING',   (0,0),(-1,-1), 0),
    ('RIGHTPADDING',  (0,0),(-1,-1), 0),
    ('TOPPADDING',    (0,0),(-1,-1), 0),
    ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ('VALIGN',        (0,0),(-1,-1), 'TOP'),
    ('LEFTPADDING',   (1,0),(1,0),   6),
]))

story.append(feature_block(
    '2.1', 'Clinical Duty Rota (Department-Scoped, Multi-Shift)', 'EXTEND',
    ['PDF #6', 'CSV'],
    'Requirement #6 references the attached CSV as the rota template. The current RosterManager '
    'has a basic monthly grid but lacks the clinical details hospitals use: short shift codes, '
    'per-employee hours totals, shift-type staff counts, comp-off tracking, mid-month '
    'join/leave handling, CSV export in the hospital format, and minimum staffing alerts.',
    [
        'shifts table — add code TEXT (short code: D, N, M, A, etc.) and shift_category (morning / afternoon / night)',
        'roster_assignments — add planned_hours DECIMAL, actual_hours DECIMAL, co_hours DECIMAL',
        'New table: department_staffing_rules (department_id, shift_category, min_staff) — used by Feature 7.2',
        'RosterManager.jsx — department-scoped view/publish, compact cell showing short code not full name',
        'Reports module — new "Staffing Compliance" report tab (days where min coverage met vs missed)',
    ],
    [
        'Grid cell view: show shift code (D / N1 / A) in the monthly cell — matches the CSV layout employees are familiar with',
        'Per-employee totals column: planned_hours and actual_hours for the month (mirrors "Total Hrs / Total Hrs done" in CSV)',
        'Summary footer rows: count Morning / Afternoon / Night / Off per day — matches the CSV summary rows',
        'CO/Comp-off balance: when a public holiday falls on an employee\'s scheduled day, record co_hours; link to leave_balances',
        'Mid-month joiners: grey out cells before join_date; show "Joined DD/MM" label in first active cell',
        'CSV export: generate in the exact Dubai Medical University Hospital format (header, staff rows, summary)',
        'CSV import: parse the same format and bulk-load into roster_assignments',
    ],
    extras=[
        Spacer(1, 5),
        Paragraph('Shift codes and leave codes from the provided CSV template:', styles['lbl']),
        Spacer(1, 3),
        code_tables,
        Spacer(1, 4),
    ],
))

story.append(feature_block(
    '2.2', 'Biometric / Punching Machine Integration', 'NEW',
    ['PDF #7', 'PDF #8'],
    'Requirements #7 and #8: attendance must come from the physical biometric device (fingerprint '
    'or card reader), not manual portal clock-in. The employee portal dashboard must show today\'s '
    'actual punch times, and flag late arrivals automatically.',
    [
        'clock_events table — add source column (portal | biometric | manual_correction)',
        'attendance_records table — add source column',
        'EmpHome.jsx — "Today: Checked in HH:MM | Checked out HH:MM" card from biometric feed [PDF #8]',
        'EmpHome.jsx — late-arrival alert if punch-in > shift.start_time + grace_minutes [PDF #8]',
        'New DB table: biometric_devices (id, name, ip_address, api_key, device_type, last_sync_at, active)',
        'New BiometricSettings.jsx — admin configures device IP, API key, sync interval in Company Settings',
    ],
    [
        'Integration model A (Pull): Supabase Edge Function scheduled every 5 minutes polls device API, upserts into clock_events with source = biometric',
        'Integration model B (Push): device vendor SDK sends a webhook POST to an Edge Function endpoint on each punch event',
        'Common device vendors in UAE healthcare: ZKTeco, FingerTec, HikVision — all expose REST APIs',
        'Late flag: when biometric clock_in_time > shift.start_time + grace, insert late_arrival in-app notification to the employee',
        'Admin AttendanceManager: existing overtime and records tabs already support source column display — just add a filter for biometric vs portal',
        'EmpAttendance.jsx: replace "Clock In / Clock Out" manual buttons with read-only biometric display when biometric device is configured',
    ],
))

story.append(feature_block(
    '2.3', 'Probation-Aware Leave Rules', 'EXTEND',
    ['PDF #9'],
    'Requirement #9: employees on probation must only see leave types applicable during probation. '
    'The accrual rate during probation is 2 days/month; after confirmation it becomes 2.5 days/month. '
    'If a probation employee tries to apply for a non-eligible leave type, they must see a clear '
    'notification: "You are not entitled to paid leave during your probation period." '
    'The specific leave types eligible during probation should be configurable by HR — NOT hardcoded.',
    [
        'leave_types table — add probation_eligible BOOLEAN DEFAULT false column',
        'leaveEngine.js — validateLeaveRequest(): check employmentStatus === Probation; reject non-eligible types with the required message',
        'leaveEngine.js — calculateAnnualLeaveAccrual(): return 2 days/month for Probation status, 2.5 days/month after',
        'EmpLeave.jsx — filter leave type <select> to only show types where probation_eligible = true when employee status is Probation',
        'LeaveManager Settings tab — checkbox "Eligible during probation" on each leave type configuration row',
    ],
    [
        'HR marks which leave types are allowed during probation (e.g. Sick Leave, Emergency) via the leave type settings — this is configurable, not hardcoded',
        'EmpLeave: if employee.employmentStatus === Probation and selected type has probation_eligible = false, show inline warning and disable submit',
        'Warning text verbatim from requirement: "You are not entitled to paid leave during your probation period"',
        'Accrual rates: update leaveEngine.ACCRUAL_RATES constant — add separate rate for Probation (2d/month) vs Confirmed (2.5d/month)',
        'Leave balance: when HR confirms employee (status changes from Probation to Full-Time), recalculate balance at the higher rate from confirmation date',
    ],
))

story.append(feature_block(
    '2.4', 'Leave Document Attachments (Mandatory by Leave Type)', 'EXTEND',
    ['PDF #10'],
    'Requirement #10: for certain leave types, employees must attach a supporting document '
    'before the request can be submitted. Example: Sick Leave requires a medical certificate; '
    'Maternity Leave requires a birth certificate. HR configures which types require documents.',
    [
        'leave_types table — add requires_document BOOLEAN DEFAULT false, document_label TEXT (e.g. "Medical Certificate")',
        'leave_requests table — add attachment_path TEXT, attachment_filename TEXT',
        'EmpLeave.jsx — when selected leave type has requires_document = true, show a file upload input; block submission without it',
        'LeaveManager.jsx requests table — show paperclip icon with download link when attachment_path is set',
        'LeaveManager Settings tab — "Requires Document" toggle and label field per leave type',
    ],
    [
        'HR configures requires_document and document_label per leave type in the Leave Settings tab',
        'EmpLeave: when a document-required type is selected, show: "Please attach: {document_label}"',
        'File upload uses Supabase Storage — stored under leave-attachments/{admin_uid}/{emp_id}/{request_id} path',
        'Submission blocked (button disabled) if leave type requires a document and no file is selected',
        'LeaveManager: HR can click to download/view the attachment before approving or rejecting the request',
    ],
))

story.append(Spacer(1, 8))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Org Structure & Approvals
# ══════════════════════════════════════════════════════════════════════════════
story.append(section_header('SECTION 3 — Org Structure & Approvals'))
story.append(Spacer(1, 6))

story.append(feature_block(
    '3.1', 'Department Hierarchy & Org Tree', 'NEW',
    ['PDF #1'],
    'Requirement #1: "Team and hierarchy management for each department." The current system '
    'stores department as a free-text field on each employee with no tree structure and no '
    'department heads. Hospitals have formal hierarchies (Medical > Nursing > OPD etc.) that '
    'must drive reporting lines and approval chains.',
    [
        'New DB table: departments (id, name, parent_id FK self, head_employee_id FK employees, user_id)',
        'employees table — change department TEXT to department_id UUID FK departments (migration required)',
        'EmployeeModal.jsx — department field becomes a hierarchical selector showing the dept tree',
        'LeaveManager / ManagerLeaveQueue — approval chain auto-routes to department head (not just "reporting manager")',
        'RosterManager.jsx — department filter dropdown populated from departments table',
        'CompanySettings.jsx — new "Departments" section: add / rename / nest departments, assign head',
    ],
    [
        'Org tree rendered as collapsible nested list in CompanySettings; drag-to-rearrange optional (v2)',
        'Supabase recursive CTE query for department tree: WITH RECURSIVE dept_tree AS (SELECT ... UNION ALL ...)',
        'Department head auto-routing: on leave/letter/expense request, system looks up departments.head_employee_id for the employee\'s department',
        'If department head is on leave: fall back to leave_approval_delegates table (already built)',
        'EmployeeManager filter sidebar: add "Filter by Department" using the dept tree instead of free-text search',
    ],
))

story.append(feature_block(
    '3.2', 'Multi-Level Approval for All Request Types', 'EXTEND',
    ['PDF #1'],
    'Requirement #1 says approval workflow is needed for Leave, Documents, Letters "etc." — '
    'meaning all employee requests go through department head before reaching HR. Currently '
    'only Leave has a 2-level flow (Manager + HR). Letter requests (Feature 1.3) and Expense '
    'Claims need the same pattern.',
    [
        'letter_requests table — add dept_head_status, dept_head_approved_by, dept_head_approved_at',
        'expense_claims table — add dept_head_status, dept_head_approved_by, dept_head_approved_at',
        'ManagerShell.jsx / ManagerLeaveQueue — rename to ManagerRequestQueue; add tabs for Letters and Expenses alongside Leave',
        'notificationStorage.js — fire dept_approval_required notification to department head on each new letter or expense request',
        'HR sees requests only after dept_head_status = approved (configurable toggle per request type in Company Settings)',
    ],
    [
        'Status flow for letters and expenses: pending → dept_approved → hr_approved / hr_rejected',
        'Manager sees their team\'s pending letters and expenses in the manager portal queue tabs',
        'HR admin can configure "bypass dept approval" per request type if a flat workflow is preferred',
        'Rejection by dept head: employee notified with reason; request status = dept_rejected; cannot be resubmitted without editing',
        'Audit trail: each approval or rejection logged with approver email and timestamp',
    ],
))

story.append(Spacer(1, 8))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — HR Dashboard & Analytics
# ══════════════════════════════════════════════════════════════════════════════
story.append(section_header('SECTION 4 — HR Dashboard & Analytics'))
story.append(Spacer(1, 6))

kpi_rows = [
    [Paragraph(h, styles['th']) for h in ['KPI Card', 'Data Source', 'Drill-Down']],
    ['Total Active Employees',       'employees WHERE active = true',          'EmployeeManager'],
    ['New Joiners This Month',        'employees.join_date in current month',   'Filtered employee list'],
    ['Birthdays This Month',          'employees.date_of_birth (new field)',    'List with name + dept'],
    ['On Probation',                  'employment_status = Probation',          'ProbationModal'],
    ['Confirmed / Permanent',         'employment_status = Full-Time',          'Filtered list'],
    ['Expiring Credentials < 30d',    'employee_documents.expiry_date',        'Documents tab per employee'],
    ['On Leave Today',                'leave_requests approved + date range',   'Leave calendar'],
    ['Pending Leave Requests',        'leave_requests.status = Pending',        'LeaveManager Requests tab'],
    ['Pending Letter Requests',       'letter_requests.status = pending',       'Letter request queue'],
    ['Staff on Duty Now',             'clock_events today, no clock-out',       'Attendance module'],
    ['Late Arrivals Today',           'biometric punch vs shift start time',    'Attendance filtered'],
]
kpi_t = Table(
    [[Paragraph(str(c), styles['th'] if r == 0 else styles['tc_l'])
      for c in row] for r, row in enumerate(kpi_rows)],
    colWidths=[58*mm, 68*mm, 48*mm]
)
kpi_t.setStyle(TableStyle([
    ('BACKGROUND',    (0,0),(-1,0), NAVY),
    ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, GRAY_BG]),
    ('GRID',          (0,0),(-1,-1), 0.3, GRAY_LIGHT),
    ('TOPPADDING',    (0,0),(-1,-1), 4),
    ('BOTTOMPADDING', (0,0),(-1,-1), 4),
    ('LEFTPADDING',   (0,0),(-1,-1), 6),
    ('FONTSIZE',      (0,0),(-1,-1), 8),
    ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
]))

story.append(feature_block(
    '4.1', 'Clinical HR Dashboard with Drill-Down KPI Cards', 'EXTEND',
    ['PDF #5'],
    'Requirement #5: HR needs a dashboard showing Total Employees, New Joiners, Birthdays '
    'this month, Probation employees, Confirmed employees — with drill-down from each card. '
    'The current dashboard has basic stats but lacks DOB tracking, birthday cards, letter '
    'request counts, and the clickable drill-down behaviour.',
    [
        'Dashboard.jsx — add new stat cards for all clinical KPIs listed below',
        'employees table — add date_of_birth DATE column (also needed for Feature 1.2 self-upload)',
        'EmployeeModal.jsx Personal tab — add Date of Birth field',
        'Each card onClick: calls onNavigate() with a filter param so the target component pre-filters',
        'EmployeeManager, LeaveManager, AttendanceManager — accept initialFilter prop for drill-down',
    ],
    [
        'Birthday card: filter employees where month(dob) = current month; show name + department + date in drill-down list',
        'Expiring Credentials card: replaces/supplements existing document expiry alert; links directly to the employee\'s Documents tab',
        'Pending Letter Requests card: count from letter_requests table (Feature 1.3); visible to HR only',
        'Late Arrivals card: only meaningful after biometric integration (Feature 2.2); gracefully hidden if no biometric device configured',
        'Drill-down: onNavigate passes { page, filter } object; target component reads filter in its useEffect to pre-apply',
    ],
    extras=[Spacer(1,5), kpi_t, Spacer(1,4)],
))

story.append(Spacer(1, 8))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Payroll & Compensation
# ══════════════════════════════════════════════════════════════════════════════
story.append(section_header('SECTION 5 — Payroll & Compensation'))
story.append(Spacer(1, 6))

story.append(feature_block(
    '5.1', 'Contract-Type Based Salary Component Distribution', 'EXTEND',
    ['PDF #12', 'UAE'],
    'Requirement #12: salary must be distributed across components (basic, housing, transport, '
    'allowances) according to UAE government rules for the employee\'s contract type. '
    'The current PayrollEditor accepts any values without validating component ratios. '
    'The UAE MoHRE recommends Basic >= 60% of total package for most contract types.',
    [
        'PayrollEditor.jsx — add validation warning when salary component percentages fall outside recommended ratios',
        'employees table — add fte DECIMAL DEFAULT 1.0 (full-time equivalent) and employment_category column',
        'PayrollList.jsx — add Locum / Per-Diem run type (daily rate, no benefits, no leave accrual)',
        'leaveEngine.js — all accruals pro-rated by fte for part-time staff',
    ],
    [
        'Recommended ratios (MoHRE guidance): Basic >= 60%, Housing <= 25%, Transport <= 10%, Other <= 5% of total package',
        'Show amber warning in PayrollEditor header if any employee\'s component split is outside recommended range; not a hard block',
        'Locum run: new payroll_runs.run_type = locum — includes only employees with employment_category = locum; entries use daily_rate × days_worked',
        'Part-time FTE: contracted_hours / 48 (UAE standard week) = fte; annual leave accrual and gratuity scaled by fte',
        'Free-zone employees (e.g. Dubai Healthcare City DHCC): flag with different WPS bank routing code requirement in the SIF generator',
    ],
))

story.append(feature_block(
    '5.2', 'Overtime → Payroll Auto-Integration', 'EXTEND',
    ['UAE'],
    'Overtime calculation already exists in full (attendanceEngine.js: Art. 19 at 1.25x, '
    'Art. 20 rest-day at 1.5x, Art. 26 night shift at 1.25x; AttendanceManager has an Overtime '
    'tab with approval workflow). However, approved overtime amounts are NOT automatically '
    'carried into PayrollEditor — HR currently has to manually add them as deduction/allowance '
    'entries. For a clinic where nursing staff regularly work overtime, this manual step is '
    'error-prone and time-consuming.',
    [
        'PayrollEditor.jsx — auto-load approved overtime totals from attendance_records for each employee in the payroll period',
        'attendanceStorage.js — new function getApprovedOvertimeForPeriod(companyId, period): returns per-employee OT hours and amounts',
        'PayrollEditor AllowDeductPanel — pre-populate an "Overtime Pay (Art. 19/20)" line item automatically when OT > 0',
        'attendance_records table — add payroll_run_id column to mark which records have been included in a payroll run',
    ],
    [
        'On PayrollEditor load: call getApprovedOvertimeForPeriod(period) and merge results into entry.otherPay or a dedicated OT field per employee',
        'Show an info panel (green, like the Expenses panel) listing OT hours and pre-computed amounts pulled from Attendance',
        'HR can override: OT amounts are editable after auto-population — the Attendance value is a starting point',
        'After payroll submission: mark the included attendance_records.payroll_run_id = run.id to prevent double-counting in future runs',
        'Night shift premium (Art. 26): hasNightShiftHours() helper already exists; OT type = NIGHT_SHIFT auto-detected from clock times',
    ],
))

story.append(Spacer(1, 8))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Performance & Development
# ══════════════════════════════════════════════════════════════════════════════
story.append(section_header('SECTION 6 — Employee Performance & Development'))
story.append(Spacer(1, 6))

story.append(feature_block(
    '6.1', 'Employee Evaluation & Appraisal Module', 'NEW',
    ['PDF #11'],
    'Requirement #11: Employee Evaluation & Management Module. Structured periodic performance '
    'reviews are standard in UAE healthcare — mandatory for JCIA/JCI-accredited facilities. '
    'The system needs template-based appraisals, self-assessment, manager scoring, and HR sign-off.',
    [
        'New DB table: appraisal_templates (id, name, cycle_months, competencies JSONB, rating_scale_max, user_id)',
        'New DB table: appraisals (id, employee_id, template_id, period_start, period_end, status, self_score, manager_score, final_score, user_id)',
        'New DB table: appraisal_competency_scores (appraisal_id, competency_key, self_rating, manager_rating, comments)',
        'New AppraisalManager.jsx (admin) — template builder, active cycle view, score summary',
        'New EmpAppraisal.jsx (employee portal tab) — self-assessment form, past results history',
        'ManagerShell.jsx — new "Appraisals" tab for managers to score their direct reports',
        'Dashboard.jsx — "Appraisals Due" alert (probation ending or annual cycle due within 14 days)',
    ],
    [
        'Template builder: HR defines competency categories (Clinical Skills, Communication, Teamwork, Attendance, Compliance) with weights',
        'Auto-trigger: when probation_end_date - TODAY <= 14 days, auto-create an appraisal record for probation review',
        'Status flow: draft → self_assessment_open → manager_review → hr_final → closed',
        'Score: weighted average of rated competencies → final_score; HR sets pass threshold per template',
        'PDF export: print appraisal report to employee file using the same window.open() pattern as payslips',
        'Probation outcome: confirming employee or extending probation can be triggered directly from the appraisal result screen',
    ],
))

story.append(Spacer(1, 8))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Compliance & Regulatory
# ══════════════════════════════════════════════════════════════════════════════
story.append(section_header('SECTION 7 — Compliance & Regulatory (UAE Healthcare)'))
story.append(Spacer(1, 6))

story.append(feature_block(
    '7.1', 'DHA / MOH / DOH Professional Licence Compliance Gate', 'NEW',
    ['UAE'],
    'All clinical staff practising in Dubai must hold a valid DHA (Dubai Health Authority) '
    'licence; Abu Dhabi requires DOH; other Emirates require MOH. These licences are stored '
    'as documents in Feature 1.1, but this feature adds the compliance gate: the system '
    'actively blocks payroll generation and roster publishing for employees with expired '
    'professional licences. Feature 1.1 = document storage; Feature 7.1 = enforcement.',
    [
        'employees table — add licence_authority (DHA | DOH | MOH | HAAD | None), licence_number TEXT, licence_expiry DATE, licence_status computed column',
        'PayrollList.jsx — before generating SIF, check all included employees: if licence_status = expired → block or warn with list of non-compliant staff',
        'RosterManager.jsx — publishRoster() validation: flag employees assigned to shifts who have expired licences',
        'Dashboard.jsx — "Non-Compliant Staff" card: count of employees with expired or expiring (<30d) licences',
        'Notification chain: fire clinical_licence_expiry notifications at 60d / 30d / 14d / expiry — separate from document notifications in Feature 1.1',
    ],
    [
        'Licence status derived dynamically: active (> 30d remaining), expiring (1–30d), expired (<= 0d)',
        'Payroll block: when any active employee has licence_status = expired, show a non-dismissible warning listing affected employees; HR must either remove them from the run or confirm override with reason',
        'Roster block: publishRoster() validates all assigned employees in the month; surfaces failing employees per day per department',
        'Override: HR can mark a compliance exception with a mandatory reason text — logged to a compliance_overrides audit table',
        'Licence data entry: add a "Professional Licence" section in EmployeeModal UAE Compliance tab with authority selector, licence number, and expiry date (separate from the document file upload in Feature 1.1)',
    ],
))

story.append(feature_block(
    '7.2', 'Shift Minimum Staffing Compliance', 'NEW',
    ['CSV', 'UAE'],
    'UAE healthcare regulations (DHA Facility Standards) require minimum staffing ratios per '
    'department per shift. The CSV shows hospitals already track morning/afternoon/night/off '
    'counts manually per day. This feature automates the check and blocks under-staffed '
    'rosters from being published.',
    [
        'New DB table: department_staffing_rules (department_id, shift_category, min_staff, effective_from, effective_to, user_id)',
        'RosterManager.jsx — run staffing validation before publish; list days and shifts that fall below min_staff',
        'CompanySettings.jsx — new "Staffing Rules" sub-section in Departments tab to configure min_staff per dept/shift',
        'Reports module — new "Staffing Compliance" report tab (heatmap: days x departments, green/amber/red by coverage ratio)',
    ],
    [
        'HR sets minimum staff per department per shift category (morning / afternoon / night) in Company Settings',
        'publishRoster(): count assigned (non-off) staff per day per department per shift_category and compare to rules',
        'If any day fails: modal showing table of failing days with actual vs required count; cannot publish until resolved or overridden with reason',
        'Staffing report: month-view heatmap — each cell shows actual/required; red = below minimum, amber = at minimum, green = above',
        'Summary row in RosterManager grid (below employee rows): Morning count / Afternoon / Night / Off — mirrors the CSV summary rows employees recognise',
    ],
))

story.append(Spacer(1, 8))

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════
story.append(section_header('SUMMARY — Priority & Effort Matrix'))
story.append(Spacer(1, 6))

summary = [
    ['#',    'Feature',                                               'Status', 'Effort', 'P'],
    ['1.1',  'Clinical credential tracking (BLS, ACLS, CME, DHA lic.)',  'EXTEND', 'M',  'P1'],
    ['1.2',  'Employee self-upload documents (portal)',                   'NEW',    'M',  'P1'],
    ['1.3',  'Letter & certificate request system',                       'NEW',    'M',  'P2'],
    ['2.1',  'Clinical duty rota (dept-scoped, shift codes, CSV I/O)',    'EXTEND', 'L',  'P1'],
    ['2.2',  'Biometric / punching machine integration',                  'NEW',    'L',  'P1'],
    ['2.3',  'Probation-aware leave rules (configurable per type)',        'EXTEND', 'S',  'P1'],
    ['2.4',  'Leave document attachments (mandatory by leave type)',       'EXTEND', 'S',  'P2'],
    ['3.1',  'Department hierarchy & org tree',                           'NEW',    'L',  'P2'],
    ['3.2',  'Multi-level approvals for all request types',               'EXTEND', 'M',  'P2'],
    ['4.1',  'Clinical HR dashboard with drill-down KPI cards',           'EXTEND', 'M',  'P1'],
    ['5.1',  'Contract-type salary distribution validation',              'EXTEND', 'M',  'P2'],
    ['5.2',  'Overtime → Payroll auto-integration',                      'EXTEND', 'M',  'P1'],
    ['6.1',  'Employee evaluation & appraisal module',                    'NEW',    'XL', 'P3'],
    ['7.1',  'DHA/MOH/DOH licence compliance gate (payroll & roster)',    'NEW',    'M',  'P1'],
    ['7.2',  'Shift minimum staffing compliance enforcement',              'NEW',    'M',  'P2'],
]

P_COLOR = {'P1': colors.HexColor('#FEE2E2'), 'P2': AMBER, 'P3': GRAY_BG}
S_COL   = [10*mm, 100*mm, 22*mm, 16*mm, 10*mm]

def sum_row(r, row):
    if r == 0:
        return [Paragraph(str(c), styles['th']) for c in row]
    return [
        Paragraph(row[0], styles['tc']),
        Paragraph(row[1], styles['tc_l']),
        Paragraph(row[2], badge_style(row[2])),
        Paragraph(row[3], styles['tc']),
        Paragraph(row[4], styles['tc']),
    ]

sum_t = Table([sum_row(r, row) for r, row in enumerate(summary)], colWidths=S_COL)

ts = [
    ('BACKGROUND',    (0,0),(-1,0), NAVY),
    ('GRID',          (0,0),(-1,-1), 0.3, GRAY_LIGHT),
    ('TOPPADDING',    (0,0),(-1,-1), 4),
    ('BOTTOMPADDING', (0,0),(-1,-1), 4),
    ('LEFTPADDING',   (0,0),(-1,-1), 5),
    ('RIGHTPADDING',  (0,0),(-1,-1), 5),
    ('FONTSIZE',      (0,0),(-1,-1), 8),
    ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
]
for i, row in enumerate(summary[1:], 1):
    bg = GRAY_BG if i % 2 == 0 else WHITE
    ts += [
        ('BACKGROUND', (0,i),(1,i), bg),
        ('BACKGROUND', (2,i),(2,i), BADGE_BG.get(row[2], bg)),
        ('BACKGROUND', (3,i),(3,i), bg),
        ('BACKGROUND', (4,i),(4,i), P_COLOR.get(row[4], bg)),
    ]
sum_t.setStyle(TableStyle(ts))
story.append(sum_t)
story.append(Spacer(1, 8))

key_t = Table([[Paragraph(
    '<b>Effort:</b>  S = days &nbsp;&nbsp; M = 1–2 weeks &nbsp;&nbsp; '
    'L = 2–4 weeks &nbsp;&nbsp; XL = 4+ weeks &nbsp;&nbsp;&nbsp;&nbsp; '
    '<b>Priority:</b>  P1 = Required to go live &nbsp;&nbsp; '
    'P2 = Needed within 3 months &nbsp;&nbsp; P3 = Nice-to-have',
    styles['body'])]], colWidths=[CONTENT_W])
key_t.setStyle(TableStyle([
    ('BACKGROUND',    (0,0),(-1,-1), GRAY_BG),
    ('TOPPADDING',    (0,0),(-1,-1), 7),
    ('BOTTOMPADDING', (0,0),(-1,-1), 7),
    ('LEFTPADDING',   (0,0),(-1,-1), 10),
]))
story.append(key_t)

# ── Build ──────────────────────────────────────────────────────────────────────
OUTPUT = 'Workloop_Clinic_HRMS_Feature_List.pdf'
doc = SimpleDocTemplate(
    OUTPUT, pagesize=A4,
    leftMargin=MARGIN, rightMargin=MARGIN,
    topMargin=14*mm, bottomMargin=12*mm,
    title='Workloop Clinic HRMS Feature List',
    author='Workloop',
)
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print(f'PDF generated: {OUTPUT}')
