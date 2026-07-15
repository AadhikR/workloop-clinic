import { useState, useEffect } from 'react';
import { Plus, Check, X, DollarSign, Clock, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react';
import { getEmployees } from '../utils/storage';
import { getAdvances, saveAdvance, getAdvanceRepayments } from '../utils/storage';
import { formatDateUAE } from '../utils/uaeValidators';

const STATUS_BADGE = {
  pending:   'badge-amber',
  active:    'badge-blue',
  settled:   'badge-green',
  cancelled: 'badge-red',
};

const EMPTY_FORM = {
  employeeId:      '',
  amount:          '',
  disbursedDate:   new Date().toISOString().split('T')[0],
  reason:          '',
  repaymentMonths: '3',
};

export default function AdvancesManager() {
  const [employees, setEmployees]     = useState([]);
  const [advances, setAdvances]       = useState([]);
  const [loading, setLoading]         = useState(true);
  const [filter, setFilter]           = useState('all');
  const [showForm, setShowForm]       = useState(false);
  const [form, setForm]               = useState(EMPTY_FORM);
  const [saving, setSaving]           = useState(false);
  const [formError, setFormError]     = useState('');
  const [expandedId, setExpandedId]   = useState(null);
  const [repayments, setRepayments]   = useState({});
  const [loadingReps, setLoadingReps] = useState(false);

  // Inline reject/cancel form state
  const [rejectingId,  setRejectingId]  = useState(null); // advance id being acted on
  const [rejectAction, setRejectAction] = useState('');   // 'reject' | 'cancel'
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    Promise.all([getEmployees(), getAdvances()])
      .then(([emps, advs]) => {
        setEmployees(emps.filter(e => e.active !== false));
        setAdvances(advs);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleField = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const monthlyDeduction = () => {
    const amt    = parseFloat(form.amount) || 0;
    const months = parseInt(form.repaymentMonths) || 1;
    return amt > 0 && months > 0 ? (amt / months).toFixed(2) : '0.00';
  };

  const handleCreate = async () => {
    setFormError('');
    if (!form.employeeId) { setFormError('Please select an employee.'); return; }
    if (!form.amount || parseFloat(form.amount) <= 0) { setFormError('Enter a valid amount.'); return; }
    if (!form.reason.trim()) { setFormError('Reason is required.'); return; }

    setSaving(true);
    try {
      const months = parseInt(form.repaymentMonths) || 1;
      const amount = parseFloat(form.amount);
      const saved = await saveAdvance({
        employeeId:         form.employeeId,
        amount,
        disbursedDate:      form.disbursedDate,
        reason:             form.reason.trim(),
        repaymentMonths:    months,
        monthlyDeduction:   parseFloat((amount / months).toFixed(2)),
        outstandingBalance: amount,
        status:             'active',
      });
      setAdvances(prev => [saved, ...prev]);
      setShowForm(false);
      setForm(EMPTY_FORM);
    } catch (err) {
      setFormError(err.message || 'Failed to create advance.');
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async (adv) => {
    try {
      const months  = adv.repaymentMonths || 1;
      const updated = await saveAdvance({
        ...adv,
        status:             'active',
        monthlyDeduction:   parseFloat((adv.amount / months).toFixed(2)),
        outstandingBalance: adv.amount,
      });
      setAdvances(prev => prev.map(a => a.id === updated.id ? updated : a));
    } catch (err) {
      alert('Could not approve: ' + err.message);
    }
  };

  // Opens the inline reason form
  const startAction = (adv, action) => {
    setRejectingId(adv.id);
    setRejectAction(action);
    setRejectReason('');
  };

  const cancelAction = () => {
    setRejectingId(null);
    setRejectAction('');
    setRejectReason('');
  };

  const confirmAction = async (adv) => {
    try {
      const updated = await saveAdvance({
        ...adv,
        status:          'cancelled',
        rejectionReason: rejectReason.trim() || null,
      });
      setAdvances(prev => prev.map(a => a.id === updated.id ? updated : a));
      cancelAction();
    } catch (err) {
      alert('Action failed: ' + err.message);
    }
  };

  const handleSettle = async (adv) => {
    if (!window.confirm('Mark this advance as fully settled?')) return;
    try {
      const updated = await saveAdvance({ ...adv, status: 'settled', outstandingBalance: 0 });
      setAdvances(prev => prev.map(a => a.id === updated.id ? updated : a));
    } catch (err) {
      alert('Could not settle: ' + err.message);
    }
  };

  const toggleExpand = async (advId) => {
    if (expandedId === advId) { setExpandedId(null); return; }
    setExpandedId(advId);
    if (!repayments[advId]) {
      setLoadingReps(true);
      const reps = await getAdvanceRepayments(advId).catch(() => []);
      setRepayments(prev => ({ ...prev, [advId]: reps }));
      setLoadingReps(false);
    }
  };

  const empName = (id) => employees.find(e => e.id === id)?.name || '—';

  const filtered      = advances.filter(a => filter === 'all' || a.status === filter);
  const pendingCount  = advances.filter(a => a.status === 'pending').length;
  const activeCount   = advances.filter(a => a.status === 'active').length;
  const totalOut      = advances.filter(a => a.status === 'active')
    .reduce((s, a) => s + a.outstandingBalance, 0);

  if (loading) return <div style={{ padding: 32 }}>Loading advances…</div>;

  return (
    <div>
      <div className="page-header">
        <h2><DollarSign size={20} style={{ marginRight: 8 }}/>Salary Advances</h2>
        <div className="page-header-actions">
          <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(true); setFormError(''); }}>
            <Plus size={14}/> New Advance
          </button>
        </div>
      </div>

      <div className="page-body">

        {/* ── Stat cards ── */}
        <div className="stats-grid mb-4">
          <div className="stat-card">
            <div className="stat-label">Pending Requests</div>
            <div className="stat-value" style={{ color: pendingCount > 0 ? 'var(--warning)' : undefined }}>
              {pendingCount}
            </div>
            <div className="stat-sub">awaiting approval</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Active Advances</div>
            <div className="stat-value">{activeCount}</div>
            <div className="stat-sub">being repaid</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Outstanding</div>
            <div className="stat-value" style={{ color: 'var(--primary)' }}>
              {totalOut.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
            </div>
            <div className="stat-sub">AED — outstanding balance</div>
          </div>
        </div>

        {/* ── Create advance form ── */}
        {showForm && (
          <div className="card mb-4">
            <div className="card-header">
              <h3>New Salary Advance</h3>
              <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setShowForm(false)}><X size={15}/></button>
            </div>
            <div className="card-body">
              {formError && (
                <div className="alert alert-danger mb-3">
                  <AlertCircle size={14}/> {formError}
                </div>
              )}
              <div className="form-grid form-grid-2">
                <div className="form-group">
                  <label>Employee *</label>
                  <select className="form-control" value={form.employeeId}
                    onChange={e => handleField('employeeId', e.target.value)}>
                    <option value="">— Select employee —</option>
                    {employees.map(e => (
                      <option key={e.id} value={e.id}>{e.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Advance Amount (AED) *</label>
                  <input className="form-control" type="number" min="1" step="0.01"
                    placeholder="e.g. 3000"
                    value={form.amount}
                    onChange={e => handleField('amount', e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Disbursement Date</label>
                  <input className="form-control" type="date"
                    value={form.disbursedDate}
                    onChange={e => handleField('disbursedDate', e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Repayment Months *</label>
                  <input className="form-control" type="number" min="1" max="36"
                    value={form.repaymentMonths}
                    onChange={e => handleField('repaymentMonths', e.target.value)} />
                  {parseFloat(form.amount) > 0 && (
                    <span className="hint">
                      Monthly deduction: AED {monthlyDeduction()}
                    </span>
                  )}
                </div>
                <div className="form-group" style={{ gridColumn: '1/-1' }}>
                  <label>Reason *</label>
                  <input className="form-control" type="text"
                    placeholder="e.g. Emergency medical expense"
                    value={form.reason}
                    onChange={e => handleField('reason', e.target.value)} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button className="btn btn-primary btn-sm" onClick={handleCreate}
                  disabled={saving || !form.employeeId || !form.amount || !form.reason.trim()}>
                  {saving ? 'Creating…' : 'Create Advance'}
                </button>
                <button className="btn btn-outline btn-sm" onClick={() => setShowForm(false)} disabled={saving}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Filter tabs + table ── */}
        <div className="card">
          <div className="card-header">
            <h3>All Advances</h3>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['all','pending','active','settled','cancelled'].map(s => (
                <button
                  key={s}
                  className={`btn btn-sm ${filter === s ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setFilter(s)}
                  style={{ textTransform: 'capitalize' }}
                >
                  {s}{s === 'all'
                    ? ` (${advances.length})`
                    : ` (${advances.filter(a => a.status === s).length})`}
                </button>
              ))}
            </div>
          </div>

          {filtered.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--gray-400)' }}>
              No {filter !== 'all' ? filter + ' ' : ''}advances found.
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Amount (AED)</th>
                    <th>Disbursed</th>
                    <th>Repayment</th>
                    <th className="text-right">Monthly Ded.</th>
                    <th className="text-right">Outstanding</th>
                    <th>Reason</th>
                    <th>Status</th>
                    <th>Actions</th>
                    <th style={{ width: 30 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(adv => (
                    <>
                      <tr key={adv.id}>
                        <td style={{ fontWeight: 500 }}>{empName(adv.employeeId)}</td>
                        <td>{adv.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}</td>
                        <td className="text-sm">{adv.disbursedDate ? formatDateUAE(adv.disbursedDate) : '—'}</td>
                        <td className="text-sm">{adv.repaymentMonths} month{adv.repaymentMonths !== 1 ? 's' : ''}</td>
                        <td className="text-right text-sm" style={{ color: 'var(--danger)' }}>
                          {adv.status === 'active'
                            ? adv.monthlyDeduction.toLocaleString('en-AE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>
                        <td className="text-right" style={{
                          fontWeight: 600,
                          color: adv.outstandingBalance > 0 ? 'var(--primary)' : 'var(--success)',
                        }}>
                          {adv.outstandingBalance.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="text-sm" style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {adv.reason}
                        </td>
                        <td>
                          <span className={`badge ${STATUS_BADGE[adv.status] || 'badge-gray'}`} style={{ textTransform: 'capitalize' }}>
                            {adv.status}
                          </span>
                          {adv.status === 'cancelled' && adv.rejectionReason && (
                            <div style={{ fontSize: 10, color: 'var(--gray-400)', marginTop: 2, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                              title={adv.rejectionReason}>
                              {adv.rejectionReason}
                            </div>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 4 }}>
                            {adv.status === 'pending' && (
                              <>
                                <button className="btn btn-success btn-icon btn-sm" title="Approve request"
                                  onClick={() => handleApprove(adv)}>
                                  <Check size={13}/>
                                </button>
                                <button className="btn btn-ghost btn-icon btn-sm" title="Reject request"
                                  style={{ color: 'var(--danger)' }}
                                  onClick={() => startAction(adv, 'reject')}>
                                  <X size={13}/>
                                </button>
                              </>
                            )}
                            {adv.status === 'active' && (
                              <>
                                <button className="btn btn-success btn-sm" title="Mark as settled"
                                  onClick={() => handleSettle(adv)}
                                  style={{ fontSize: 11, padding: '2px 8px' }}>
                                  Settle
                                </button>
                                <button className="btn btn-ghost btn-icon btn-sm" title="Cancel advance"
                                  style={{ color: 'var(--danger)' }}
                                  onClick={() => startAction(adv, 'cancel')}>
                                  <X size={13}/>
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                        <td>
                          <button
                            className="btn btn-ghost btn-icon btn-sm"
                            title="View repayment history"
                            onClick={() => toggleExpand(adv.id)}
                          >
                            {expandedId === adv.id ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
                          </button>
                        </td>
                      </tr>

                      {/* ── Inline reject / cancel reason form ── */}
                      {rejectingId === adv.id && (
                        <tr key={`${adv.id}-action`}>
                          <td colSpan={10} style={{ background: 'rgba(220,38,38,0.04)', padding: '10px 16px' }}>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                              <span style={{ fontSize: 13, color: 'var(--gray-600)', whiteSpace: 'nowrap' }}>
                                {rejectAction === 'reject' ? 'Rejection reason' : 'Cancellation reason'}
                                <span style={{ color: 'var(--gray-400)', marginLeft: 4 }}>(optional)</span>:
                              </span>
                              <input
                                className="form-control"
                                style={{ flex: 1, minWidth: 200, fontSize: 13 }}
                                placeholder="e.g. Advance limit reached this month…"
                                value={rejectReason}
                                onChange={e => setRejectReason(e.target.value)}
                                autoFocus
                              />
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => confirmAction(adv)}
                              >
                                {rejectAction === 'reject' ? 'Reject' : 'Cancel Advance'}
                              </button>
                              <button className="btn btn-ghost btn-sm" onClick={cancelAction}>
                                Back
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}

                      {/* ── Repayment history row ── */}
                      {expandedId === adv.id && (
                        <tr key={`${adv.id}-reps`}>
                          <td colSpan={10} style={{ background: 'var(--gray-50)', padding: '12px 20px' }}>
                            <strong style={{ fontSize: 12 }}>Repayment History</strong>
                            {loadingReps ? (
                              <div style={{ fontSize: 12, color: 'var(--gray-400)', marginTop: 6 }}>Loading…</div>
                            ) : !repayments[adv.id]?.length ? (
                              <div style={{ fontSize: 12, color: 'var(--gray-400)', marginTop: 6 }}>No repayments recorded yet.</div>
                            ) : (
                              <table style={{ width: '100%', marginTop: 8, fontSize: 12 }}>
                                <thead>
                                  <tr>
                                    <th style={{ textAlign: 'left', padding: '4px 8px' }}>Date</th>
                                    <th style={{ textAlign: 'right', padding: '4px 8px' }}>Amount (AED)</th>
                                    <th style={{ textAlign: 'left', padding: '4px 8px' }}>Payroll Run</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {repayments[adv.id].map(rep => (
                                    <tr key={rep.id}>
                                      <td style={{ padding: '4px 8px' }}>{formatDateUAE(rep.paidDate)}</td>
                                      <td style={{ textAlign: 'right', padding: '4px 8px', color: 'var(--danger)' }}>
                                        -{rep.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                                      </td>
                                      <td style={{ padding: '4px 8px', color: 'var(--gray-400)' }}>
                                        {rep.payrollRunId ? rep.payrollRunId.slice(0, 8) + '…' : 'Manual'}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
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
      </div>
    </div>
  );
}
