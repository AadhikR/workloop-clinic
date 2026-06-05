import { useState, useEffect } from 'react';
import { FileText, Plus, Trash2, X, Download, AlertCircle, Calendar, ChevronRight, Copy } from 'lucide-react';
import { getPayrolls, getEmployees, getCompany, savePayroll, deletePayroll } from '../utils/storage';
import { useCompany } from '../context/CompanyContext';
import { generateSIF, generateSIFFilename } from '../utils/sifGenerator';

function getMonthName(month) {
  return ['January','February','March','April','May','June',
          'July','August','September','October','November','December'][month - 1];
}

export default function PayrollList({ onEdit }) {
  const { activeCompanyId } = useCompany();
  const [payrolls, setPayrolls]         = useState([]);
  const [employees, setEmployees]       = useState([]);
  const [company, setCompany]           = useState(null);
  const [loading, setLoading]           = useState(true);
  const [showNew, setShowNew]           = useState(false);
  const [showRepeat, setShowRepeat]     = useState(false);
  const [repeatSource, setRepeatSource] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting]         = useState(false);
  const [newForm, setNewForm]           = useState(null);
  const [repeatForm, setRepeatForm]     = useState(null);
  const [formErrors, setFormErrors]     = useState({});
  const [repeatErrors, setRepeatErrors] = useState({});
  const [creating, setCreating]         = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([getPayrolls(activeCompanyId), getEmployees(activeCompanyId), getCompany(activeCompanyId)]).then(([p, e, c]) => {
      setPayrolls(p);
      setEmployees(e);
      setCompany(c);
      setLoading(false);
    });
  }, [activeCompanyId]); // Re-load when the active branch changes

  const openNew = () => {
    const now = new Date();
    const hhmm = String(now.getHours()).padStart(2, '0') + String(now.getMinutes()).padStart(2, '0');
    setNewForm({
      period: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
      paymentDate: '',
      sequenceNo: hhmm,
      scrBankRoutingCode: company?.defaultBankRoutingCode || '',
      description: '',
    });
    setFormErrors({});
    setShowNew(true);
  };

  const fChange = (field, val) => {
    setNewForm(p => {
      const next = { ...p, [field]: val };
      if (field === 'period') {
        const [y, m] = val.split('-').map(Number);
        if (y && m) {
          const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          next.description = `Sal for ${names[m-1]} ${y}`;
        }
      }
      return next;
    });
    setFormErrors(p => ({ ...p, [field]: undefined }));
  };

  const handleCreate = async () => {
    const e = {};
    if (!newForm.period) e.period = 'Required';
    if (!newForm.paymentDate) e.paymentDate = 'Required';
    if (!newForm.sequenceNo || !/^\d{3,4}$/.test(newForm.sequenceNo)) e.sequenceNo = 'Must be 3-4 digit time (HHMM)';
    if (!newForm.scrBankRoutingCode.trim()) e.scrBankRoutingCode = 'Required';
    if (Object.keys(e).length) { setFormErrors(e); return; }

    setCreating(true);
    try {
      const activeEmps = employees.filter(emp => emp.active);
      // Pre-fill salary breakdown from employee profile (housing, transport, allowances)
      const entries = activeEmps.map(emp => ({
        employeeId:         emp.id,
        basicSalary:        emp.basicSalary,
        housingAllowance:   emp.housingAllowance ?? 0,
        transportAllowance: emp.transportAllowance ?? 0,
        allowance:          emp.allowance ?? 0,
        increment:          0,
        bonus:              0,
        otherPay:           0,
        duCost:             0,
        additionalAllowances: [],
        deductions:         [],
        variableAllowance:  0,
        excluded:           false,
      }));

      // Generate a UUID-compatible id for the new payroll
      const id = crypto.randomUUID ? crypto.randomUUID() : (Date.now().toString(36) + Math.random().toString(36).slice(2));

      const payroll = {
        id,
        ...newForm,
        entries,
        createdAt: new Date().toISOString(),
        status: 'draft',
        companyId: activeCompanyId,  // Feature 21: tag payroll to the active branch
      };

      await savePayroll(payroll);
      setPayrolls(prev => [...prev, payroll]);
      setShowNew(false);
      onEdit(payroll);
    } catch (err) {
      console.error('Create payroll failed:', err);
      alert('Failed to create payroll run: ' + err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id) => {
    setDeleting(true);
    try {
      await deletePayroll(id);
      setPayrolls(prev => prev.filter(p => p.id !== id));
      setDeleteConfirm(null);
    } catch (err) {
      console.error('Delete payroll failed:', err);
      alert('Failed to delete payroll run: ' + err.message);
    } finally {
      setDeleting(false);
    }
  };

  const openRepeat = (sourcePayroll) => {
    setRepeatSource(sourcePayroll);
    const now = new Date();
    const hhmm = String(now.getHours()).padStart(2, '0') + String(now.getMinutes()).padStart(2, '0');
    const [sy, sm] = sourcePayroll.period.split('-').map(Number);
    const nextMonth = sm === 12 ? 1 : sm + 1;
    const nextYear  = sm === 12 ? sy + 1 : sy;
    const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    setRepeatForm({
      period: `${nextYear}-${String(nextMonth).padStart(2, '0')}`,
      paymentDate: '',
      sequenceNo: hhmm,
      scrBankRoutingCode: sourcePayroll.scrBankRoutingCode || company?.defaultBankRoutingCode || '',
      description: `Sal for ${names[nextMonth - 1]} ${nextYear}`,
    });
    setRepeatErrors({});
    setShowRepeat(true);
  };

  const handleRepeat = async () => {
    const e = {};
    if (!repeatForm.period) e.period = 'Required';
    if (!repeatForm.paymentDate) e.paymentDate = 'Required';
    if (!repeatForm.sequenceNo || !/^\d{3,4}$/.test(repeatForm.sequenceNo)) e.sequenceNo = 'Must be 3-4 digit time (HHMM)';
    if (!repeatForm.scrBankRoutingCode.trim()) e.scrBankRoutingCode = 'Required';
    if (Object.keys(e).length) { setRepeatErrors(e); return; }

    setCreating(true);
    try {
      const copiedEntries = repeatSource.entries.map(entry => ({
        ...entry,
        variableAllowance: 0,
      }));

      const [y, m] = repeatForm.period.split('-').map(Number);
      const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      const id = crypto.randomUUID ? crypto.randomUUID() : (Date.now().toString(36) + Math.random().toString(36).slice(2));

      const payroll = {
        id,
        ...repeatForm,
        entries: copiedEntries,
        createdAt: new Date().toISOString(),
        status: 'draft',
        description: repeatForm.description || `Sal for ${names[m - 1]} ${y}`,
      };

      await savePayroll(payroll);
      setPayrolls(prev => [...prev, payroll]);
      setShowRepeat(false);
      onEdit(payroll);
    } catch (err) {
      console.error('Repeat payroll failed:', err);
      alert('Failed to create payroll run: ' + err.message);
    } finally {
      setCreating(false);
    }
  };

  const rChange = (field, val) => {
    setRepeatForm(p => {
      const next = { ...p, [field]: val };
      if (field === 'period') {
        const [y, m] = val.split('-').map(Number);
        if (y && m) {
          const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          next.description = `Sal for ${names[m-1]} ${y}`;
        }
      }
      return next;
    });
    setRepeatErrors(p => ({ ...p, [field]: undefined }));
  };

  const handleQuickDownload = async (payroll) => {
    const content  = generateSIF(company, employees, payroll);
    const filename = generateSIFFilename(company, payroll);
    // Use Uint8Array + application/octet-stream — prevents browser line-ending normalisation
    const bytes = new TextEncoder().encode(content);
    const blob = new Blob([bytes], { type: 'application/octet-stream' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);

    const updated = { ...payroll, status: 'generated' };
    try {
      await savePayroll(updated);
      setPayrolls(prev => prev.map(p => p.id === payroll.id ? updated : p));
    } catch (err) {
      console.error('Failed to update payroll status:', err);
    }
  };

  const sortedPayrolls = [...payrolls].sort((a, b) => b.period.localeCompare(a.period));
  const activeEmpCount = employees.filter(e => e.active).length;
  const latestPayroll  = sortedPayrolls[0] || null;

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
        Loading payroll runs…
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h2>Payroll Runs</h2>
        <div className="page-header-actions">
          {latestPayroll && (
            <button className="btn btn-outline" onClick={() => openRepeat(latestPayroll)}>
              <Copy size={15} /> Repeat Last Payroll
            </button>
          )}
          <button className="btn btn-primary" onClick={openNew} disabled={!activeEmpCount}>
            <Plus size={15} /> New Payroll Run
          </button>
        </div>
      </div>

      <div className="page-body">
        {!company?.molEmployerId && (
          <div className="alert alert-warning mb-4">
            <AlertCircle size={16} />
            Please set your <strong>Company MOL Employer ID</strong> in Company Settings before creating payroll runs.
          </div>
        )}
        {activeEmpCount === 0 && (
          <div className="alert alert-warning mb-4">
            <AlertCircle size={16} />
            No active employees found. Please add employees in <strong>Employee Master Data</strong> first.
          </div>
        )}

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Runs</div>
            <div className="stat-value">{payrolls.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Generated</div>
            <div className="stat-value" style={{ color: 'var(--success)' }}>
              {payrolls.filter(p => p.status === 'generated').length}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Drafts</div>
            <div className="stat-value" style={{ color: 'var(--warning)' }}>
              {payrolls.filter(p => p.status !== 'generated').length}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>
              <FileText size={16} style={{ display: 'inline', marginRight: 6 }} />
              Payroll History
            </h3>
          </div>

          {sortedPayrolls.length === 0 ? (
            <div className="empty-state">
              <Calendar size={40} />
              <h3>No payroll runs yet</h3>
              <p>Create your first payroll run to get started.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Payment Date</th>
                    <th>Employees</th>
                    <th>Total (AED)</th>
                    <th>Description</th>
                    <th>Status</th>
                    <th>Approval</th>
                    <th>WPS</th>
                    <th>Run By</th>
                    <th>SIF Filename</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {sortedPayrolls.map(p => {
                    const [y, m]      = p.period.split('-').map(Number);
                    const activeEntries = p.entries.filter(e => !e.excluded);
                    const total       = activeEntries.reduce(
                      (s, e) => s + (parseFloat(e.basicSalary) || 0) + (parseFloat(e.variableAllowance) || 0), 0
                    );
                    const filename = company?.molEmployerId ? generateSIFFilename(company, p) : '—';
                    return (
                      <tr key={p.id} style={{ cursor: 'pointer' }} onClick={() => onEdit(p)}>
                        <td style={{ fontWeight: 600 }}>{getMonthName(m)} {y}</td>
                        <td>{p.paymentDate || '—'}</td>
                        <td>{activeEntries.length}</td>
                        <td className="text-right font-bold">
                          {total.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="text-muted">{p.description}</td>
                        <td>
                          <span className={`badge ${p.status === 'generated' ? 'badge-green' : 'badge-yellow'}`}>
                            {p.status === 'generated' ? 'Generated' : 'Draft'}
                          </span>
                        </td>
                        <td>
                          {p.status !== 'generated' && (() => {
                            const as = p.approvalStatus ?? 'draft';
                            const ab = { draft:'badge-yellow', pending_approval:'badge-blue', approved:'badge-green' };
                            const al = { draft:'Draft', pending_approval:'Pending', approved:'Approved' };
                            return <span className={`badge ${ab[as] ?? 'badge-yellow'}`} style={{ fontSize:11 }}>{al[as] ?? as}</span>;
                          })()}
                          {p.status === 'generated' && <span className="badge badge-green" style={{ fontSize:11 }}>Approved</span>}
                        </td>
                        <td>
                          {p.status === 'generated' && (() => {
                            const wps = p.wpsStatus ?? 'draft';
                            const badges = { draft:'badge-yellow', sif_generated:'badge-blue', submitted:'badge-amber', confirmed:'badge-green', partial_rejection:'badge-amber', failed:'badge-red' };
                            const labels = { draft:'Not Submitted', sif_generated:'SIF Ready', submitted:'Submitted', confirmed:'Confirmed', partial_rejection:'Partial Reject', failed:'Failed' };
                            return <span className={`badge ${badges[wps] ?? 'badge-yellow'}`} style={{ fontSize:11 }}>{labels[wps] ?? wps}</span>;
                          })()}
                        </td>
                        <td className="text-muted text-sm">{p.runBy || '—'}</td>
                        <td className="font-mono text-sm text-muted">{filename}</td>
                        <td onClick={e => e.stopPropagation()}>
                          <div className="flex gap-2">
                            <button
                              className="btn btn-ghost btn-icon btn-sm"
                              title="Open & Edit"
                              onClick={() => onEdit(p)}
                            >
                              <ChevronRight size={14} />
                            </button>
                            {company?.molEmployerId && p.paymentDate && (
                              <button
                                className="btn btn-ghost btn-icon btn-sm text-success"
                                title="Quick Download SIF"
                                onClick={() => handleQuickDownload(p)}
                              >
                                <Download size={14} />
                              </button>
                            )}
                            <button
                              className="btn btn-ghost btn-icon btn-sm text-danger"
                              title="Delete"
                              onClick={() => setDeleteConfirm(p.id)}
                            >
                              <Trash2 size={14} />
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
      </div>

      {/* New Payroll Modal */}
      {showNew && newForm && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3>New Payroll Run</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowNew(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-grid form-grid-2">
                <div className="form-group">
                  <label>Salary Period (Month) *</label>
                  <input className="form-control" type="month" value={newForm.period}
                    onChange={e => fChange('period', e.target.value)} />
                  {formErrors.period && <span className="text-danger text-sm">{formErrors.period}</span>}
                </div>
                <div className="form-group">
                  <label>Payment Date *</label>
                  <input className="form-control" type="date" value={newForm.paymentDate}
                    onChange={e => fChange('paymentDate', e.target.value)} />
                  {formErrors.paymentDate && <span className="text-danger text-sm">{formErrors.paymentDate}</span>}
                  <span className="hint">Date salary is transferred to bank</span>
                </div>
                <div className="form-group">
                  <label>File Creation Time (HHMM) *</label>
                  <input className="form-control font-mono" maxLength={4} value={newForm.sequenceNo}
                    placeholder="e.g. 1430"
                    onChange={e => fChange('sequenceNo', e.target.value.replace(/\D/g, '').slice(0, 4))} />
                  {formErrors.sequenceNo && <span className="text-danger text-sm">{formErrors.sequenceNo}</span>}
                  <span className="hint">Time file is created — used in SCR line &amp; filename</span>
                </div>
                <div className="form-group">
                  <label>SCR Bank Routing Code *</label>
                  <input className="form-control font-mono" value={newForm.scrBankRoutingCode}
                    onChange={e => fChange('scrBankRoutingCode', e.target.value.trim())}
                    placeholder="e.g. 302620122" />
                  {formErrors.scrBankRoutingCode && <span className="text-danger text-sm">{formErrors.scrBankRoutingCode}</span>}
                </div>
                <div className="form-group" style={{ gridColumn: '1/-1' }}>
                  <label>Description</label>
                  <input className="form-control" value={newForm.description}
                    onChange={e => fChange('description', e.target.value)}
                    placeholder="e.g. Sal for Feb 2026" />
                </div>
              </div>
              <div className="alert alert-info mt-3">
                <AlertCircle size={16} />
                <span>
                  Creates a payroll run with all <strong>{activeEmpCount} active employees</strong>.
                  Adjust individual amounts on the next screen.
                </span>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setShowNew(false)} disabled={creating}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
                <Plus size={15} /> {creating ? 'Creating…' : 'Create Payroll Run'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Repeat Last Payroll Modal */}
      {showRepeat && repeatForm && repeatSource && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3><Copy size={16} style={{ display: 'inline', marginRight: 6 }} />Repeat Last Payroll</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowRepeat(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="alert alert-info mb-3">
                <AlertCircle size={16} />
                <span>
                  Copying all salary entries from <strong>{repeatSource.description || repeatSource.period}</strong>.
                  All amounts, allowances, deductions and DU costs will be carried over — you can edit them after creation.
                </span>
              </div>
              <div className="form-grid form-grid-2">
                <div className="form-group">
                  <label>New Salary Period (Month) *</label>
                  <input className="form-control" type="month" value={repeatForm.period}
                    onChange={e => rChange('period', e.target.value)} />
                  {repeatErrors.period && <span className="text-danger text-sm">{repeatErrors.period}</span>}
                </div>
                <div className="form-group">
                  <label>Payment Date *</label>
                  <input className="form-control" type="date" value={repeatForm.paymentDate}
                    onChange={e => rChange('paymentDate', e.target.value)} />
                  {repeatErrors.paymentDate && <span className="text-danger text-sm">{repeatErrors.paymentDate}</span>}
                  <span className="hint">Date salary is transferred to bank</span>
                </div>
                <div className="form-group">
                  <label>File Creation Time (HHMM) *</label>
                  <input className="form-control font-mono" maxLength={4} value={repeatForm.sequenceNo}
                    placeholder="e.g. 1430"
                    onChange={e => rChange('sequenceNo', e.target.value.replace(/\D/g, '').slice(0, 4))} />
                  {repeatErrors.sequenceNo && <span className="text-danger text-sm">{repeatErrors.sequenceNo}</span>}
                  <span className="hint">Time file is created — used in SCR line &amp; filename</span>
                </div>
                <div className="form-group">
                  <label>SCR Bank Routing Code *</label>
                  <input className="form-control font-mono" value={repeatForm.scrBankRoutingCode}
                    onChange={e => rChange('scrBankRoutingCode', e.target.value.trim())}
                    placeholder="e.g. 302620122" />
                  {repeatErrors.scrBankRoutingCode && <span className="text-danger text-sm">{repeatErrors.scrBankRoutingCode}</span>}
                </div>
                <div className="form-group" style={{ gridColumn: '1/-1' }}>
                  <label>Description</label>
                  <input className="form-control" value={repeatForm.description}
                    onChange={e => rChange('description', e.target.value)}
                    placeholder="e.g. Sal for Mar 2026" />
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setShowRepeat(false)} disabled={creating}>Cancel</button>
              <button className="btn btn-primary" onClick={handleRepeat} disabled={creating}>
                <Copy size={15} /> {creating ? 'Creating…' : 'Create from Last Payroll'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3>Delete Payroll Run</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setDeleteConfirm(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete this payroll run? This cannot be undone.</p>
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
