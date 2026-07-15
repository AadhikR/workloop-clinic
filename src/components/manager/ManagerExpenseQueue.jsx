/**
 * ManagerExpenseQueue.jsx — Manager portal: expense pre-approval queue
 *
 * Managers see all expense claims from their direct reports.
 * They can pre-approve (→ 'manager_approved') or reject (→ 'manager_rejected').
 * Final HR approval happens in the admin ExpensesManager.
 */
import { useState, useEffect } from 'react';
import { Receipt, Check, X, AlertCircle, RefreshCw } from 'lucide-react';
import {
  getExpenseQueueForManager,
  managerApproveExpense,
  managerRejectExpense,
} from '../../utils/expenseStorage';
import { getMyEmployeeRecord } from '../../utils/profileStorage';
import { getEmployees } from '../../utils/storage';
import { EXPENSE_CATEGORIES } from '../ExpensesManager';
import { formatDateUAE } from '../../utils/uaeValidators';

const STATUS_BADGE = {
  pending:          'badge-amber',
  manager_approved: 'badge-blue',
  manager_rejected: 'badge-red',
  approved:         'badge-green',
  paid:             'badge-green',
  rejected:         'badge-red',
};

const STATUS_LABEL = {
  pending:          'Pending',
  manager_approved: 'You Approved',
  manager_rejected: 'You Rejected',
  approved:         'HR Approved',
  paid:             'Paid',
  rejected:         'Rejected',
};

export default function ManagerExpenseQueue() {
  const [claims, setClaims]     = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [filter, setFilter]     = useState('pending');
  const [rejectId, setRejectId] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [busy, setBusy]         = useState(false);
  const [msg, setMsg]           = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([getExpenseQueueForManager(), getEmployees()])
      .then(([rawClaims, emps]) => {
        setEmployees(emps);
        const empMap = Object.fromEntries(emps.map(e => [e.id, e.name]));
        setClaims(rawClaims.map(c => ({ ...c, employeeName: c.employeeName || empMap[c.employeeId] || null })));
      })
      .catch(err => setMsg({ type: 'error', text: err.message }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const flash = (type, text) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  const pendingCount = claims.filter(c => c.status === 'pending').length;

  const filtered = filter === 'all'
    ? claims
    : claims.filter(c => c.status === filter);

  const handleApprove = async (id) => {
    setBusy(true);
    try {
      await managerApproveExpense(id);
      setClaims(prev => prev.map(c => c.id === id ? { ...c, status: 'manager_approved' } : c));
      flash('success', 'Expense pre-approved. HR will give final sign-off.');
    } catch (err) {
      flash('error', err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) return;
    setBusy(true);
    try {
      await managerRejectExpense(rejectId, rejectReason.trim());
      setClaims(prev => prev.map(c => c.id === rejectId
        ? { ...c, status: 'manager_rejected', managerRejectionReason: rejectReason.trim() }
        : c
      ));
      setRejectId(null);
      setRejectReason('');
      flash('success', 'Expense rejected.');
    } catch (err) {
      flash('error', err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="emp-page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2>Expense Queue</h2>
            <p className="text-muted text-sm">Review and pre-approve your team's expense claims</p>
          </div>
          <button className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      <div className="emp-page-body">

        {msg && (
          <div className={`alert alert-${msg.type === 'error' ? 'danger' : 'success'} mb-4`}>
            <AlertCircle size={14} /> {msg.text}
          </div>
        )}

        {/* Filter tabs */}
        <div className="tab-bar mb-3">
          {['all', 'pending', 'manager_approved', 'manager_rejected', 'approved', 'paid', 'rejected'].map(f => (
            <button
              key={f}
              className={`tab-btn ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f === 'all' ? 'All' : STATUS_LABEL[f]}
              {f === 'pending' && pendingCount > 0 && (
                <span className="badge badge-amber" style={{ marginLeft: 6, fontSize: 10, padding: '1px 6px' }}>
                  {pendingCount}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="emp-card" style={{ padding: 0, overflow: 'hidden' }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-500)' }}>
              Loading expense queue…
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--gray-400)' }}>
              <Receipt size={36} style={{ marginBottom: 12, opacity: 0.4 }} />
              <p>No {filter === 'all' ? '' : STATUS_LABEL[filter] + ' '}expense claims.</p>
              {filter === 'pending' && (
                <p className="text-sm" style={{ marginTop: 6 }}>
                  Your direct reports' submissions will appear here.
                </p>
              )}
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Category</th>
                    <th>Amount</th>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(claim => (
                    <>
                      <tr key={claim.id}>
                        <td style={{ fontWeight: 500 }}>{claim.employeeName || '—'}</td>
                        <td>{EXPENSE_CATEGORIES[claim.category] || claim.category}</td>
                        <td style={{ fontWeight: 600 }}>
                          AED {claim.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                        </td>
                        <td style={{ whiteSpace: 'nowrap' }}>{formatDateUAE(claim.expenseDate)}</td>
                        <td style={{ maxWidth: 200 }}>
                          <span title={claim.description} style={{
                            display: 'block', overflow: 'hidden',
                            whiteSpace: 'nowrap', textOverflow: 'ellipsis',
                          }}>
                            {claim.description || <span className="text-muted">—</span>}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${STATUS_BADGE[claim.status] || 'badge-yellow'}`}>
                            {STATUS_LABEL[claim.status] || claim.status}
                          </span>
                          {claim.status === 'manager_rejected' && claim.managerRejectionReason && (
                            <div style={{ fontSize: 10, color: 'var(--danger)', marginTop: 2 }}>
                              {claim.managerRejectionReason}
                            </div>
                          )}
                        </td>
                        <td>
                          {claim.status === 'pending' && (
                            <div style={{ display: 'flex', gap: 4 }}>
                              <button
                                className="btn btn-sm"
                                style={{ background: 'var(--success)', color: '#fff', border: 'none' }}
                                onClick={() => handleApprove(claim.id)}
                                disabled={busy}
                                title="Approve"
                              >
                                <Check size={13} />
                              </button>
                              <button
                                className="btn btn-sm"
                                style={{ background: 'var(--danger)', color: '#fff', border: 'none' }}
                                onClick={() => { setRejectId(claim.id); setRejectReason(''); }}
                                disabled={busy}
                                title="Reject"
                              >
                                <X size={13} />
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>

                      {/* Inline reject form */}
                      {rejectId === claim.id && (
                        <tr key={`${claim.id}-reject`} style={{ background: 'var(--danger-light)' }}>
                          <td colSpan={7} style={{ padding: '10px 16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--danger)', whiteSpace: 'nowrap' }}>
                                Rejection reason:
                              </span>
                              <input
                                className="form-control"
                                style={{ flex: 1 }}
                                placeholder="e.g. Missing receipt, over budget…"
                                value={rejectReason}
                                onChange={e => setRejectReason(e.target.value)}
                                autoFocus
                              />
                              <button
                                className="btn btn-sm"
                                style={{ background: 'var(--danger)', color: '#fff', border: 'none', whiteSpace: 'nowrap' }}
                                onClick={handleReject}
                                disabled={!rejectReason.trim() || busy}
                              >
                                Confirm Reject
                              </button>
                              <button
                                className="btn btn-sm btn-outline"
                                onClick={() => setRejectId(null)}
                                disabled={busy}
                              >
                                Cancel
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {pendingCount > 0 && (
          <div className="alert alert-info mt-4">
            <AlertCircle size={14} />
            <span>
              Claims you approve will be sent to HR for final sign-off before reimbursement.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
