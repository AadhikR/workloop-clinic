/**
 * EmpTraining.jsx — Employee self-service view for Feature 19.
 *
 * Shows the employee's own training records and certifications.
 * Read-only — admin manages all records via TrainingManager.
 * Data is fetched via the training_records_employee_read and
 * certifications_employee_read RLS policies (no admin scope).
 */

import { useState, useEffect } from 'react';
import { GraduationCap, Award, AlertTriangle, ExternalLink } from 'lucide-react';
import { getMyEmployeeRecord } from '../../utils/profileStorage';
import { getEmployeeTrainingRecords, getEmployeeCertifications } from '../../utils/trainingStorage';

// ─── Constants ────────────────────────────────────────────────────────────────

const TRAINING_TYPE_LABELS = {
  internal:   'Internal',
  external:   'External',
  online:     'Online / E-Learning',
  conference: 'Conference / Seminar',
};

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

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

// ─── Main Component ───────────────────────────────────────────────────────────

export default function EmpTraining() {
  const [records,  setRecords]  = useState([]);
  const [certs,    setCerts]    = useState([]);
  const [loading,  setLoading]  = useState(true);

  useEffect(() => {
    getMyEmployeeRecord().then(emp => {
      if (!emp?.id) { setLoading(false); return; }
      Promise.all([
        getEmployeeTrainingRecords(emp.id),
        getEmployeeCertifications(emp.id),
      ]).then(([recs, cs]) => {
        setRecords(recs);
        setCerts(cs);
        setLoading(false);
      }).catch(() => setLoading(false));
    });
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>
    );
  }

  // Compute derived values
  const expiringSoon = certs.filter(c => {
    const d = certDaysLeft(c.expiryDate);
    return d !== null && d >= 0 && d <= 60;
  });
  const expiredCerts = certs.filter(c => {
    const d = certDaysLeft(c.expiryDate);
    return d !== null && d < 0;
  });
  const completedCount  = records.filter(r => r.status === 'completed').length;
  const activeCertCount = certs.filter(c => {
    const d = certDaysLeft(c.expiryDate);
    return d === null || d >= 0;
  }).length;

  return (
    <div>
      <div className="emp-page-header">
        <h2>Training &amp; Certifications</h2>
      </div>

      <div className="emp-page-body">
        {/* ── Expiry alerts ─────────────────────────────────────────────────── */}
        {expiredCerts.length > 0 && (
          <div className="emp-card" style={{
            marginBottom: 14,
            background: '#fef2f2',
            border: '1px solid #fecaca',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <AlertTriangle size={16} color="#ef4444" />
              <strong style={{ fontSize: 14, color: '#991b1b' }}>
                {expiredCerts.length} certification{expiredCerts.length !== 1 ? 's' : ''} expired
              </strong>
            </div>
            {expiredCerts.map(c => (
              <div key={c.id} style={{
                fontSize: 13, color: '#991b1b',
                padding: '3px 0',
                borderBottom: '1px solid #fecaca',
              }}>
                <strong>{c.certificationName}</strong>
                {c.issuingBody && ` — ${c.issuingBody}`}
                <span style={{ marginLeft: 6, opacity: 0.8 }}>expired {c.expiryDate}</span>
              </div>
            ))}
          </div>
        )}

        {expiringSoon.length > 0 && (
          <div className="emp-card" style={{
            marginBottom: 14,
            background: '#fffbeb',
            border: '1px solid #fde68a',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <AlertTriangle size={16} color="#d97706" />
              <strong style={{ fontSize: 14, color: '#92400e' }}>
                {expiringSoon.length} certification{expiringSoon.length !== 1 ? 's' : ''} expiring soon
              </strong>
            </div>
            {expiringSoon.map(c => {
              const days = certDaysLeft(c.expiryDate);
              return (
                <div key={c.id} style={{
                  fontSize: 13, color: '#92400e',
                  padding: '3px 0',
                  borderBottom: '1px solid #fde68a',
                }}>
                  <strong>{c.certificationName}</strong>
                  {' — expires in '}
                  <strong>{days} day{days !== 1 ? 's' : ''}</strong>
                  {' '}({c.expiryDate})
                </div>
              );
            })}
          </div>
        )}

        {/* ── Summary cards ─────────────────────────────────────────────────── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: 12,
          marginBottom: 20,
        }}>
          {[
            { val: records.length,    label: 'Total Trainings',  color: 'var(--primary)' },
            { val: completedCount,    label: 'Completed',        color: '#10b981'         },
            { val: certs.length,      label: 'Certifications',   color: 'var(--primary)' },
            { val: activeCertCount,   label: 'Active Certs',     color: '#10b981'         },
          ].map(({ val, label, color }) => (
            <div key={label} className="emp-card" style={{ textAlign: 'center', padding: 16 }}>
              <div style={{ fontSize: 28, fontWeight: 700, color }}>{val}</div>
              <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>{label}</div>
            </div>
          ))}
        </div>

        {/* ── Training Records ──────────────────────────────────────────────── */}
        <div className="emp-card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <GraduationCap size={18} color="var(--primary)" />
            <h4 style={{ margin: 0, fontSize: 15 }}>Training Records</h4>
          </div>

          {records.length === 0 ? (
            <p style={{ color: 'var(--gray-400)', fontSize: 14, textAlign: 'center', padding: '16px 0' }}>
              No training records yet. Your HR admin will add them here.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {records.map(r => (
                <div key={r.id} style={{
                  border: '1px solid var(--gray-200)',
                  borderRadius: 10,
                  padding: '10px 14px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{r.trainingTitle}</div>
                      {r.provider && (
                        <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>{r.provider}</div>
                      )}
                    </div>
                    <span className={`badge ${STATUS_BADGE[r.status] || 'badge-gray'}`}>
                      {STATUS_LABEL[r.status] || r.status}
                    </span>
                  </div>
                  <div style={{
                    display: 'flex', gap: 14, marginTop: 8,
                    fontSize: 12, color: 'var(--gray-500)',
                    flexWrap: 'wrap', alignItems: 'center',
                  }}>
                    <span>{TRAINING_TYPE_LABELS[r.trainingType] || r.trainingType}</span>
                    {r.startDate && (
                      <span>
                        📅 {r.startDate}
                        {r.endDate && r.endDate !== r.startDate ? ` → ${r.endDate}` : ''}
                      </span>
                    )}
                    {r.durationHours != null && <span>⏱ {r.durationHours}h</span>}
                    {r.status === 'completed' && r.score && <span>Score: {r.score}</span>}
                    {r.status === 'completed' && r.passed !== null && (
                      <span style={{ color: r.passed ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                        {r.passed ? '✓ Passed' : '✗ Failed'}
                      </span>
                    )}
                    {r.certificateUrl && (
                      <a
                        href={r.certificateUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--primary)', display: 'inline-flex', alignItems: 'center', gap: 3 }}
                      >
                        View Certificate <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Certifications ────────────────────────────────────────────────── */}
        <div className="emp-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Award size={18} color="var(--primary)" />
            <h4 style={{ margin: 0, fontSize: 15 }}>Certifications</h4>
          </div>

          {certs.length === 0 ? (
            <p style={{ color: 'var(--gray-400)', fontSize: 14, textAlign: 'center', padding: '16px 0' }}>
              No certifications on record. Your HR admin will add them here.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {certs.map(c => {
                const { badge, label: statusLabel } = certBadge(c.expiryDate);
                return (
                  <div key={c.id} style={{
                    border: '1px solid var(--gray-200)',
                    borderRadius: 10,
                    padding: '10px 14px',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                          {c.certificationName}
                          {c.certificateUrl && (
                            <a
                              href={c.certificateUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: 'var(--primary)', display: 'inline-flex', alignItems: 'center' }}
                              title="View certificate"
                            >
                              <ExternalLink size={12} />
                            </a>
                          )}
                        </div>
                        {c.issuingBody && (
                          <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>{c.issuingBody}</div>
                        )}
                      </div>
                      <span className={`badge ${badge}`}>{statusLabel}</span>
                    </div>
                    <div style={{
                      display: 'flex', gap: 14, marginTop: 8,
                      fontSize: 12, color: 'var(--gray-500)',
                      flexWrap: 'wrap',
                    }}>
                      {c.certificateNo && <span>No: {c.certificateNo}</span>}
                      {c.issuedDate    && <span>Issued: {c.issuedDate}</span>}
                      {c.expiryDate
                        ? <span>Expires: {c.expiryDate}</span>
                        : <span>No expiry date</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
