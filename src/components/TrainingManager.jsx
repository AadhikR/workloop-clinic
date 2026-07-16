/**
 * TrainingManager.jsx — Admin view for Feature 19: Training & Certification Records.
 *
 * Two tabs:
 *   Training Records  — course/programme history per employee (CRUD)
 *   Certifications    — professional cert registry with expiry tracking (CRUD)
 *
 * Employee portal reads are handled by EmpTraining.jsx via the employee self-read RLS policy.
 */

import { useState, useEffect, useCallback } from 'react';
import { Plus, Edit2, Trash2, GraduationCap, Award, X, AlertTriangle, ExternalLink, CheckCircle, XCircle, BookOpen } from 'lucide-react';
import { getEmployees } from '../utils/storage';
import { formatDateUAE } from '../utils/uaeValidators';
import {
  getTrainingRecords, saveTrainingRecord, deleteTrainingRecord,
  getCertifications,  saveCertification,  deleteCertification,
  getCmeRequirements, saveCmeRequirement, deleteCmeRequirement,
  getCmeTrainingRecords,
} from '../utils/trainingStorage';

// ─── Constants ────────────────────────────────────────────────────────────────

export const TRAINING_TYPES = [
  { value: 'internal',   label: 'Internal' },
  { value: 'external',   label: 'External' },
  { value: 'online',     label: 'Online / E-Learning' },
  { value: 'conference', label: 'Conference / Seminar' },
];

export const TRAINING_STATUSES = [
  { value: 'planned',     label: 'Planned',     badge: 'badge-gray'   },
  { value: 'in_progress', label: 'In Progress', badge: 'badge-blue'   },
  { value: 'completed',   label: 'Completed',   badge: 'badge-green'  },
  { value: 'cancelled',   label: 'Cancelled',   badge: 'badge-red'    },
];

/**
 * Returns expiry status label + badge class for a certification.
 * expiryDate: ISO date string | null
 */
export function certExpiryInfo(expiryDate) {
  if (!expiryDate) return { label: 'No Expiry', badge: 'badge-gray', days: null };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const exp = new Date(expiryDate);
  exp.setHours(0, 0, 0, 0);
  const days = Math.ceil((exp - today) / 86400000);
  if (days < 0)   return { label: 'Expired',              badge: 'badge-red',    days };
  if (days <= 30) return { label: `${days}d — Expiring`,  badge: 'badge-red',    days };
  if (days <= 60) return { label: `${days}d — Due Soon`,  badge: 'badge-yellow', days };
  return               { label: 'Active',                  badge: 'badge-green',  days };
}

// ─── Training Record Modal ────────────────────────────────────────────────────

function TrainingModal({ record, employees, onSave, onClose }) {
  const isEdit = !!record?.id;

  const [form, setForm] = useState({
    id:             record?.id             ?? undefined,
    employeeId:     record?.employeeId     ?? '',
    trainingTitle:  record?.trainingTitle  ?? '',
    trainingType:   record?.trainingType   ?? 'external',
    provider:       record?.provider       ?? '',
    startDate:      record?.startDate      ?? '',
    endDate:        record?.endDate        ?? '',
    durationHours:  record?.durationHours  != null ? String(record.durationHours) : '',
    cost:           record?.cost           != null ? String(record.cost)           : '',
    status:         record?.status         ?? 'planned',
    score:          record?.score          ?? '',
    passed:         record?.passed         ?? null,
    certificateUrl: record?.certificateUrl ?? '',
    notes:          record?.notes          ?? '',
    isCme:          record?.isCme          ?? false,
  });

  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault();
    setErr('');
    if (!form.employeeId)            { setErr('Please select an employee.');       return; }
    if (!form.trainingTitle.trim())  { setErr('Training title is required.');       return; }
    setSaving(true);
    try { await onSave(form); }
    catch (ex) { setErr(ex.message || 'Failed to save.'); setSaving(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isEdit ? 'Edit Training Record' : 'Add Training Record'}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16} /></button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
            {err && (
              <div className="alert alert-danger" style={{ padding: '8px 12px', fontSize: 13 }}>{err}</div>
            )}

            <div className="form-group">
              <label className="form-label">Employee *</label>
              <select className="form-control" value={form.employeeId}
                onChange={e => set('employeeId', e.target.value)} disabled={isEdit}>
                <option value="">Select employee…</option>
                {employees.map(emp => (
                  <option key={emp.id} value={emp.id}>{emp.name}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Training Title *</label>
              <input className="form-control" value={form.trainingTitle}
                onChange={e => set('trainingTitle', e.target.value)}
                placeholder="e.g. Fire Safety Awareness" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="form-control" value={form.trainingType}
                  onChange={e => set('trainingType', e.target.value)}>
                  {TRAINING_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Status</label>
                <select className="form-control" value={form.status}
                  onChange={e => set('status', e.target.value)}>
                  {TRAINING_STATUSES.map(s => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Provider / Institution</label>
              <input className="form-control" value={form.provider}
                onChange={e => set('provider', e.target.value)}
                placeholder="e.g. UAE NCEMA, Coursera" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Start Date</label>
                <input type="date" className="form-control" value={form.startDate}
                  onChange={e => set('startDate', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">End Date</label>
                <input type="date" className="form-control" value={form.endDate}
                  onChange={e => set('endDate', e.target.value)} />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Duration (hours)</label>
                <input type="number" className="form-control" value={form.durationHours}
                  onChange={e => set('durationHours', e.target.value)}
                  placeholder="e.g. 8" min="0" step="0.5" />
              </div>
              <div className="form-group">
                <label className="form-label">Cost (AED)</label>
                <input type="number" className="form-control" value={form.cost}
                  onChange={e => set('cost', e.target.value)}
                  placeholder="0" min="0" step="0.01" />
              </div>
            </div>

            {/* Show pass/score only for completed trainings */}
            {form.status === 'completed' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Score / Grade</label>
                  <input className="form-control" value={form.score}
                    onChange={e => set('score', e.target.value)}
                    placeholder="e.g. 92% or Distinction" />
                </div>
                <div className="form-group">
                  <label className="form-label">Result</label>
                  <select className="form-control"
                    value={form.passed === null ? '' : String(form.passed)}
                    onChange={e => set('passed', e.target.value === '' ? null : e.target.value === 'true')}>
                    <option value="">— N/A —</option>
                    <option value="true">Passed</option>
                    <option value="false">Failed</option>
                  </select>
                </div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Certificate / Document URL</label>
              <input className="form-control" value={form.certificateUrl}
                onChange={e => set('certificateUrl', e.target.value)}
                placeholder="https://drive.google.com/… or leave blank" />
            </div>

            <div className="form-group">
              <label className="form-label">Notes</label>
              <textarea className="form-control" rows={2} value={form.notes}
                onChange={e => set('notes', e.target.value)} />
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
              <input type="checkbox" checked={form.isCme}
                onChange={e => set('isCme', e.target.checked)} />
              Count as CME (Continuing Medical Education) hours
            </label>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Record'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Certification Modal ──────────────────────────────────────────────────────

function CertModal({ cert, employees, onSave, onClose }) {
  const isEdit = !!cert?.id;

  const [form, setForm] = useState({
    id:                cert?.id                ?? undefined,
    employeeId:        cert?.employeeId        ?? '',
    certificationName: cert?.certificationName ?? '',
    issuingBody:       cert?.issuingBody       ?? '',
    certificateNo:     cert?.certificateNo     ?? '',
    issuedDate:        cert?.issuedDate        ?? '',
    expiryDate:        cert?.expiryDate        ?? '',
    certificateUrl:    cert?.certificateUrl    ?? '',
    notes:             cert?.notes             ?? '',
  });

  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault();
    setErr('');
    if (!form.employeeId)               { setErr('Please select an employee.');           return; }
    if (!form.certificationName.trim()) { setErr('Certification name is required.');      return; }
    setSaving(true);
    try { await onSave(form); }
    catch (ex) { setErr(ex.message || 'Failed to save.'); setSaving(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 520 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isEdit ? 'Edit Certification' : 'Add Certification'}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16} /></button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
            {err && (
              <div className="alert alert-danger" style={{ padding: '8px 12px', fontSize: 13 }}>{err}</div>
            )}

            <div className="form-group">
              <label className="form-label">Employee *</label>
              <select className="form-control" value={form.employeeId}
                onChange={e => set('employeeId', e.target.value)} disabled={isEdit}>
                <option value="">Select employee…</option>
                {employees.map(emp => (
                  <option key={emp.id} value={emp.id}>{emp.name}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Certification Name *</label>
              <input className="form-control" value={form.certificationName}
                onChange={e => set('certificationName', e.target.value)}
                placeholder="e.g. ISO 9001 Lead Auditor" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Issuing Body</label>
                <input className="form-control" value={form.issuingBody}
                  onChange={e => set('issuingBody', e.target.value)}
                  placeholder="e.g. Bureau Veritas" />
              </div>
              <div className="form-group">
                <label className="form-label">Certificate No.</label>
                <input className="form-control" value={form.certificateNo}
                  onChange={e => set('certificateNo', e.target.value)}
                  placeholder="e.g. BV-2024-001" />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Issue Date</label>
                <input type="date" className="form-control" value={form.issuedDate}
                  onChange={e => set('issuedDate', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">
                  Expiry Date{' '}
                  <span style={{ color: 'var(--gray-400)', fontWeight: 400, fontSize: 11 }}>
                    (leave blank if no expiry)
                  </span>
                </label>
                <input type="date" className="form-control" value={form.expiryDate}
                  onChange={e => set('expiryDate', e.target.value)} />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Certificate URL</label>
              <input className="form-control" value={form.certificateUrl}
                onChange={e => set('certificateUrl', e.target.value)}
                placeholder="https://drive.google.com/… or leave blank" />
            </div>

            <div className="form-group">
              <label className="form-label">Notes</label>
              <textarea className="form-control" rows={2} value={form.notes}
                onChange={e => set('notes', e.target.value)} />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Certification'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── CME Requirement Modal ────────────────────────────────────────────────────

function CmeModal({ req, employees, defaultYear, onSave, onClose }) {
  const isEdit = !!req?.id;
  const [form, setForm] = useState({
    id:            req?.id            ?? undefined,
    employeeId:    req?.employeeId    ?? '',
    year:          req?.year          ?? defaultYear,
    requiredHours: req?.requiredHours != null ? String(req.requiredHours) : '25',
    notes:         req?.notes         ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [err,    setErr]    = useState('');
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault();
    setErr('');
    if (!form.employeeId) { setErr('Please select an employee.'); return; }
    if (!form.requiredHours || parseFloat(form.requiredHours) <= 0) {
      setErr('Required hours must be greater than 0.'); return;
    }
    setSaving(true);
    try { await onSave({ ...form, requiredHours: parseFloat(form.requiredHours) }); }
    catch (ex) { setErr(ex.message || 'Failed to save.'); setSaving(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 460 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isEdit ? 'Edit CME Target' : 'Set CME Target'}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
            {err && <div className="alert alert-danger" style={{ padding: '8px 12px', fontSize: 13 }}>{err}</div>}
            <div className="form-group">
              <label className="form-label">Employee *</label>
              <select className="form-control" value={form.employeeId}
                onChange={e => set('employeeId', e.target.value)} disabled={isEdit}>
                <option value="">Select employee…</option>
                {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.name}</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Year</label>
                <input type="number" className="form-control" value={form.year}
                  onChange={e => set('year', Number(e.target.value))} min="2020" max="2050" />
              </div>
              <div className="form-group">
                <label className="form-label">Required Hours *</label>
                <input type="number" className="form-control" value={form.requiredHours}
                  onChange={e => set('requiredHours', e.target.value)} min="0" step="0.5" placeholder="25" />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Notes</label>
              <textarea className="form-control" rows={2} value={form.notes}
                onChange={e => set('notes', e.target.value)}
                placeholder="e.g. DHA CME requirement for licensed physicians" />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Set Target'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Delete Confirmation ──────────────────────────────────────────────────────

function DeleteConfirm({ title, message, onConfirm, onCancel }) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" style={{ maxWidth: 400 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header"><h3>{title}</h3></div>
        <div className="modal-body"><p>{message}</p></div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn btn-danger" onClick={onConfirm}>Delete</button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function TrainingManager() {
  const [activeTab, setActiveTab] = useState('training');

  // Shared
  const [employees, setEmployees] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [flash,     setFlash]     = useState(null);

  // Training Records state
  const [records,        setRecords]        = useState([]);
  const [trainingModal,  setTrainingModal]  = useState(null); // null | 'new' | record obj
  const [deleteTrainId,  setDeleteTrainId]  = useState(null);
  const [empFilter,      setEmpFilter]      = useState('');
  const [statusFilter,   setStatusFilter]   = useState('all');

  // Certifications state
  const [certs,          setCerts]          = useState([]);
  const [certModal,      setCertModal]      = useState(null); // null | 'new' | cert obj
  const [deleteCertId,   setDeleteCertId]   = useState(null);
  const [certEmpFilter,  setCertEmpFilter]  = useState('');
  const [certExpiryFilter, setCertExpiryFilter] = useState('all'); // all | expiring | expired | active

  // CME state
  const [cmeRequirements, setCmeRequirements] = useState([]);
  const [cmeRecords,      setCmeRecords]      = useState([]);
  const [cmeYear,         setCmeYear]         = useState(new Date().getFullYear());
  const [cmeModal,        setCmeModal]        = useState(null); // null | 'new' | req obj
  const [deleteCmeId,     setDeleteCmeId]     = useState(null);

  // ── Flash helper ──
  const showFlash = (type, msg) => {
    setFlash({ type, msg });
    setTimeout(() => setFlash(null), 4000);
  };

  // ── Load ──
  const load = useCallback(async () => {
    setLoading(true);
    const [emps, recs, cs, cmeReqs, cmeRecs] = await Promise.all([
      getEmployees(),
      getTrainingRecords(),
      getCertifications(),
      getCmeRequirements().catch(() => []),
      getCmeTrainingRecords().catch(() => []),
    ]);
    setEmployees(emps.filter(e => e.active !== false && e.employmentStatus !== 'Terminated'));
    setRecords(recs);
    setCerts(cs);
    setCmeRequirements(cmeReqs);
    setCmeRecords(cmeRecs);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── Training handlers ──
  const handleSaveTraining = async form => {
    const saved = await saveTrainingRecord(form);
    setRecords(prev => form.id
      ? prev.map(r => r.id === form.id ? saved : r)
      : [saved, ...prev]);
    setTrainingModal(null);
    showFlash('success', form.id ? 'Training record updated.' : 'Training record added.');
  };

  const handleDeleteTraining = async () => {
    if (!deleteTrainId) return;
    await deleteTrainingRecord(deleteTrainId);
    setRecords(prev => prev.filter(r => r.id !== deleteTrainId));
    setDeleteTrainId(null);
    showFlash('success', 'Training record deleted.');
  };

  // ── Cert handlers ──
  const handleSaveCert = async form => {
    const saved = await saveCertification(form);
    setCerts(prev => form.id
      ? prev.map(c => c.id === form.id ? saved : c)
      : [saved, ...prev]);
    setCertModal(null);
    showFlash('success', form.id ? 'Certification updated.' : 'Certification added.');
  };

  const handleDeleteCert = async () => {
    if (!deleteCertId) return;
    await deleteCertification(deleteCertId);
    setCerts(prev => prev.filter(c => c.id !== deleteCertId));
    setDeleteCertId(null);
    showFlash('success', 'Certification deleted.');
  };

  // ── CME handlers ──
  const handleSaveCme = async form => {
    const saved = await saveCmeRequirement(form);
    setCmeRequirements(prev => form.id
      ? prev.map(r => r.id === form.id ? saved : r)
      : [saved, ...prev]);
    setCmeModal(null);
    showFlash('success', form.id ? 'CME requirement updated.' : 'CME requirement added.');
  };

  const handleDeleteCme = async () => {
    if (!deleteCmeId) return;
    await deleteCmeRequirement(deleteCmeId);
    setCmeRequirements(prev => prev.filter(r => r.id !== deleteCmeId));
    setDeleteCmeId(null);
    showFlash('success', 'CME requirement deleted.');
  };

  const handleCertReview = async (cert, newStatus) => {
    const saved = await saveCertification({ ...cert, status: newStatus });
    setCerts(prev => prev.map(c => c.id === cert.id ? saved : c));
    showFlash('success', newStatus === 'verified' ? 'Certification verified.' : 'Certification rejected.');
  };

  // ── Derived / filtered data ──
  const filteredRecords = records.filter(r => {
    if (empFilter    && r.employeeId !== empFilter) return false;
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    return true;
  });

  const filteredCerts = certs.filter(c => {
    if (certEmpFilter && c.employeeId !== certEmpFilter) return false;
    if (certExpiryFilter !== 'all') {
      if (certExpiryFilter === 'pending') return c.status === 'pending_review';
      const { days } = certExpiryInfo(c.expiryDate);
      if (certExpiryFilter === 'expired'  && (days === null || days >= 0))         return false;
      if (certExpiryFilter === 'expiring' && (days === null || days < 0 || days > 60)) return false;
      if (certExpiryFilter === 'active'   && days !== null && days < 0)             return false;
    }
    return true;
  });

  const pendingCertCount = certs.filter(c => c.status === 'pending_review').length;

  // Training stats
  const totalCost          = records.reduce((s, r) => s + (r.cost || 0), 0);
  const completedCount     = records.filter(r => r.status === 'completed').length;
  const inProgressCount    = records.filter(r => r.status === 'in_progress').length;

  // Cert stats
  const expiredCertsCount  = certs.filter(c => c.expiryDate && new Date(c.expiryDate) < new Date()).length;
  const expiringSoonCount  = certs.filter(c => {
    if (!c.expiryDate) return false;
    const d = Math.ceil((new Date(c.expiryDate) - new Date()) / 86400000);
    return d >= 0 && d <= 60;
  }).length;
  const lifetimeCount      = certs.filter(c => !c.expiryDate).length;

  const statusInfo = s => TRAINING_STATUSES.find(x => x.value === s) || { label: s, badge: 'badge-gray' };
  const typeLabel  = t => TRAINING_TYPES.find(x => x.value === t)?.label || t;

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
        Loading training records…
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h2>Training &amp; Certifications</h2>
        <button
          className="btn btn-primary"
          onClick={() => {
            if (activeTab === 'training') setTrainingModal('new');
            else if (activeTab === 'certs') setCertModal('new');
            else setCmeModal('new');
          }}
        >
          <Plus size={16} />
          {activeTab === 'training' ? 'Add Training' : activeTab === 'certs' ? 'Add Certification' : 'Set CME Target'}
        </button>
      </div>

      <div className="page-body">
        {/* Flash message */}
        {flash && (
          <div className={`alert alert-${flash.type}`} style={{ marginBottom: 16 }}>
            {flash.msg}
          </div>
        )}

        {/* Tab switcher */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <button
            className={`btn ${activeTab === 'training' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setActiveTab('training')}
          >
            <GraduationCap size={15} aria-hidden="true" /> Training Records
          </button>
          <button
            className={`btn ${activeTab === 'certs' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setActiveTab('certs')}
          >
            <Award size={15} aria-hidden="true" /> Certifications
            {(expiredCertsCount + expiringSoonCount) > 0 && (
              <span style={{
                marginLeft: 6, background: '#ef4444', color: '#fff',
                borderRadius: 10, fontSize: 10, fontWeight: 700,
                padding: '1px 6px', lineHeight: 1.5,
              }}>
                {expiredCertsCount + expiringSoonCount}
              </span>
            )}
          </button>
          <button
            className={`btn ${activeTab === 'cme' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setActiveTab('cme')}
          >
            <BookOpen size={15} aria-hidden="true" /> CME Hours
          </button>
        </div>

        {/* ── Training Records Tab ─────────────────────────────────────────── */}
        {activeTab === 'training' && (
          <>
            {/* Stat cards */}
            <div className="stats-grid" style={{ marginBottom: 20 }}>
              <div className="stat-card">
                <div className="stat-label">Total Records</div>
                <div className="stat-value">{records.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Completed</div>
                <div className="stat-value" style={{ color: '#10b981' }}>{completedCount}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">In Progress</div>
                <div className="stat-value" style={{ color: 'var(--primary)' }}>{inProgressCount}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Total Cost</div>
                <div className="stat-value" style={{ fontSize: 18 }}>
                  AED {totalCost.toLocaleString('en-AE', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </div>
              </div>
            </div>

            {/* Filters */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
              <select
                className="form-control"
                style={{ width: 200 }}
                value={empFilter}
                onChange={e => setEmpFilter(e.target.value)}
              >
                <option value="">All Employees</option>
                {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>

              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {[{ v: 'all', l: 'All' }, ...TRAINING_STATUSES.map(s => ({ v: s.value, l: s.label }))].map(s => (
                  <button
                    key={s.v}
                    className={`btn btn-sm ${statusFilter === s.v ? 'btn-primary' : 'btn-ghost'}`}
                    onClick={() => setStatusFilter(s.v)}
                  >
                    {s.l}
                  </button>
                ))}
              </div>
            </div>

            {/* Table */}
            <div className="card">
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Title</th>
                      <th>Type</th>
                      <th>Provider</th>
                      <th>Dates</th>
                      <th>Hours</th>
                      <th>Cost (AED)</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRecords.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: 'center', color: 'var(--gray-400)', padding: 32 }}>
                          No training records found.{' '}
                          <button className="btn btn-ghost btn-sm" onClick={() => setTrainingModal('new')}>
                            Add one
                          </button>
                        </td>
                      </tr>
                    ) : filteredRecords.map(r => {
                      const si = statusInfo(r.status);
                      return (
                        <tr key={r.id}>
                          <td style={{ fontWeight: 500 }}>{r.employeeName}</td>
                          <td>
                            {r.trainingTitle}
                            {r.certificateUrl && (
                              <a href={r.certificateUrl} target="_blank" rel="noopener noreferrer"
                                title="View certificate" style={{ marginLeft: 6, color: 'var(--primary)', verticalAlign: 'middle' }}>
                                <ExternalLink size={12} />
                              </a>
                            )}
                          </td>
                          <td><span className="badge badge-gray">{typeLabel(r.trainingType)}</span></td>
                          <td style={{ color: 'var(--gray-500)', fontSize: 13 }}>{r.provider || '—'}</td>
                          <td style={{ fontSize: 13, whiteSpace: 'nowrap' }}>
                            {r.startDate ? formatDateUAE(r.startDate) : '—'}
                            {r.endDate && r.endDate !== r.startDate && (
                              <span style={{ color: 'var(--gray-400)' }}> → {formatDateUAE(r.endDate)}</span>
                            )}
                          </td>
                          <td style={{ fontSize: 13 }}>{r.durationHours != null ? `${r.durationHours}h` : '—'}</td>
                          <td style={{ fontSize: 13 }}>{r.cost > 0 ? r.cost.toLocaleString('en-AE') : '—'}</td>
                          <td>
                            <span className={`badge ${si.badge}`}>{si.label}</span>
                            {r.status === 'completed' && r.passed !== null && (
                              <span style={{ marginLeft: 4, fontSize: 11, color: r.passed ? '#10b981' : '#ef4444' }}>
                                {r.passed ? '✓' : '✗'}
                              </span>
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button className="btn btn-ghost btn-sm" title="Edit"
                                onClick={() => setTrainingModal(r)}>
                                <Edit2 size={14} />
                              </button>
                              <button className="btn btn-ghost btn-sm" title="Delete"
                                style={{ color: 'var(--danger)' }}
                                onClick={() => setDeleteTrainId(r.id)}>
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
          </>
        )}

        {/* ── Certifications Tab ───────────────────────────────────────────── */}
        {activeTab === 'certs' && (
          <>
            {/* Stat cards */}
            <div className="stats-grid" style={{ marginBottom: 20 }}>
              <div className="stat-card">
                <div className="stat-label">Total Certifications</div>
                <div className="stat-value">{certs.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Expired</div>
                <div className="stat-value" style={{ color: expiredCertsCount > 0 ? 'var(--danger)' : 'var(--success)' }}>
                  {expiredCertsCount}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Expiring ≤ 60 days</div>
                <div className="stat-value" style={{ color: expiringSoonCount > 0 ? '#d97706' : 'var(--success)' }}>
                  {expiringSoonCount}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Lifetime / No Expiry</div>
                <div className="stat-value">{lifetimeCount}</div>
              </div>
            </div>

            {/* Expiry warning banner */}
            {(expiredCertsCount + expiringSoonCount) > 0 && (
              <div className="alert alert-warning" style={{ marginBottom: 16 }}>
                <AlertTriangle size={16} />
                <div>
                  <strong>
                    {expiredCertsCount > 0 && `${expiredCertsCount} expired`}
                    {expiredCertsCount > 0 && expiringSoonCount > 0 && ' and '}
                    {expiringSoonCount > 0 && `${expiringSoonCount} expiring within 60 days`}
                    {' — '}
                  </strong>
                  review and renew certifications to stay compliant.
                </div>
              </div>
            )}

            {/* Filters */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
              <select
                className="form-control"
                style={{ width: 200 }}
                value={certEmpFilter}
                onChange={e => setCertEmpFilter(e.target.value)}
              >
                <option value="">All Employees</option>
                {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>

              <div style={{ display: 'flex', gap: 4 }}>
                {[
                  { v: 'all',      l: 'All'           },
                  { v: 'pending',  l: `Pending Review${pendingCertCount ? ` (${pendingCertCount})` : ''}` },
                  { v: 'expired',  l: 'Expired'       },
                  { v: 'expiring', l: 'Expiring Soon'  },
                  { v: 'active',   l: 'Active'         },
                ].map(f => (
                  <button
                    key={f.v}
                    className={`btn btn-sm ${certExpiryFilter === f.v ? 'btn-primary' : 'btn-ghost'}`}
                    onClick={() => setCertExpiryFilter(f.v)}
                  >
                    {f.l}
                  </button>
                ))}
              </div>
            </div>

            {/* Table */}
            <div className="card">
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Certification</th>
                      <th>Issuing Body</th>
                      <th>Cert No.</th>
                      <th>Issued</th>
                      <th>Expires</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCerts.length === 0 ? (
                      <tr>
                        <td colSpan={8} style={{ textAlign: 'center', color: 'var(--gray-400)', padding: 32 }}>
                          No certifications found.{' '}
                          <button className="btn btn-ghost btn-sm" onClick={() => setCertModal('new')}>
                            Add one
                          </button>
                        </td>
                      </tr>
                    ) : filteredCerts.map(c => {
                      const exSt = certExpiryInfo(c.expiryDate);
                      const isPending = c.status === 'pending_review';
                      const isRejected = c.status === 'rejected';
                      return (
                        <tr key={c.id} style={isPending ? { background: '#fffbeb' } : undefined}>
                          <td style={{ fontWeight: 500 }}>{c.employeeName}</td>
                          <td>
                            {c.certificationName}
                            {c.certificateUrl && (
                              <a href={c.certificateUrl} target="_blank" rel="noopener noreferrer"
                                title="View certificate" style={{ marginLeft: 6, color: 'var(--primary)', verticalAlign: 'middle' }}>
                                <ExternalLink size={12} />
                              </a>
                            )}
                            {isPending && <span style={{ fontSize: 10, color: '#92400e', marginLeft: 6 }}>Self-submitted</span>}
                          </td>
                          <td style={{ fontSize: 13, color: 'var(--gray-600)' }}>{c.issuingBody || '—'}</td>
                          <td style={{ fontSize: 13, color: 'var(--gray-500)' }}>{c.certificateNo || '—'}</td>
                          <td style={{ fontSize: 13 }}>{c.issuedDate ? formatDateUAE(c.issuedDate) : '—'}</td>
                          <td style={{ fontSize: 13 }}>{c.expiryDate ? formatDateUAE(c.expiryDate) : <span style={{ color: 'var(--gray-400)' }}>No expiry</span>}</td>
                          <td>
                            {isPending
                              ? <span className="badge badge-amber">Pending Review</span>
                              : isRejected
                                ? <span className="badge badge-red">Rejected</span>
                                : <span className={`badge ${exSt.badge}`}>{exSt.label}</span>}
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: 6 }}>
                              {isPending && (
                                <>
                                  <button className="btn btn-ghost btn-sm" title="Verify"
                                    style={{ color: 'var(--success)' }}
                                    onClick={() => handleCertReview(c, 'verified')}>
                                    <CheckCircle size={14} />
                                  </button>
                                  <button className="btn btn-ghost btn-sm" title="Reject"
                                    style={{ color: 'var(--danger)' }}
                                    onClick={() => handleCertReview(c, 'rejected')}>
                                    <XCircle size={14} />
                                  </button>
                                </>
                              )}
                              <button className="btn btn-ghost btn-sm" title="Edit"
                                onClick={() => setCertModal(c)}>
                                <Edit2 size={14} />
                              </button>
                              <button className="btn btn-ghost btn-sm" title="Delete"
                                style={{ color: 'var(--danger)' }}
                                onClick={() => setDeleteCertId(c.id)}>
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
          </>
        )}

        {/* ── CME Hours Tab ───────────────────────────────────────────────── */}
        {activeTab === 'cme' && (() => {
          const yearReqs = cmeRequirements.filter(r => r.year === cmeYear);
          const yearRecs = cmeRecords.filter(r => r.startDate && r.startDate.startsWith(String(cmeYear)));

          const empSummary = employees.map(emp => {
            const req = yearReqs.find(r => r.employeeId === emp.id);
            const target = req?.requiredHours || 0;
            const completed = yearRecs
              .filter(r => r.employeeId === emp.id && r.status === 'completed')
              .reduce((sum, r) => sum + (r.durationHours || 0), 0);
            const inProg = yearRecs
              .filter(r => r.employeeId === emp.id && r.status !== 'completed')
              .reduce((sum, r) => sum + (r.durationHours || 0), 0);
            return { ...emp, target, completed, inProg, remaining: Math.max(0, target - completed), reqId: req?.id };
          }).filter(e => e.target > 0 || yearRecs.some(r => r.employeeId === e.id));

          const totalTarget = empSummary.reduce((s, e) => s + e.target, 0);
          const totalCompleted = empSummary.reduce((s, e) => s + e.completed, 0);
          const belowTarget = empSummary.filter(e => e.target > 0 && e.completed < e.target).length;

          return (
            <>
              <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
                <label className="form-label" style={{ margin: 0 }}>Year:</label>
                <select className="form-control" style={{ width: 120 }} value={cmeYear}
                  onChange={e => setCmeYear(Number(e.target.value))}>
                  {[cmeYear - 1, cmeYear, cmeYear + 1].map(y => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>

              <div className="stats-grid" style={{ marginBottom: 20 }}>
                <div className="stat-card">
                  <div className="stat-label">Staff with CME Targets</div>
                  <div className="stat-value">{empSummary.filter(e => e.target > 0).length}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Total Hours Completed</div>
                  <div className="stat-value" style={{ color: 'var(--success)' }}>{totalCompleted}h</div>
                  <div className="stat-sub">{totalTarget > 0 ? `of ${totalTarget}h target` : ''}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Below Target</div>
                  <div className="stat-value" style={{ color: belowTarget > 0 ? 'var(--danger)' : 'var(--success)' }}>
                    {belowTarget}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Overall Compliance</div>
                  <div className="stat-value">
                    {totalTarget > 0 ? `${Math.round(totalCompleted / totalTarget * 100)}%` : '—'}
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Employee</th>
                        <th>Department</th>
                        <th>Target Hours</th>
                        <th>Completed</th>
                        <th>In Progress</th>
                        <th>Remaining</th>
                        <th>Progress</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {empSummary.length === 0 ? (
                        <tr>
                          <td colSpan={8} style={{ textAlign: 'center', color: 'var(--gray-400)', padding: 32 }}>
                            No CME targets set for {cmeYear}.{' '}
                            <button className="btn btn-ghost btn-sm" onClick={() => setCmeModal('new')}>
                              Set a target
                            </button>
                          </td>
                        </tr>
                      ) : empSummary.map(e => {
                        const pct = e.target > 0 ? Math.min(100, Math.round(e.completed / e.target * 100)) : 0;
                        return (
                          <tr key={e.id}>
                            <td style={{ fontWeight: 500 }}>{e.name}</td>
                            <td style={{ fontSize: 13, color: 'var(--gray-500)' }}>{e.department || '—'}</td>
                            <td>{e.target > 0 ? `${e.target}h` : '—'}</td>
                            <td style={{ color: 'var(--success)', fontWeight: 500 }}>{e.completed}h</td>
                            <td style={{ fontSize: 13, color: 'var(--gray-500)' }}>{e.inProg > 0 ? `${e.inProg}h` : '—'}</td>
                            <td>
                              {e.remaining > 0
                                ? <span className="badge badge-amber">{e.remaining}h</span>
                                : <span className="badge badge-green">Met</span>}
                            </td>
                            <td style={{ minWidth: 120 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <div style={{ flex: 1, height: 6, borderRadius: 4, background: 'var(--gray-100)', maxWidth: 80 }}>
                                  <div style={{
                                    width: `${pct}%`, height: '100%', borderRadius: 4,
                                    background: pct >= 100 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--danger)',
                                    transition: 'width 0.4s ease',
                                  }} />
                                </div>
                                <span style={{ fontSize: 12, color: 'var(--gray-500)' }}>{pct}%</span>
                              </div>
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button className="btn btn-ghost btn-sm" title="Edit target"
                                  onClick={() => setCmeModal({ id: e.reqId, employeeId: e.id, year: cmeYear, requiredHours: e.target })}>
                                  <Edit2 size={14} />
                                </button>
                                {e.reqId && (
                                  <button className="btn btn-ghost btn-sm" title="Remove target"
                                    style={{ color: 'var(--danger)' }}
                                    onClick={() => setDeleteCmeId(e.reqId)}>
                                    <Trash2 size={14} />
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          );
        })()}
      </div>

      {/* ── Modals ── */}
      {trainingModal && (
        <TrainingModal
          record={trainingModal === 'new' ? null : trainingModal}
          employees={employees}
          onSave={handleSaveTraining}
          onClose={() => setTrainingModal(null)}
        />
      )}

      {certModal && (
        <CertModal
          cert={certModal === 'new' ? null : certModal}
          employees={employees}
          onSave={handleSaveCert}
          onClose={() => setCertModal(null)}
        />
      )}

      {deleteTrainId && (
        <DeleteConfirm
          title="Delete Training Record"
          message="Are you sure you want to delete this training record? This cannot be undone."
          onConfirm={handleDeleteTraining}
          onCancel={() => setDeleteTrainId(null)}
        />
      )}

      {deleteCertId && (
        <DeleteConfirm
          title="Delete Certification"
          message="Are you sure you want to delete this certification? This cannot be undone."
          onConfirm={handleDeleteCert}
          onCancel={() => setDeleteCertId(null)}
        />
      )}

      {cmeModal && (
        <CmeModal
          req={cmeModal === 'new' ? null : cmeModal}
          employees={employees}
          defaultYear={cmeYear}
          onSave={handleSaveCme}
          onClose={() => setCmeModal(null)}
        />
      )}

      {deleteCmeId && (
        <DeleteConfirm
          title="Remove CME Target"
          message="Remove this CME hour target? Training records will remain but progress tracking will stop."
          onConfirm={handleDeleteCme}
          onCancel={() => setDeleteCmeId(null)}
        />
      )}
    </div>
  );
}
