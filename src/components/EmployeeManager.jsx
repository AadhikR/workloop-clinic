import { useState, useEffect, useRef, Component } from 'react';
import {
  Users, Plus, Trash2, X, Upload, AlertCircle, Search,
  FileDown, Info, Download, History, AlertTriangle, Calculator,
  UserCheck, CalendarClock, ClipboardList
} from 'lucide-react';
import { getEmployees, saveEmployee, saveEmployees, archiveEmployee, getJobHistory, addJobHistoryEntry } from '../utils/storage';
import { parseCSV, readFileAsText } from '../utils/csvImport';
import { formatDateUAE, formatAED, daysUntil, expiryBadgeClass } from '../utils/uaeValidators';
import { calculateGratuity } from '../utils/gratuityCalculator';
import { useCompany } from '../context/CompanyContext';
import EmployeeModal from './EmployeeModal';
import EndOfServiceScreen from './EndOfServiceScreen';
import OffboardingModal from './OffboardingModal';

// ── CSV column spec ──────────────────────────────────────────────────────────
const CSV_COLUMNS = [
  { col:'A (0)',  header:'No',               required:false, example:'1',                       note:'Employee sequence number' },
  { col:'B (1)',  header:'Month',             required:false, example:'May 2026',                note:'Payroll month label (ignored on import)' },
  { col:'C (2)',  header:'Name',              required:true,  example:'John Smith',              note:'Full employee name' },
  { col:'D (3)',  header:'Labor Card No',     required:true,  example:'10003048635715',          note:'MOL ID — must be 10+ digits' },
  { col:'E (4)',  header:'Bank',              required:false, example:'ENBD',                    note:'Bank short name' },
  { col:'F (5)',  header:'Bank / Routing Code',required:true, example:'302620122',               note:'WPS routing / agent code' },
  { col:'G (6)',  header:'Bank Account No',   required:true,  example:'AE080260001014950445301', note:'IBAN or account number' },
  { col:'H (7)',  header:'Basic',             required:true,  example:'5000.00',                 note:'Basic salary (AED)' },
  { col:'I (8)',  header:'Allowance',         required:false, example:'3000.00',                 note:'Fixed monthly allowance (AED)' },
  { col:'J (9)',  header:'Increment',         required:false, example:'0',                       note:'Increment amount (AED)' },
  { col:'K (10)', header:'Bonus / Incentive', required:false, example:'0',                       note:'Bonus (AED)' },
  { col:'L (11)', header:'Other Pay',         required:false, example:'0',                       note:'Other additions (AED)' },
  { col:'M (12)', header:'DU Deduction',      required:false, example:'0',                       note:'DU phone deduction (AED)' },
  { col:'N (13)', header:'Salary Deduction',  required:false, example:'0',                       note:'Salary deduction (AED)' },
  { col:'O (14)', header:'Loan Deduction',    required:false, example:'0',                       note:'Loan repayment (AED)' },
  { col:'P (15)', header:'Other Deduction',   required:false, example:'0',                       note:'Other deductions (AED)' },
  { col:'Q (16)', header:'WPS BASIC',         required:false, example:'5000.00',                 note:'WPS basic (overrides col H if present)' },
  { col:'R (17)', header:'WPS ALLOW',         required:false, example:'3000.00',                 note:'WPS allowance (overrides col I if present)' },
  { col:'S (18)', header:'TOTAL',             required:false, example:'8000.00',                 note:'Total salary (informational)' },
];

function downloadTemplate() {
  const header  = CSV_COLUMNS.map(c => c.header).join(',');
  const example = CSV_COLUMNS.map(c => `"${c.example}"`).join(',');
  const blob = new Blob([header + '\n' + example + '\n'], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'employee_import_template.csv'; a.click();
  URL.revokeObjectURL(url);
}

function exportToCSV(employees) {
  const headers = ['Emp No','Name','MOL ID','Job Title','Department','Status','Basic Salary','Housing','Transport','Total Package','Bank','IBAN','Nationality','Visa Type','Visa Expiry','Passport Expiry','Emirates ID','EID Expiry','Labour Card Expiry'];
  const rows = employees.map(e => [
    e.empNo, e.name, e.molId, e.jobTitle, e.department, e.employmentStatus,
    e.basicSalary, e.housingAllowance, e.transportAllowance,
    (parseFloat(e.basicSalary)||0)+(parseFloat(e.housingAllowance)||0)+(parseFloat(e.transportAllowance)||0)+(parseFloat(e.otherAllowances)||0),
    e.bankName, e.iban, e.nationality, e.visaType,
    formatDateUAE(e.visaExpiry), formatDateUAE(e.passportExpiry),
    e.emiratesId, formatDateUAE(e.emiratesIdExpiry), formatDateUAE(e.labourCardExpiry),
  ]);
  const csv = [headers, ...rows].map(r => r.map(v => `"${v ?? ''}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'employees_export.csv'; a.click();
  URL.revokeObjectURL(url);
}

// ── CSV Format Guide Modal ───────────────────────────────────────────────────
function CSVFormatModal({ onClose, onProceed }) {
  const thS = { padding:'8px 10px', textAlign:'left', fontWeight:600, color:'var(--gray-700)', whiteSpace:'nowrap' };
  const tdS = { padding:'6px 10px', verticalAlign:'top' };
  return (
    <div className="modal-overlay" style={{ zIndex:1100 }}>
      <div className="modal" style={{ maxWidth:780, width:'95vw' }}>
        <div className="modal-header">
          <h3 style={{ display:'flex', alignItems:'center', gap:8 }}><Info size={18}/> CSV Import Format</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>
        <div className="modal-body" style={{ padding:'0 0 4px' }}>
          <p style={{ padding:'12px 24px 4px', color:'var(--gray-600)', fontSize:13 }}>
            Your CSV must have the following columns <strong>in this exact order</strong>.
          </p>
          <div style={{ overflowX:'auto', padding:'8px 24px 16px' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
              <thead>
                <tr style={{ background:'var(--gray-50)', borderBottom:'2px solid var(--gray-200)' }}>
                  <th style={thS}>Column</th><th style={thS}>Header</th><th style={thS}>Required</th><th style={thS}>Example</th><th style={{ ...thS, minWidth:200 }}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {CSV_COLUMNS.map((c,i) => (
                  <tr key={i} style={{ borderBottom:'1px solid var(--gray-100)', background:c.required?'rgba(239,68,68,0.03)':'white' }}>
                    <td style={{ ...tdS, fontFamily:'monospace', color:'var(--gray-500)' }}>{c.col}</td>
                    <td style={{ ...tdS, fontWeight:c.required?600:400 }}>{c.header}</td>
                    <td style={{ ...tdS, textAlign:'center' }}>{c.required?<span style={{ color:'var(--danger)', fontWeight:700 }}>✓ Yes</span>:<span style={{ color:'var(--gray-400)' }}>No</span>}</td>
                    <td style={{ ...tdS, fontFamily:'monospace', color:'var(--primary)' }}>{c.example}</td>
                    <td style={{ ...tdS, color:'var(--gray-500)' }}>{c.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ margin:'0 24px 16px', padding:'10px 14px', background:'var(--gray-50)', borderRadius:8, fontSize:12, color:'var(--gray-600)', borderLeft:'3px solid var(--primary)' }}>
            <strong>Tips:</strong> Export your salary spreadsheet as CSV. Rows without a valid 10+ digit Labor Card No are skipped.
            Existing employees are matched by Labor Card No and updated; new ones are added.
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={downloadTemplate}><FileDown size={15}/> Download Template</button>
          <div style={{ flex:1 }}/>
          <button className="btn btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={onProceed}><Upload size={15}/> Choose CSV File</button>
        </div>
      </div>
    </div>
  );
}

// ── Expiry Badge ─────────────────────────────────────────────────────────────
function ExpiryBadge({ date }) {
  if (!date) return <span className="badge badge-gray">—</span>;
  const days = daysUntil(date);
  if (days === null) return <span className="badge badge-gray">—</span>;
  const cls   = expiryBadgeClass(days);
  const label = days < 0 ? `Expired ${Math.abs(days)}d ago` : days === 0 ? 'Today' : `${days}d`;
  return <span className={`badge ${cls}`} title={formatDateUAE(date)}>{formatDateUAE(date)} ({label})</span>;
}

// ── Status Badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const map = { Active:'badge-green', Probation:'badge-blue', 'On Leave':'badge-amber', Terminated:'badge-gray' };
  return <span className={`badge ${map[status]||'badge-gray'}`}>{status||'Active'}</span>;
}

// ── Document Expiry Panel ────────────────────────────────────────────────────
function DocumentExpiryPanel({ employees }) {
  const today = new Date();
  const warnings = [];

  employees.forEach(emp => {
    if (emp.employmentStatus === 'Terminated') return;
    const checks = [
      { label:'Visa',        date:emp.visaExpiry,        warnDays:60 },
      { label:'Passport',    date:emp.passportExpiry,    warnDays:60 },
      { label:'Emirates ID', date:emp.emiratesIdExpiry,  warnDays:30 },
      { label:'Labour Card', date:emp.labourCardExpiry,  warnDays:60 },
    ];
    checks.forEach(({ label, date, warnDays }) => {
      if (!date) return;
      const days = daysUntil(date);
      if (days !== null && days <= 90) {
        warnings.push({ emp: emp.name, empId: emp.id, label, date, daysLeft: days, warnDays });
      }
    });
  });

  warnings.sort((a, b) => a.daysLeft - b.daysLeft);

  if (warnings.length === 0) {
    return (
      <div className="card mb-4">
        <div className="card-header">
          <h3><AlertTriangle size={16} style={{ display:'inline', marginRight:6 }}/>Document Expiry — Next 90 Days</h3>
        </div>
        <div style={{ padding:'20px', textAlign:'center', color:'var(--success)', fontSize:13 }}>
          ✓ No documents expiring in the next 90 days
        </div>
      </div>
    );
  }

  const groups = {
    Visas:        warnings.filter(w => w.label === 'Visa'),
    Passports:    warnings.filter(w => w.label === 'Passport'),
    'Emirates IDs': warnings.filter(w => w.label === 'Emirates ID'),
    'Labour Cards': warnings.filter(w => w.label === 'Labour Card'),
  };

  return (
    <div className="card mb-4">
      <div className="card-header">
        <h3><AlertTriangle size={16} style={{ display:'inline', marginRight:6 }}/>Document Expiry — Next 90 Days</h3>
        <span className="badge badge-red">{warnings.length} alert{warnings.length !== 1 ? 's' : ''}</span>
      </div>
      <div style={{ padding:'0 20px 16px' }}>
        {Object.entries(groups).map(([groupName, items]) => {
          if (!items.length) return null;
          return (
            <div key={groupName} style={{ marginTop:16 }}>
              <div style={{ fontWeight:600, fontSize:12, textTransform:'uppercase', letterSpacing:'0.05em', color:'var(--gray-500)', marginBottom:8 }}>
                {groupName} ({items.length})
              </div>
              <div style={{ display:'flex', flexWrap:'wrap', gap:8 }}>
                {items.map((w, i) => {
                  const cls = expiryBadgeClass(w.daysLeft);
                  return (
                    <div key={i} style={{ display:'flex', alignItems:'center', gap:8, padding:'6px 12px', borderRadius:6, background:'var(--gray-50)', border:'1px solid var(--gray-200)', fontSize:12.5 }}>
                      <span className={`badge ${cls}`} style={{ fontSize:11 }}>
                        {w.daysLeft < 0 ? 'EXPIRED' : `${w.daysLeft}d`}
                      </span>
                      <span style={{ fontWeight:500 }}>{w.emp}</span>
                      <span style={{ color:'var(--gray-500)' }}>{formatDateUAE(w.date)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Job History Modal ────────────────────────────────────────────────────────
function JobHistoryModal({ employee, onClose }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getJobHistory(employee.id).then(h => {
      setHistory(h);
      setLoading(false);
    });
  }, [employee.id]);

  return (
    <div className="modal-overlay">
      <div className="modal modal-lg">
        <div className="modal-header">
          <h3><History size={16} style={{ marginRight:6 }}/>Job History — {employee.name}</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>
        <div className="modal-body">
          {loading ? (
            <p style={{ color:'var(--gray-400)', textAlign:'center' }}>Loading…</p>
          ) : history.length === 0 ? (
            <p style={{ color:'var(--gray-500)', textAlign:'center' }}>No job history recorded yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th><th>Change Type</th><th>From</th><th>To</th><th>Reason</th><th>By</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(h => (
                    <tr key={h.id}>
                      <td className="text-sm">{formatDateUAE(h.changedAt?.split('T')[0])}</td>
                      <td><span className="badge badge-blue">{h.changeType}</span></td>
                      <td className="text-muted text-sm">{h.oldValue || '—'}</td>
                      <td style={{ fontWeight:500 }}>{h.newValue || '—'}</td>
                      <td className="text-muted text-sm">{h.reason || '—'}</td>
                      <td className="text-muted text-sm">{h.changedBy || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ── Error Boundary ───────────────────────────────────────────────────────────
class EmpErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40 }}>
          <div className="alert alert-danger">
            <AlertCircle size={16}/>
            <div>
              <strong>Failed to load Employees page.</strong>
              <br/>
              <span style={{ fontSize: 12, fontFamily: 'monospace' }}>{String(this.state.error)}</span>
              <br/>
              <span style={{ fontSize: 12 }}>
                If this is a new deployment, please run the database migration first:
                open <code>supabase_migration_existing_db.sql</code> in Supabase SQL Editor and click Run.
              </span>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Main EmployeeManager ─────────────────────────────────────────────────────
// ── ProbationModal (Feature 11) ───────────────────────────────────────────────
function ProbationModal({ employee, onClose, onConfirm, onExtend, onTerminate }) {
  const [mode, setMode]         = useState(null); // null | 'extend' | 'terminate'
  const [newEndDate, setNewEndDate] = useState('');
  const [busy, setBusy]         = useState(false);

  const today = new Date();
  const days  = employee.probationEndDate
    ? Math.ceil((new Date(employee.probationEndDate) - today) / 86400000)
    : null;

  const act = async (fn) => {
    setBusy(true);
    try { await fn(); } finally { setBusy(false); }
  };

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: 460 }}>
        <div className="modal-header">
          <h3><UserCheck size={16} style={{ marginRight: 6 }} />Probation Actions</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>
        <div className="modal-body">
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--gray-900)' }}>{employee.name}</div>
            <div style={{ fontSize: 13, color: 'var(--gray-500)', marginTop: 2 }}>{employee.jobTitle || 'Employee'}{employee.department ? ` · ${employee.department}` : ''}</div>
            {employee.probationEndDate && (
              <div style={{ marginTop: 10, padding: '8px 12px', background: days !== null && days <= 0 ? 'var(--danger-light)' : 'var(--warning-light, #fffbeb)', borderRadius: 8, fontSize: 13 }}>
                <CalendarClock size={13} style={{ marginRight: 5, display: 'inline' }} />
                Probation ends: <strong>{employee.probationEndDate}</strong>
                {days !== null && (
                  <span style={{ marginLeft: 8, fontWeight: 700, color: days <= 0 ? 'var(--danger)' : days <= 7 ? 'var(--warning)' : 'var(--gray-600)' }}>
                    {days < 0 ? `(${Math.abs(days)}d overdue)` : days === 0 ? '(ends today)' : `(${days}d remaining)`}
                  </span>
                )}
                {employee.probationExtended && <span className="badge badge-amber" style={{ marginLeft: 8, fontSize: 10 }}>Extended</span>}
              </div>
            )}
          </div>

          {mode === 'extend' && (
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>New Probation End Date</label>
              <input
                className="form-control"
                type="date"
                value={newEndDate}
                min={new Date().toISOString().slice(0, 10)}
                onChange={e => setNewEndDate(e.target.value)}
                autoFocus
              />
            </div>
          )}

          {mode === 'terminate' && (
            <div className="alert alert-danger" style={{ borderRadius: 10 }}>
              <AlertTriangle size={14} />
              <div>
                <strong>Terminate employment?</strong><br/>
                <span style={{ fontSize: 13 }}>
                  Under UAE Labour Law, employees on probation can be terminated with 14 days' notice. This will archive the employee record and cannot be undone.
                </span>
              </div>
            </div>
          )}
        </div>
        <div className="modal-footer" style={{ justifyContent: 'space-between' }}>
          {mode === null && (
            <>
              <button className="btn btn-outline btn-sm" onClick={onClose}>Cancel</button>
              <div className="flex gap-2">
                <button className="btn btn-outline btn-sm" style={{ color: 'var(--warning)' }} onClick={() => setMode('extend')}>
                  <CalendarClock size={13} /> Extend
                </button>
                <button className="btn btn-outline btn-sm text-danger" onClick={() => setMode('terminate')}>
                  <Trash2 size={13} /> Terminate
                </button>
                <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => act(onConfirm)}>
                  <UserCheck size={13} /> {busy ? 'Saving…' : 'Confirm Active'}
                </button>
              </div>
            </>
          )}
          {mode === 'extend' && (
            <>
              <button className="btn btn-outline btn-sm" onClick={() => setMode(null)}>Back</button>
              <button className="btn btn-primary btn-sm" disabled={!newEndDate || busy} onClick={() => act(() => onExtend(newEndDate))}>
                <CalendarClock size={13} /> {busy ? 'Saving…' : 'Save Extension'}
              </button>
            </>
          )}
          {mode === 'terminate' && (
            <>
              <button className="btn btn-outline btn-sm" onClick={() => setMode(null)}>Back</button>
              <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => act(onTerminate)}>
                <Trash2 size={13} /> {busy ? 'Terminating…' : 'Confirm Terminate'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function EmployeeManagerInner() {
  const { activeCompanyId } = useCompany();
  const [employees, setEmployees]         = useState([]);
  const [loading, setLoading]             = useState(true);
  const [modal, setModal]                 = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting]           = useState(false);
  const [search, setSearch]               = useState('');
  const [filterStatus, setFilterStatus]   = useState('');
  const [filterDept, setFilterDept]       = useState('');
  const [importMsg, setImportMsg]         = useState(null);
  const [dragOver, setDragOver]           = useState(false);
  const [showFormatGuide, setShowFormatGuide] = useState(false);
  const [historyEmp, setHistoryEmp]       = useState(null);
  const [eosEmp, setEosEmp]               = useState(null); // end-of-service screen
  const [probationEmp, setProbationEmp]   = useState(null); // probation actions modal
  const [offboardingEmp, setOffboardingEmp] = useState(null); // offboarding checklist modal (Feature 13)
  const [activeTab, setActiveTab]         = useState('list'); // 'list' | 'expiry'
  const fileRef = useRef();

  useEffect(() => {
    setLoading(true);
    getEmployees(activeCompanyId).then(emps => {
      setEmployees(emps);
      setLoading(false);
    });
  }, [activeCompanyId]); // Re-load when the active branch changes

  const handleSaveEmployee = async (emp) => {
    try {
      const old = emp.id ? employees.find(e => e.id === emp.id) : null;
      // Assign to the active branch when creating a new employee
      const empWithCompany = emp.companyId ? emp : { ...emp, companyId: activeCompanyId };
      const saved = await saveEmployee(empWithCompany);

      if (old) {
        const checks = [
          { field: 'basicSalary',      type: 'salary_change' },
          { field: 'jobTitle',         type: 'title_change' },
          { field: 'department',       type: 'department_change' },
          { field: 'employmentStatus', type: 'status_change' },
        ];
        const changed = checks.filter(c => String(old[c.field] ?? '') !== String(emp[c.field] ?? ''));
        if (changed.length > 0) {
          try {
            await Promise.all(changed.map(c => addJobHistoryEntry(emp.id, c.type, old[c.field], emp[c.field])));
          } catch (histErr) {
            console.warn('Job history not saved (table may need RLS policy):', histErr.message);
          }
        }
      }

      setEmployees(prev =>
        emp.id
          ? prev.map(e => e.id === emp.id ? saved : e)
          : [...prev, saved]
      );
      setModal(null);
    } catch (err) {
      console.error('Save employee failed:', err);
      alert('Failed to save employee: ' + err.message);
    }
  };

  const handleDelete = async (id) => {
    setDeleting(true);
    try {
      await archiveEmployee(id);
      setEmployees(prev => prev.map(e => e.id === id
        ? { ...e, active: false, employmentStatus: 'Terminated' }
        : e
      ));
      setDeleteConfirm(null);
    } catch (err) {
      console.error('Archive employee failed:', err);
      alert('Failed to archive employee: ' + err.message);
    } finally {
      setDeleting(false);
    }
  };

  const handleCSVImport = async (file) => {
    try {
      const text = await readFileAsText(file);
      const { employees: imported } = parseCSV(text);
      if (!imported.length) {
        setImportMsg({ type:'warning', text:'No valid employee rows found in CSV.' });
        return;
      }
      let updated = [...employees];
      let added = 0, updatedCount = 0;
      for (const imp of imported) {
        const existing = updated.find(e => e.molId === imp.molId);
        if (existing) {
          Object.assign(existing, { ...imp, id: existing.id, active: existing.active });
          updatedCount++;
        } else {
          updated.push({ ...imp, active: true });
          added++;
        }
      }
      await saveEmployees(updated);
      const fresh = await getEmployees(activeCompanyId);
      setEmployees(fresh);
      setImportMsg({ type:'success', text:`Import complete: ${added} added, ${updatedCount} updated.` });
      setTimeout(() => setImportMsg(null), 5000);
    } catch (err) {
      setImportMsg({ type:'danger', text:'Failed to import CSV: ' + err.message });
    }
  };

  const onFileChange = (e) => {
    const file = e.target.files[0];
    if (file) handleCSVImport(file);
    e.target.value = '';
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleCSVImport(file);
  };

  // Unique departments for filter
  const departments = [...new Set(employees.map(e => e.department).filter(Boolean))].sort();

  const filtered = employees.filter(e => {
    const matchSearch = !search ||
      e.name?.toLowerCase().includes(search.toLowerCase()) ||
      e.molId?.includes(search) ||
      e.empNo?.includes(search) ||
      e.department?.toLowerCase().includes(search.toLowerCase());
    const matchStatus = !filterStatus || e.employmentStatus === filterStatus;
    const matchDept   = !filterDept   || e.department === filterDept;
    return matchSearch && matchStatus && matchDept;
  });

  // Defensive: employmentStatus may be undefined on pre-migration records
  const activeCount     = employees.filter(e => (e.employmentStatus || 'Active') !== 'Terminated' && e.active !== false).length;
  const terminatedCount = employees.filter(e => (e.employmentStatus || 'Active') === 'Terminated').length;

  // Count expiry alerts — defensive: handle employees without new fields (pre-migration)
  const expiryAlerts = employees.reduce((count, emp) => {
    if ((emp.employmentStatus || 'Active') === 'Terminated') return count;
    const checks = [emp.visaExpiry, emp.passportExpiry, emp.emiratesIdExpiry, emp.labourCardExpiry];
    return count + checks.filter(d => {
      if (!d) return false;
      try { const days = daysUntil(d); return days !== null && days <= 60; } catch { return false; }
    }).length;
  }, 0);

  return (
    <div>
      <div className="page-header">
        <h2>Employees</h2>
        <div className="page-header-actions">
          <button className="btn btn-outline btn-sm" onClick={() => exportToCSV(employees)}>
            <Download size={14}/> Export CSV
          </button>
          <button className="btn btn-outline btn-sm" onClick={() => setShowFormatGuide(true)}>
            <Upload size={14}/> Import CSV
          </button>
          <input ref={fileRef} type="file" accept=".csv" style={{ display:'none' }} onChange={onFileChange}/>
          <button className="btn btn-primary" onClick={() => setModal('add')}>
            <Plus size={15}/> Add Employee
          </button>
        </div>
      </div>

      <div className="page-body">
        {importMsg && (
          <div className={`alert alert-${importMsg.type} mb-4`}>
            <AlertCircle size={16}/>{importMsg.text}
          </div>
        )}

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Employees</div>
            <div className="stat-value">{employees.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Active</div>
            <div className="stat-value" style={{ color:'var(--success)' }}>{activeCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Terminated</div>
            <div className="stat-value" style={{ color:'var(--gray-400)' }}>{terminatedCount}</div>
          </div>
          <div className="stat-card" style={{ cursor:'pointer' }} onClick={() => setActiveTab('expiry')}>
            <div className="stat-label">Doc Expiry Alerts</div>
            <div className="stat-value" style={{ color: expiryAlerts > 0 ? 'var(--danger)' : 'var(--success)' }}>{expiryAlerts}</div>
            <div className="stat-sub">within 60 days</div>
          </div>
        </div>

        {/* Tab bar */}
        <div className="tabs" style={{ marginBottom:16 }}>
          <button className={`tab-btn ${activeTab==='list'?'active':''}`} onClick={() => setActiveTab('list')}>
            <Users size={13} style={{ marginRight:5 }}/>Employee List
          </button>
          <button className={`tab-btn ${activeTab==='expiry'?'active':''}`} onClick={() => setActiveTab('expiry')}>
            <AlertTriangle size={13} style={{ marginRight:5 }}/>
            Document Expiry {expiryAlerts > 0 && <span className="badge badge-red" style={{ marginLeft:6, fontSize:10 }}>{expiryAlerts}</span>}
          </button>
        </div>

        {/* ── EXPIRY TAB ── */}
        {activeTab === 'expiry' && (
          <DocumentExpiryPanel employees={employees}/>
        )}

        {/* ── LIST TAB ── */}
        {activeTab === 'list' && (
          <>
            {/* CSV Drop Zone */}
            <div
              className={`file-upload-area mb-4 ${dragOver?'drag-over':''}`}
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => setShowFormatGuide(true)}
            >
              <Upload size={24} style={{ margin:'0 auto 8px', display:'block' }}/>
              <p style={{ fontWeight:500 }}>Drop your salary CSV here or click to browse</p>
              <p className="text-sm mt-1">Click to see the required format, then choose your file</p>
            </div>

            <div className="card">
              <div className="card-header">
                <h3><Users size={16} style={{ display:'inline', marginRight:6 }}/>Employees ({filtered.length})</h3>
                <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
                  {/* Search */}
                  <div style={{ position:'relative' }}>
                    <Search size={14} style={{ position:'absolute', left:9, top:'50%', transform:'translateY(-50%)', color:'var(--gray-400)' }}/>
                    <input
                      className="form-control"
                      style={{ paddingLeft:28, width:200 }}
                      placeholder="Search name, MOL ID, dept…"
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                    />
                  </div>
                  {/* Status filter */}
                  <select className="form-control" style={{ width:140 }} value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                    <option value="">All Statuses</option>
                    <option value="Active">Active</option>
                    <option value="Probation">Probation</option>
                    <option value="On Leave">On Leave</option>
                    <option value="Terminated">Terminated</option>
                  </select>
                  {/* Department filter */}
                  {departments.length > 0 && (
                    <select className="form-control" style={{ width:160 }} value={filterDept} onChange={e => setFilterDept(e.target.value)}>
                      <option value="">All Departments</option>
                      {departments.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  )}
                </div>
              </div>

              {loading ? (
                <div className="empty-state"><p style={{ color:'var(--gray-400)' }}>Loading employees…</p></div>
              ) : filtered.length === 0 ? (
                <div className="empty-state">
                  <Users size={40}/>
                  <h3>No employees yet</h3>
                  <p>Add employees manually or import from a salary CSV file.</p>
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>No.</th>
                        <th>Name</th>
                        <th>MOL ID</th>
                        <th>Job Title</th>
                        <th>Department</th>
                        <th>Status</th>
                        <th>Basic (AED)</th>
                        <th>Total Pkg (AED)</th>
                        <th>Bank</th>
                        <th>Visa Expiry</th>
                        <th>EID Expiry</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map(emp => {
                        const totalPkg = (parseFloat(emp.basicSalary)||0) + (parseFloat(emp.housingAllowance)||0) + (parseFloat(emp.transportAllowance)||0) + (parseFloat(emp.otherAllowances)||0);
                        return (
                          <tr key={emp.id}>
                            <td className="text-muted">{emp.empNo || '—'}</td>
                            <td style={{ fontWeight:500 }}>{emp.name}</td>
                            <td className="font-mono text-sm">{emp.molId}</td>
                            <td className="text-sm">{emp.jobTitle || '—'}</td>
                            <td className="text-sm">{emp.department || '—'}</td>
                            <td><StatusBadge status={emp.employmentStatus}/></td>
                            <td className="text-right">{Number(emp.basicSalary).toLocaleString('en-AE', { minimumFractionDigits:2 })}</td>
                            <td className="text-right">{totalPkg > 0 ? totalPkg.toLocaleString('en-AE', { minimumFractionDigits:2 }) : '—'}</td>
                            <td className="text-sm">{emp.bankName || '—'}</td>
                            <td><ExpiryBadge date={emp.visaExpiry}/></td>
                            <td><ExpiryBadge date={emp.emiratesIdExpiry}/></td>
                            <td>
                              <div className="flex gap-2">
                                <button
                                  className="btn btn-ghost btn-icon btn-sm"
                                  title="Edit employee"
                                  onClick={() => setModal(emp)}
                                >
                                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                                </button>
                                <button
                                  className="btn btn-ghost btn-icon btn-sm"
                                  title="Job history"
                                  onClick={() => setHistoryEmp(emp)}
                                >
                                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                                </button>
                                <button
                                  className="btn btn-ghost btn-icon btn-sm"
                                  title="End-of-service settlement"
                                  style={{ color: 'var(--warning)' }}
                                  onClick={() => setEosEmp(emp)}
                                >
                                  <Calculator size={13}/>
                                </button>
                                {emp.employmentStatus === 'Probation' && (
                                  <button
                                    className="btn btn-ghost btn-icon btn-sm"
                                    title="Probation actions"
                                    style={{ color: 'var(--primary)' }}
                                    onClick={() => setProbationEmp(emp)}
                                  >
                                    <UserCheck size={13}/>
                                  </button>
                                )}
                                {emp.employmentStatus === 'Terminated' && (
                                  <button
                                    className="btn btn-ghost btn-icon btn-sm"
                                    title="Offboarding checklist"
                                    style={{ color: '#6366f1' }}
                                    onClick={() => setOffboardingEmp(emp)}
                                  >
                                    <ClipboardList size={13}/>
                                  </button>
                                )}
                                <button
                                  className="btn btn-ghost btn-icon btn-sm text-danger"
                                  title="Delete employee"
                                  onClick={() => setDeleteConfirm(emp.id)}
                                >
                                  <Trash2 size={13}/>
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* CSV Format Guide Modal */}
      {showFormatGuide && (
        <CSVFormatModal
          onClose={() => setShowFormatGuide(false)}
          onProceed={() => { setShowFormatGuide(false); fileRef.current.click(); }}
        />
      )}

      {/* Add/Edit Modal */}
      {modal && (
        <EmployeeModal
          employee={modal === 'add' ? null : modal}
          allEmployees={employees}
          onSave={handleSaveEmployee}
          onClose={() => setModal(null)}
        />
      )}

      {/* Job History Modal */}
      {historyEmp && (
        <JobHistoryModal
          employee={historyEmp}
          onClose={() => setHistoryEmp(null)}
        />
      )}

      {/* End-of-Service Settlement */}
      {eosEmp && (
        <EndOfServiceScreen
          employee={eosEmp}
          onClose={() => setEosEmp(null)}
        />
      )}

      {/* Probation Actions Modal (Feature 11) */}
      {probationEmp && (
        <ProbationModal
          employee={probationEmp}
          onClose={() => setProbationEmp(null)}
          onConfirm={async () => {
            const updated = { ...probationEmp, employmentStatus: 'Active', probationEndDate: '' };
            await saveEmployee(updated);
            await addJobHistoryEntry(probationEmp.id, 'probation_confirmed', 'Probation', 'Active', 'Probation period confirmed — employee moved to Active');
            setEmployees(prev => prev.map(e => e.id === probationEmp.id ? updated : e));
            setProbationEmp(null);
          }}
          onExtend={async (newEndDate) => {
            const updated = { ...probationEmp, probationEndDate: newEndDate, probationExtended: true };
            await saveEmployee(updated);
            await addJobHistoryEntry(probationEmp.id, 'probation_extended', probationEmp.probationEndDate || '—', newEndDate, 'Probation period extended');
            setEmployees(prev => prev.map(e => e.id === probationEmp.id ? updated : e));
            setProbationEmp(null);
          }}
          onTerminate={async () => {
            await archiveEmployee(probationEmp.id);
            await addJobHistoryEntry(probationEmp.id, 'probation_terminated', 'Probation', 'Terminated', 'Probation not passed — employment terminated');
            setEmployees(prev => prev.map(e => e.id === probationEmp.id ? { ...e, active: false, employmentStatus: 'Terminated' } : e));
            setProbationEmp(null);
          }}
        />
      )}

      {/* Offboarding Checklist Modal (Feature 13) */}
      {offboardingEmp && (
        <OffboardingModal
          employee={offboardingEmp}
          onClose={() => setOffboardingEmp(null)}
        />
      )}

      {/* Delete Confirm */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth:400 }}>
            <div className="modal-header">
              <h3>Archive Employee</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setDeleteConfirm(null)}><X size={18}/></button>
            </div>
            <div className="modal-body">
              <p>This employee will be marked as <strong>Terminated</strong> and hidden from active lists. Their payroll history and records are retained.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)} disabled={deleting}>Cancel</button>
              <button className="btn btn-danger" onClick={() => handleDelete(deleteConfirm)} disabled={deleting}>
                <Trash2 size={14}/> {deleting ? 'Archiving…' : 'Archive Employee'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function EmployeeManager() {
  return (
    <EmpErrorBoundary>
      <EmployeeManagerInner />
    </EmpErrorBoundary>
  );
}
