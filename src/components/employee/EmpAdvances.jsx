import { useState, useEffect } from 'react';
import { DollarSign, AlertCircle, Clock, CheckCircle, XCircle, X } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { getAdvances, withdrawEmployeeAdvance } from '../../utils/storage';
import { formatDateUAE, validateAmount } from '../../utils/uaeValidators';
import { getMyEmployeeRecord } from '../../utils/profileStorage';

const STATUS_ICON = {
  pending:   <Clock      size={14} style={{ color: 'var(--warning)' }}/>,
  active:    <CheckCircle size={14} style={{ color: 'var(--primary)' }}/>,
  settled:   <CheckCircle size={14} style={{ color: 'var(--success)' }}/>,
  cancelled: <XCircle    size={14} style={{ color: 'var(--danger)' }}/>,
};

const STATUS_LABEL = {
  pending:   'Pending approval',
  active:    'Active — being repaid',
  settled:   'Fully settled',
  cancelled: 'Cancelled / Rejected',
};

export default function EmpAdvances() {
  const [emp, setEmp]           = useState(null);
  const [advances, setAdvances] = useState([]);
  const [loading, setLoading]   = useState(true);

  const [showForm, setShowForm]     = useState(false);
  const [amount, setAmount]         = useState('');
  const [reason, setReason]         = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError]   = useState('');
  const [success, setSuccess]       = useState('');
  const [cancellingId, setCancellingId] = useState(null); // id currently being cancelled

  useEffect(() => {
    getMyEmployeeRecord().then(e => {
      setEmp(e);
      if (e?.id) return getAdvances(e.id);
      return [];
    }).then(advs => {
      setAdvances(advs);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleSubmit = async () => {
    setFormError('');
    setSuccess('');
    // Cap at one month's basic salary (UAE Labour Law norm). Fall back to a
    // wide ceiling when the employee record hasn't loaded yet so the form
    // still submits — the server RPC + HR review are the ultimate authority.
    const basic = parseFloat(emp?.basic_salary) || 0;
    const cap = basic > 0 ? basic : 1_000_000;
    const check = validateAmount(amount, { min: 1, max: cap, fieldName: 'Amount' });
    if (!check.valid) {
      setFormError(
        basic > 0 && check.value > basic
          ? `Amount cannot exceed one month's basic salary (${basic.toLocaleString('en-AE')} AED). Contact HR for exceptions.`
          : check.message,
      );
      return;
    }
    const amt = check.value;
    if (!reason.trim())   { setFormError('Please provide a reason for your request.'); return; }

    setSubmitting(true);
    try {
      const { error } = await supabase.rpc('employee_request_advance', {
        p_amount: amt,
        p_reason: reason.trim(),
      });
      if (error) throw error;

      const updated = await getAdvances(emp?.id).catch(() => advances);
      setAdvances(updated);
      setAmount('');
      setReason('');
      setShowForm(false);
      setSuccess('Your advance request has been submitted. HR will review it shortly.');
      setTimeout(() => setSuccess(''), 8000);
    } catch (err) {
      setFormError(err.message || 'Failed to submit request. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (adv) => {
    if (!window.confirm(`Withdraw your pending request for AED ${adv.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}? This cannot be undone.`)) return;
    setCancellingId(adv.id);
    setFormError('');
    try {
      await withdrawEmployeeAdvance(adv.id);
      setAdvances(current => current.map(item => item.id === adv.id
        ? { ...item, status: 'cancelled', rejectionReason: 'Withdrawn by employee' }
        : item));
      setSuccess('Your advance request has been withdrawn.');
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setFormError(err.message || 'Could not withdraw the request. Please try again.');
    } finally {
      setCancellingId(null);
    }
  };

  if (loading) return <div style={{ padding: 32 }}>Loading advances…</div>;

  const active     = advances.filter(a => a.status === 'active');
  const pending    = advances.filter(a => a.status === 'pending');
  const historical = advances.filter(a => a.status === 'settled' || a.status === 'cancelled');
  const totalOut   = active.reduce((s, a) => s + a.outstandingBalance, 0);

  return (
    <div>
      <div className="emp-page-header">
        <div>
          <h2 style={{ fontWeight: 700, fontSize: 20, color: '#1e293b', margin: 0 }}>
            Salary Advances
          </h2>
          <p style={{ fontSize: 13, color: 'var(--gray-500)', marginTop: 4 }}>
            View your advances and submit new requests
          </p>
        </div>
        {!showForm && (
          <button className="btn btn-primary btn-sm" onClick={() => { setShowForm(true); setFormError(''); }}>
            + Request Advance
          </button>
        )}
      </div>

      <div className="emp-page-body">

        {success && (
          <div className="alert alert-success mb-4">
            <CheckCircle size={15}/> {success}
          </div>
        )}

        {formError && !showForm && (
          <div className="alert alert-danger mb-4">
            <AlertCircle size={14}/> {formError}
          </div>
        )}

        {/* ── Summary ── */}
        {active.length > 0 && (
          <div className="emp-card mb-4" style={{
            padding: '16px 18px',
            background: 'linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%)',
            border: '1px solid #bfdbfe',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
                background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <DollarSign size={18} color="#fff"/>
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--gray-500)' }}>Total Outstanding Balance</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--primary)' }}>
                  AED {totalOut.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                </div>
                <div style={{ fontSize: 12, color: 'var(--gray-400)' }}>
                  across {active.length} active advance{active.length !== 1 ? 's' : ''}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Request form ── */}
        {showForm && (
          <div className="emp-card mb-4" style={{ padding: '16px 18px' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>New Advance Request</h3>
            {formError && (
              <div className="alert alert-danger mb-3">
                <AlertCircle size={14}/> {formError}
              </div>
            )}
            <div className="form-group" style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 13, fontWeight: 500 }}>Requested Amount (AED) *</label>
              <input
                className="form-control"
                type="number"
                min="1"
                step="0.01"
                placeholder="e.g. 2000"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                disabled={submitting}
              />
              <span className="hint">The final approved amount may differ from your request.</span>
            </div>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, fontWeight: 500 }}>Reason *</label>
              <textarea
                className="form-control"
                rows={3}
                placeholder="Briefly explain why you need this advance…"
                value={reason}
                onChange={e => setReason(e.target.value)}
                disabled={submitting}
                style={{ resize: 'vertical' }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleSubmit}
                disabled={submitting || !amount || !reason.trim()}
              >
                {submitting ? 'Submitting…' : 'Submit Request'}
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => setShowForm(false)} disabled={submitting}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* ── Pending requests ── */}
        {pending.length > 0 && (
          <div className="emp-card mb-4" style={{ padding: '16px 18px' }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Clock size={14}/>Pending Requests
            </h3>
            {pending.map(adv => (
              <div key={adv.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                padding: '10px 0', borderBottom: '1px solid var(--gray-100)', gap: 12,
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>
                    AED {adv.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                    {adv.reason}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 2 }}>
                    Submitted {formatDateUAE(adv.createdAt)}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                  <span className="badge badge-amber">Pending</span>
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: 11, padding: '2px 8px', color: 'var(--danger)', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    onClick={() => handleCancel(adv)}
                    disabled={cancellingId === adv.id}
                    title="Withdraw this pending request"
                  >
                    <X size={11} />
                    {cancellingId === adv.id ? 'Withdrawing…' : 'Withdraw'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Active advances ── */}
        {active.length > 0 && (
          <div className="emp-card mb-4" style={{ padding: '16px 18px' }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Active Advances</h3>
            {active.map(adv => {
              const repaidPct = adv.amount > 0
                ? Math.min(100, Math.max(0, ((adv.amount - adv.outstandingBalance) / adv.amount) * 100))
                : 0;
              return (
                <div key={adv.id} style={{ padding: '12px 0', borderBottom: '1px solid var(--gray-100)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 15 }}>
                        AED {adv.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                        {adv.reason}
                      </div>
                      {adv.disbursedDate && (
                        <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 2 }}>
                          Disbursed: {formatDateUAE(adv.disbursedDate)}
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 16 }}>
                      <div style={{ fontSize: 12, color: 'var(--gray-500)' }}>Outstanding</div>
                      <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--primary)' }}>
                        AED {adv.outstandingBalance.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                  </div>

                  {/* Repayment progress bar */}
                  {adv.repaymentMonths > 0 && (
                    <div style={{ marginTop: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--gray-500)', marginBottom: 4 }}>
                        <span>Monthly deduction: AED {adv.monthlyDeduction.toLocaleString('en-AE', { minimumFractionDigits: 2 })}</span>
                        <span>Over {adv.repaymentMonths} month{adv.repaymentMonths !== 1 ? 's' : ''}</span>
                      </div>
                      <div style={{ background: 'var(--gray-100)', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', borderRadius: 4,
                          background: 'linear-gradient(90deg, var(--primary), var(--accent))',
                          width: `${repaidPct}%`,
                          transition: 'width 0.3s ease',
                        }}/>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 3 }}>
                        {repaidPct.toFixed(0)}% repaid
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ── Historical ── */}
        {historical.length > 0 && (
          <div className="emp-card" style={{ padding: '16px 18px' }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--gray-500)' }}>
              Past Advances
            </h3>
            {historical.map(adv => (
              <div key={adv.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                padding: '8px 0', borderBottom: '1px solid var(--gray-100)',
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: 13 }}>
                    AED {adv.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 1 }}>
                    {adv.reason} · {formatDateUAE(adv.createdAt)}
                  </div>
                  {adv.status === 'cancelled' && adv.rejectionReason && (
                    <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 2 }}>
                      Reason: {adv.rejectionReason}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--gray-500)', flexShrink: 0, marginLeft: 12 }}>
                  {STATUS_ICON[adv.status]}
                  {STATUS_LABEL[adv.status]}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {advances.length === 0 && !showForm && (
          <div className="emp-card" style={{ textAlign: 'center', padding: 40 }}>
            <DollarSign size={36} style={{ color: 'var(--gray-300)', marginBottom: 12 }}/>
            <p style={{ color: 'var(--gray-500)', marginBottom: 16 }}>No advance requests yet.</p>
            <button className="btn btn-primary btn-sm" onClick={() => setShowForm(true)}>
              Request an Advance
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
