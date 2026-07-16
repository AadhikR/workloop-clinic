/**
 * IncidentManager.jsx — Feature 7.3: Clinical incident reporting.
 * Admin log of workplace/patient safety incidents with filter, severity tracking, and root-cause fields.
 */
import { useState, useEffect, useCallback } from 'react';
import { Plus, Edit2, Trash2, X, AlertTriangle, ShieldAlert, FileText } from 'lucide-react';
import {
  getIncidents, saveIncident, deleteIncident,
  INCIDENT_TYPES, INCIDENT_SEVERITY, INCIDENT_STATUS,
} from '../utils/incidentStorage';
import { getEmployees } from '../utils/storage';
import { getDepartments } from '../utils/departmentStorage';
import { formatDateUAE } from '../utils/uaeValidators';
import { useCompany } from '../context/CompanyContext';
import LoadError from './LoadError';
import ConfirmModal from './ConfirmModal';

function IncidentModal({ incident, employees, departments, onSave, onClose }) {
  const isEdit = !!incident?.id;
  const [form, setForm] = useState({
    id:               incident?.id               ?? undefined,
    incidentDate:     incident?.incidentDate     ?? new Date().toISOString().slice(0, 10),
    incidentTime:     incident?.incidentTime     ?? '',
    location:         incident?.location         ?? '',
    department:       incident?.department       ?? '',
    incidentType:     incident?.incidentType     ?? 'other',
    severity:         incident?.severity         ?? 'low',
    description:      incident?.description      ?? '',
    reportedById:     incident?.reportedById     ?? '',
    involvedEmpId:    incident?.involvedEmpId    ?? '',
    immediateAction:  incident?.immediateAction  ?? '',
    rootCause:        incident?.rootCause        ?? '',
    correctiveAction: incident?.correctiveAction ?? '',
    status:           incident?.status           ?? 'open',
    closedBy:         incident?.closedBy         ?? '',
    notes:            incident?.notes            ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault();
    setErr('');
    if (!form.incidentDate) { setErr('Incident date is required.'); return; }
    if (!form.description.trim()) { setErr('Description is required.'); return; }
    setSaving(true);
    try { await onSave(form); }
    catch (ex) { setErr(ex.message || 'Failed to save.'); setSaving(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 680 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isEdit ? 'Edit Incident Report' : 'New Incident Report'}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
            {err && <div className="alert alert-danger" style={{ padding: '8px 12px', fontSize: 13 }}>{err}</div>}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Date *</label>
                <input type="date" className="form-control" value={form.incidentDate}
                  onChange={e => set('incidentDate', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Time</label>
                <input type="time" className="form-control" value={form.incidentTime}
                  onChange={e => set('incidentTime', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Severity</label>
                <select className="form-control" value={form.severity}
                  onChange={e => set('severity', e.target.value)}>
                  {INCIDENT_SEVERITY.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="form-control" value={form.incidentType}
                  onChange={e => set('incidentType', e.target.value)}>
                  {INCIDENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Department</label>
                <select className="form-control" value={form.department}
                  onChange={e => set('department', e.target.value)}>
                  <option value="">—</option>
                  {departments.map(d => <option key={d.id} value={d.name}>{d.name}</option>)}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Location</label>
              <input className="form-control" value={form.location}
                onChange={e => set('location', e.target.value)}
                placeholder="e.g. Ward 2B, Room 305, Pharmacy" />
            </div>

            <div className="form-group">
              <label className="form-label">Description *</label>
              <textarea className="form-control" rows={3} value={form.description}
                onChange={e => set('description', e.target.value)}
                placeholder="What happened, when, and who was present…" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Reported By</label>
                <select className="form-control" value={form.reportedById}
                  onChange={e => set('reportedById', e.target.value)}>
                  <option value="">—</option>
                  {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Involved Staff</label>
                <select className="form-control" value={form.involvedEmpId}
                  onChange={e => set('involvedEmpId', e.target.value)}>
                  <option value="">—</option>
                  {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.name}</option>)}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Immediate Action Taken</label>
              <textarea className="form-control" rows={2} value={form.immediateAction}
                onChange={e => set('immediateAction', e.target.value)}
                placeholder="First response actions…" />
            </div>

            <div className="form-group">
              <label className="form-label">Root Cause</label>
              <textarea className="form-control" rows={2} value={form.rootCause}
                onChange={e => set('rootCause', e.target.value)}
                placeholder="Analysis of underlying cause…" />
            </div>

            <div className="form-group">
              <label className="form-label">Corrective Action</label>
              <textarea className="form-control" rows={2} value={form.correctiveAction}
                onChange={e => set('correctiveAction', e.target.value)}
                placeholder="Preventive measures to be taken…" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Status</label>
                <select className="form-control" value={form.status}
                  onChange={e => set('status', e.target.value)}>
                  {INCIDENT_STATUS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
              {form.status === 'closed' && (
                <div className="form-group">
                  <label className="form-label">Closed By</label>
                  <input className="form-control" value={form.closedBy}
                    onChange={e => set('closedBy', e.target.value)}
                    placeholder="Approver name" />
                </div>
              )}
            </div>

            <div className="form-group">
              <label className="form-label">Additional Notes</label>
              <textarea className="form-control" rows={2} value={form.notes}
                onChange={e => set('notes', e.target.value)} />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Submit Report'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function IncidentManager() {
  const { activeCompanyId } = useCompany();
  const [incidents,   setIncidents]   = useState([]);
  const [employees,   setEmployees]   = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [loadError,   setLoadError]   = useState(null);
  const [flash,       setFlash]       = useState(null);

  const [modal,       setModal]       = useState(null); // null | 'new' | incident obj
  const [deleteId,    setDeleteId]    = useState(null);

  const [statusFilter,   setStatusFilter]   = useState('all');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [typeFilter,     setTypeFilter]     = useState('all');

  const showFlash = (type, msg) => {
    setFlash({ type, msg });
    setTimeout(() => setFlash(null), 4000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [inc, emps, depts] = await Promise.all([
        getIncidents(activeCompanyId),
        getEmployees(activeCompanyId),
        getDepartments(),
      ]);
      setIncidents(inc);
      setEmployees(emps.filter(e => e.active !== false && e.employmentStatus !== 'Terminated'));
      setDepartments(depts);
    } catch (ex) {
      setLoadError(ex.message || 'Failed to load incidents.');
    }
    setLoading(false);
  }, [activeCompanyId]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async form => {
    const saved = await saveIncident(form, activeCompanyId);
    setIncidents(prev => form.id
      ? prev.map(i => i.id === form.id ? saved : i)
      : [saved, ...prev]);
    setModal(null);
    showFlash('success', form.id ? 'Incident updated.' : 'Incident report submitted.');
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    await deleteIncident(deleteId);
    setIncidents(prev => prev.filter(i => i.id !== deleteId));
    setDeleteId(null);
    showFlash('success', 'Incident deleted.');
  };

  const filtered = incidents.filter(i => {
    if (statusFilter   !== 'all' && i.status       !== statusFilter)   return false;
    if (severityFilter !== 'all' && i.severity     !== severityFilter) return false;
    if (typeFilter     !== 'all' && i.incidentType !== typeFilter)     return false;
    return true;
  });

  const openCount     = incidents.filter(i => i.status === 'open').length;
  const criticalCount = incidents.filter(i => i.severity === 'critical' && i.status !== 'closed').length;
  const thisMonth     = incidents.filter(i => i.incidentDate?.startsWith(new Date().toISOString().slice(0, 7))).length;

  const typeLabel     = t => INCIDENT_TYPES.find(x => x.value === t)?.label     || t;
  const severityInfo  = s => INCIDENT_SEVERITY.find(x => x.value === s)          || { label: s, badge: 'badge-gray' };
  const statusInfo    = s => INCIDENT_STATUS.find(x => x.value === s)            || { label: s, badge: 'badge-gray' };

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading incidents…</div>;
  }
  if (loadError) return <LoadError isAdmin message={loadError} onRetry={load} />;

  return (
    <div>
      <div className="page-header">
        <h2>Incident Reports</h2>
        <button className="btn btn-primary" onClick={() => setModal('new')}>
          <Plus size={16} /> New Report
        </button>
      </div>

      <div className="page-body">
        {flash && <div className={`alert alert-${flash.type}`} style={{ marginBottom: 16 }}>{flash.msg}</div>}

        <div className="stats-grid" style={{ marginBottom: 20 }}>
          <div className="stat-card">
            <div className="stat-label">Total Reports</div>
            <div className="stat-value">{incidents.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Open</div>
            <div className="stat-value" style={{ color: openCount > 0 ? 'var(--primary)' : 'var(--success)' }}>{openCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Critical / High (Open)</div>
            <div className="stat-value" style={{ color: criticalCount > 0 ? 'var(--danger)' : 'var(--success)' }}>{criticalCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">This Month</div>
            <div className="stat-value">{thisMonth}</div>
          </div>
        </div>

        {criticalCount > 0 && (
          <div className="alert alert-warning" style={{ marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
            <ShieldAlert size={18} />
            <span><strong>{criticalCount} critical incident{criticalCount > 1 ? 's' : ''}</strong> still open — investigate promptly.</span>
          </div>
        )}

        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            {[{ v: 'all', l: 'All' }, ...INCIDENT_STATUS.map(s => ({ v: s.value, l: s.label }))].map(f => (
              <button key={f.v}
                className={`btn btn-sm ${statusFilter === f.v ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setStatusFilter(f.v)}>{f.l}</button>
            ))}
          </div>
          <select className="form-control" style={{ width: 160 }} value={severityFilter}
            onChange={e => setSeverityFilter(e.target.value)}>
            <option value="all">All Severities</option>
            {INCIDENT_SEVERITY.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <select className="form-control" style={{ width: 200 }} value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}>
            <option value="all">All Types</option>
            {INCIDENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        <div className="card">
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Department</th>
                  <th>Location</th>
                  <th>Description</th>
                  <th>Reported By</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', color: 'var(--gray-400)', padding: 32 }}>
                      <FileText size={20} style={{ opacity: 0.4, marginBottom: 6 }} /><br />
                      No incidents match the current filters.
                    </td>
                  </tr>
                ) : filtered.map(i => {
                  const sev = severityInfo(i.severity);
                  const st  = statusInfo(i.status);
                  return (
                    <tr key={i.id}>
                      <td style={{ whiteSpace: 'nowrap', fontSize: 13 }}>
                        {formatDateUAE(i.incidentDate)}
                        {i.incidentTime && <div style={{ color: 'var(--gray-400)', fontSize: 11 }}>{i.incidentTime.slice(0, 5)}</div>}
                      </td>
                      <td style={{ fontSize: 13 }}>{typeLabel(i.incidentType)}</td>
                      <td><span className={`badge ${sev.badge}`}>{sev.label}</span></td>
                      <td style={{ fontSize: 13 }}>{i.department || '—'}</td>
                      <td style={{ fontSize: 13, color: 'var(--gray-500)' }}>{i.location || '—'}</td>
                      <td style={{ maxWidth: 260, fontSize: 13 }}>
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                             title={i.description}>{i.description}</div>
                      </td>
                      <td style={{ fontSize: 13 }}>{i.reportedByName || '—'}</td>
                      <td><span className={`badge ${st.badge}`}>{st.label}</span></td>
                      <td>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => setModal(i)}>
                            <Edit2 size={14} />
                          </button>
                          <button className="btn btn-ghost btn-sm" title="Delete"
                            style={{ color: 'var(--danger)' }}
                            onClick={() => setDeleteId(i.id)}>
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
        </div>
      </div>

      {modal && (
        <IncidentModal
          incident={modal === 'new' ? null : modal}
          employees={employees}
          departments={departments}
          onSave={handleSave}
          onClose={() => setModal(null)}
        />
      )}

      {deleteId && (
        <ConfirmModal
          title="Delete Incident Report"
          message="Are you sure you want to delete this incident report? This cannot be undone."
          confirmLabel="Delete"
          destructive
          onConfirm={handleDelete}
          onCancel={() => setDeleteId(null)}
        />
      )}
    </div>
  );
}
