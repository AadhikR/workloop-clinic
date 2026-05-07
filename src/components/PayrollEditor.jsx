import { useState, useRef, useEffect, useCallback } from 'react';
import { Download, Eye, Upload, AlertCircle, Plus, ChevronDown, CheckCircle } from 'lucide-react';
import { generateSIF, generateSIFFilename } from '../utils/sifGenerator';
import { parseCSV, readFileAsText } from '../utils/csvImport';
import { savePayroll } from '../utils/storage';
import AllowDeductPanel, { computeFinalAllowance } from './AllowDeductPanel';
import SIFPreviewModal from './SIFPreviewModal';

function getMonthName(month) {
  return ['January','February','March','April','May','June',
          'July','August','September','October','November','December'][month - 1];
}

function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function normaliseEntry(e) {
  return {
    allowance: e.allowance ?? e.variableAllowance ?? 0,
    increment: e.increment ?? 0,
    bonus: e.bonus ?? 0,
    otherPay: e.otherPay ?? 0,
    additionalAllowances: e.additionalAllowances ?? [],
    deductions: e.deductions ?? [],
    ...e,
  };
}

export default function PayrollEditor({ payroll, employees, company, onSave, onBack }) {
  const [entries, setEntries] = useState(payroll.entries.map(normaliseEntry));
  const [meta, setMeta] = useState({
    paymentDate: payroll.paymentDate,
    sequenceNo: payroll.sequenceNo,
    scrBankRoutingCode: payroll.scrBankRoutingCode,
    description: payroll.description,
  });
  const [preview, setPreview] = useState(null);
  const [importMsg, setImportMsg] = useState(null);
  const [showPanel, setShowPanel] = useState(false);
  const [autoSaved, setAutoSaved] = useState(false);
  const autoSaveTimer = useRef(null);
  const fileRef = useRef();

  // Auto-save helper — debounced 800ms after last change
  const triggerAutoSave = useCallback((updatedEntries, updatedMeta) => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(async () => {
      const p = {
        ...payroll,
        ...updatedMeta,
        sequenceNo: updatedMeta.sequenceNo,
        entries: updatedEntries.map(e => ({
          ...e,
          variableAllowance: computeFinalAllowance(e),
        })),
      };
      try {
        await savePayroll(p);
        onSave(p);
        setAutoSaved(true);
        setTimeout(() => setAutoSaved(false), 2000);
      } catch (err) {
        console.error('Auto-save failed:', err);
      }
    }, 800);
  }, [payroll, onSave]);

  const [year, month] = payroll.period.split('-').map(Number);
  const daysInMonth = getDaysInMonth(year, month);

  const updateEntry = (idx, field, value) => {
    setEntries(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      triggerAutoSave(next, meta);
      return next;
    });
  };

  const getEmp = (id) => employees.find(e => e.id === id);
  const activeEntries = entries.filter(e => !e.excluded);

  const totalBasic      = activeEntries.reduce((s, e) => s + (parseFloat(e.basicSalary) || 0), 0);
  const totalAllowance  = activeEntries.reduce((s, e) => s + (parseFloat(e.allowance) || 0), 0);
  const totalIncrement  = activeEntries.reduce((s, e) => s + (parseFloat(e.increment) || 0), 0);
  const totalBonus      = activeEntries.reduce((s, e) => s + (parseFloat(e.bonus) || 0), 0);
  const totalOtherPay   = activeEntries.reduce((s, e) => s + (parseFloat(e.otherPay) || 0), 0);
  const totalDuCost     = activeEntries.reduce((s, e) => s + (parseFloat(e.duCost) || 0), 0);
  const totalAddAllow   = activeEntries.reduce((s, e) => s + (e.additionalAllowances || []).reduce((a, x) => a + (parseFloat(x.amount) || 0), 0), 0);
  const totalDeductions = activeEntries.reduce((s, e) => s + (e.deductions || []).reduce((a, x) => a + (parseFloat(x.amount) || 0), 0), 0);
  const totalFinal      = activeEntries.reduce((s, e) => s + computeFinalAllowance(e), 0);
  const grandTotal      = totalBasic + totalFinal;

  const buildPayroll = () => ({
    ...payroll,
    ...meta,
    sequenceNo: parseInt(meta.sequenceNo),
    entries: entries.map(e => ({
      ...e,
      variableAllowance: computeFinalAllowance(e),
    })),
  });

  const doDownload = (p) => {
    const content = generateSIF(company, employees, p);
    const filename = generateSIFFilename(company, p);
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
    return { content, filename };
  };

  const handlePreview = () => {
    const p = buildPayroll();
    const content = generateSIF(company, employees, p);
    const filename = generateSIFFilename(company, p);
    setPreview({ content, filename, payroll: p });
  };

  const handleDownload = () => {
    const p = buildPayroll();
    doDownload(p);
    onSave({ ...p, status: 'generated' });
  };

  const handleMetaChange = (field, value) => {
    setMeta(prev => {
      const next = { ...prev, [field]: value };
      triggerAutoSave(entries, next);
      return next;
    });
  };

  const handleSaveDraft = () => {
    onSave({ ...buildPayroll(), status: payroll.status === 'generated' ? 'generated' : 'draft' });
  };

  const handleCSVImport = async (file) => {
    try {
      const text = await readFileAsText(file);
      const { payrollEntries } = parseCSV(text);
      if (!payrollEntries.length) {
        setImportMsg({ type: 'warning', text: 'No valid rows found in CSV.' });
        return;
      }
      let matched = 0;
      const next = entries.map(entry => {
        const emp = getEmp(entry.employeeId);
        if (!emp) return entry;
        const csvRow = payrollEntries.find(r => r.molId === emp.molId);
        if (csvRow) {
          matched++;
          return {
            ...entry,
            basicSalary: csvRow.basicSalary || entry.basicSalary,
            allowance: csvRow.variableAllowance || entry.allowance || 0,
          };
        }
        return entry;
      });
      setEntries(next);
      setImportMsg({ type: 'success', text: `Updated ${matched} employee entries from CSV.` });
      setTimeout(() => setImportMsg(null), 5000);
    } catch (err) {
      setImportMsg({ type: 'danger', text: 'Failed to parse CSV: ' + err.message });
    }
  };

  const canGenerate = company?.molEmployerId && meta.paymentDate && meta.scrBankRoutingCode && activeEntries.length > 0;

  const hdrClickable = {
    cursor: 'pointer',
    color: 'var(--primary)',
    textDecoration: 'underline dotted',
    display: 'flex',
    alignItems: 'center',
    gap: 3,
    whiteSpace: 'nowrap',
  };

  return (
    <div>
      {/* ── Header ── */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <button className="btn btn-ghost btn-sm" onClick={onBack}>← Back</button>
          <h2>
            Payroll: {getMonthName(month)} {year}
            <span
              className={`badge ${payroll.status === 'generated' ? 'badge-green' : 'badge-yellow'}`}
              style={{ marginLeft: 8 }}
            >
              {payroll.status === 'generated' ? 'Generated' : 'Draft'}
            </span>
          </h2>
        </div>
        <div className="page-header-actions">
          {autoSaved && (
            <span className="auto-save-indicator">
              <CheckCircle size={14} /> Auto-saved
            </span>
          )}
          <button className="btn btn-outline btn-sm" onClick={() => fileRef.current.click()}>
            <Upload size={14} /> Import CSV
          </button>
          <input
            ref={fileRef} type="file" accept=".csv" style={{ display: 'none' }}
            onChange={e => { if (e.target.files[0]) handleCSVImport(e.target.files[0]); e.target.value = ''; }}
          />
          <button className="btn btn-outline btn-sm" onClick={handleSaveDraft}>Save Draft</button>
          <button className="btn btn-outline btn-sm" onClick={handlePreview} disabled={!canGenerate}>
            <Eye size={14} /> Preview SIF
          </button>
          <button className="btn btn-success btn-sm" onClick={handleDownload} disabled={!canGenerate}>
            <Download size={14} /> Download SIF
          </button>
        </div>
      </div>

      <div className="page-body">
        {importMsg && (
          <div className={`alert alert-${importMsg.type} mb-4`}>
            <AlertCircle size={16} /> {importMsg.text}
          </div>
        )}
        {!company?.molEmployerId && (
          <div className="alert alert-danger mb-4">
            <AlertCircle size={16} />
            Company MOL Employer ID is not set. Please configure it in <strong>Company Settings</strong> first.
          </div>
        )}

        {/* ── Payroll Meta ── */}
        <div className="card mb-4">
          <div className="card-header"><h3>Payroll Run Details</h3></div>
          <div className="card-body">
            <div className="form-grid form-grid-3">
              <div className="form-group">
                <label>Payment Date</label>
                <input className="form-control" type="date" value={meta.paymentDate}
                  onChange={e => handleMetaChange('paymentDate', e.target.value)} />
              </div>
              <div className="form-group">
                <label>File Creation Time (HHMM)</label>
                <input className="form-control font-mono" maxLength={4} value={meta.sequenceNo}
                  placeholder="e.g. 1430"
                  onChange={e => handleMetaChange('sequenceNo', e.target.value.replace(/\D/g, '').slice(0, 4))} />
                <span className="hint">4-digit time in HHMM format — used in SCR line &amp; filename</span>
              </div>
              <div className="form-group">
                <label>SCR Bank Routing Code</label>
                <input className="form-control font-mono" value={meta.scrBankRoutingCode}
                  onChange={e => handleMetaChange('scrBankRoutingCode', e.target.value.trim())} />
              </div>
              <div className="form-group" style={{ gridColumn: '1/-1' }}>
                <label>Description</label>
                <input className="form-control" value={meta.description}
                  onChange={e => handleMetaChange('description', e.target.value)} />
              </div>
            </div>
          </div>
        </div>

        {/* ── Stats ── */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Employees</div>
            <div className="stat-value">{activeEntries.length}</div>
            <div className="stat-sub">{entries.length - activeEntries.length} excluded</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Basic</div>
            <div className="stat-value">{totalBasic.toLocaleString('en-AE')}</div>
            <div className="stat-sub">AED</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total WPS Allowance</div>
            <div className="stat-value">{totalFinal.toLocaleString('en-AE')}</div>
            <div className="stat-sub">AED (Final Allowance)</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Grand Total (WPS)</div>
            <div className="stat-value" style={{ color: 'var(--primary)' }}>
              {grandTotal.toLocaleString('en-AE')}
            </div>
            <div className="stat-sub">AED — {daysInMonth} days</div>
          </div>
        </div>

        {/* ── Entry Table ── */}
        <div className="card">
          <div className="card-header">
            <h3>Employee Salary Entries</h3>
            <div className="flex items-center gap-2">
              <button className="btn btn-outline btn-sm" onClick={() => setShowPanel(true)}>
                <Plus size={13} /> Allowances &amp; Deductions
              </button>
              <span className="text-sm text-muted">
                Period: {getMonthName(month)} {year} (1–{daysInMonth})
              </span>
            </div>
          </div>

          <div className="table-wrap payroll-table">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 36 }}>✓</th>
                  <th>Name</th>
                  <th>MOL ID</th>
                  <th style={{ width: 130 }}>Basic</th>
                  <th style={{ width: 130 }}>Allowance</th>
                  <th style={{ width: 110 }}>Increment</th>
                  <th style={{ width: 130 }}>Bonus/Incentive</th>
                  <th style={{ width: 110 }}>Other Pay</th>
                  <th style={{ width: 110 }}>DU Cost</th>
                  <th
                    style={{ width: 100 }}
                    title="Click to add named additional allowances per employee"
                    onClick={() => setShowPanel(true)}
                  >
                    <span style={hdrClickable}>
                      Add. Allow <ChevronDown size={11} />
                    </span>
                  </th>
                  <th
                    style={{ width: 100 }}
                    title="Click to add named deductions per employee"
                    onClick={() => setShowPanel(true)}
                  >
                    <span style={{ ...hdrClickable, color: 'var(--danger)' }}>
                      Deductions <ChevronDown size={11} />
                    </span>
                  </th>
                  <th style={{ width: 110, background: 'var(--primary-light)', color: 'var(--primary-dark)' }}>
                    Final Allow.
                  </th>
                  <th style={{ width: 110 }}>Total (AED)</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, idx) => {
                  const emp = getEmp(entry.employeeId);
                  if (!emp) return null;
                  const finalAllow = computeFinalAllowance(entry);
                  const addAllow = (entry.additionalAllowances || []).reduce((s, a) => s + (parseFloat(a.amount) || 0), 0);
                  const deds = (entry.deductions || []).reduce((s, d) => s + (parseFloat(d.amount) || 0), 0);
                  const total = (parseFloat(entry.basicSalary) || 0) + finalAllow;
                  return (
                    <tr key={entry.employeeId} className={entry.excluded ? 'excluded' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          checked={!entry.excluded}
                          onChange={() => updateEntry(idx, 'excluded', !entry.excluded)}
                        />
                      </td>
                      <td style={{ fontWeight: 500 }}>{emp.name}</td>
                      <td className="font-mono text-sm">{emp.molId}</td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.basicSalary} disabled={entry.excluded}
                          onChange={e => updateEntry(idx, 'basicSalary', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.allowance} disabled={entry.excluded}
                          onChange={e => updateEntry(idx, 'allowance', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.increment} disabled={entry.excluded}
                          onChange={e => updateEntry(idx, 'increment', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.bonus} disabled={entry.excluded}
                          onChange={e => updateEntry(idx, 'bonus', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="1"
                          value={entry.otherPay} disabled={entry.excluded}
                          onChange={e => updateEntry(idx, 'otherPay', e.target.value)} />
                      </td>
                      <td>
                        <input type="number" min="0" step="0.01"
                          value={entry.duCost ?? ''}
                          disabled={entry.excluded}
                          placeholder="0.00"
                          onChange={e => updateEntry(idx, 'duCost', e.target.value)} />
                      </td>
                      <td
                        className="text-right text-sm"
                        style={{ color: addAllow > 0 ? 'var(--success)' : 'var(--gray-400)', cursor: 'pointer' }}
                        onClick={() => setShowPanel(true)}
                        title="Click to edit"
                      >
                        {addAllow > 0 ? `+${addAllow.toLocaleString('en-AE')}` : '—'}
                      </td>
                      <td
                        className="text-right text-sm"
                        style={{ color: deds > 0 ? 'var(--danger)' : 'var(--gray-400)', cursor: 'pointer' }}
                        onClick={() => setShowPanel(true)}
                        title="Click to edit"
                      >
                        {deds > 0 ? `-${deds.toLocaleString('en-AE')}` : '—'}
                      </td>
                      <td
                        className="text-right font-bold"
                        style={{
                          background: 'var(--primary-light)',
                          color: entry.excluded ? 'var(--gray-400)' : 'var(--primary-dark)',
                        }}
                      >
                        {finalAllow.toLocaleString('en-AE')}
                      </td>
                      <td
                        className="text-right font-bold"
                        style={{ color: entry.excluded ? 'var(--gray-400)' : 'var(--gray-800)' }}
                      >
                        {total.toLocaleString('en-AE')}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr style={{ background: 'var(--gray-50)', fontWeight: 700, fontSize: 13 }}>
                  <td colSpan={3} style={{ textAlign: 'right', paddingRight: 12, color: 'var(--gray-600)' }}>TOTALS</td>
                  <td style={{ paddingLeft: 8, textAlign: 'right' }}>{totalBasic.toLocaleString('en-AE')}</td>
                  <td className="text-right">{totalAllowance.toLocaleString('en-AE')}</td>
                  <td className="text-right">{totalIncrement.toLocaleString('en-AE')}</td>
                  <td className="text-right">{totalBonus.toLocaleString('en-AE')}</td>
                  <td className="text-right">{totalOtherPay.toLocaleString('en-AE')}</td>
                  <td className="text-right" style={{ color: 'var(--gray-700)' }}>
                    {totalDuCost.toLocaleString('en-AE')}
                  </td>
                  <td className="text-right" style={{ color: 'var(--success)' }}>
                    {totalAddAllow > 0 ? `+${totalAddAllow.toLocaleString('en-AE')}` : '—'}
                  </td>
                  <td className="text-right" style={{ color: 'var(--danger)' }}>
                    {totalDeductions > 0 ? `-${totalDeductions.toLocaleString('en-AE')}` : '—'}
                  </td>
                  <td className="text-right" style={{ background: 'var(--primary-light)', color: 'var(--primary-dark)' }}>
                    {totalFinal.toLocaleString('en-AE')}
                  </td>
                  <td className="text-right" style={{ color: 'var(--primary)' }}>
                    {grandTotal.toLocaleString('en-AE')}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>

      {/* ── Panels / Modals ── */}
      {showPanel && (
        <AllowDeductPanel
          entries={entries}
          employees={employees}
          onClose={() => setShowPanel(false)}
          onSave={(updated) => { setEntries(updated); setShowPanel(false); }}
        />
      )}

      {preview && (
        <SIFPreviewModal
          sifContent={preview.content}
          filename={preview.filename}
          onClose={() => setPreview(null)}
          onDownload={() => {
            doDownload(preview.payroll);
            onSave({ ...preview.payroll, status: 'generated' });
            setPreview(null);
          }}
        />
      )}
    </div>
  );
}
