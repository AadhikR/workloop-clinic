import { useEffect, useState } from 'react';
import { Mail, XCircle, Printer } from 'lucide-react';
import { getLetterRequests, completeLetterRequest, rejectLetterRequest } from '../utils/letterStorage';
import { getCompany, getEmployees } from '../utils/storage';
import { printLetter } from '../utils/letterTemplates';
import { useCompany } from '../context/CompanyContext';
import { formatDateUAE } from '../utils/uaeValidators';

const STATUS_BADGE = {
  pending:   { cls: 'badge-amber', label: 'Pending' },
  completed: { cls: 'badge-green', label: 'Completed' },
  rejected:  { cls: 'badge-red',   label: 'Rejected' },
};

const FILTERS = [
  { key: 'pending',   label: 'Pending' },
  { key: 'completed', label: 'Completed' },
  { key: 'rejected',  label: 'Rejected' },
  { key: 'all',       label: 'All Requests' },
];

export default function LetterRequestsManager() {
  const { activeCompanyId } = useCompany();
  const [requests, setRequests] = useState([]);
  const [company,  setCompany]  = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [filter,   setFilter]   = useState('pending');
  const [rejectId,     setRejectId]     = useState(null);
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([getEmployees(activeCompanyId), getCompany(activeCompanyId)])
      .then(([emps, co]) =>
        getLetterRequests(emps).then(reqs => {
          setRequests(reqs);
          setCompany(co);
          setLoading(false);
        })
      );
  }, [activeCompanyId]);

  const handleComplete = async (req) => {
    printLetter(req, company);
    try {
      await completeLetterRequest(req.id);
      setRequests(prev => prev.map(r => r.id === req.id ? { ...r, status: 'completed', completedAt: new Date().toISOString() } : r));
    } catch (err) {
      alert('Failed to mark complete: ' + err.message);
    }
  };

  const handleReject = async () => {
    if (!rejectId) return;
    try {
      await rejectLetterRequest(rejectId, rejectReason);
      setRequests(prev => prev.map(r => r.id === rejectId ? { ...r, status: 'rejected', rejectionReason: rejectReason } : r));
      setRejectId(null);
      setRejectReason('');
    } catch (err) {
      alert('Reject failed: ' + err.message);
    }
  };

  const counts = {
    pending:   requests.filter(r => r.status === 'pending').length,
    completed: requests.filter(r => r.status === 'completed').length,
    rejected:  requests.filter(r => r.status === 'rejected').length,
    all:       requests.length,
  };

  const visible = filter === 'all'
    ? requests
    : requests.filter(r => r.status === filter);

  if (loading) return <div className="page-body"><div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div></div>;

  return (
    <div className="page-body">
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Letter Requests</h1>
          <p style={{ color: 'var(--gray-500)', fontSize: 13, marginTop: 2 }}>
            Generate and manage employee HR letter requests
          </p>
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {FILTERS.map(f => (
          <button
            key={f.key}
            className={`btn tab-btn ${filter === f.key ? 'tab-btn-active' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
            {counts[f.key] > 0 && (
              <span
                className={`badge ${f.key === 'pending' ? 'badge-amber' : f.key === 'rejected' ? 'badge-red' : 'badge-blue'}`}
                style={{ marginLeft: 6, fontSize: 11 }}
              >
                {counts[f.key]}
              </span>
            )}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <div className="card" style={{ padding: '48px 24px', textAlign: 'center' }}>
          <Mail size={36} style={{ margin: '0 auto 12px', display: 'block', opacity: 0.25 }} />
          <p style={{ color: 'var(--gray-500)', fontSize: 14 }}>
            {filter === 'pending'   ? 'No pending letter requests.' :
         filter === 'completed' ? 'No completed requests yet.' :
         filter === 'rejected'  ? 'No rejected requests.' :
         'No letter requests yet.'}
          </p>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style={{ minWidth: 140 }}>Employee</th>
                  <th style={{ minWidth: 180 }}>Letter Type</th>
                  <th style={{ minWidth: 140 }}>Purpose</th>
                  <th style={{ minWidth: 100 }}>Requested</th>
                  <th style={{ minWidth: 100 }}>Status</th>
                  <th style={{ minWidth: 200 }}>Rejection Reason</th>
                  <th style={{ minWidth: 120 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {visible.map(req => {
                  const badge = STATUS_BADGE[req.status] || STATUS_BADGE.pending;
                  const isRejectingThis = rejectId === req.id;
                  return (
                    <>
                      <tr key={req.id} style={req.status === 'pending' ? { background: 'rgba(217,119,6,0.03)' } : undefined}>
                        <td>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{req.employeeName}</div>
                          <div style={{ fontSize: 11, color: 'var(--gray-400)' }}>{req.jobTitle || '—'} {req.department ? `· ${req.department}` : ''}</div>
                        </td>
                        <td style={{ fontSize: 13 }}>{req.letterType}</td>
                        <td style={{ fontSize: 12, color: 'var(--gray-500)', maxWidth: 180 }}>{req.purpose || <span style={{ color: 'var(--gray-300)' }}>—</span>}</td>
                        <td style={{ fontSize: 12, color: 'var(--gray-500)', whiteSpace: 'nowrap' }}>{formatDateUAE(req.requestedAt)}</td>
                        <td>
                          <span className={`badge ${badge.cls}`} style={{ fontSize: 11 }}>{badge.label}</span>
                          {req.status === 'completed' && req.completedAt && (
                            <div style={{ fontSize: 10, color: 'var(--gray-400)', marginTop: 2 }}>{formatDateUAE(req.completedAt)}</div>
                          )}
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--danger)' }}>
                          {req.status === 'rejected' && req.rejectionReason
                            ? req.rejectionReason
                            : <span style={{ color: 'var(--gray-300)' }}>—</span>}
                        </td>
                        <td>
                          {req.status === 'pending' && (
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button
                                className="btn btn-primary btn-sm"
                                style={{ gap: 5, display: 'flex', alignItems: 'center' }}
                                title="Print letter and mark complete"
                                onClick={() => handleComplete(req)}
                              >
                                <Printer size={13} /> Generate
                              </button>
                              <button
                                className="btn btn-ghost btn-sm text-danger"
                                title="Reject request"
                                onClick={() => { setRejectId(isRejectingThis ? null : req.id); setRejectReason(''); }}
                              >
                                <XCircle size={13} />
                              </button>
                            </div>
                          )}
                          {req.status === 'completed' && (
                            <button
                              className="btn btn-ghost btn-sm"
                              style={{ gap: 5, display: 'flex', alignItems: 'center', color: 'var(--gray-500)' }}
                              title="Re-print letter"
                              onClick={() => printLetter(req, company)}
                            >
                              <Printer size={13} /> Re-print
                            </button>
                          )}
                        </td>
                      </tr>
                      {isRejectingThis && (
                        <tr key={`reject-${req.id}`}>
                          <td colSpan={7} style={{ background: 'rgba(220,38,38,0.04)', padding: '10px 16px' }}>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                              <input
                                className="form-control"
                                style={{ flex: 1, fontSize: 13 }}
                                placeholder="Rejection reason (shown to employee)…"
                                value={rejectReason}
                                onChange={e => setRejectReason(e.target.value)}
                                autoFocus
                              />
                              <button className="btn btn-danger btn-sm" onClick={handleReject}>Reject</button>
                              <button className="btn btn-ghost btn-sm" onClick={() => setRejectId(null)}>Cancel</button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
