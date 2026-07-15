/**
 * ManagerAppraisals.jsx — Manager portal: score direct reports' appraisals
 * AND view own appraisals (merged "My Appraisals" sub-view).
 */
import { useState, useEffect } from 'react';
import { Star, ChevronDown, ChevronUp, Save, CheckCircle, AlertTriangle, Users, User } from 'lucide-react';
import { getMyTeamAppraisals, getMyAppraisals, managerRateSection, RATING_LABELS } from '../../utils/appraisalStorage';

const STATUS_BADGE = {
  pending:       'badge-amber',
  self_reviewed: 'badge-blue',
  reviewed:      'badge-green',
  calibrated:    'badge-purple',
};
const STATUS_LABEL = {
  pending:       'Awaiting Review',
  self_reviewed: 'Self-Reviewed',
  reviewed:      'Reviewed',
  calibrated:    'Calibrated',
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

function Stars({ value }) {
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {[1, 2, 3, 4, 5].map(n => (
        <Star key={n} size={14} fill={n <= value ? '#f59e0b' : 'none'} color={n <= value ? '#f59e0b' : 'var(--gray-300)'} />
      ))}
    </span>
  );
}

export default function ManagerAppraisals({ emp }) {
  const [view, setView] = useState('team'); // 'team' | 'my'
  const [appraisals, setAppraisals] = useState([]);
  const [myAppraisals, setMyAppraisals] = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [expanded,   setExpanded]   = useState(null);
  const [sectionEdits, setSectionEdits] = useState({});
  const [savingAppraisal, setSavingAppraisal] = useState(null);
  const [savedAppraisal, setSavedAppraisal]   = useState(null);
  const [showConfirm, setShowConfirm] = useState(null);

  useEffect(() => {
    Promise.all([
      getMyTeamAppraisals().catch(() => []),
      getMyAppraisals().catch(() => []),
    ]).then(([team, mine]) => {
      setAppraisals(team);
      setMyAppraisals(mine);
      setLoading(false);
    });
  }, []);

  const handleSectionChange = (sectionId, field, val) => {
    setSectionEdits(prev => ({
      ...prev,
      [sectionId]: { ...(prev[sectionId] || {}), [field]: val },
    }));
  };

  const handleSaveAppraisal = async (appraisal) => {
    const sections = appraisal.sections || [];
    const toSave = sections.map(s => {
      const edits = sectionEdits[s.id] || {};
      return { id: s.id, rating: edits.rating ?? s.rating ?? 0, comments: edits.comments ?? s.comments ?? '' };
    });
    const missing = toSave.filter(s => !s.rating);
    if (missing.length > 0) { alert(`Please rate all ${missing.length} section(s) before saving.`); return; }

    setShowConfirm(appraisal.id);
  };

  const confirmSave = async (appraisal) => {
    setShowConfirm(null);
    const sections = appraisal.sections || [];
    const toSave = sections.map(s => {
      const edits = sectionEdits[s.id] || {};
      return { id: s.id, rating: edits.rating ?? s.rating ?? 0, comments: edits.comments ?? s.comments ?? '' };
    });

    setSavingAppraisal(appraisal.id);
    try {
      for (const s of toSave) {
        await managerRateSection(s.id, { rating: s.rating, comments: s.comments });
      }
      setSavedAppraisal(appraisal.id);
      const updated = await getMyTeamAppraisals().catch(() => appraisals);
      setAppraisals(updated.length > 0 ? updated : appraisals.map(a =>
        a.id === appraisal.id ? { ...a, status: 'reviewed' } : a
      ));
      setTimeout(() => setSavedAppraisal(null), 3000);
    } catch (err) {
      alert('Save failed: ' + (err.message || 'Unknown error'));
    } finally {
      setSavingAppraisal(null);
    }
  };

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading appraisals…</div>;

  return (
    <div>
      <div className="emp-page-header">
        <h2>Appraisals</h2>
        <p className="text-muted text-sm">Review your team and view your own appraisals</p>
      </div>

      <div className="emp-page-body">
        {/* Sub-view toggle */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <button
            className={`btn ${view === 'team' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => { setView('team'); setExpanded(null); }}
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, padding: '8px 16px' }}
          >
            <Users size={14} /> Team Appraisals
          </button>
          <button
            className={`btn ${view === 'my' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => { setView('my'); setExpanded(null); }}
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, padding: '8px 16px' }}
          >
            <User size={14} /> My Appraisals
          </button>
        </div>

        {/* ── TEAM VIEW ── */}
        {view === 'team' && (
          <>
            {appraisals.length === 0 ? (
              <div className="emp-card" style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--gray-400)' }}>
                <Star size={36} style={{ marginBottom: 14, opacity: 0.3 }} />
                <p style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>No appraisals assigned to your team yet.</p>
                <p className="text-sm">The HR admin creates appraisal cycles and assigns staff. Your direct reports will appear here.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {appraisals.map(a => {
                  const isExpanded = expanded === a.id;
                  const isLocked = a.status === 'reviewed' || a.status === 'calibrated';
                  return (
                    <div key={a.id} className="emp-card" style={{ padding: 0, overflow: 'hidden' }}>
                      <div
                        style={{
                          display: 'flex', alignItems: 'center', gap: 14,
                          padding: '16px 20px', cursor: 'pointer',
                          background: isExpanded ? 'var(--gray-50)' : 'white',
                          borderBottom: isExpanded ? '1px solid var(--gray-100)' : 'none',
                        }}
                        onClick={() => setExpanded(prev => prev === a.id ? null : a.id)}
                      >
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 16 }}>{a.employeeName || '—'}</div>
                          <div style={{ fontSize: 13, color: 'var(--gray-500)', marginTop: 4 }}>
                            {a.jobTitle ? `${a.jobTitle} · ` : ''}{a.cycleName || 'Appraisal Cycle'}
                            {a.reviewFrom && a.reviewTo ? ` · ${a.reviewFrom} → ${a.reviewTo}` : ''}
                          </div>
                        </div>
                        {a.overallRating && (
                          <div style={{ textAlign: 'right', marginRight: 8 }}>
                            <div style={{ fontSize: 14, fontWeight: 600 }}>{parseFloat(a.overallRating).toFixed(2)} / 5</div>
                          </div>
                        )}
                        <span className={`badge ${STATUS_BADGE[a.status] || 'badge-amber'}`}>
                          {a.status === 'pending' ? 'Pending Review' : a.status}
                        </span>
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </div>

                      {isExpanded && (
                        <div style={{ padding: '20px 24px' }}>
                          <table className="table" style={{ marginBottom: 16 }}>
                            <thead>
                              <tr>
                                <th style={{ padding: '10px 14px' }}>Section</th>
                                <th style={{ padding: '10px 14px' }}>Weight</th>
                                <th style={{ padding: '10px 14px' }}>Rating</th>
                                <th style={{ padding: '10px 14px', minWidth: 180 }}>Comments</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(a.sections || []).map(s => {
                                const edits = sectionEdits[s.id] || {};
                                const currentRating   = edits.rating   ?? s.rating   ?? 0;
                                const currentComments = edits.comments ?? s.comments ?? '';
                                return (
                                  <tr key={s.id}>
                                    <td style={{ fontWeight: 500, minWidth: 160, padding: '12px 14px' }}>{s.sectionName}</td>
                                    <td style={{ color: 'var(--gray-500)', fontSize: 13, padding: '12px 14px' }}>×{s.weight}</td>
                                    <td style={{ padding: '12px 14px' }}>
                                      <StarRating
                                        value={currentRating}
                                        onChange={val => handleSectionChange(s.id, 'rating', val)}
                                        disabled={isLocked}
                                      />
                                    </td>
                                    <td style={{ padding: '12px 14px' }}>
                                      <input
                                        className="form-control"
                                        style={{ fontSize: 13, padding: '6px 10px' }}
                                        value={currentComments}
                                        onChange={e => handleSectionChange(s.id, 'comments', e.target.value)}
                                        placeholder="Optional comments…"
                                        disabled={isLocked}
                                      />
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                          {isLocked ? (
                            <p className="text-sm" style={{ color: 'var(--gray-400)', marginTop: 8 }}>
                              {a.status === 'calibrated'
                                ? 'This appraisal has been calibrated by HR and is locked for further edits.'
                                : 'This appraisal has been submitted and is awaiting HR calibration.'}
                            </p>
                          ) : (
                            <>
                              {/* Confirmation dialog */}
                              {showConfirm === a.id && (
                                <div className="alert" style={{
                                  background: '#fffbeb', border: '1px solid #f59e0b', borderRadius: 10,
                                  padding: '14px 18px', marginBottom: 14,
                                  display: 'flex', alignItems: 'flex-start', gap: 12,
                                }}>
                                  <AlertTriangle size={18} color="#f59e0b" style={{ flexShrink: 0, marginTop: 2 }} />
                                  <div style={{ flex: 1 }}>
                                    <div style={{ fontWeight: 600, fontSize: 14, color: '#92400e', marginBottom: 6 }}>
                                      Submit appraisal review?
                                    </div>
                                    <p style={{ fontSize: 13, color: '#78350f', margin: 0, marginBottom: 12 }}>
                                      Once submitted, this appraisal will be marked as reviewed and sent to HR for final calibration. You will not be able to change your ratings after HR calibrates.
                                    </p>
                                    <div style={{ display: 'flex', gap: 8 }}>
                                      <button
                                        className="btn btn-primary"
                                        style={{ padding: '6px 16px', fontSize: 13 }}
                                        onClick={() => confirmSave(a)}
                                        disabled={savingAppraisal === a.id}
                                      >
                                        <Save size={13} /> {savingAppraisal === a.id ? 'Submitting…' : 'Confirm & Submit'}
                                      </button>
                                      <button
                                        className="btn btn-ghost"
                                        style={{ padding: '6px 16px', fontSize: 13 }}
                                        onClick={() => setShowConfirm(null)}
                                      >
                                        Cancel
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              )}

                              {showConfirm !== a.id && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
                                  <button
                                    className="btn btn-primary"
                                    style={{ padding: '8px 20px', fontSize: 13 }}
                                    onClick={() => handleSaveAppraisal(a)}
                                    disabled={savingAppraisal === a.id}
                                  >
                                    <Save size={14} /> Save Appraisal
                                  </button>
                                  {savedAppraisal === a.id && (
                                    <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--success)', fontSize: 13, fontWeight: 600 }}>
                                      <CheckCircle size={15} /> Saved
                                    </span>
                                  )}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ── MY APPRAISALS VIEW ── */}
        {view === 'my' && (
          <>
            {myAppraisals.length === 0 ? (
              <div className="emp-card" style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--gray-400)' }}>
                <Star size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
                <p>No appraisals on file yet.</p>
                <p className="text-sm">Your performance reviews will appear here once they are completed.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {myAppraisals.map(a => (
                  <div key={a.id} className="emp-card" style={{ padding: 0, overflow: 'hidden' }}>
                    <div
                      style={{
                        display: 'flex', alignItems: 'center', gap: 12,
                        padding: '14px 18px', cursor: 'pointer',
                        background: expanded === a.id ? 'var(--gray-50)' : 'white',
                        borderBottom: expanded === a.id ? '1px solid var(--gray-100)' : 'none',
                      }}
                      onClick={() => setExpanded(prev => prev === a.id ? null : a.id)}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 15 }}>{a.cycleName || 'Appraisal Cycle'}</div>
                        <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                          {a.reviewFrom && a.reviewTo ? `${a.reviewFrom} → ${a.reviewTo}` : ''}
                        </div>
                      </div>
                      {a.overallRating && (
                        <div style={{ textAlign: 'right', marginRight: 8 }}>
                          <Stars value={Math.round(a.overallRating)} />
                          <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                            {parseFloat(a.overallRating).toFixed(2)} / 5
                          </div>
                        </div>
                      )}
                      <span className={`badge ${STATUS_BADGE[a.status] || 'badge-amber'}`}>
                        {STATUS_LABEL[a.status] || a.status}
                      </span>
                      {expanded === a.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </div>

                    {expanded === a.id && (
                      <div style={{ padding: '16px 18px' }}>
                        {a.sections && a.sections.length > 0 ? (
                          <table className="table" style={{ marginBottom: 16 }}>
                            <thead>
                              <tr>
                                <th>Section</th>
                                <th>Weight</th>
                                <th>Rating</th>
                                <th>Comments</th>
                              </tr>
                            </thead>
                            <tbody>
                              {a.sections.map((s, i) => (
                                <tr key={i}>
                                  <td style={{ fontWeight: 500 }}>{s.sectionName}</td>
                                  <td style={{ color: 'var(--gray-500)', fontSize: 13 }}>×{s.weight}</td>
                                  <td>
                                    {s.rating ? (
                                      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <Stars value={s.rating} />
                                        <span style={{ fontSize: 12, color: 'var(--gray-500)' }}>
                                          {RATING_LABELS[s.rating] || s.rating}
                                        </span>
                                      </span>
                                    ) : <span className="text-muted text-sm">Not rated</span>}
                                  </td>
                                  <td style={{ fontSize: 13, color: 'var(--gray-600)' }}>{s.comments || '—'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p className="text-muted text-sm" style={{ marginBottom: 12 }}>Rating sections not available.</p>
                        )}

                        {a.reviewerComments && (
                          <div style={{ background: 'var(--gray-50)', borderRadius: 8, padding: '12px 14px', marginBottom: 12 }}>
                            <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--gray-600)', marginBottom: 4 }}>Reviewer Comments</div>
                            <p style={{ fontSize: 13, color: 'var(--gray-700)', margin: 0 }}>{a.reviewerComments}</p>
                          </div>
                        )}

                        {a.developmentPlan && (
                          <div style={{ background: '#eff6ff', borderRadius: 8, padding: '12px 14px' }}>
                            <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--primary)', marginBottom: 4 }}>Development Plan</div>
                            <p style={{ fontSize: 13, color: 'var(--gray-700)', margin: 0 }}>{a.developmentPlan}</p>
                          </div>
                        )}

                        {a.reviewedBy && (
                          <p style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 12, marginBottom: 0 }}>
                            Reviewed by {a.reviewedBy}
                            {a.reviewedAt ? ` on ${new Date(a.reviewedAt).toLocaleDateString('en-AE')}` : ''}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
