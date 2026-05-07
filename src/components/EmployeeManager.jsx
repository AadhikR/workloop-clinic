import { useState, useEffect, useRef } from 'react';
import { Users, Plus, Pencil, Trash2, X, Check, Upload, AlertCircle, Search } from 'lucide-react';
import { getEmployees, saveEmployee, saveEmployees, deleteEmployee } from '../utils/storage';
import { parseCSV, readFileAsText } from '../utils/csvImport';

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
    if (file) handleCSVImport(file);
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
          <button className="btn btn-outline" onClick={() => fileRef.current.click()}>
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
          onClick={() => fileRef.current.click()}
        >
          <Upload size={24} style={{margin:'0 auto 8px', display:'block'}} />
          <p style={{fontWeight:500}}>Drop your salary CSV here or click to browse</p>
          <p className="text-sm mt-1">Imports employee master data from your monthly salary spreadsheet</p>
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
