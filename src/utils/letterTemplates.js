/**
 * letterTemplates.js — UAE-standard HR letter HTML templates (Feature 1.3)
 * Printed via window.open() + document.write(), matching the EndOfServiceScreen pattern.
 */

function todayUAE() {
  return new Date().toLocaleDateString('en-AE', { day: '2-digit', month: 'long', year: 'numeric' });
}

function baseStyle() {
  return `
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body { font-family: Arial, Helvetica, sans-serif; font-size: 13px; color: #1a1a1a; padding: 40px 56px; }
      .letterhead { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #08122e; padding-bottom: 16px; margin-bottom: 24px; }
      .company-name { font-size: 20px; font-weight: 700; color: #08122e; }
      .company-sub { font-size: 11px; color: #555; margin-top: 3px; }
      .date { font-size: 12px; color: #555; text-align: right; }
      .ref { font-size: 11px; color: #888; margin-top: 2px; text-align: right; }
      h2 { font-size: 15px; font-weight: 700; text-align: center; text-decoration: underline; margin: 20px 0 18px; letter-spacing: 0.5px; color: #08122e; }
      p { line-height: 1.8; margin-bottom: 10px; }
      .highlight { font-weight: 700; }
      .signature-block { margin-top: 48px; display: flex; justify-content: space-between; }
      .sig { width: 45%; }
      .sig-line { border-top: 1px solid #333; margin-top: 40px; padding-top: 6px; font-size: 12px; color: #555; }
      .footer { margin-top: 40px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 10px; color: #888; text-align: center; }
      @media print { body { padding: 20px 40px; } }
    </style>`;
}

function letterhead(company, refSuffix) {
  const ref = `HR/${new Date().getFullYear()}/${String(Date.now()).slice(-5)}`;
  return `
    <div class="letterhead">
      <div>
        <div class="company-name">${company?.name || 'Company Name'}</div>
        <div class="company-sub">Dubai, United Arab Emirates</div>
      </div>
      <div>
        <div class="date">${todayUAE()}</div>
        <div class="ref">Ref: ${ref}${refSuffix || ''}</div>
      </div>
    </div>`;
}

function signature(company) {
  return `
    <div class="signature-block">
      <div class="sig">
        <div class="sig-line">Authorised Signatory<br>${company?.name || ''}</div>
      </div>
      <div class="sig">
        <div class="sig-line">HR Department<br>${company?.name || ''}</div>
      </div>
    </div>
    <div class="footer">This letter is issued on official company letterhead and is valid as of the date stated above.</div>`;
}

// ── Salary Certificate ─────────────────────────────────────────────────────────
export function salaryCertificateLetter(req, company) {
  const gross = (req.basicSalary || 0) + (req.allowance || 0);
  const purposeNote = req.purpose ? ` for the purpose of <span class="highlight">${req.purpose}</span>` : '';
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Salary Certificate</title>${baseStyle()}</head><body>
    ${letterhead(company, '-SC')}
    <h2>SALARY CERTIFICATE</h2>
    <p>To Whom It May Concern,</p>
    <p>This is to certify that <span class="highlight">${req.employeeName}</span>, holding the position of
    <span class="highlight">${req.jobTitle || 'Employee'}</span>${req.department ? ` in the ${req.department} department` : ''},
    is a full-time employee of <span class="highlight">${company?.name || 'our company'}</span>.</p>
    <p>The employee's monthly salary details are as follows:</p>
    <table style="margin:12px 0 16px 20px; border-collapse:collapse;">
      <tr><td style="padding:3px 24px 3px 0; color:#555;">Basic Salary</td><td style="font-weight:600;">AED ${req.basicSalary?.toLocaleString('en-AE', {minimumFractionDigits:2}) || '0.00'}</td></tr>
      ${req.allowance ? `<tr><td style="padding:3px 24px 3px 0; color:#555;">Allowances</td><td style="font-weight:600;">AED ${req.allowance.toLocaleString('en-AE', {minimumFractionDigits:2})}</td></tr>` : ''}
      <tr style="border-top:1px solid #ccc;"><td style="padding:6px 24px 3px 0; font-weight:700;">Total Monthly Salary</td><td style="font-weight:700; font-size:14px;">AED ${gross.toLocaleString('en-AE', {minimumFractionDigits:2})}</td></tr>
    </table>
    <p>This letter is issued${purposeNote} and should not be used for any other purpose.</p>
    ${signature(company)}
  </body></html>`;
}

// ── NOC ────────────────────────────────────────────────────────────────────────
export function nocLetter(req, company) {
  const purposeNote = req.purpose ? ` for the purpose of <span class="highlight">${req.purpose}</span>` : '';
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>No Objection Certificate</title>${baseStyle()}</head><body>
    ${letterhead(company, '-NOC')}
    <h2>NO OBJECTION CERTIFICATE</h2>
    <p>To Whom It May Concern,</p>
    <p>This is to certify that <span class="highlight">${req.employeeName}</span>, ${req.jobTitle ? `${req.jobTitle}, ` : ''}is a valued employee of
    <span class="highlight">${company?.name || 'our company'}</span>${req.joinDate ? ` since <span class="highlight">${req.joinDate}</span>` : ''}.</p>
    <p>We have no objection to the bearer${purposeNote}.</p>
    <p>We wish ${req.employeeName.split(' ')[0] || 'the employee'} all the best and confirm that they are in good standing with our organisation.</p>
    ${signature(company)}
  </body></html>`;
}

// ── Experience Letter ──────────────────────────────────────────────────────────
export function experienceLetter(req, company) {
  const toDate = todayUAE();
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Experience Letter</title>${baseStyle()}</head><body>
    ${letterhead(company, '-EXP')}
    <h2>EXPERIENCE LETTER</h2>
    <p>To Whom It May Concern,</p>
    <p>This is to certify that <span class="highlight">${req.employeeName}</span> has been employed with
    <span class="highlight">${company?.name || 'our company'}</span>
    ${req.joinDate ? `from <span class="highlight">${req.joinDate}</span> to <span class="highlight">${toDate}</span>` : `up to ${toDate}`}
    in the capacity of <span class="highlight">${req.jobTitle || 'Employee'}</span>${req.department ? ` in the ${req.department} Department` : ''}.</p>
    <p>During their tenure, ${req.employeeName.split(' ')[0] || 'the employee'} has demonstrated professionalism, dedication, and a high standard of work. We wish them continued success in their future endeavours.</p>
    <p>This letter is issued upon request for whatever purpose it may serve.</p>
    ${signature(company)}
  </body></html>`;
}

// ── Employment Certificate ─────────────────────────────────────────────────────
export function employmentCertificateLetter(req, company) {
  const purposeNote = req.purpose ? ` for the purpose of <span class="highlight">${req.purpose}</span>` : '';
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Employment Certificate</title>${baseStyle()}</head><body>
    ${letterhead(company, '-EMP')}
    <h2>EMPLOYMENT CERTIFICATE</h2>
    <p>To Whom It May Concern,</p>
    <p>This is to certify that <span class="highlight">${req.employeeName}</span> is currently employed with
    <span class="highlight">${company?.name || 'our company'}</span>
    ${req.joinDate ? `since <span class="highlight">${req.joinDate}</span>` : ''}
    as a <span class="highlight">${req.jobTitle || 'Employee'}</span>
    ${req.department ? `in the <span class="highlight">${req.department}</span> Department` : ''}.</p>
    <p>This letter is issued${purposeNote} upon the employee's request.</p>
    ${signature(company)}
  </body></html>`;
}

// ── Salary Transfer Letter ─────────────────────────────────────────────────────
export function salaryTransferLetter(req, company) {
  const gross = (req.basicSalary || 0) + (req.allowance || 0);
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Salary Transfer Letter</title>${baseStyle()}</head><body>
    ${letterhead(company, '-STL')}
    <h2>SALARY TRANSFER LETTER</h2>
    <p>To: The Branch Manager</p>
    <p style="margin-bottom:20px;">Subject: <strong>Salary Transfer Request — ${req.employeeName}</strong></p>
    <p>Dear Sir / Madam,</p>
    <p>This is to inform you that <span class="highlight">${req.employeeName}</span>, employed as
    <span class="highlight">${req.jobTitle || 'Employee'}</span> at <span class="highlight">${company?.name || 'our company'}</span>,
    receives a monthly salary of <span class="highlight">AED ${gross.toLocaleString('en-AE', {minimumFractionDigits:2})}</span>.</p>
    <p>We request you to kindly process the salary transfer to the employee's account and provide all banking facilities as may be required.</p>
    <p>Please do not hesitate to contact us for any further information.</p>
    ${signature(company)}
  </body></html>`;
}

// ── Router ────────────────────────────────────────────────────────────────────
export function generateLetterHTML(req, company) {
  switch (req.letterType) {
    case 'Salary Certificate — Bank':
    case 'Salary Certificate — Embassy':
    case 'Salary Certificate — Personal Use':
      return salaryCertificateLetter(req, company);
    case 'NOC (No Objection Certificate)':
      return nocLetter(req, company);
    case 'Experience Letter':
      return experienceLetter(req, company);
    case 'Employment Certificate':
      return employmentCertificateLetter(req, company);
    case 'Salary Transfer Letter':
      return salaryTransferLetter(req, company);
    default:
      return salaryCertificateLetter(req, company);
  }
}

export function printLetter(req, company) {
  const html = generateLetterHTML(req, company);
  const win = window.open('', '_blank');
  if (!win) { alert('Please allow pop-ups to print letters.'); return; }
  win.document.write(html);
  win.document.close();
  win.focus();
  setTimeout(() => win.print(), 400);
}

export const LETTER_TYPES = [
  'Salary Certificate — Bank',
  'Salary Certificate — Embassy',
  'Salary Certificate — Personal Use',
  'NOC (No Objection Certificate)',
  'Experience Letter',
  'Employment Certificate',
  'Salary Transfer Letter',
];
