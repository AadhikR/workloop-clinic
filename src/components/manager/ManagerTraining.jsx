/**
 * ManagerTraining.jsx — Manager portal: manage training & certifications
 * for direct reports + view own training (sub-view toggle).
 */
import { useState, useEffect, useCallback } from 'react';
import { Plus, Edit2, Trash2, GraduationCap, Award, X, AlertTriangle, ExternalLink, Users, User, Upload, FileText } from 'lucide-react';
import { formatDateUAE } from '../../utils/uaeValidators';
import {
  getTeamTrainingRecords, saveTeamTrainingRecord, deleteTeamTrainingRecord,
  getTeamCertifications, saveTeamCertification, deleteTeamCertification,
  getEmployeeTrainingRecords, getEmployeeCertifications, employeeSaveTrainingRecord,
  employeeSaveCertification, getManagerDirectReports,
  uploadCertificateFile, getCertificateSignedUrl,
} from '../../utils/trainingStorage';
import { TRAINING_TYPES, TRAINING_STATUSES, certExpiryInfo } from '../TrainingManager';

const STATUS_BADGE = { planned: 'badge-gray', in_progress: 'badge-blue', completed: 'badge-green', cancelled: 'badge-red' };
const STATUS_LABEL = { planned: 'Planned', in_progress: 'In Progress', completed: 'Completed', cancelled: 'Cancelled' };
const TYPE_LABEL = Object.fromEntries(TRAINING_TYPES.map(t => [t.value, t.label]));

function certBadge(expiryDate) {
  const info = certExpiryInfo(expiryDate);
  return { badge: info.badge, label: info.label };
}

// ── Training Record Modal ────────────────────────────────────────────────────

function TrainingModal({ record, employees, onSave, onClose }) {
  const isEdit = !!record?.id;
  const [form, setForm] = useState({
    id: record?.id, employeeId: record?.employeeId ?? '',
    trainingTitle: record?.trainingTitle ?? '', trainingType: record?.trainingType ?? 'external',
    provider: record?.provider ?? '', startDate: record?.startDate ?? '', endDate: record?.endDate ?? '',
    durationHours: record?.durationHours != null ? String(record.durationHours) : '',
    cost: record?.cost != null ? String(record.cost) : '',
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
    if (!form.employeeId) { setErr('Please select an employee.'); return; }
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
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isEdit ? 'Edit Training Record' : 'Add Training Record'}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
            {err && <div className="alert alert-danger" style={{ padding: '8px 12px', fontSize: 13 }}>{err}</div>}
            <div className="form-group">
              <label className="form-label">Employee *</label>
              <select className="form-control" value={form.employeeId} onChange={e => set('employeeId', e.target.value)} disabled={isEdit}>
                <option value="">Select employee…</option>
                {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Training Title *</label>
              <input className="form-control" value={form.trainingTitle} onChange={e => set('trainingTitle', e.target.value)} placeholder="e.g. Fire Safety Awareness" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="form-control" value={form.trainingType} onChange={e => set('trainingType', e.target.value)}>
                  {TRAINING_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Status</label>
                <select className="form-control" value={form.status} onChange={e => set('status', e.target.value)}>
                  {TRAINING_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Provider / Institution</label>
              <input className="form-control" value={form.provider} onChange={e => set('provider', e.target.value)} placeholder="e.g. UAE NCEMA, Coursera" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Start Date</label>
                <input type="date" className="form-control" value={form.startDate} onChange={e => set('startDate', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">End Date</label>
                <input type="date" className="form-control" value={form.endDate} onChange={e => set('endDate', e.target.value)} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Duration (hours)</label>
                <input type="number" className="form-control" value={form.durationHours} onChange={e => set('durationHours', e.target.value)} placeholder="e.g. 8" min="0" step="0.5" />
              </div>
              <div className="form-group">
                <label className="form-label">Cost (AED)</label>
                <input type="number" className="form-control" value={form.cost} onChange={e => set('cost', e.target.value)} placeholder="0" min="0" step="0.01" />
              </div>
            </div>
            {form.status === 'completed' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Score / Grade</label>
                  <input className="form-control" value={form.score} onChange={e => set('score', e.target.value)} placeholder="e.g. 92%" />
                </div>
                <div className="form-group">
                  <label className="form-label">Result</label>
                  <select className="form-control" value={form.passed === null ? '' : String(form.passed)} onChange={e => set('passed', e.target.value === '' ? null : e.target.value === 'true')}>
                    <option value="">— N/A —</option>
                    <option value="true">Passed</option>
                    <option value="false">Failed</option>
                  </select>
                </div>
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Certificate / Document</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                  border: '1px dashed var(--gray-200)', borderRadius: 6, cursor: 'pointer',
                  fontSize: 13, color: 'var(--gray-500)',
                }}>
                  <Upload size={14} />
                  {file ? file.name : record?.fileName ? `Current: ${record.fileName}` : 'Upload certificate file…'}
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" style={{ display: 'none' }}
                    onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]); }} />
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--gray-400)' }}>
                  <span>or paste URL:</span>
                  <input className="form-control" value={form.certificateUrl} onChange={e => set('certificateUrl', e.target.value)} placeholder="https://…" style={{ fontSize: 12, flex: 1 }} />
                </div>
              </div>
            </div>
            <div className="form-group">
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <input type="checkbox" checked={!!form.isCme} onChange={e => set('isCme', e.target.checked)} />
                <span>Count these hours toward the employee's <strong>CME</strong> requirement</span>
              </label>
            </div>
            <div className="form-group">
              <label className="form-label">Notes</label>
              <textarea className="form-control" rows={2} value={form.notes} onChange={e => set('notes', e.target.value)} />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>{uploading ? 'Uploading…' : saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Record'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Certification Modal ──────────────────────────────────────────────────────

function CertModal({ cert, employees, onSave, onClose }) {
  const isEdit = !!cert?.id;
  const [form, setForm] = useState({
    id: cert?.id, employeeId: cert?.employeeId ?? '',
    certificationName: cert?.certificationName ?? '', issuingBody: cert?.issuingBody ?? '',
    certificateNo: cert?.certificateNo ?? '', issuedDate: cert?.issuedDate ?? '',
    expiryDate: cert?.expiryDate ?? '', certificateUrl: cert?.certificateUrl ?? '', notes: cert?.notes ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault(); setErr('');
    if (!form.employeeId) { setErr('Please select an employee.'); return; }
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
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 520 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isEdit ? 'Edit Certification' : 'Add Certification'}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'grid', gap: 14 }}>
            {err && <div className="alert alert-danger" style={{ padding: '8px 12px', fontSize: 13 }}>{err}</div>}
            <div className="form-group">
              <label className="form-label">Employee *</label>
              <select className="form-control" value={form.employeeId} onChange={e => set('employeeId', e.target.value)} disabled={isEdit}>
                <option value="">Select employee…</option>
                {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Certification Name *</label>
              <input className="form-control" value={form.certificationName} onChange={e => set('certificationName', e.target.value)} placeholder="e.g. ISO 9001 Lead Auditor" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Issuing Body</label>
                <input className="form-control" value={form.issuingBody} onChange={e => set('issuingBody', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Certificate No.</label>
                <input className="form-control" value={form.certificateNo} onChange={e => set('certificateNo', e.target.value)} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Issue Date</label>
                <input type="date" className="form-control" value={form.issuedDate} onChange={e => set('issuedDate', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Expiry Date</label>
                <input type="date" className="form-control" value={form.expiryDate} onChange={e => set('expiryDate', e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Certificate File</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                  border: '1px dashed var(--gray-200)', borderRadius: 6, cursor: 'pointer',
                  fontSize: 13, color: 'var(--gray-500)',
                }}>
                  <Upload size={14} />
                  {file ? file.name : cert?.fileName ? `Current: ${cert.fileName}` : 'Upload certificate file…'}
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" style={{ display: 'none' }}
                    onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]); }} />
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--gray-400)' }}>
                  <span>or paste URL:</span>
                  <input className="form-control" value={form.certificateUrl} onChange={e => set('certificateUrl', e.target.value)} placeholder="https://…" style={{ fontSize: 12, flex: 1 }} />
                </div>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Notes</label>
              <textarea className="form-control" rows={2} value={form.notes} onChange={e => set('notes', e.target.value)} />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>{uploading ? 'Uploading…' : saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Certification'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

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

// ── My Training (own view with self-enrollment) ─────────────────────────────

function MyTrainingForm({ record, employeeId, onSave, onCancel }) {
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
            <input className="form-control" value={form.trainingTitle} onChange={e => set('trainingTitle', e.target.value)} style={{ fontSize: 13 }} />
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
            <label className="form-label" style={{ fontSize: 12 }}>Provider</label>
            <input className="form-control" value={form.provider} onChange={e => set('provider', e.target.value)} style={{ fontSize: 13 }} />
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
                <input className="form-control" value={form.certificateUrl} onChange={e => set('certificateUrl', e.target.value)} placeholder="https://…" style={{ fontSize: 11, flex: 1 }} />
              </div>
            </div>
          </div>
          <div className="form-group">
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
              <input type="checkbox" checked={!!form.isCme} onChange={e => set('isCme', e.target.checked)} />
              <span>Count these hours toward my <strong>CME</strong> (Continuing Medical Education) requirement</span>
            </label>
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

const CERT_STATUS_BADGE = { pending_review: 'badge-amber', verified: 'badge-green', rejected: 'badge-red' };
const CERT_STATUS_LABEL = { pending_review: 'Pending Review', verified: 'Verified', rejected: 'Rejected' };

function MyCertForm({ record, employeeId, onSave, onCancel }) {
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
            <input className="form-control" value={form.certificationName} onChange={e => set('certificationName', e.target.value)} placeholder="e.g. BLS Provider" style={{ fontSize: 13 }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Issuing Body</label>
              <input className="form-control" value={form.issuingBody} onChange={e => set('issuingBody', e.target.value)} style={{ fontSize: 13 }} />
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 12 }}>Certificate No.</label>
              <input className="form-control" value={form.certificateNo} onChange={e => set('certificateNo', e.target.value)} style={{ fontSize: 13 }} />
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
                <input className="form-control" value={form.certificateUrl} onChange={e => set('certificateUrl', e.target.value)} placeholder="https://…" style={{ fontSize: 11, flex: 1 }} />
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

function MyTrainingView({ emp }) {
  const [records, setRecords] = useState([]);
  const [certs, setCerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(null);
  const [showCertForm, setShowCertForm] = useState(null);
  const [flash, setFlash] = useState(null);

  useEffect(() => {
    if (!emp?.id) { setLoading(false); return; }
    Promise.all([
      getEmployeeTrainingRecords(emp.id),
      getEmployeeCertifications(emp.id),
    ]).then(([r, c]) => { setRecords(r); setCerts(c); setLoading(false); })
      .catch(() => setLoading(false));
  }, [emp?.id]);

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

  if (loading) return <div style={{ padding: 32, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>;

  const completedCount = records.filter(r => r.status === 'completed').length;

  return (
    <>
      {flash && <div className={`alert alert-${flash.type}`} style={{ marginBottom: 12 }}>{flash.msg}</div>}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div />
        {!showForm && (
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm('new')} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, padding: '8px 16px' }}>
            <Plus size={14} /> Add Training
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10, marginBottom: 16 }}>
        {[
          { val: records.length, label: 'Total Trainings', color: 'var(--primary)' },
          { val: completedCount, label: 'Completed', color: '#10b981' },
          { val: certs.length, label: 'Certifications', color: 'var(--primary)' },
        ].map(({ val, label, color }) => (
          <div key={label} className="emp-card" style={{ textAlign: 'center', padding: 14 }}>
            <div style={{ fontSize: 24, fontWeight: 700, color }}>{val}</div>
            <div style={{ fontSize: 11, color: 'var(--gray-500)', marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      {showForm && (
        <MyTrainingForm
          record={showForm === 'new' ? null : showForm}
          employeeId={emp?.id}
          onSave={handleSaveTraining}
          onCancel={() => setShowForm(null)}
        />
      )}

      <div className="emp-card" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px 0' }}>
          <GraduationCap size={16} color="var(--primary)" />
          <h4 style={{ margin: 0, fontSize: 14 }}>My Training Records</h4>
        </div>
        {records.length === 0 ? (
          <p style={{ color: 'var(--gray-400)', fontSize: 13, textAlign: 'center', padding: '14px 0' }}>
            No training records yet.
            {!showForm && (
              <button className="btn btn-ghost btn-sm" onClick={() => setShowForm('new')} style={{ marginLeft: 6 }}>Add one</button>
            )}
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 16px 14px' }}>
            {records.map(r => (
              <div key={r.id} style={{ border: '1px solid var(--gray-200)', borderRadius: 8, padding: '8px 12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{r.trainingTitle}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span className={`badge ${STATUS_BADGE[r.status] || 'badge-gray'}`}>{STATUS_LABEL[r.status] || r.status}</span>
                    {r.status !== 'cancelled' && (
                      <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => setShowForm(r)}>
                        <Edit2 size={12} />
                      </button>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--gray-500)', marginTop: 4, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {r.provider && <span>{r.provider}</span>}
                  {r.startDate && <span>{formatDateUAE(r.startDate)}{r.endDate && r.endDate !== r.startDate ? ` → ${formatDateUAE(r.endDate)}` : ''}</span>}
                  {r.durationHours != null && <span>{r.durationHours}h</span>}
                  {r.status === 'completed' && r.passed !== null && (
                    <span style={{ color: r.passed ? '#10b981' : '#ef4444', fontWeight: 600 }}>{r.passed ? 'Passed' : 'Failed'}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="emp-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '12px 16px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Award size={16} color="var(--primary)" />
            <h4 style={{ margin: 0, fontSize: 14 }}>My Certifications</h4>
          </div>
          {!showCertForm && (
            <button className="btn btn-primary btn-sm" onClick={() => setShowCertForm('new')}
              style={{ fontSize: 12, whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 12px' }}>
              <Plus size={13} /> Add Certification
            </button>
          )}
        </div>
        <div style={{ padding: '8px 16px 14px' }}>
          {showCertForm && (
            <MyCertForm
              record={showCertForm === 'new' ? null : showCertForm}
              employeeId={emp?.id}
              onSave={handleSaveCert}
              onCancel={() => setShowCertForm(null)}
            />
          )}
          {certs.length === 0 ? (
            <p style={{ color: 'var(--gray-400)', fontSize: 13, textAlign: 'center', padding: '14px 0' }}>
              No certifications on record. Click "Add Certification" to submit one for review.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {certs.map(c => {
                const { badge: expiryBadge, label: expiryLabel } = certBadge(c.expiryDate);
                const isPending = c.status === 'pending_review';
                const isRejected = c.status === 'rejected';
                return (
                  <div key={c.id} style={{ border: '1px solid var(--gray-200)', borderRadius: 8, padding: '8px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                      <div style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>
                        {c.certificationName}
                        {(c.storagePath || c.certificateUrl) && (
                          <a href={c.certificateUrl || '#'} target="_blank" rel="noopener noreferrer"
                            title={c.storagePath ? `File: ${c.fileName}` : 'View certificate'}
                            style={{ marginLeft: 6, color: 'var(--primary)' }}
                            onClick={async ev => {
                              if (c.storagePath) {
                                ev.preventDefault();
                                try { const url = await getCertificateSignedUrl(c.storagePath); window.open(url, '_blank'); } catch { /* ignore */ }
                              }
                            }}>
                            {c.storagePath ? <FileText size={11} /> : <ExternalLink size={11} />}
                          </a>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                        {(isPending || isRejected) && (
                          <span className={`badge ${CERT_STATUS_BADGE[c.status]}`}>{CERT_STATUS_LABEL[c.status]}</span>
                        )}
                        {c.status === 'verified' && <span className={`badge ${expiryBadge}`}>{expiryLabel}</span>}
                        {isPending && !showCertForm && (
                          <button className="btn btn-ghost btn-sm" onClick={() => setShowCertForm(c)} style={{ padding: '3px 8px', fontSize: 11 }}>
                            <Edit2 size={11} /> Edit
                          </button>
                        )}
                      </div>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--gray-500)', marginTop: 4, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                      {c.issuingBody && <span>{c.issuingBody}</span>}
                      {c.issuedDate && <span>Issued: {formatDateUAE(c.issuedDate)}</span>}
                      {c.expiryDate ? <span>Expires: {formatDateUAE(c.expiryDate)}</span> : <span>No expiry</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function ManagerTraining({ emp }) {
  const [view, setView] = useState('team');
  const [activeTab, setActiveTab] = useState('training');
  const [directReports, setDirectReports] = useState([]);
  const [records, setRecords] = useState([]);
  const [certs, setCerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState(null);
  const [trainingModal, setTrainingModal] = useState(null);
  const [certModal, setCertModal] = useState(null);
  const [deleteTrainId, setDeleteTrainId] = useState(null);
  const [deleteCertId, setDeleteCertId] = useState(null);
  const [empFilter, setEmpFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const showFlash = (type, msg) => { setFlash({ type, msg }); setTimeout(() => setFlash(null), 4000); };

  const load = useCallback(async () => {
    setLoading(true);
    const [reports, recs, cs] = await Promise.all([
      getManagerDirectReports(),
      getTeamTrainingRecords(),
      getTeamCertifications(),
    ]);
    setDirectReports(reports);
    setRecords(recs);
    setCerts(cs);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSaveTraining = async form => {
    const saved = await saveTeamTrainingRecord(form);
    setRecords(prev => form.id ? prev.map(r => r.id === form.id ? saved : r) : [saved, ...prev]);
    setTrainingModal(null);
    showFlash('success', form.id ? 'Training record updated.' : 'Training record added.');
  };

  const handleDeleteTraining = async () => {
    if (!deleteTrainId) return;
    await deleteTeamTrainingRecord(deleteTrainId);
    setRecords(prev => prev.filter(r => r.id !== deleteTrainId));
    setDeleteTrainId(null);
    showFlash('success', 'Training record deleted.');
  };

  const handleSaveCert = async form => {
    const saved = await saveTeamCertification(form);
    setCerts(prev => form.id ? prev.map(c => c.id === form.id ? saved : c) : [saved, ...prev]);
    setCertModal(null);
    showFlash('success', form.id ? 'Certification updated.' : 'Certification added.');
  };

  const handleDeleteCert = async () => {
    if (!deleteCertId) return;
    await deleteTeamCertification(deleteCertId);
    setCerts(prev => prev.filter(c => c.id !== deleteCertId));
    setDeleteCertId(null);
    showFlash('success', 'Certification deleted.');
  };

  const filteredRecords = records.filter(r => {
    if (empFilter && r.employeeId !== empFilter) return false;
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    return true;
  });

  const filteredCerts = certs.filter(c => {
    if (empFilter && c.employeeId !== empFilter) return false;
    return true;
  });

  const completedCount = records.filter(r => r.status === 'completed').length;
  const inProgressCount = records.filter(r => r.status === 'in_progress').length;
  const expiredCertsCount = certs.filter(c => { const i = certExpiryInfo(c.expiryDate); return i.days !== null && i.days < 0; }).length;
  const expiringSoonCount = certs.filter(c => { const i = certExpiryInfo(c.expiryDate); return i.days !== null && i.days >= 0 && i.days <= 60; }).length;

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading training…</div>;

  return (
    <div>
      <div className="emp-page-header">
        <h2>Training &amp; Certifications</h2>
        <p className="text-muted text-sm">Manage your team's training and view your own</p>
      </div>

      <div className="emp-page-body">
        {flash && <div className={`alert alert-${flash.type}`} style={{ marginBottom: 14 }}>{flash.msg}</div>}

        {/* View toggle */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <button className={`btn ${view === 'team' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setView('team')} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, padding: '8px 16px' }}>
            <Users size={14} /> Team Training
          </button>
          <button className={`btn ${view === 'my' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setView('my')} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, padding: '8px 16px' }}>
            <User size={14} /> My Training
          </button>
        </div>

        {/* ── MY TRAINING ── */}
        {view === 'my' && <MyTrainingView emp={emp} />}

        {/* ── TEAM TRAINING ── */}
        {view === 'team' && (
          <>
            {/* Tab switcher + add button */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className={`btn btn-sm ${activeTab === 'training' ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => setActiveTab('training')}>
                  <GraduationCap size={14} /> Training Records
                </button>
                <button className={`btn btn-sm ${activeTab === 'certs' ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => setActiveTab('certs')}>
                  <Award size={14} /> Certifications
                  {(expiredCertsCount + expiringSoonCount) > 0 && (
                    <span style={{ marginLeft: 6, background: '#ef4444', color: '#fff', borderRadius: 10, fontSize: 10, fontWeight: 700, padding: '1px 6px' }}>
                      {expiredCertsCount + expiringSoonCount}
                    </span>
                  )}
                </button>
              </div>
              <button className="btn btn-primary btn-sm" onClick={() => activeTab === 'training' ? setTrainingModal('new') : setCertModal('new')}>
                <Plus size={14} /> {activeTab === 'training' ? 'Add Training' : 'Add Certification'}
              </button>
            </div>

            {/* Filters */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
              <select className="form-control" style={{ width: 180, fontSize: 13 }} value={empFilter} onChange={e => setEmpFilter(e.target.value)}>
                <option value="">All Reports</option>
                {directReports.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
              {activeTab === 'training' && (
                <div style={{ display: 'flex', gap: 4 }}>
                  {[{ v: 'all', l: 'All' }, ...TRAINING_STATUSES.map(s => ({ v: s.value, l: s.label }))].map(s => (
                    <button key={s.v} className={`btn btn-sm ${statusFilter === s.v ? 'btn-primary' : 'btn-ghost'}`}
                      onClick={() => setStatusFilter(s.v)} style={{ fontSize: 12 }}>{s.l}</button>
                  ))}
                </div>
              )}
            </div>

            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 10, marginBottom: 16 }}>
              {activeTab === 'training' ? (
                <>
                  <div className="emp-card" style={{ textAlign: 'center', padding: 12 }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--primary)' }}>{records.length}</div>
                    <div style={{ fontSize: 11, color: 'var(--gray-500)' }}>Total</div>
                  </div>
                  <div className="emp-card" style={{ textAlign: 'center', padding: 12 }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#10b981' }}>{completedCount}</div>
                    <div style={{ fontSize: 11, color: 'var(--gray-500)' }}>Completed</div>
                  </div>
                  <div className="emp-card" style={{ textAlign: 'center', padding: 12 }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--primary)' }}>{inProgressCount}</div>
                    <div style={{ fontSize: 11, color: 'var(--gray-500)' }}>In Progress</div>
                  </div>
                </>
              ) : (
                <>
                  <div className="emp-card" style={{ textAlign: 'center', padding: 12 }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--primary)' }}>{certs.length}</div>
                    <div style={{ fontSize: 11, color: 'var(--gray-500)' }}>Total Certs</div>
                  </div>
                  <div className="emp-card" style={{ textAlign: 'center', padding: 12 }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: expiredCertsCount > 0 ? '#ef4444' : '#10b981' }}>{expiredCertsCount}</div>
                    <div style={{ fontSize: 11, color: 'var(--gray-500)' }}>Expired</div>
                  </div>
                  <div className="emp-card" style={{ textAlign: 'center', padding: 12 }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: expiringSoonCount > 0 ? '#d97706' : '#10b981' }}>{expiringSoonCount}</div>
                    <div style={{ fontSize: 11, color: 'var(--gray-500)' }}>Expiring Soon</div>
                  </div>
                </>
              )}
            </div>

            {/* Expiry warning */}
            {activeTab === 'certs' && (expiredCertsCount + expiringSoonCount) > 0 && (
              <div className="emp-card" style={{ background: '#fffbeb', border: '1px solid #fde68a', padding: '10px 14px', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={14} color="#d97706" />
                  <span style={{ fontSize: 13, color: '#92400e', fontWeight: 600 }}>
                    {expiredCertsCount > 0 && `${expiredCertsCount} expired`}
                    {expiredCertsCount > 0 && expiringSoonCount > 0 && ', '}
                    {expiringSoonCount > 0 && `${expiringSoonCount} expiring within 60 days`}
                  </span>
                </div>
              </div>
            )}

            {/* ── Training records list ── */}
            {activeTab === 'training' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {filteredRecords.length === 0 ? (
                  <div className="emp-card" style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--gray-400)' }}>
                    <GraduationCap size={28} style={{ marginBottom: 8, opacity: 0.3 }} />
                    <p>No training records for your team yet.</p>
                    <button className="btn btn-primary btn-sm" onClick={() => setTrainingModal('new')} style={{ marginTop: 8 }}>
                      <Plus size={13} /> Add Training
                    </button>
                  </div>
                ) : filteredRecords.map(r => (
                  <div key={r.id} className="emp-card" style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 14 }}>{r.trainingTitle}</div>
                        <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                          {r.employeeName || '—'}
                          {r.provider && ` · ${r.provider}`}
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className={`badge ${STATUS_BADGE[r.status] || 'badge-gray'}`}>{STATUS_LABEL[r.status] || r.status}</span>
                        <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => setTrainingModal(r)}><Edit2 size={13} /></button>
                        <button className="btn btn-ghost btn-sm" title="Delete" style={{ color: 'var(--danger)' }} onClick={() => setDeleteTrainId(r.id)}><Trash2 size={13} /></button>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 12, color: 'var(--gray-500)', flexWrap: 'wrap' }}>
                      <span className="badge badge-gray" style={{ fontSize: 11 }}>{TYPE_LABEL[r.trainingType] || r.trainingType}</span>
                      {r.startDate && <span>{formatDateUAE(r.startDate)}{r.endDate && r.endDate !== r.startDate ? ` → ${formatDateUAE(r.endDate)}` : ''}</span>}
                      {r.durationHours != null && <span>{r.durationHours}h</span>}
                      {r.cost > 0 && <span>AED {r.cost.toLocaleString('en-AE')}</span>}
                      {r.status === 'completed' && r.passed !== null && (
                        <span style={{ color: r.passed ? '#10b981' : '#ef4444', fontWeight: 600 }}>{r.passed ? 'Passed' : 'Failed'}</span>
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
                          Certificate {r.storagePath ? <FileText size={11} /> : <ExternalLink size={11} />}
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Certifications list ── */}
            {activeTab === 'certs' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {filteredCerts.length === 0 ? (
                  <div className="emp-card" style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--gray-400)' }}>
                    <Award size={28} style={{ marginBottom: 8, opacity: 0.3 }} />
                    <p>No certifications for your team yet.</p>
                    <button className="btn btn-primary btn-sm" onClick={() => setCertModal('new')} style={{ marginTop: 8 }}>
                      <Plus size={13} /> Add Certification
                    </button>
                  </div>
                ) : filteredCerts.map(c => {
                  const { badge, label } = certBadge(c.expiryDate);
                  return (
                    <div key={c.id} className="emp-card" style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 14 }}>
                            {c.certificationName}
                            {(c.storagePath || c.certificateUrl) && (
                              <a href={c.certificateUrl || '#'} target="_blank" rel="noopener noreferrer"
                                style={{ marginLeft: 6, color: 'var(--primary)' }}
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
                          <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                            {c.employeeName || '—'}
                            {c.issuingBody && ` · ${c.issuingBody}`}
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className={`badge ${badge}`}>{label}</span>
                          <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => setCertModal(c)}><Edit2 size={13} /></button>
                          <button className="btn btn-ghost btn-sm" title="Delete" style={{ color: 'var(--danger)' }} onClick={() => setDeleteCertId(c.id)}><Trash2 size={13} /></button>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 12, color: 'var(--gray-500)', flexWrap: 'wrap' }}>
                        {c.certificateNo && <span>No: {c.certificateNo}</span>}
                        {c.issuedDate && <span>Issued: {formatDateUAE(c.issuedDate)}</span>}
                        {c.expiryDate ? <span>Expires: {formatDateUAE(c.expiryDate)}</span> : <span>No expiry</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {/* Modals */}
      {trainingModal && (
        <TrainingModal
          record={trainingModal === 'new' ? null : trainingModal}
          employees={directReports}
          onSave={handleSaveTraining}
          onClose={() => setTrainingModal(null)}
        />
      )}
      {certModal && (
        <CertModal
          cert={certModal === 'new' ? null : certModal}
          employees={directReports}
          onSave={handleSaveCert}
          onClose={() => setCertModal(null)}
        />
      )}
      {deleteTrainId && (
        <DeleteConfirm title="Delete Training Record" message="Are you sure? This cannot be undone."
          onConfirm={handleDeleteTraining} onCancel={() => setDeleteTrainId(null)} />
      )}
      {deleteCertId && (
        <DeleteConfirm title="Delete Certification" message="Are you sure? This cannot be undone."
          onConfirm={handleDeleteCert} onCancel={() => setDeleteCertId(null)} />
      )}
    </div>
  );
}
