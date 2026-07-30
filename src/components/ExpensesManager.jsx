/**
 * ExpensesManager.jsx — Admin: Expense Claims & Reimbursements (Feature 14)
 *
 * Allows HR to review employee expense submissions:
 *   - Filter by status (All / Pending / Approved / Paid / Rejected)
 *   - Approve claims (one click)
 *   - Reject claims (requires a reason)
 *   - Delete claims
 *   - View receipt links
 *   - Summary stat cards
 */
import { useState, useEffect } from 'react';
import { Receipt, Check, X, Trash2, ExternalLink, AlertCircle, RefreshCw } from 'lucide-react';
import { getExpenseClaims, approveExpenseClaim, rejectExpenseClaim, deleteExpenseClaim } from '../utils/expenseStorage';
import { formatDateUAE, validateRejectionReason } from '../utils/uaeValidators';

// ── Constants ─────────────────────────────────────────────────────────────────

export const EXPENSE_CATEGORIES = {
  travel:          'Travel',
  meals:           'Meals & Entertainment',
  accommodation:   'Accommodation',
  office_supplies: 'Office Supplies',
  medical:         'Medical',
  phone_internet:  'Phone & Internet',
  training:        'Training & Education',
  other:           'Other',
};

const STATUS_BADGE = {
  pending:          'badge-amber',
  manager_approved: 'badge-blue',
  approved:         'badge-green',
  paid:             'badge-green',
  manager_rejected: 'badge-red',
  rejected:         'badge-red',
};

const STATUS_LABEL = {
  pending:          'Pending',
  manager_approved: 'Mgr Approved',
  approved:         'HR Approved',
  paid:             'Paid',
  manager_rejected: 'Mgr Rejected',
  rejected:         'Rejected',
};

const FILTERS = ['all', 'pending', 'manager_approved', 'approved', 'paid', 'rejected'];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ExpensesManager() {
  const [claims, setClaims]       = useState([]);
  const [loading, setLoading]     = useState(true);
  const [filter, setFilter]       = useState('pending');
  const [rejectId, setRejectId]   = useState(null);   // claim being rejected
  const [rejectReason, setRejectReason] = useState('');
  const [actionBusy, setActionBusy]     = useState(false);
  const [actionMsg, setActionMsg]       = useState(null); // { type, text }
  const [deleteConfirm, setDeleteConfirm] = useState(null); // claim id

  const load = () => {
    setLoading(true);
    getExpenseClaims()
      .then(setClaims)
      .catch(err => setActionMsg({ type: 'error', text: err.message }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  // ── Derived ───────────────────────────────────────────────────────────────
  const filtered = filter === 'all' ? claims : claims.filter(c => c.status === filter);

  const pendingCount   = claims.filter(c => c.status === 'pending').length;
  const mgrApprovedCount = claims.filter(c => c.status === 'manager_approved').length;
  const pendingTotal   = claims.filter(c => c.status === 'pending').reduce((s, c) => s + c.amount, 0);
  const approvedTotal  = claims.filter(c => c.status === 'approved').reduce((s, c) => s + c.amount, 0);
  const paidTotal      = claims.filter(c => c.status === 'paid').reduce((s, c) => s + c.amount, 0);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const flash = (type, text) => {
    setActionMsg({ type, text });
    setTimeout(() => setActionMsg(null), 4000);
  };

  const handleApprove = async (id) => {
    setActionBusy(true);
    try {
      await approveExpenseClaim(id);
      setClaims(prev => prev.map(c => c.id === id
        ? { ...c, status: 'approved' }
        : c
      ));
      flash('success', 'Claim approved.');
    } catch (err) {
      flash('error', err.message);
    } finally {
      setActionBusy(false);
    }
  };

  const handleReject = async () => {
    const check = validateRejectionReason(rejectReason);
    if (!check.valid) { flash('error', check.message); return; }
    setActionBusy(true);
    try {
      await rejectExpenseClaim(rejectId, rejectReason.trim());
      setClaims(prev => prev.map(c => c.id === rejectId
        ? { ...c, status: 'rejected', rejectionReason: rejectReason.trim() }
        : c
      ));
      setRejectId(null);
      setRejectReason('');
      flash('success', 'Claim rejected.');
    } catch (err) {
      flash('error', err.message);
    } finally {
      setActionBusy(false);
    }
  };

  const handleDelete = async () => {
    setActionBusy(true);
    try {
      await deleteExpenseClaim(deleteConfirm);
      setClaims(prev => prev.filter(c => c.id !== deleteConfirm));
      setDeleteConfirm(null);
      flash('success', 'Claim deleted.');
    } catch (err) {
      flash('error', err.message);
    } finally {
      setActionBusy(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <h2>Expense Claims</h2>
          <p className="text-muted text-sm">Review and approve employee expense reimbursements</p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      <div className="page-body">

        {/* ── Flash messages ── */}
        {actionMsg && (
          <div className={`alert alert-${actionMsg.type === 'error' ? 'danger' : 'success'} mb-4`}>
            <AlertCircle size={14} />
            {actionMsg.text}
          </div>
        )}

        {/* ── Stat cards ── */}
        <div className="stats-grid mb-4" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(245,158,11,0.10)' }}>
              <Receipt size={20} color="var(--warning)" />
            </div>
            <div>
              <div className="stat-value">{pendingCount}</div>
              <div className="stat-label">Pending Claims</div>
              {pendingCount > 0 && (
                <div className="stat-sub">
                  AED {pendingTotal.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                </div>
              )}
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(37,99,235,0.10)' }}>
              <Check size={20} color="var(--primary)" />
            </div>
            <div>
              <div className="stat-value">
                AED {approvedTotal.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
              </div>
              <div className="stat-label">Approved (Unpaid)</div>
              <div className="stat-sub">Reimbursed in next payroll</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(22,163,74,0.10)' }}>
              <Check size={20} color="var(--success)" />
            </div>
            <div>
              <div className="stat-value">
                AED {paidTotal.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
              </div>
              <div className="stat-label">Total Paid</div>
              <div className="stat-sub">All time</div>
            </div>
          </div>
        </div>

        {/* ── Filter tabs ── */}
        <div className="tab-bar mb-3">
          {FILTERS.map(f => (
            <button
              key={f}
              className={`tab-btn ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {STATUS_LABEL[f] || (f === 'all' ? 'All' : f)}
              {f === 'pending' && pendingCount > 0 && (
                <span className="badge badge-amber" style={{ marginLeft: 6, fontSize: 10, padding: '1px 6px' }}>
                  {pendingCount}
                </span>
              )}
              {f === 'manager_approved' && mgrApprovedCount > 0 && (
                <span className="badge badge-blue" style={{ marginLeft: 6, fontSize: 10, padding: '1px 6px' }}>
                  {mgrApprovedCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Main table ── */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-500)' }}>
              Loading expense claims…
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--gray-400)' }}>
              <Receipt size={36} style={{ marginBottom: 12, opacity: 0.4 }} />
              <p>No {filter === 'all' ? '' : filter + ' '}expense claims found.</p>
              {filter === 'pending' && (
                <p className="text-sm" style={{ marginTop: 6 }}>
                  Employees can submit claims from the Employee Portal → Expenses tab.
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
                    <th>Receipt</th>
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
                        <td style={{ maxWidth: 220 }}>
                          <span title={claim.description} style={{
                            display: 'block', overflow: 'hidden',
                            whiteSpace: 'nowrap', textOverflow: 'ellipsis',
                          }}>
                            {claim.description || <span className="text-muted">—</span>}
                          </span>
                        </td>
                        <td>
                          {claim.receiptUrl ? (
                            <a
                              href={claim.receiptUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--primary)', fontSize: 12 }}
                            >
                              <ExternalLink size={12} /> View
                            </a>
                          ) : (
                            <span className="text-muted text-sm">None</span>
                          )}
                        </td>
                        <td>
                          <span className={`badge ${STATUS_BADGE[claim.status] || 'badge-yellow'}`}>
                            {STATUS_LABEL[claim.status] || claim.status}
                          </span>
                          {claim.status === 'manager_approved' && claim.managerApprovedBy && (
                            <div style={{ fontSize: 10, color: 'var(--gray-400)', marginTop: 2 }}>
                              by {claim.managerApprovedBy}
                            </div>
                          )}
                          {claim.status === 'manager_rejected' && claim.managerRejectionReason && (
                            <div style={{ fontSize: 10, color: 'var(--danger)', marginTop: 2 }}>
                              {claim.managerRejectionReason}
                            </div>
                          )}
                          {claim.status === 'paid' && claim.payrollRunId && (
                            <div style={{ fontSize: 10, color: 'var(--gray-400)', marginTop: 2 }}>
                              via payroll
                            </div>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 4 }}>
                            {(claim.status === 'pending' || claim.status === 'manager_approved') && (
                              <>
                                <button
                                  className="btn btn-sm"
                                  style={{ background: 'var(--success)', color: '#fff', border: 'none' }}
                                  onClick={() => handleApprove(claim.id)}
                                  disabled={actionBusy}
                                  title={claim.status === 'manager_approved' ? 'Final Approve' : 'Approve'}
                                >
                                  <Check size={13} />
                                </button>
                                <button
                                  className="btn btn-sm"
                                  style={{ background: 'var(--danger)', color: '#fff', border: 'none' }}
                                  onClick={() => { setRejectId(claim.id); setRejectReason(''); }}
                                  disabled={actionBusy}
                                  title="Reject"
                                >
                                  <X size={13} />
                                </button>
                              </>
                            )}
                            {(claim.status === 'rejected' || claim.status === 'manager_rejected') && (
                              <button
                                className="btn btn-sm btn-outline"
                                onClick={() => handleApprove(claim.id)}
                                disabled={actionBusy}
                                title="Re-approve"
                              >
                                <Check size={13} /> Approve
                              </button>
                            )}
                            {(claim.status === 'pending' || claim.status === 'rejected' || claim.status === 'manager_rejected') && (
                              <button
                                className="btn btn-ghost btn-icon btn-sm text-danger"
                                onClick={() => setDeleteConfirm(claim.id)}
                                disabled={actionBusy}
                                title="Delete claim"
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* ── Inline reject form ── */}
                      {rejectId === claim.id && (
                        <tr key={`${claim.id}-reject`} style={{ background: 'var(--danger-light)' }}>
                          <td colSpan={8} style={{ padding: '10px 16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--danger)', whiteSpace: 'nowrap' }}>
                                Rejection reason:
                              </span>
                              <input
                                className="form-control"
                                style={{ flex: 1 }}
                                placeholder="e.g. Missing receipt, over policy limit…"
                                value={rejectReason}
                                onChange={e => setRejectReason(e.target.value)}
                                autoFocus
                              />
                              <button
                                className="btn btn-sm"
                                style={{ background: 'var(--danger)', color: '#fff', border: 'none', whiteSpace: 'nowrap' }}
                                onClick={handleReject}
                                disabled={!rejectReason.trim() || actionBusy}
                              >
                                Confirm Reject
                              </button>
                              <button
                                className="btn btn-sm btn-outline"
                                onClick={() => setRejectId(null)}
                                disabled={actionBusy}
                              >
                                Cancel
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}

                      {/* ── Rejection reason display ── */}
                      {claim.status === 'rejected' && claim.rejectionReason && (
                        <tr key={`${claim.id}-reason`} style={{ background: '#fff5f5' }}>
                          <td colSpan={8} style={{ padding: '6px 16px 10px' }}>
                            <span style={{ fontSize: 12, color: 'var(--danger)' }}>
                              Reason: {claim.rejectionReason}
                            </span>
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

        {/* ── Payroll info banner (shown when there are approved unpaid claims) ── */}
        {claims.filter(c => c.status === 'approved').length > 0 && (
          <div className="alert alert-info mt-4">
            <AlertCircle size={14} />
            <span>
              <strong>
                AED {approvedTotal.toLocaleString('en-AE', { minimumFractionDigits: 2 })} in approved expenses
              </strong>{' '}
              will be automatically marked as <strong>Paid</strong> when the next payroll run is submitted.
              Add the reimbursement amounts to employee entries via the Allowances &amp; Deductions panel
              in the Payroll Module before generating the SIF.
            </span>
          </div>
        )}
      </div>

      {/* ── Delete confirmation modal ── */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3>Delete Expense Claim</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setDeleteConfirm(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to permanently delete this expense claim? This cannot be undone.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)} disabled={actionBusy}>
                Cancel
              </button>
              <button
                className="btn"
                style={{ background: 'var(--danger)', color: '#fff', border: 'none' }}
                onClick={handleDelete}
                disabled={actionBusy}
              >
                {actionBusy ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
