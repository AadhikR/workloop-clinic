/**
 * ManagerAppraisals.jsx — Manager portal: score direct reports' appraisals.
 * Uses appraisals_manager_read + appraisal_sections_manager_update RLS policies (migration 033).
 */
import { useState, useEffect } from 'react';
import { Star, ChevronDown, ChevronUp, Save, CheckCircle } from 'lucide-react';
import { getMyTeamAppraisals, managerRateSection, RATING_LABELS } from '../../utils/appraisalStorage';

const STATUS_BADGE = {
  pending:       'badge-amber',
  self_reviewed: 'badge-blue',
  reviewed:      'badge-green',
  calibrated:    'badge-purple',
};

function StarRating({ value, onChange, disabled }) {
  const [hover, setHover] = useState(0);
  return (
    <span style={{ display: 'inline-flex', gap: 4, cursor: disabled ? 'default' : 'pointer' }}>
      {[1, 2, 3, 4, 5].map(n => (
        <Star
          key={n}
          size={18}
          fill={(hover || value) >= n ? '#f59e0b' : 'none'}
          color={(hover || value) >= n ? '#f59e0b' : 'var(--gray-300)'}
          onMouseEnter={() => !disabled && setHover(n)}
          onMouseLeave={() => setHover(0)}
          onClick={() => !disabled && onChange(n)}
          style={{ transition: 'color 0.1s' }}
        />
      ))}
      {value > 0 && (
        <span style={{ fontSize: 12, color: 'var(--gray-500)', marginLeft: 4, alignSelf: 'center' }}>
          {RATING_LABELS[value] || value}
        </span>
      )}
    </span>
  );
}

export default function ManagerAppraisals() {
  const [appraisals, setAppraisals] = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [expanded,   setExpanded]   = useState(null);
  const [sectionEdits, setSectionEdits] = useState({}); // { [sectionId]: { rating, comments } }
  const [saving, setSaving] = useState({});
  const [saved,  setSaved]  = useState({});

  useEffect(() => {
    getMyTeamAppraisals()
      .catch(() => [])
      .then(apps => { setAppraisals(apps); setLoading(false); });
  }, []);

  const handleSectionChange = (sectionId, field, val) => {
    setSectionEdits(prev => ({
      ...prev,
      [sectionId]: { ...(prev[sectionId] || {}), [field]: val },
    }));
  };

  const handleSaveSection = async (section) => {
    const edits = sectionEdits[section.id] || {};
    const rating   = edits.rating   ?? section.rating;
    const comments = edits.comments ?? section.comments;
    if (!rating) { alert('Please select a rating (1–5 stars) before saving.'); return; }
    setSaving(prev => ({ ...prev, [section.id]: true }));
    try {
      await managerRateSection(section.id, { rating, comments });
      setSaved(prev => ({ ...prev, [section.id]: true }));
      const updated = await getMyTeamAppraisals().catch(() => appraisals);
      setAppraisals(updated);
      setTimeout(() => setSaved(prev => ({ ...prev, [section.id]: false })), 2000);
    } catch (err) {
      alert('Save failed: ' + (err.message || 'Unknown error'));
    } finally {
      setSaving(prev => ({ ...prev, [section.id]: false }));
    }
  };

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading team appraisals…</div>;

  return (
    <div className="emp-page-body">
      <div className="emp-page-header">
        <h2>Team Appraisals</h2>
        <p className="text-muted text-sm">Rate your direct reports — click an appraisal to expand</p>
      </div>

      {appraisals.length === 0 ? (
        <div className="emp-card" style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--gray-400)' }}>
          <Star size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
          <p>No appraisals assigned to your team yet.</p>
          <p className="text-sm">The HR admin creates appraisal cycles and assigns staff. Your direct reports will appear here.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {appraisals.map(a => {
            const isExpanded = expanded === a.id;
            return (
              <div key={a.id} className="emp-card" style={{ padding: 0, overflow: 'hidden' }}>
                <div
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '14px 18px', cursor: 'pointer',
                    background: isExpanded ? 'var(--gray-50)' : 'white',
                    borderBottom: isExpanded ? '1px solid var(--gray-100)' : 'none',
                  }}
                  onClick={() => setExpanded(prev => prev === a.id ? null : a.id)}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 15 }}>{a.employeeName || '—'}</div>
                    <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                      {a.jobTitle ? `${a.jobTitle} · ` : ''}{a.cycleName || 'Appraisal Cycle'}
                      {a.reviewFrom && a.reviewTo ? ` · ${a.reviewFrom} → ${a.reviewTo}` : ''}
                    </div>
                  </div>
                  {a.overallRating && (
                    <div style={{ textAlign: 'right', marginRight: 8 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{parseFloat(a.overallRating).toFixed(2)} / 5</div>
                    </div>
                  )}
                  <span className={`badge ${STATUS_BADGE[a.status] || 'badge-amber'}`}>
                    {a.status === 'pending' ? 'Pending Review' : a.status}
                  </span>
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>

                {isExpanded && (
                  <div style={{ padding: '16px 18px' }}>
                    <table className="table" style={{ marginBottom: 16 }}>
                      <thead>
                        <tr>
                          <th>Section</th>
                          <th>Weight</th>
                          <th>Rating</th>
                          <th>Comments</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {(a.sections || []).map(s => {
                          const edits = sectionEdits[s.id] || {};
                          const currentRating   = edits.rating   ?? s.rating   ?? 0;
                          const currentComments = edits.comments ?? s.comments ?? '';
                          const isSaving = saving[s.id];
                          const isSaved  = saved[s.id];
                          return (
                            <tr key={s.id}>
                              <td style={{ fontWeight: 500, minWidth: 160 }}>{s.sectionName}</td>
                              <td style={{ color: 'var(--gray-500)', fontSize: 13 }}>×{s.weight}</td>
                              <td>
                                <StarRating
                                  value={currentRating}
                                  onChange={val => handleSectionChange(s.id, 'rating', val)}
                                  disabled={a.status === 'calibrated'}
                                />
                              </td>
                              <td>
                                <input
                                  className="form-control"
                                  style={{ fontSize: 13, padding: '4px 8px' }}
                                  value={currentComments}
                                  onChange={e => handleSectionChange(s.id, 'comments', e.target.value)}
                                  placeholder="Optional comments…"
                                  disabled={a.status === 'calibrated'}
                                />
                              </td>
                              <td>
                                {isSaved ? (
                                  <CheckCircle size={16} color="var(--success)" />
                                ) : (
                                  <button
                                    className="btn btn-primary btn-sm"
                                    style={{ padding: '4px 10px', fontSize: 12 }}
                                    onClick={() => handleSaveSection(s)}
                                    disabled={isSaving || a.status === 'calibrated'}
                                  >
                                    <Save size={12} /> {isSaving ? 'Saving…' : 'Save'}
                                  </button>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    {a.status === 'calibrated' && (
                      <p className="text-sm" style={{ color: 'var(--gray-400)' }}>
                        This appraisal has been calibrated by HR and is locked for further edits.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
