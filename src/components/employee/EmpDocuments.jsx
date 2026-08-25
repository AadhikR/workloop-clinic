import { useEffect, useRef, useState } from 'react';
import { Upload, FileText, Clock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { getMyDocuments, getMyEmployeeRecord } from '../../utils/profileStorage';
import { CLINICAL_DOC_TYPES, DOC_GROUPS } from '../EmployeeModal';
import { validateEmiratesID } from '../../utils/uaeValidators';

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB

const EMPTY_FORM = { type: 'Visa', number: '', expiryDate: '', notes: '', file: null };

function statusBadge(status) {
  if (status === 'pending_verification') return { label: 'Pending Review', cls: 'badge-amber', Icon: Clock };
  if (status === 'rejected')             return { label: 'Rejected',       cls: 'badge-red',   Icon: XCircle };
  return                                        { label: 'Verified',       cls: 'badge-green', Icon: CheckCircle };
}

function docExpiryLabel(expiryDate) {
  if (!expiryDate) return null;
  const days = Math.ceil((new Date(expiryDate) - new Date()) / (1000 * 60 * 60 * 24));
  if (days < 0)   return { text: `Expired ${Math.abs(days)}d ago`, cls: 'badge-red' };
  if (days <= 30) return { text: `${days}d left`,                  cls: 'badge-red' };
  if (days <= 60) return { text: `${days}d left`,                  cls: 'badge-amber' };
  return null; // valid — no badge
}

function formatBytes(bytes) {
  if (!bytes) return '';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function EmpDocuments() {
  const [emp, setEmp]             = useState(null);
  const [docs, setDocs]           = useState([]);
  const [loading, setLoading]     = useState(true);
  const [form, setForm]           = useState(EMPTY_FORM);
  const [uploading, setUploading] = useState(false);
  const [toast, setToast]         = useState(null);
  const fileRef                   = useRef(null);

  useEffect(() => {
    Promise.all([getMyEmployeeRecord(), getMyDocuments()]).then(([e, d]) => {
      setEmp(e);
      setDocs(d);
      setLoading(false);
    });
  }, []);

  const showToast = (type, msg) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const reload = () => getMyDocuments().then(setDocs);

  const handleSubmit = async e => {
    e.preventDefault();
    if (!form.file) { showToast('error', 'Please select a file to upload.'); return; }
    if (form.file.size > MAX_FILE_BYTES) { showToast('error', 'File must be under 10 MB.'); return; }
    if (!emp?.id || !emp?.user_id) { showToast('error', 'Employee record not loaded. Please try refreshing.'); return; }

    // Emirates ID format check — only when the field is non-empty and type
    // matches, so it stays optional.
    if (form.type === 'Emirates ID' && form.number && form.number.trim()) {
      const eidCheck = validateEmiratesID(form.number);
      if (!eidCheck.valid) { showToast('error', eidCheck.message); return; }
    }

    // Document number is required on ALL uploads — HR needs it to match against
    // MoHRE / DHA / DOH / MOH portals, and the SIF compliance gate looks it up.
    const num = (form.number || '').trim();
    if (!num) {
      showToast('error', 'Document number is required — please enter it before uploading.');
      return;
    }
    // Clinical licence numbers follow a stricter format so they can be matched
    // one-to-one against the government portals.
    const CLINICAL_LICENCE_TYPES = new Set(['DHA Licence', 'DOH Licence', 'MOH Licence']);
    if (CLINICAL_LICENCE_TYPES.has(form.type)) {
      if (!/^[A-Za-z0-9\-/]{3,30}$/.test(num)) {
        showToast('error', 'Licence number must be 3–30 letters/digits (hyphens and slashes allowed).');
        return;
      }
    }

    // Expiry cannot be in the past — an expired doc shouldn't be submitted for review.
    if (form.expiryDate) {
      const expiry = new Date(form.expiryDate);
      const today  = new Date();
      today.setHours(0, 0, 0, 0);
      expiry.setHours(0, 0, 0, 0);
      if (expiry < today) {
        showToast('error', 'Expiry date is in the past. Please upload a valid document.');
        return;
      }
    }

    setUploading(true);
    try {
      // Upload file to Storage: {admin_uid}/{emp_id}/{timestamp}_{filename}
      const safeName = form.file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
      const path = `${emp.user_id}/${emp.id}/${Date.now()}_${safeName}`;
      const { error: uploadErr } = await supabase.storage
        .from('employee-documents')
        .upload(path, form.file, { upsert: false });
      if (uploadErr) throw new Error(`Upload failed: ${uploadErr.message}`);

      // Write DB row via SECURITY DEFINER RPC
      const { error: rpcErr } = await supabase.rpc('employee_submit_document', {
        p_document_type:   form.type,
        p_document_number: form.number,
        p_expiry_date:     form.expiryDate || null,
        p_notes:           form.notes,
        p_storage_path:    path,
        p_file_name:       form.file.name,
        p_file_size:       form.file.size,
      });
      if (rpcErr) {
        // Clean up orphan file on DB failure
        await supabase.storage.from('employee-documents').remove([path]).catch(() => {});
        throw new Error(rpcErr.message);
      }

      setForm(EMPTY_FORM);
      if (fileRef.current) fileRef.current.value = '';
      await reload();
      showToast('success', 'Document submitted for HR review.');
    } catch (err) {
      showToast('error', err.message || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="emp-page-body">
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading documents…</div>
      </div>
    );
  }

  return (
    <div className="emp-page-body">
      {toast && (
        <div className={`alert alert-${toast.type === 'success' ? 'success' : 'danger'}`} style={{ marginBottom: 16 }}>
          {toast.msg}
        </div>
      )}

      {/* Upload form */}
      <div className="emp-card" style={{ marginBottom: 20 }}>
        <div className="emp-card-header">
          <h3>Submit a Document</h3>
          <p style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
            Upload your credentials for HR review. Supported: PDF, JPG, PNG — max 10 MB.
          </p>
        </div>
        <div className="emp-card-body">
          <form onSubmit={handleSubmit}>
            <div className="form-grid form-grid-2" style={{ gap: 14 }}>

              <div className="form-group">
                <label>Document Type</label>
                <select
                  className="form-control"
                  value={form.type}
                  onChange={e => setForm(p => ({ ...p, type: e.target.value }))}
                >
                  {DOC_GROUPS.map(g => (
                    <optgroup key={g.label} label={g.label}>
                      {g.types.map(t => <option key={t} value={t}>{t}</option>)}
                    </optgroup>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>
                  Document Number
                  <span aria-hidden="true" style={{ color: 'var(--danger)', marginLeft: 3, fontWeight: 700 }}>*</span>
                </label>
                <input
                  className="form-control"
                  placeholder="e.g. DHA-123456, Passport No."
                  value={form.number}
                  onChange={e => setForm(p => ({ ...p, number: e.target.value }))}
                />
              </div>

              <div className="form-group">
                <label>
                  Expiry Date
                  <span style={{ color: 'var(--gray-400)', fontWeight: 400, marginLeft: 4 }}>(optional)</span>
                </label>
                <input
                  type="date"
                  className="form-control"
                  value={form.expiryDate}
                  onChange={e => setForm(p => ({ ...p, expiryDate: e.target.value }))}
                />
              </div>

              <div className="form-group">
                <label>
                  Notes
                  <span style={{ color: 'var(--gray-400)', fontWeight: 400, marginLeft: 4 }}>(optional)</span>
                </label>
                <input
                  className="form-control"
                  placeholder="e.g. Original submitted to PRO"
                  value={form.notes}
                  onChange={e => setForm(p => ({ ...p, notes: e.target.value }))}
                />
              </div>

              <div className="form-group" style={{ gridColumn: '1/-1' }}>
                <label>File</label>
                <div
                  style={{
                    border: '2px dashed var(--gray-300)', borderRadius: 8,
                    padding: '14px 18px', textAlign: 'center', cursor: 'pointer',
                    background: 'var(--gray-50)', fontSize: 13, color: 'var(--gray-500)',
                  }}
                  onClick={() => fileRef.current?.click()}
                >
                  {form.file
                    ? <><strong style={{ color: 'var(--gray-800)' }}>{form.file.name}</strong>
                        <span style={{ color: 'var(--gray-400)', marginLeft: 6 }}>({formatBytes(form.file.size)})</span></>
                    : <><Upload size={14} style={{ display: 'inline', marginRight: 6 }} />Click to choose file</>
                  }
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  style={{ display: 'none' }}
                  onChange={e => {
                    const f = e.target.files[0];
                    if (f) setForm(p => ({ ...p, file: f }));
                    e.target.value = '';
                  }}
                />
              </div>

            </div>

            {CLINICAL_DOC_TYPES.has(form.type) && (
              <div style={{
                marginTop: 12, padding: '8px 12px', borderRadius: 8,
                background: 'rgba(6,182,212,0.08)', border: '1px solid rgba(6,182,212,0.20)',
                fontSize: 12, color: 'var(--accent)',
              }}>
                <strong>Clinical credential</strong> — HR will verify this document before it appears as active in your record. You&apos;ll be notified once reviewed.
              </div>
            )}

            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={uploading || !form.file}
              >
                {uploading ? 'Uploading…' : 'Submit for Review'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Document list */}
      <div className="emp-card">
        <div className="emp-card-header">
          <h3>My Documents {!loading && `(${docs.length})`}</h3>
        </div>
        {docs.length === 0 ? (
          <div style={{ padding: '28px 20px', textAlign: 'center', color: 'var(--gray-500)', fontSize: 13 }}>
            <FileText size={32} style={{ margin: '0 auto 10px', display: 'block', opacity: 0.3 }} />
            No documents on file yet. Use the form above to submit your credentials.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Number</th>
                  <th>File</th>
                  <th>Expiry</th>
                  <th>Status</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {docs.map(doc => {
                  const clinical  = CLINICAL_DOC_TYPES.has(doc.documentType);
                  const { label: stLabel, cls: stCls, Icon: StIcon } = statusBadge(doc.status);
                  const expiry    = docExpiryLabel(doc.expiryDate);
                  return (
                    <tr key={doc.id}>
                      <td>
                        <span className={`badge ${clinical ? 'badge-cyan' : 'badge-blue'}`} style={{ fontSize: 11 }}>
                          {doc.documentType}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: 'var(--gray-600)' }}>
                        {doc.documentNumber || <span style={{ color: 'var(--gray-300)' }}>—</span>}
                      </td>
                      <td>
                        {doc.signedUrl
                          ? <a href={doc.signedUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--primary)', fontSize: 13, fontWeight: 500, textDecoration: 'none' }}>{doc.fileName}</a>
                          : <span style={{ fontSize: 12, color: 'var(--gray-600)' }}>{doc.fileName}</span>
                        }
                      </td>
                      <td>
                        {expiry
                          ? <span className={`badge ${expiry.cls}`} style={{ fontSize: 11 }}>{expiry.text}</span>
                          : <span style={{ fontSize: 12, color: 'var(--gray-400)' }}>{doc.expiryDate || '—'}</span>
                        }
                      </td>
                      <td>
                        <span className={`badge ${stCls}`} style={{ fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <StIcon size={10} />
                          {stLabel}
                        </span>
                        {doc.status === 'rejected' && doc.rejectionReason && (
                          <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 2 }}>
                            <AlertTriangle size={10} style={{ display: 'inline', marginRight: 2 }} />
                            {doc.rejectionReason}
                          </div>
                        )}
                      </td>
                      <td style={{ fontSize: 11, color: 'var(--gray-400)' }}>
                        {doc.submittedBy === 'employee' ? 'Self' : 'HR'}
                        <div>{doc.uploadedAt?.split('T')[0] || '—'}</div>
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
  );
}
