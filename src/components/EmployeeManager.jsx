import { useState, useEffect, useRef } from 'react';
import { Users, Plus, Pencil, Trash2, X, Check, Upload, AlertCircle, Search, FileDown, Info } from 'lucide-react';
import { getEmployees, saveEmployee, saveEmployees, deleteEmployee } from '../utils/storage';
import { parseCSV, readFileAsText } from '../utils/csvImport';

// ── CSV column spec ──────────────────────────────────────────────────────────
const CSV_COLUMNS = [
  { col: 'A (0)',  header: 'No',                  required: false, example: '1',                    note: 'Employee sequence number' },
  { col: 'B (1)',  header: 'Month',                required: false, example: 'May 2026',             note: 'Payroll month label (ignored on import)' },
  { col: 'C (2)',  header: 'Name',                 required: true,  example: 'John Smith',           note: 'Full employee name' },
  { col: 'D (3)',  header: 'Labor Card No',        required: true,  example: '10003048635715',       note: 'MOL ID — must be 10+ digits' },
  { col: 'E (4)',  header: 'Bank',                 required: false, example: 'ENBD',                 note: 'Bank short name' },
  { col: 'F (5)',  header: 'Bank / Routing Code',  required: true,  example: '302620122',            note: 'WPS routing / agent code' },
  { col: 'G (6)',  header: 'Bank Account No',      required: true,  example: 'AE080260001014950445301', note: 'IBAN or account number' },
  { col: 'H (7)',  header: 'Basic',                required: true,  example: '5000.00',              note: 'Basic salary (AED)' },
  { col: 'I (8)',  header: 'Allowance',            required: false, example: '3000.00',              note: 'Fixed monthly allowance (AED)' },
  { col: 'J (9)',  header: 'Increment',            required: false, example: '0',                    note: 'Increment amount (AED)' },
  { col: 'K (10)', header: 'Bonus / Incentive',    required: false, example: '0',                    note: 'Bonus (AED)' },
  { col: 'L (11)', header: 'Other Pay',            required: false, example: '0',                    note: 'Other additions (AED)' },
  { col: 'M (12)', header: 'DU Deduction',         required: false, example: '0',                    note: 'DU phone deduction (AED)' },
  { col: 'N (13)', header: 'Salary Deduction',     required: false, example: '0',                    note: 'Salary deduction (AED)' },
  { col: 'O (14)', header: 'Loan Deduction',       required: false, example: '0',                    note: 'Loan repayment (AED)' },
  { col: 'P (15)', header: 'Other Deduction',      required: false, example: '0',                    note: 'Other deductions (AED)' },
  { col: 'Q (16)', header: 'WPS BASIC',            required: false, example: '5000.00',              note: 'WPS basic (overrides col H if present)' },
  { col: 'R (17)', header: 'WPS ALLOW',            required: false, example: '3000.00',              note: 'WPS allowance (overrides col I if present)' },
  { col: 'S (18)', header: 'TOTAL',                required: false, example: '8000.00',              note: 'Total salary (informational)' },
];

function downloadTemplate() {
  const header = CSV_COLUMNS.map(c => c.header).join(',');
  const example = CSV_COLUMNS.map(c => `"${c.example}"`).join(',');
  const blob = new Blob([header + '\n' + example + '\n'], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'employee_import_template.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ── CSV Format Guide Modal ───────────────────────────────────────────────────
function CSVFormatModal({ onClose, onProceed }) {
  return (
    <div className="modal-overlay" style={{ zIndex: 1100 }}>
      <div className="modal" style={{ maxWidth: 780, width: '95vw' }}>
        <div className="modal-header">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Info size={18} /> CSV Import Format
          </h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="modal-body" style={{ padding: '0 0 4px' }}>
          <p style={{ padding: '12px 24px 4px', color: 'var(--gray-600)', fontSize: 13 }}>
            Your CSV file must have the following columns <strong>in this exact order</strong> (row 1 = header, row 2+ = data).
            Columns marked <span style={{ color: 'var(--danger)', fontWeight: 600 }}>required</span> must have values for a row to be imported.
          </p>

          <div style={{ overflowX: 'auto', padding: '8px 24px 16px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: 'var(--gray-50)', borderBottom: '2px solid var(--gray-200)' }}>
                  <th style={thStyle}>Column</th>
                  <th style={thStyle}>Header Name</th>
                  <th style={thStyle}>Required</th>
                  <th style={thStyle}>Example Value</th>
                  <th style={{ ...thStyle, minWidth: 200 }}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {CSV_COLUMNS.map((c, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--gray-100)', background: c.required ? 'rgba(239,68,68,0.03)' : 'white' }}>
                    <td style={{ ...tdStyle, fontFamily: 'monospace', color: 'var(--gray-500)' }}>{c.col}</td>
                    <td style={{ ...tdStyle, fontWeight: c.required ? 600 : 400 }}>{c.header}</td>
                    <td style={{ ...tdStyle, textAlign: 'center' }}>
                      {c.required
                        ? <span style={{ color: 'var(--danger)', fontWeight: 700 }}>✓ Yes</span>
                        : <span style={{ color: 'var(--gray-400)' }}>No</span>}
                    </td>
                    <td style={{ ...tdStyle, fontFamily: 'monospace', color: 'var(--primary)' }}>{c.example}</td>
                    <td style={{ ...tdStyle, color: 'var(--gray-500)' }}>{c.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ margin: '0 24px 16px', padding: '10px 14px', background: 'var(--gray-50)', borderRadius: 8, fontSize: 12, color: 'var(--gray-600)', borderLeft: '3px solid var(--primary)' }}>
            <strong>Tips:</strong> Export your salary spreadsheet as CSV (File → Save As → CSV). Rows without a valid 10+ digit Labor Card No are skipped automatically.
            Existing employees are matched by Labor Card No and updated; new ones are added.
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={downloadTemplate}>
            <FileDown size={15} /> Download Template
          </button>
          <div style={{ flex: 1 }} />
          <button className="btn btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={onProceed}>
            <Upload size={15} /> Choose CSV File
          </button>
        </div>
      </div>
    </div>
  );
}

const thStyle = { padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--gray-700)', whiteSpace: 'nowrap' };
const tdStyle = { padding: '6px 10px', verticalAlign: 'top' };

const EMPTY_EMP = {
  empNo: '',
  name: '',
  molId: '',
  bankName: '',
  bankRoutingCode: '',
  iban: '',
  basicSalary: '',
  allowance: '',
  active: true,
};

function EmployeeModal({ employee, onSave, onClose }) {
  const [form, setForm]     = useState(employee || EMPTY_EMP);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Required';
    if (!form.molId.trim()) e.molId = 'Required';
    if (!/^\d{10,15}$/.test(form.molId.trim())) e.molId = 'Must be 10-15 digits';
    if (!form.bankRoutingCode.trim()) e.bankRoutingCode = 'Required';
    if (!form.iban.trim()) e.iban = 'Required';
    if (!form.basicSalary || isNaN(form.basicSalary) || Number(form.basicSalary) < 0) e.basicSalary = 'Must be a positive number';
    if (form.allowance !== '' && (isNaN(form.allowance) || Number(form.allowance) < 0)) e.allowance = 'Must be a positive number';
    return e;
  };

  const handleSave = async () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    setSaving(true);
    try {
      await onSave({
        ...form,
        basicSalary: parseFloat(form.basicSalary),
        allowance: form.allowance !== '' ? parseFloat(form.allowance) : 0,
      });
    } finally {
      setSaving(false);
    }
  };

  const f = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: undefined }));
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h3>{employee?.id ? 'Edit Employee' : 'Add Employee'}</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="modal-body">
          <div className="form-grid form-grid-2">
            <div className="form-group">
              <label>Employee No.</label>
              <input className="form-control" value={form.empNo} onChange={e => f('empNo', e.target.value)} placeholder="e.g. 1001" />
            </div>
            <div className="form-group">
              <label>Full Name *</label>
              <input className="form-control" value={form.name} onChange={e => f('name', e.target.value)} placeholder="e.g. John Smith" />
              {errors.name && <span className="text-danger text-sm">{errors.name}</span>}
            </div>
            <div className="form-group" style={{gridColumn:'1/-1'}}>
              <label>MOL Employee ID (Labor Card No.) *</label>
              <input className="form-control font-mono" value={form.molId} onChange={e => f('molId', e.target.value.trim())} placeholder="e.g. 10003048635715" />
              {errors.molId && <span className="text-danger text-sm">{errors.molId}</span>}
              <span className="hint">Unique ID provided by Ministry of Labour</span>
            </div>
            <div className="form-group">
              <label>Bank Name</label>
              <input className="form-control" value={form.bankName} onChange={e => f('bankName', e.target.value)} placeholder="e.g. ENBD" />
            </div>
            <div className="form-group">
              <label>Bank / Routing Code *</label>
              <input className="form-control font-mono" value={form.bankRoutingCode} onChange={e => f('bankRoutingCode', e.target.value.trim())} placeholder="e.g. 302620122" />
              {errors.bankRoutingCode && <span className="text-danger text-sm">{errors.bankRoutingCode}</span>}
            </div>
            <div className="form-group" style={{gridColumn:'1/-1'}}>
              <label>IBAN / Account Number *</label>
              <input className="form-control font-mono" value={form.iban} onChange={e => f('iban', e.target.value.trim())} placeholder="e.g. AE080260001014950445301" />
              {errors.iban && <span className="text-danger text-sm">{errors.iban}</span>}
              <span className="hint">23-digit IBAN or card number for exchange houses</span>
            </div>
            <div className="form-group">
              <label>Basic Salary (AED) *</label>
              <input className="form-control" type="number" min="0" step="0.01" value={form.basicSalary} onChange={e => f('basicSalary', e.target.value)} placeholder="e.g. 5000" />
              {errors.basicSalary && <span className="text-danger text-sm">{errors.basicSalary}</span>}
            </div>
            <div className="form-group">
              <label>Allowance (AED)</label>
              <input className="form-control" type="number" min="0" step="0.01" value={form.allowance ?? ''} onChange={e => f('allowance', e.target.value)} placeholder="e.g. 8000" />
              {errors.allowance && <span className="text-danger text-sm">{errors.allowance}</span>}
              <span className="hint">Fixed monthly allowance — pre-filled in every payroll run</span>
            </div>
            <div className="form-group">
              <label>Status</label>
              <select className="form-control" value={form.active ? 'active' : 'inactive'} onChange={e => f('active', e.target.value === 'active')}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            <Check size={15} />{saving ? 'Saving…' : 'Save Employee'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function EmployeeManager() {
  const [employees, setEmployees]   = useState([]);
  const [loading, setLoading]       = useState(true);
  const [modal, setModal]           = useState(null); // null | 'add' | {employee}
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting]     = useState(false);
  const [search, setSearch]         = useState('');
  const [importMsg, setImportMsg]   = useState(null);
  const [dragOver, setDragOver]     = useState(false);
  const [showFormatGuide, setShowFormatGuide] = useState(false);
  const fileRef = useRef();

  useEffect(() => {
    getEmployees().then(emps => {
      setEmployees(emps);
      setLoading(false);
    });
  }, []);

  const handleSaveEmployee = async (emp) => {
    try {
      const saved = await saveEmployee(emp);
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
      await deleteEmployee(id);
      setEmployees(prev => prev.filter(e => e.id !== id));
      setDeleteConfirm(null);
    } catch (err) {
      console.error('Delete employee failed:', err);
      alert('Failed to delete employee: ' + err.message);
    } finally {
      setDeleting(false);
    }
  };

  const handleCSVImport = async (file) => {
    try {
      const text = await readFileAsText(file);
      const { employees: imported } = parseCSV(text);
      if (!imported.length) {
        setImportMsg({ type: 'warning', text: 'No valid employee rows found in CSV.' });
        return;
      }

      // Merge: update existing by molId, add new
      let updated = [...employees];
      let added = 0, updated_count = 0;
      for (const imp of imported) {
        const existing = updated.find(e => e.molId === imp.molId);
        if (existing) {
          Object.assign(existing, { ...imp, id: existing.id, active: existing.active });
          updated_count++;
        } else {
          updated.push({ ...imp, active: true });
          added++;
        }
      }

      await saveEmployees(updated);
      // Reload from DB to get proper UUIDs
      const fresh = await getEmployees();
      setEmployees(fresh);
      setImportMsg({ type: 'success', text: `Import complete: ${added} added, ${updated_count} updated.` });
      setTimeout(() => setImportMsg(null), 5000);
    } catch (err) {
      setImportMsg({ type: 'danger', text: 'Failed to import CSV: ' + err.message });
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
    if (file) {
      // If a file is dropped directly, import it (user already knows the format)
      handleCSVImport(file);
    }
  };

  const filtered = employees.filter(e =>
    !search ||
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.molId.includes(search) ||
    e.empNo?.includes(search)
  );

  const activeCount = employees.filter(e => e.active).length;

  return (
    <div>
      <div className="page-header">
        <h2>Employee Master Data</h2>
        <div className="page-header-actions">
          <button className="btn btn-outline" onClick={() => setShowFormatGuide(true)}>
            <Upload size={15} /> Import CSV
          </button>
          <input ref={fileRef} type="file" accept=".csv" style={{display:'none'}} onChange={onFileChange} />
          <button className="btn btn-primary" onClick={() => setModal('add')}>
            <Plus size={15} /> Add Employee
          </button>
        </div>
      </div>

      <div className="page-body">
        {importMsg && (
          <div className={`alert alert-${importMsg.type} mb-4`}>
            <AlertCircle size={16} />
            {importMsg.text}
          </div>
        )}

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Employees</div>
            <div className="stat-value">{employees.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Active</div>
            <div className="stat-value" style={{color:'var(--success)'}}>{activeCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Inactive</div>
            <div className="stat-value" style={{color:'var(--gray-400)'}}>{employees.length - activeCount}</div>
          </div>
        </div>

        {/* CSV Drop Zone */}
        <div
          className={`file-upload-area mb-4 ${dragOver ? 'drag-over' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => setShowFormatGuide(true)}
        >
          <Upload size={24} style={{margin:'0 auto 8px', display:'block'}} />
          <p style={{fontWeight:500}}>Drop your salary CSV here or click to browse</p>
          <p className="text-sm mt-1">Click to see the required format, then choose your file</p>
        </div>

        <div className="card">
          <div className="card-header">
            <h3><Users size={16} style={{display:'inline',marginRight:6}} />Employees ({filtered.length})</h3>
            <div style={{position:'relative'}}>
              <Search size={14} style={{position:'absolute',left:9,top:'50%',transform:'translateY(-50%)',color:'var(--gray-400)'}} />
              <input
                className="form-control"
                style={{paddingLeft:28, width:220}}
                placeholder="Search name, MOL ID..."
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <div className="empty-state">
              <p style={{color:'var(--gray-400)'}}>Loading employees…</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <Users size={40} />
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
                    <th>Bank</th>
                    <th>Routing Code</th>
                    <th>IBAN</th>
                    <th>Basic (AED)</th>
                    <th>Allowance (AED)</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(emp => (
                    <tr key={emp.id}>
                      <td className="text-muted">{emp.empNo || '—'}</td>
                      <td style={{fontWeight:500}}>{emp.name}</td>
                      <td className="font-mono text-sm">{emp.molId}</td>
                      <td>{emp.bankName || '—'}</td>
                      <td className="font-mono text-sm">{emp.bankRoutingCode}</td>
                      <td className="font-mono text-sm truncate" style={{maxWidth:180}}>{emp.iban}</td>
                      <td className="text-right">{Number(emp.basicSalary).toLocaleString('en-AE', {minimumFractionDigits:2})}</td>
                      <td className="text-right">{emp.allowance ? Number(emp.allowance).toLocaleString('en-AE', {minimumFractionDigits:2}) : '—'}</td>
                      <td>
                        <span className={`badge ${emp.active ? 'badge-green' : 'badge-gray'}`}>
                          {emp.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td>
                        <div className="flex gap-2">
                          <button className="btn btn-ghost btn-icon btn-sm" title="Edit" onClick={() => setModal(emp)}>
                            <Pencil size={14} />
                          </button>
                          <button className="btn btn-ghost btn-icon btn-sm text-danger" title="Delete" onClick={() => setDeleteConfirm(emp.id)}>
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
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
          onSave={handleSaveEmployee}
          onClose={() => setModal(null)}
        />
      )}

      {/* Delete Confirm */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{maxWidth:400}}>
            <div className="modal-header">
              <h3>Delete Employee</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setDeleteConfirm(null)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete this employee? This cannot be undone.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)} disabled={deleting}>Cancel</button>
              <button className="btn btn-danger" onClick={() => handleDelete(deleteConfirm)} disabled={deleting}>
                <Trash2 size={14} /> {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
