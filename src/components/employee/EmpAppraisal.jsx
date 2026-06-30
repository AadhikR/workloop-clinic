/**
 * EmpAppraisal.jsx — Employee portal view of their performance appraisals.
 * Read-only: employees see their rated sections, overall score, and reviewer comments.
 * Managers score directly in ManagerShell's Appraisals tab.
 */
import { useState, useEffect } from 'react';
import { Star, ChevronDown, ChevronUp } from 'lucide-react';
import { getMyAppraisals, RATING_LABELS } from '../../utils/appraisalStorage';

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

function Stars({ value }) {
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {[1, 2, 3, 4, 5].map(n => (
        <Star
          key={n}
          size={14}
          fill={n <= value ? '#f59e0b' : 'none'}
          color={n <= value ? '#f59e0b' : 'var(--gray-300)'}
        />
      ))}
    </span>
  );
}

export default function EmpAppraisal({ emp }) {
  const [appraisals, setAppraisals] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [expanded, setExpanded]     = useState(null);

  useEffect(() => {
    getMyAppraisals().then(data => {
      setAppraisals(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="emp-page-body"><p style={{ color: 'var(--gray-400)', textAlign: 'center', paddingTop: 40 }}>Loading appraisals…</p></div>;

  return (
    <div className="emp-page-body">
      <div className="emp-page-header">
        <h2>My Appraisals</h2>
        <p className="text-muted text-sm">Performance reviews completed by your manager</p>
      </div>

      {appraisals.length === 0 ? (
        <div className="emp-card" style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--gray-400)' }}>
          <Star size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
          <p>No appraisals on file yet.</p>
          <p className="text-sm">Your performance reviews will appear here once they are completed.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {appraisals.map(a => (
            <div key={a.id} className="emp-card" style={{ padding: 0, overflow: 'hidden' }}>
              {/* Header row */}
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
                    {a.reviewPeriod ? `Period: ${a.reviewPeriod}` : ''}
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

              {/* Expanded detail */}
              {expanded === a.id && (
                <div style={{ padding: '16px 18px' }}>
                  {a.sections && a.sections.length > 0 ? (
                    <>
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
                    </>
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
    </div>
  );
}
