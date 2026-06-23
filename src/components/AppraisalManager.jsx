import { useState, useEffect } from 'react';
import { Plus, Star, ChevronDown, ChevronUp, Trash2, X, ClipboardList, CheckCircle, AlertCircle } from 'lucide-react';
import {
  getAppraisalCycles, saveAppraisalCycle, deleteAppraisalCycle,
  getAppraisalsForCycle, createAppraisalsForCycle, saveAppraisalReview,
  calibrateAppraisal, deleteAppraisal, RATING_LABELS, DEFAULT_SECTIONS,
} from '../utils/appraisalStorage';
import { getEmployees } from '../utils/storage';
import { useAuth } from '../context/AuthContext';

const STATUS_BADGE = {
  pending:       'badge-amber',
  self_reviewed: 'badge-blue',
  reviewed:      'badge-green',
  calibrated:    'badge-purple',
};
const STATUS_LABEL = {
  pending:       'Pending Review',
  self_reviewed: 'Self Reviewed',
  reviewed:      'Reviewed',
  calibrated:    'Calibrated',
};
const CYCLE_STATUS_BADGE = { draft: 'badge-amber', active: 'badge-green', closed: 'badge-red' };

function RatingInput({ value, onChange, disabled, small }) {
  return (
    <div style={{ display: 'flex', gap: small ? 2 : 4, alignItems: 'center' }}>
      {[1, 2, 3, 4, 5].map(n => (
        <button
          key={n}
          type="button"
          onClick={() => !disabled && onChange(value === n ? null : n)}
          title={RATING_LABELS[n]}
          style={{
            background: 'none', border: 'none', cursor: disabled ? 'default' : 'pointer',
            padding: small ? '0 1px' : '0 2px', opacity: disabled ? 0.7 : 1,
          }}
        >
          <Star
            size={small ? 16 : 20}
            fill={value >= n ? '#f59e0b' : 'none'}
            color={value >= n ? '#f59e0b' : '#cbd5e1'}
          />
        </button>
      ))}
      {value != null && (
        <span style={{ fontSize: 11, color: 'var(--gray-500)', marginLeft: 2 }}>
          {Number(value).toFixed(1)} — {RATING_LABELS[Math.round(value)]}
        </span>
      )}
    </div>
  );
}

function AppraisalModal({ appraisal, employee, onSave, onClose, reviewerEmail, disabled }) {
  const [sections, setSections] = useState(
    (appraisal.sections || []).slice().sort((a, b) => a.sortOrder - b.sortOrder)
  );
  const [reviewerComments, setReviewerComments] = useState(appraisal.reviewerComments || '');
  const [developmentPlan, setDevelopmentPlan]   = useState(appraisal.developmentPlan  || '');
  const [saving, setSaving]                     = useState(false);
  const [err, setErr]                           = useState(null);

  const ratedCount = sections.filter(s => s.rating != null).length;
  const totalWeight = sections.filter(s => s.rating != null).reduce((s, sec) => s + (sec.weight || 1), 0);
  const weightedSum = sections.filter(s => s.rating != null).reduce((s, sec) => s + sec.rating * (sec.weight || 1), 0);
  const liveOverall = totalWeight > 0 ? Math.round(weightedSum / totalWeight * 10) / 10 : null;

  const setRating = (idx, val) =>
    setSections(prev => prev.map((s, i) => i === idx ? { ...s, rating: val } : s));
  const setComment = (idx, val) =>
    setSections(prev => prev.map((s, i) => i === idx ? { ...s, comments: val } : s));

  const handleSave = async () => {
    setSaving(true);
    setErr(null);
    try {
      const saved = await saveAppraisalReview(appraisal.id, {
        sections: sections.map(s => ({ id: s.id, rating: s.rating, selfRating: s.selfRating, comments: s.comments, weight: s.weight })),
        reviewerComments, developmentPlan, reviewedBy: reviewerEmail,
      });
      onSave(saved);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 680, maxHeight: '90vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ClipboardList size={18} />
            Appraisal Review — {employee?.name}
          </h2>
          <button className="modal-close" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="modal-body" style={{ overflowY: 'auto', flex: 1 }}>
          {err && <div className="alert alert-error mb-3">{err}</div>}

          {/* Overall rating summary */}
          <div style={{
            background: liveOverall != null ? '#f0fdf4' : '#fffbeb',
            border: `1px solid ${liveOverall != null ? '#bbf7d0' : '#fde68a'}`,
            borderRadius: 8, padding: '10px 16px', marginBottom: 16,
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--gray-500)', fontWeight: 600 }}>OVERALL RATING</div>
              {liveOverall != null ? (
                <div style={{ fontSize: 24, fontWeight: 700, color: '#166534', lineHeight: 1.2 }}>
                  {liveOverall.toFixed(1)} / 5.0
                </div>
              ) : (
                <div style={{ fontSize: 13, color: '#92400e' }}>Rate all sections to compute</div>
              )}
            </div>
            {liveOverall != null && (
              <div style={{ fontSize: 13, fontWeight: 600, color: '#166534' }}>
                {RATING_LABELS[Math.round(liveOverall)]}
              </div>
            )}
            <div style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--gray-400)' }}>
              {ratedCount} / {sections.length} sections rated
            </div>
          </div>

          {/* Sections */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
            {sections.map((sec, idx) => (
              <div key={sec.id} style={{
                border: '1px solid var(--gray-200)', borderRadius: 8, padding: '10px 14px',
                background: sec.rating != null ? '#f8fafc' : '#fff',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>
                    {sec.sectionName}
                    <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--gray-400)', marginLeft: 6 }}>
                      ×{sec.weight} weight
                    </span>
                  </span>
                  {sec.selfRating != null && (
                    <span style={{ fontSize: 11, color: 'var(--gray-500)' }}>
                      Self: <strong>{sec.selfRating.toFixed(1)}</strong>
                    </span>
                  )}
                </div>
                <RatingInput value={sec.rating} onChange={val => setRating(idx, val)} disabled={disabled} />
                <textarea
                  placeholder="Section comments (optional)"
                  value={sec.comments || ''}
                  onChange={e => setComment(idx, e.target.value)}
                  disabled={disabled}
                  rows={2}
                  style={{
                    width: '100%', marginTop: 8, fontSize: 12, border: '1px solid var(--gray-200)',
                    borderRadius: 6, padding: '6px 10px', resize: 'vertical', boxSizing: 'border-box',
                    background: disabled ? '#f8fafc' : '#fff', color: 'var(--gray-700)',
                  }}
                />
              </div>
            ))}
          </div>

          {/* Reviewer summary fields */}
          <div className="form-group">
            <label className="form-label">Reviewer Comments</label>
            <textarea
              className="form-control"
              rows={3}
              value={reviewerComments}
              onChange={e => setReviewerComments(e.target.value)}
              disabled={disabled}
              placeholder="Overall performance summary, strengths, areas for improvement…"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Development Plan</label>
            <textarea
              className="form-control"
              rows={3}
              value={developmentPlan}
              onChange={e => setDevelopmentPlan(e.target.value)}
              disabled={disabled}
              placeholder="Goals, training, career development actions for next period…"
            />
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
          {!disabled && (
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save Review'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AppraisalManager() {
  const { user } = useAuth();
  const [tab, setTab]               = useState('cycles');
  const [cycles, setCycles]         = useState([]);
  const [employees, setEmployees]   = useState([]);
  const [appraisals, setAppraisals] = useState([]);
  const [activeCycleId, setActiveCycleId] = useState(null);
  const [loading, setLoading]       = useState(true);
  const [err, setErr]               = useState(null);
  const [toast, setToast]           = useState(null);

  // Cycle form
  const [showCycleForm, setShowCycleForm] = useState(false);
  const [cycleForm, setCycleForm]         = useState({ name: '', reviewFrom: '', reviewTo: '', status: 'draft' });
  const [savingCycle, setSavingCycle]     = useState(false);

  // Appraisal modal
  const [reviewModal, setReviewModal]   = useState(null); // { appraisal, employee }

  const showToast = (type, msg) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3500);
  };

  useEffect(() => {
    Promise.all([getAppraisalCycles(), getEmployees()])
      .then(([c, e]) => {
        setCycles(c);
        setEmployees(e.filter(emp => emp.active !== false));
        if (c.length && !activeCycleId) setActiveCycleId(c[0].id);
      })
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!activeCycleId) { setAppraisals([]); return; }
    getAppraisalsForCycle(activeCycleId).then(setAppraisals).catch(() => {});
  }, [activeCycleId]);

  // ── Cycle CRUD ──────────────────────────────────────────────────────────────
  const handleSaveCycle = async () => {
    if (!cycleForm.name.trim() || !cycleForm.reviewFrom || !cycleForm.reviewTo) return;
    setSavingCycle(true);
    try {
      const saved = await saveAppraisalCycle(cycleForm);
      setCycles(prev => cycleForm.id
        ? prev.map(c => c.id === cycleForm.id ? saved : c)
        : [saved, ...prev]);
      if (!activeCycleId) setActiveCycleId(saved.id);
      setShowCycleForm(false);
      setCycleForm({ name: '', reviewFrom: '', reviewTo: '', status: 'draft' });
      showToast('success', 'Cycle saved.');
    } catch (e) {
      showToast('error', e.message);
    } finally {
      setSavingCycle(false);
    }
  };

  const handleDeleteCycle = async (id) => {
    if (!window.confirm('Delete this appraisal cycle and all its reviews?')) return;
    try {
      await deleteAppraisalCycle(id);
      setCycles(prev => prev.filter(c => c.id !== id));
      if (activeCycleId === id) setActiveCycleId(cycles[0]?.id || null);
      showToast('success', 'Cycle deleted.');
    } catch (e) {
      showToast('error', e.message);
    }
  };

  // ── Appraisals ──────────────────────────────────────────────────────────────
  const handleGenerateAppraisals = async () => {
    if (!activeCycleId) return;
    const activeEmpIds = employees.map(e => e.id);
    try {
      const created = await createAppraisalsForCycle(activeCycleId, activeEmpIds);
      if (created.length === 0) {
        showToast('info', 'All active employees already have an appraisal in this cycle.');
      } else {
        showToast('success', `Created ${created.length} appraisal${created.length !== 1 ? 's' : ''}.`);
      }
      const refreshed = await getAppraisalsForCycle(activeCycleId);
      setAppraisals(refreshed);
    } catch (e) {
      showToast('error', e.message);
    }
  };

  const handleDeleteAppraisal = async (id) => {
    if (!window.confirm('Delete this appraisal?')) return;
    try {
      await deleteAppraisal(id);
      setAppraisals(prev => prev.filter(a => a.id !== id));
      showToast('success', 'Appraisal deleted.');
    } catch (e) {
      showToast('error', e.message);
    }
  };

  const handleReviewSaved = (updatedAppraisal) => {
    setAppraisals(prev => prev.map(a => a.id === updatedAppraisal.id ? updatedAppraisal : a));
    setReviewModal(null);
    showToast('success', 'Appraisal review saved.');
  };

  // ── Stats ────────────────────────────────────────────────────────────────────
  const reviewed   = appraisals.filter(a => a.status === 'reviewed' || a.status === 'calibrated').length;
  const pending    = appraisals.filter(a => a.status === 'pending').length;
  const avgRating  = (() => {
    const rated = appraisals.filter(a => a.overallRating != null);
    if (!rated.length) return null;
    return (rated.reduce((s, a) => s + a.overallRating, 0) / rated.length).toFixed(1);
  })();
  const activeCycle = cycles.find(c => c.id === activeCycleId);

  if (loading) return <div className="page-body"><div className="card" style={{ padding: 32, textAlign: 'center' }}>Loading appraisals…</div></div>;
  if (err)     return <div className="page-body"><div className="alert alert-error">{err}</div></div>;

  return (
    <div className="page-body">
      {toast && (
        <div className={`alert alert-${toast.type === 'error' ? 'error' : toast.type === 'info' ? 'warning' : 'success'} mb-4`}
          style={{ position: 'fixed', top: 16, right: 280, zIndex: 9999, maxWidth: 340 }}>
          {toast.msg}
        </div>
      )}

      <div className="page-header">
        <div>
          <h1>Appraisals</h1>
          <p style={{ color: 'var(--gray-500)', fontSize: 13, marginTop: 4 }}>
            Employee evaluation & performance review cycles
          </p>
        </div>
        {tab === 'cycles' && (
          <button className="btn btn-primary" onClick={() => { setCycleForm({ name: '', reviewFrom: '', reviewTo: '', status: 'draft' }); setShowCycleForm(true); }}>
            <Plus size={15} /> New Cycle
          </button>
        )}
        {tab === 'reviews' && activeCycleId && (
          <button className="btn btn-primary" onClick={handleGenerateAppraisals}>
            <Plus size={15} /> Generate Appraisals
          </button>
        )}
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {[['cycles', 'Cycles'], ['reviews', 'Reviews']].map(([id, label]) => (
          <button
            key={id}
            className={`tab-btn ${tab === id ? 'active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
            {id === 'reviews' && appraisals.length > 0 && (
              <span className="badge badge-blue" style={{ marginLeft: 6, fontSize: 11 }}>
                {appraisals.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Cycles Tab ── */}
      {tab === 'cycles' && (
        <>
          {showCycleForm && (
            <div className="card mb-4">
              <div className="card-header">
                <h3>{cycleForm.id ? 'Edit Cycle' : 'New Appraisal Cycle'}</h3>
              </div>
              <div className="card-body">
                <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr auto' }}>
                  <div className="form-group">
                    <label className="form-label">Cycle Name *</label>
                    <input className="form-control" placeholder="e.g. H1 2025"
                      value={cycleForm.name}
                      onChange={e => setCycleForm(p => ({ ...p, name: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">From *</label>
                    <input className="form-control" type="date"
                      value={cycleForm.reviewFrom}
                      onChange={e => setCycleForm(p => ({ ...p, reviewFrom: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">To *</label>
                    <input className="form-control" type="date"
                      value={cycleForm.reviewTo}
                      onChange={e => setCycleForm(p => ({ ...p, reviewTo: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select className="form-control"
                      value={cycleForm.status}
                      onChange={e => setCycleForm(p => ({ ...p, status: e.target.value }))}>
                      <option value="draft">Draft</option>
                      <option value="active">Active</option>
                      <option value="closed">Closed</option>
                    </select>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <button className="btn btn-primary" onClick={handleSaveCycle} disabled={savingCycle}>
                    {savingCycle ? 'Saving…' : 'Save Cycle'}
                  </button>
                  <button className="btn btn-secondary" onClick={() => setShowCycleForm(false)}>Cancel</button>
                </div>
              </div>
            </div>
          )}

          {cycles.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <ClipboardList size={40} style={{ color: 'var(--gray-300)', marginBottom: 12 }} />
                <h3>No appraisal cycles yet</h3>
                <p>Create a cycle to start managing employee performance reviews.</p>
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Cycle Name</th>
                      <th>Review Period</th>
                      <th>Status</th>
                      <th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cycles.map(c => (
                      <tr key={c.id}>
                        <td><strong>{c.name}</strong></td>
                        <td style={{ fontSize: 13 }}>
                          {c.reviewFrom} → {c.reviewTo}
                        </td>
                        <td>
                          <span className={`badge ${CYCLE_STATUS_BADGE[c.status]}`}>
                            {c.status.charAt(0).toUpperCase() + c.status.slice(1)}
                          </span>
                        </td>
                        <td className="text-right">
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: 12, padding: '4px 10px', marginRight: 6 }}
                            onClick={() => { setActiveCycleId(c.id); setTab('reviews'); }}
                          >
                            Reviews
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: 12, padding: '4px 10px', marginRight: 6 }}
                            onClick={() => { setCycleForm({ ...c }); setShowCycleForm(true); }}
                          >
                            Edit
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: 12, padding: '4px 10px', color: 'var(--danger)' }}
                            title="Delete cycle"
                            onClick={() => handleDeleteCycle(c.id)}
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Reviews Tab ── */}
      {tab === 'reviews' && (
        <>
          {/* Cycle picker */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <label style={{ fontWeight: 600, fontSize: 13 }}>Cycle:</label>
            <select
              className="form-control"
              style={{ width: 220 }}
              value={activeCycleId || ''}
              onChange={e => setActiveCycleId(e.target.value || null)}
            >
              <option value="">Select cycle…</option>
              {cycles.map(c => <option key={c.id} value={c.id}>{c.name} ({c.status})</option>)}
            </select>
            {activeCycle && (
              <span className={`badge ${CYCLE_STATUS_BADGE[activeCycle.status]}`}>
                {activeCycle.reviewFrom} — {activeCycle.reviewTo}
              </span>
            )}
          </div>

          {/* Summary stats */}
          {appraisals.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
              {[
                { label: 'Total', value: appraisals.length,        badge: 'badge-blue' },
                { label: 'Reviewed', value: reviewed,              badge: 'badge-green' },
                { label: 'Pending',  value: pending,               badge: 'badge-amber' },
                { label: 'Avg Rating', value: avgRating ? `${avgRating} / 5.0` : '—', badge: 'badge-blue' },
              ].map(({ label, value, badge }) => (
                <div key={label} className="card" style={{ padding: '16px 20px' }}>
                  <div className="stat-label">{label}</div>
                  <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{value}</div>
                </div>
              ))}
            </div>
          )}

          {!activeCycleId ? (
            <div className="card">
              <div className="empty-state">Select a cycle above to view its reviews.</div>
            </div>
          ) : appraisals.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <CheckCircle size={36} style={{ color: 'var(--gray-300)', marginBottom: 12 }} />
                <h3>No appraisals in this cycle</h3>
                <p>Click "Generate Appraisals" to create reviews for all active employees.</p>
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Department</th>
                      <th className="text-right">Overall Rating</th>
                      <th>Status</th>
                      <th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {appraisals.map(ap => {
                      const emp = employees.find(e => e.id === ap.employeeId);
                      if (!emp) return null;
                      return (
                        <tr key={ap.id}>
                          <td>
                            <strong>{emp.name}</strong>
                            <div style={{ fontSize: 11, color: 'var(--gray-400)' }}>{emp.jobTitle}</div>
                          </td>
                          <td style={{ fontSize: 13 }}>{emp.department || '—'}</td>
                          <td className="text-right">
                            {ap.overallRating != null ? (
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                                <RatingInput value={ap.overallRating} onChange={() => {}} disabled small />
                                <span style={{ fontWeight: 700 }}>{ap.overallRating.toFixed(1)}</span>
                              </div>
                            ) : (
                              <span style={{ color: 'var(--gray-300)', fontSize: 13 }}>Not rated</span>
                            )}
                          </td>
                          <td>
                            <span className={`badge ${STATUS_BADGE[ap.status]}`}>
                              {STATUS_LABEL[ap.status]}
                            </span>
                          </td>
                          <td className="text-right">
                            <button
                              className="btn btn-primary"
                              style={{ fontSize: 12, padding: '4px 12px', marginRight: 6 }}
                              onClick={() => setReviewModal({ appraisal: ap, employee: emp })}
                            >
                              {ap.status === 'pending' ? 'Review' : 'Edit'}
                            </button>
                            <button
                              className="btn btn-secondary"
                              style={{ fontSize: 12, padding: '4px 8px', color: 'var(--danger)' }}
                              title="Delete appraisal"
                              onClick={() => handleDeleteAppraisal(ap.id)}
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* Appraisal review modal */}
      {reviewModal && (
        <AppraisalModal
          appraisal={reviewModal.appraisal}
          employee={reviewModal.employee}
          onSave={handleReviewSaved}
          onClose={() => setReviewModal(null)}
          reviewerEmail={user?.email || ''}
          disabled={activeCycle?.status === 'closed'}
        />
      )}
    </div>
  );
}
