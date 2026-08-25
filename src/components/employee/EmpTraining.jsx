/**
 * EmpTraining.jsx — Employee self-service view for Feature 19.
 *
 * Shows the employee's own training records and certifications.
 * Employees can add/update their own training records (self-enrollment).
 * Certifications remain read-only (admin/manager managed).
 */

import { useState, useEffect } from 'react';
import { GraduationCap, Award, AlertTriangle, ExternalLink, Plus, Edit2, X, Upload, FileText } from 'lucide-react';
import { getMyEmployeeRecord } from '../../utils/profileStorage';
import { getEmployeeTrainingRecords, getEmployeeCertifications, employeeSaveTrainingRecord, employeeSaveCertification, uploadCertificateFile, getCertificateSignedUrl } from '../../utils/trainingStorage';
import { formatDateUAE } from '../../utils/uaeValidators';

const TRAINING_TYPES = [
  { value: 'internal',   label: 'Internal' },
  { value: 'external',   label: 'External' },
  { value: 'online',     label: 'Online / E-Learning' },
  { value: 'conference', label: 'Conference / Seminar' },
];

const TRAINING_STATUSES = [
  { value: 'planned',     label: 'Planned' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed',   label: 'Completed' },
];

const TRAINING_TYPE_LABELS = Object.fromEntries(TRAINING_TYPES.map(t => [t.value, t.label]));

const STATUS_BADGE = {
  planned:     'badge-gray',
  in_progress: 'badge-blue',
  completed:   'badge-green',
  cancelled:   'badge-red',
};

const STATUS_LABEL = {
  planned:     'Planned',
  in_progress: 'In Progress',
  completed:   'Completed',
  cancelled:   'Cancelled',
};

function certDaysLeft(expiryDate) {
  if (!expiryDate) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const exp = new Date(expiryDate);
  exp.setHours(0, 0, 0, 0);
  return Math.ceil((exp - today) / 86400000);
}

function certBadge(expiryDate) {
  const days = certDaysLeft(expiryDate);
  if (days === null) return { badge: 'badge-gray',   label: 'No Expiry' };
  if (days < 0)      return { badge: 'badge-red',    label: 'Expired' };
  if (days <= 30)    return { badge: 'badge-red',    label: `${days}d left` };
  if (days <= 60)    return { badge: 'badge-yellow', label: `${days}d left` };
  return               { badge: 'badge-green',  label: 'Active' };
}

const CERT_STATUS_BADGE = {
  pending_review: 'badge-amber',
  verified:       'badge-green',
  rejected:       'badge-red',
};
const CERT_STATUS_LABEL = {
  pending_review: 'Pending Review',
  verified:       'Verified',
  rejected:       'Rejected',
};

// ── Certification Form (inline) ──────────────────────────────────────────────

function CertForm({ record, employeeId, onSave, onCancel }) {
  const isEdit = !!record?.id;
  const [form, setForm] = useState({
    id: record?.id, employeeId: record?.employeeId ?? employeeId,
    certificationName: record?.certificationName ?? '', issuingBody: record?.issuingBody ?? '',
    certificateNo: record?.certificateNo ?? '', issuedDate: record?.issuedDate ?? '',
    expiryDate: record?.expiryDate ?? '', certificateUrl: record?.certificateUrl ?? '',
    notes: record?.notes ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault(); setErr('');
    if (!form.certificationName.trim()) { setErr('Certification name is required.'); return; }
    setSaving(true);
    try {
      let extra = {};
      if (file) {
        setUploading(true);
        const { storagePath, fileName } = await uploadCertificateFile(form.employeeId, file);
        extra = { storagePath, fileName };
        setUploading(false);
      }
      await onSave({ ...form, ...extra });
    } catch (ex) { setErr(ex.message || 'Failed to save.'); setSaving(false); setUploading(false); }
  };

  return (
    <div className="emp-card" style={{ marginBottom: 14, border: '2px solid var(--primary-light)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px 0' }}>
        <h4 style={{ margin: 0, fontSize: 14 }}>{isEdit ? 'Edit Certification' : 'Submit Certification'}</h4>
        <button className="btn btn-ghost btn-sm" onClick={onCancel}><X size={14} /></button>
      </div>
      <form onSubmit={handleSubmit} style={{ padding: '10px 16px 14px' }}>
        {err && <div className="alert alert-danger" style={{ padding: '6px 10px', fontSize: 12, marginBottom: 8 }}>{err}</div>}
        <div style={{ display: 'grid', gap: 10 }}>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 12 }}>Certification Name *</label>
            <input className="form-control" value={form.certificationName} onChange={e => set('certificationName', e.target.value)}
              placeholder="e.g. BLS Provider" style={{ fontSize: 13 }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Issuing Body</label>
              <input className="form-control" value={form.issuingBody} onChange={e => set('issuingBody', e.target.value)}
                placeholder="e.g. American Heart Association" style={{ fontSize: 13 }} />
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Certificate No.</label>
              <input className="form-control" value={form.certificateNo} onChange={e => set('certificateNo', e.target.value)}
                placeholder="e.g. BLS-2024-001" style={{ fontSize: 13 }} />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Issue Date</label>
              <input type="date" className="form-control" value={form.issuedDate} onChange={e => set('issuedDate', e.target.value)} style={{ fontSize: 13 }} />
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Expiry Date</label>
              <input type="date" className="form-control" value={form.expiryDate} onChange={e => set('expiryDate', e.target.value)} style={{ fontSize: 13 }} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 12 }}>Certificate File</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px',
                border: '1px dashed var(--gray-200)', borderRadius: 6, cursor: 'pointer',
                fontSize: 12, color: 'var(--gray-500)',
              }}>
                <Upload size={12} />
                {file ? file.name : record?.fileName ? `Current: ${record.fileName}` : 'Upload file…'}
                <input type="file" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" style={{ display: 'none' }}
                  onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]); }} />
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--gray-400)' }}>
                <span>or URL:</span>
                <input className="form-control" value={form.certificateUrl} onChange={e => set('certificateUrl', e.target.value)}
                  placeholder="https://…" style={{ fontSize: 11, flex: 1 }} />
              </div>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 12 }}>Notes</label>
            <textarea className="form-control" rows={2} value={form.notes} onChange={e => set('notes', e.target.value)} style={{ fontSize: 13 }} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
            {uploading ? 'Uploading…' : saving ? 'Submitting…' : isEdit ? 'Save Changes' : 'Submit for Review'}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
        </div>
        <p style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 6, marginBottom: 0 }}>
          Submitted certifications will be reviewed by HR before being verified.
        </p>
      </form>
    </div>
  );
}

// ── Training Form (inline, not modal) ────────────────────────────────────────

function TrainingForm({ record, employeeId, onSave, onCancel }) {
  const isEdit = !!record?.id;
  const [form, setForm] = useState({
    id: record?.id, employeeId: record?.employeeId ?? employeeId,
    trainingTitle: record?.trainingTitle ?? '', trainingType: record?.trainingType ?? 'external',
    provider: record?.provider ?? '', startDate: record?.startDate ?? '', endDate: record?.endDate ?? '',
    durationHours: record?.durationHours != null ? String(record.durationHours) : '',
    cost: record?.cost != null ? String(record.cost) : '0',
    status: record?.status ?? 'planned', score: record?.score ?? '',
    passed: record?.passed ?? null, certificateUrl: record?.certificateUrl ?? '', notes: record?.notes ?? '',
    isCme: record?.isCme ?? false,
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault(); setErr('');
    if (!form.trainingTitle.trim()) { setErr('Training title is required.'); return; }
    setSaving(true);
    try {
      let extra = {};
      if (file) {
        setUploading(true);
        const { storagePath, fileName } = await uploadCertificateFile(form.employeeId, file);
        extra = { storagePath, fileName };
        setUploading(false);
      }
      await onSave({ ...form, ...extra });
    } catch (ex) { setErr(ex.message || 'Failed to save.'); setSaving(false); setUploading(false); }
  };

  return (
    <div className="emp-card" style={{ marginBottom: 14, border: '2px solid var(--primary-light)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px 0' }}>
        <h4 style={{ margin: 0, fontSize: 14 }}>{isEdit ? 'Edit Training' : 'Add Training'}</h4>
        <button className="btn btn-ghost btn-sm" onClick={onCancel}><X size={14} /></button>
      </div>
      <form onSubmit={handleSubmit} style={{ padding: '10px 16px 14px' }}>
        {err && <div className="alert alert-danger" style={{ padding: '6px 10px', fontSize: 12, marginBottom: 8 }}>{err}</div>}
        <div style={{ display: 'grid', gap: 10 }}>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 12 }}>Training Title *</label>
            <input className="form-control" value={form.trainingTitle} onChange={e => set('trainingTitle', e.target.value)}
              placeholder="e.g. Fire Safety Awareness" style={{ fontSize: 13 }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Type</label>
              <select className="form-control" value={form.trainingType} onChange={e => set('trainingType', e.target.value)} style={{ fontSize: 13 }}>
                {TRAINING_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Status</label>
              <select className="form-control" value={form.status} onChange={e => set('status', e.target.value)} style={{ fontSize: 13 }}>
                {TRAINING_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 12 }}>Provider / Institution</label>
            <input className="form-control" value={form.provider} onChange={e => set('provider', e.target.value)}
              placeholder="e.g. Coursera, NCEMA" style={{ fontSize: 13 }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Start Date</label>
              <input type="date" className="form-control" value={form.startDate} onChange={e => set('startDate', e.target.value)} style={{ fontSize: 13 }} />
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>End Date</label>
              <input type="date" className="form-control" value={form.endDate} onChange={e => set('endDate', e.target.value)} style={{ fontSize: 13 }} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 12 }}>Duration (hours)</label>
            <input type="number" className="form-control" value={form.durationHours} onChange={e => set('durationHours', e.target.value)}
              placeholder="e.g. 8" min="0" step="0.5" style={{ fontSize: 13 }} />
          </div>
          <div className="form-group">
            <label className="form-label" style={{ fontSize: 12 }}>Certificate / Document</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px',
                border: '1px dashed var(--gray-200)', borderRadius: 6, cursor: 'pointer',
                fontSize: 12, color: 'var(--gray-500)',
              }}>
                <Upload size={12} />
                {file ? file.name : record?.fileName ? `Current: ${record.fileName}` : 'Upload file…'}
                <input type="file" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" style={{ display: 'none' }}
                  onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]); }} />
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--gray-400)' }}>
                <span>or URL:</span>
                <input className="form-control" value={form.certificateUrl} onChange={e => set('certificateUrl', e.target.value)}
                  placeholder="https://…" style={{ fontSize: 11, flex: 1 }} />
              </div>
            </div>
          </div>
          <div className="form-group">
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
              <input type="checkbox" checked={!!form.isCme} onChange={e => set('isCme', e.target.checked)} />
              <span>Count these hours toward my <strong>CME</strong> (Continuing Medical Education) requirement</span>
            </label>
          </div>
          {form.status === 'completed' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div className="form-group">
                <label className="form-label" style={{ fontSize: 12 }}>Score / Grade</label>
                <input className="form-control" value={form.score} onChange={e => set('score', e.target.value)}
                  placeholder="e.g. 92%" style={{ fontSize: 13 }} />
              </div>
              <div className="form-group">
                <label className="form-label" style={{ fontSize: 12 }}>Result</label>
                <select className="form-control" style={{ fontSize: 13 }}
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
            <label className="form-label" style={{ fontSize: 12 }}>Notes</label>
            <textarea className="form-control" rows={2} value={form.notes} onChange={e => set('notes', e.target.value)} style={{ fontSize: 13 }} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
            {uploading ? 'Uploading…' : saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Training'}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function EmpTraining() {
  const [records,  setRecords]  = useState([]);
  const [certs,    setCerts]    = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [emp,      setEmp]      = useState(null);
  const [showForm, setShowForm] = useState(null); // null | 'new' | record
  const [showCertForm, setShowCertForm] = useState(null); // null | 'new' | cert
  const [flash,    setFlash]    = useState(null);

  useEffect(() => {
    getMyEmployeeRecord().then(e => {
      if (!e?.id) { setLoading(false); return; }
      setEmp(e);
      Promise.all([
        getEmployeeTrainingRecords(e.id),
        getEmployeeCertifications(e.id),
      ]).then(([recs, cs]) => {
        setRecords(recs);
        setCerts(cs);
        setLoading(false);
      }).catch(() => setLoading(false));
    });
  }, []);

  const handleSaveTraining = async (form) => {
    const saved = await employeeSaveTrainingRecord(form);
    setRecords(prev => form.id ? prev.map(r => r.id === form.id ? saved : r) : [saved, ...prev]);
    setShowForm(null);
    setFlash({ type: 'success', msg: form.id ? 'Training updated.' : 'Training added.' });
    setTimeout(() => setFlash(null), 3500);
  };

  const handleSaveCert = async (form) => {
    const saved = await employeeSaveCertification(form);
    setCerts(prev => form.id ? prev.map(c => c.id === form.id ? saved : c) : [saved, ...prev]);
    setShowCertForm(null);
    setFlash({ type: 'success', msg: form.id ? 'Certification updated.' : 'Certification submitted for review.' });
    setTimeout(() => setFlash(null), 3500);
  };

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>;
  }

  const expiringSoon = certs.filter(c => { const d = certDaysLeft(c.expiryDate); return d !== null && d >= 0 && d <= 60; });
  const expiredCerts = certs.filter(c => { const d = certDaysLeft(c.expiryDate); return d !== null && d < 0; });
  const completedCount  = records.filter(r => r.status === 'completed').length;
  const activeCertCount = certs.filter(c => { const d = certDaysLeft(c.expiryDate); return d === null || d >= 0; }).length;

  return (
    <div>
      <div className="emp-page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ margin: 0 }}>Training &amp; Certifications</h2>
        </div>
        {!showForm && (
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm('new')} style={{ fontSize: 13, whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px' }}>
            <Plus size={14} /> Add Training
          </button>
        )}
      </div>

      <div className="emp-page-body">
        {flash && <div className={`alert alert-${flash.type}`} style={{ marginBottom: 12 }}>{flash.msg}</div>}

        {/* Expiry alerts */}
        {expiredCerts.length > 0 && (
          <div className="emp-card" style={{ marginBottom: 14, background: '#fef2f2', border: '1px solid #fecaca', padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <AlertTriangle size={16} color="#ef4444" />
              <strong style={{ fontSize: 14, color: '#991b1b' }}>
                {expiredCerts.length} certification{expiredCerts.length !== 1 ? 's' : ''} expired
              </strong>
            </div>
            {expiredCerts.map(c => (
              <div key={c.id} style={{ fontSize: 13, color: '#991b1b', padding: '3px 0', borderBottom: '1px solid #fecaca' }}>
                <strong>{c.certificationName}</strong>
                {c.issuingBody && ` — ${c.issuingBody}`}
                <span style={{ marginLeft: 6, opacity: 0.8 }}>expired {formatDateUAE(c.expiryDate)}</span>
              </div>
            ))}
          </div>
        )}

        {expiringSoon.length > 0 && (
          <div className="emp-card" style={{ marginBottom: 14, background: '#fffbeb', border: '1px solid #fde68a', padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <AlertTriangle size={16} color="#d97706" />
              <strong style={{ fontSize: 14, color: '#92400e' }}>
                {expiringSoon.length} certification{expiringSoon.length !== 1 ? 's' : ''} expiring soon
              </strong>
            </div>
            {expiringSoon.map(c => {
              const days = certDaysLeft(c.expiryDate);
              return (
                <div key={c.id} style={{ fontSize: 13, color: '#92400e', padding: '3px 0', borderBottom: '1px solid #fde68a' }}>
                  <strong>{c.certificationName}</strong>{' — expires in '}
                  <strong>{days} day{days !== 1 ? 's' : ''}</strong> ({formatDateUAE(c.expiryDate)})
                </div>
              );
            })}
          </div>
        )}

        {/* Summary cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, marginBottom: 20 }}>
          {[
            { val: records.length,    label: 'Total Trainings',  color: 'var(--primary)' },
            { val: completedCount,    label: 'Completed',        color: '#10b981' },
            { val: certs.length,      label: 'Certifications',   color: 'var(--primary)' },
            { val: activeCertCount,   label: 'Active Certs',     color: '#10b981' },
          ].map(({ val, label, color }) => (
            <div key={label} className="emp-card" style={{ textAlign: 'center', padding: 16 }}>
              <div style={{ fontSize: 28, fontWeight: 700, color }}>{val}</div>
              <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Add/Edit training form */}
        {showForm && (
          <TrainingForm
            record={showForm === 'new' ? null : showForm}
            employeeId={emp?.id}
            onSave={handleSaveTraining}
            onCancel={() => setShowForm(null)}
          />
        )}

        {/* Training Records */}
        <div className="emp-card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: '14px 16px 0' }}>
            <GraduationCap size={18} color="var(--primary)" />
            <h4 style={{ margin: 0, fontSize: 15 }}>Training Records</h4>
          </div>

          {records.length === 0 ? (
            <p style={{ color: 'var(--gray-400)', fontSize: 14, textAlign: 'center', padding: '16px 0' }}>
              No training records yet.
              {!showForm && (
                <button className="btn btn-ghost btn-sm" onClick={() => setShowForm('new')} style={{ marginLeft: 6 }}>
                  Add one
                </button>
              )}
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '0 16px 16px' }}>
              {records.map(r => (
                <div key={r.id} style={{ border: '1px solid var(--gray-200)', borderRadius: 10, padding: '10px 14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{r.trainingTitle}</div>
                      {r.provider && <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>{r.provider}</div>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span className={`badge ${STATUS_BADGE[r.status] || 'badge-gray'}`}>
                        {STATUS_LABEL[r.status] || r.status}
                      </span>
                      {r.status !== 'cancelled' && (
                        <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => setShowForm(r)}>
                          <Edit2 size={13} />
                        </button>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 14, marginTop: 8, fontSize: 12, color: 'var(--gray-500)', flexWrap: 'wrap', alignItems: 'center' }}>
                    <span>{TRAINING_TYPE_LABELS[r.trainingType] || r.trainingType}</span>
                    {r.startDate && (
                      <span>
                        {formatDateUAE(r.startDate)}
                        {r.endDate && r.endDate !== r.startDate ? ` → ${formatDateUAE(r.endDate)}` : ''}
                      </span>
                    )}
                    {r.durationHours != null && <span>{r.durationHours}h</span>}
                    {r.status === 'completed' && r.score && <span>Score: {r.score}</span>}
                    {r.status === 'completed' && r.passed !== null && (
                      <span style={{ color: r.passed ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                        {r.passed ? 'Passed' : 'Failed'}
                      </span>
                    )}
                    {r.isCme && <span className="badge badge-blue" style={{ fontSize: 9, padding: '1px 5px' }}>CME</span>}
                    {(r.storagePath || r.certificateUrl) && (
                      <a href={r.certificateUrl || '#'} target="_blank" rel="noopener noreferrer"
                        style={{ color: 'var(--primary)', display: 'inline-flex', alignItems: 'center', gap: 3 }}
                        onClick={async ev => {
                          if (r.storagePath) {
                            ev.preventDefault();
                            try { const url = await getCertificateSignedUrl(r.storagePath); window.open(url, '_blank'); } catch { /* ignore */ }
                          }
                        }}>
                        {r.storagePath ? <>View File <FileText size={11} /></> : <>View Certificate <ExternalLink size={11} /></>}
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Certifications */}
        <div className="emp-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '14px 16px 0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Award size={18} color="var(--primary)" />
              <h4 style={{ margin: 0, fontSize: 15 }}>Certifications</h4>
            </div>
            {!showCertForm && (
              <button className="btn btn-primary btn-sm" onClick={() => setShowCertForm('new')}
                style={{ fontSize: 12, whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 12px' }}>
                <Plus size={13} /> Add Certification
              </button>
            )}
          </div>

          <div style={{ padding: '10px 16px 16px' }}>
            {showCertForm && (
              <CertForm
                record={showCertForm === 'new' ? null : showCertForm}
                employeeId={emp?.id}
                onSave={handleSaveCert}
                onCancel={() => setShowCertForm(null)}
              />
            )}

            {certs.length === 0 ? (
              <p style={{ color: 'var(--gray-400)', fontSize: 14, textAlign: 'center', padding: '16px 0' }}>
                No certifications on record. Click "Add Certification" to submit one for review.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {certs.map(c => {
                  const { badge: expiryBadge, label: expiryLabel } = certBadge(c.expiryDate);
                  const isPending = c.status === 'pending_review';
                  const isRejected = c.status === 'rejected';
                  return (
                    <div key={c.id} style={{ border: '1px solid var(--gray-200)', borderRadius: 10, padding: '10px 14px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                            {c.certificationName}
                            {(c.storagePath || c.certificateUrl) && (
                              <a href={c.certificateUrl || '#'} target="_blank" rel="noopener noreferrer"
                                title={c.storagePath ? `File: ${c.fileName}` : 'View certificate'}
                                style={{ color: 'var(--primary)', display: 'inline-flex', alignItems: 'center' }}
                                onClick={async ev => {
                                  if (c.storagePath) {
                                    ev.preventDefault();
                                    try { const url = await getCertificateSignedUrl(c.storagePath); window.open(url, '_blank'); } catch { /* ignore */ }
                                  }
                                }}>
                                {c.storagePath ? <FileText size={12} /> : <ExternalLink size={12} />}
                              </a>
                            )}
                          </div>
                          {c.issuingBody && <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>{c.issuingBody}</div>}
                        </div>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                          {(isPending || isRejected) && (
                            <span className={`badge ${CERT_STATUS_BADGE[c.status]}`}>{CERT_STATUS_LABEL[c.status]}</span>
                          )}
                          {c.status === 'verified' && <span className={`badge ${expiryBadge}`}>{expiryLabel}</span>}
                          {isPending && !showCertForm && (
                            <button className="btn btn-ghost btn-sm" onClick={() => setShowCertForm(c)}
                              style={{ padding: '3px 8px', fontSize: 11 }}>
                              <Edit2 size={11} /> Edit
                            </button>
                          )}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 14, marginTop: 8, fontSize: 12, color: 'var(--gray-500)', flexWrap: 'wrap' }}>
                        {c.certificateNo && <span>No: {c.certificateNo}</span>}
                        {c.issuedDate    && <span>Issued: {formatDateUAE(c.issuedDate)}</span>}
                        {c.expiryDate ? <span>Expires: {formatDateUAE(c.expiryDate)}</span> : <span>No expiry date</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
