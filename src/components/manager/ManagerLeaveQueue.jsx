/**
 * ManagerLeaveQueue.jsx — Leave approval queue for manager-role users.
 *
 * Shows leave requests from the manager's direct reports (reporting_manager_id).
 * Managers can:
 *   - Approve pending requests (calls manager_approve_leave RPC)
 *   - Reject pending requests with a required reason (calls manager_reject_leave RPC)
 *
 * If approval_level_required = 1 → approval moves the request straight to 'Approved'.
 * If approval_level_required = 2 → approval moves it to 'ManagerApproved', awaiting HR.
 */
import { useState, useEffect, useCallback } from 'react';
import { Check, X, Users, RefreshCw, ChevronDown, ChevronUp, CalendarDays, Clock, AlertCircle } from 'lucide-react';
import { getMyEmployeeRecord } from '../../utils/profileStorage';
import { getLeaveQueueForManager, approveLeaveAsManager, rejectLeaveAsManager } from '../../utils/leaveStorage';
import { getEmployees } from '../../utils/storage';
import { formatDateUAE } from '../../utils/uaeValidators';
import { LEAVE_STATUS_COLORS } from '../../utils/leaveEngine';

function StatusBadge({ status }) {
  const cls = LEAVE_STATUS_COLORS[status] || 'badge-gray';
  return <span className={`badge ${cls}`}>{status}</span>;
}

export default function ManagerLeaveQueue() {
  const [emp, setEmp]               = useState(null);
  const [requests, setRequests]     = useState([]);
  const [employees, setEmployees]   = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');

  // Reject modal state
  const [rejectId, setRejectId]     = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectErr, setRejectErr]   = useState('');
  const [actionBusy, setActionBusy] = useState('');

  // History toggle
  const [showHistory, setShowHistory] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const myEmp = await getMyEmployeeRecord();
      setEmp(myEmp);
      const [reqs, emps] = await Promise.all([
        myEmp ? getLeaveQueueForManager(myEmp.id) : [],
        getEmployees(),
      ]);
      setRequests(reqs);
      setEmployees(emps);
    } catch (e) {
      setError(e.message || 'Failed to load leave queue.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const empName = (id) => employees.find(e => e.id === id)?.name || 'Unknown';

  const pending  = requests.filter(r => r.status === 'Pending');
  const history  = requests.filter(r => r.status !== 'Pending');

  const handleApprove = async (id) => {
    setActionBusy(id + '_approve');
    setError('');
    try {
      await approveLeaveAsManager(id);
      await load();
    } catch (e) {
      setError(e.message || 'Failed to approve.');
    } finally {
      setActionBusy('');
    }
  };

  const openReject = (id) => {
    setRejectId(id);
    setRejectReason('');
    setRejectErr('');
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) { setRejectErr('Please enter a reason.'); return; }
    setActionBusy(rejectId + '_reject');
    setRejectErr('');
    try {
      await rejectLeaveAsManager(rejectId, rejectReason.trim());
      setRejectId(null);
      await load();
    } catch (e) {
      setRejectErr(e.message || 'Failed to reject.');
    } finally {
      setActionBusy('');
    }
  };

  const rejectReq = rejectId ? requests.find(r => r.id === rejectId) : null;

  // ── Row ───────────────────────────────────────────────────────────────────
  const Row = ({ req }) => {
    const isPending   = req.status === 'Pending';
    const isBusy      = actionBusy === req.id + '_approve' || actionBusy === req.id + '_reject';
    return (
      <>
        <td style={{ padding: '12px 14px' }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: '#1e293b' }}>{empName(req.employeeId)}</div>
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
            Submitted {req.submittedAt ? formatDateUAE(req.submittedAt.slice(0,10)) : '—'}
          </div>
        </td>
        <td style={{ padding: '12px 14px' }}>
          <span style={{
            background: '#f0f9ff', border: '1px solid #bae6fd',
            borderRadius: 6, padding: '3px 8px', fontSize: 12, color: '#0369a1', fontWeight: 600,
          }}>
            {req.leaveTypeCode}
          </span>
        </td>
        <td style={{ padding: '12px 14px', fontSize: 13, color: '#374151' }}>
          {req.startDate === req.endDate
            ? formatDateUAE(req.startDate)
            : `${formatDateUAE(req.startDate)} – ${formatDateUAE(req.endDate)}`}
        </td>
        <td style={{ padding: '12px 14px', fontSize: 13, fontWeight: 600, color: '#1e293b', textAlign: 'center' }}>
          {req.daysRequested}
        </td>
        <td style={{ padding: '12px 14px', maxWidth: 200 }}>
          <div style={{ fontSize: 12, color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {req.reason || '—'}
          </div>
          {req.warnings?.length > 0 && (
            <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {req.warnings.map((w, i) => (
                <div key={i} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  background: '#fffbeb', border: '1px solid #fcd34d',
                  borderRadius: 4, padding: '2px 6px', fontSize: 11,
                  color: '#92400e', whiteSpace: 'normal',
                }}>
                  <AlertCircle size={10} style={{ flexShrink: 0 }} /> {w}
                </div>
              ))}
            </div>
          )}
        </td>
        <td style={{ padding: '12px 14px' }}>
          <StatusBadge status={req.status} />
          {req.status === 'ManagerApproved' && (
            <div style={{ fontSize: 11, color: '#0369a1', marginTop: 3 }}>Awaiting HR approval</div>
          )}
          {req.status === 'ManagerRejected' && req.managerRejectionReason && (
            <div style={{ fontSize: 11, color: '#ef4444', marginTop: 3 }}>{req.managerRejectionReason}</div>
          )}
        </td>
        {isPending && (
          <td style={{ padding: '12px 14px' }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => handleApprove(req.id)}
                disabled={isBusy}
                title="Approve"
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '6px 12px', borderRadius: 7, border: 'none',
                  background: '#22c55e', color: '#fff', fontSize: 12,
                  cursor: isBusy ? 'not-allowed' : 'pointer', fontWeight: 600,
                  opacity: isBusy ? 0.7 : 1,
                }}
              >
                <Check size={13} /> Approve
              </button>
              <button
                onClick={() => openReject(req.id)}
                disabled={isBusy}
                title="Reject"
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '6px 12px', borderRadius: 7, border: 'none',
                  background: '#ef4444', color: '#fff', fontSize: 12,
                  cursor: isBusy ? 'not-allowed' : 'pointer', fontWeight: 600,
                  opacity: isBusy ? 0.7 : 1,
                }}
              >
                <X size={13} /> Reject
              </button>
            </div>
          </td>
        )}
        {!isPending && <td style={{ padding: '12px 14px' }} />}
      </>
    );
  };

  // ── Render ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#64748b', fontSize: 14 }}>
        Loading leave queue…
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: '#1e293b', marginBottom: 4 }}>
            Leave Approval Queue
          </h2>
          <p style={{ fontSize: 13, color: '#64748b' }}>
            Pending leave requests from your direct reports
          </p>
        </div>
        <button
          onClick={load}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 16px', borderRadius: 8,
            border: '1.5px solid #e2e8f0', background: '#f8fafc',
            fontSize: 13, cursor: 'pointer', color: '#374151', fontWeight: 600,
          }}
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {error && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, background: '#fef2f2',
          border: '1px solid #fecaca', color: '#dc2626', fontSize: 13, marginBottom: 16,
        }}>
          {error}
        </div>
      )}

      {/* Pending requests */}
      {pending.length === 0 ? (
        <div style={{
          background: '#f8fafc', borderRadius: 12, border: '1.5px dashed #e2e8f0',
          padding: 48, textAlign: 'center',
        }}>
          <CalendarDays size={40} style={{ color: '#cbd5e1', margin: '0 auto 12px' }} />
          <p style={{ fontSize: 14, fontWeight: 600, color: '#1e293b', marginBottom: 4 }}>
            No pending requests
          </p>
          <p style={{ fontSize: 13, color: '#94a3b8' }}>
            Your direct reports have no leave requests awaiting approval.
          </p>
        </div>
      ) : (
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                  {['Employee', 'Type', 'Dates', 'Days', 'Reason', 'Status', 'Actions'].map(h => (
                    <th key={h} style={{
                      padding: '10px 14px', textAlign: 'left',
                      fontSize: 11, fontWeight: 700, color: '#6b7280',
                      textTransform: 'uppercase', letterSpacing: '0.05em',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pending.map((req, i) => (
                  <tr key={req.id} style={{ borderBottom: i < pending.length - 1 ? '1px solid #f1f5f9' : 'none' }}>
                    <Row req={req} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* History (ManagerApproved / ManagerRejected) */}
      {history.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <button
            onClick={() => setShowHistory(h => !h)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: 600, color: '#64748b', padding: 0, marginBottom: 12,
            }}
          >
            {showHistory ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            Recently actioned ({history.length})
          </button>

          {showHistory && (
            <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                      {['Employee', 'Type', 'Dates', 'Days', 'Reason', 'Status', ''].map(h => (
                        <th key={h} style={{
                          padding: '10px 14px', textAlign: 'left',
                          fontSize: 11, fontWeight: 700, color: '#6b7280',
                          textTransform: 'uppercase', letterSpacing: '0.05em',
                        }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((req, i) => (
                      <tr key={req.id} style={{ borderBottom: i < history.length - 1 ? '1px solid #f1f5f9' : 'none' }}>
                        <Row req={req} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Reject modal — inlined to avoid inner-function remount on each keystroke */}
      {rejectId && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: '#fff', borderRadius: 14, padding: 28, width: 380,
            boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
          }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#1e293b', marginBottom: 6 }}>Reject Leave Request</h3>
            {rejectReq && (
              <p style={{ fontSize: 13, color: '#64748b', marginBottom: 14 }}>
                {empName(rejectReq.employeeId)} — {rejectReq.leaveTypeCode} ({rejectReq.daysRequested}d)
              </p>
            )}
            <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
              Reason (required)
            </label>
            <textarea
              value={rejectReason}
              onChange={e => setRejectReason(e.target.value)}
              placeholder="Enter reason for rejection…"
              rows={3}
              style={{
                width: '100%', padding: '8px 10px', borderRadius: 8,
                border: rejectErr ? '1.5px solid #ef4444' : '1.5px solid #e2e8f0',
                fontSize: 13, resize: 'vertical', boxSizing: 'border-box',
              }}
            />
            {rejectErr && <p style={{ fontSize: 12, color: '#ef4444', marginTop: 4 }}>{rejectErr}</p>}
            <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
              <button
                onClick={() => setRejectId(null)}
                style={{
                  flex: 1, padding: '9px 0', borderRadius: 8, border: '1.5px solid #e2e8f0',
                  background: '#f8fafc', fontSize: 13, cursor: 'pointer', fontWeight: 600, color: '#64748b',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={!!actionBusy}
                style={{
                  flex: 1, padding: '9px 0', borderRadius: 8, border: 'none',
                  background: '#ef4444', color: '#fff', fontSize: 13,
                  cursor: actionBusy ? 'not-allowed' : 'pointer', fontWeight: 600, opacity: actionBusy ? 0.7 : 1,
                }}
              >
                {actionBusy ? 'Rejecting…' : 'Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
