/**
 * EmpExpenses.jsx — Employee self-service: Expense Claims (Feature 14)
 *
 * Employees can:
 *  - Submit new expense claims (via employee_submit_expense SECURITY DEFINER RPC)
 *  - View their past claims and current status
 *  - See rejection reasons
 */
import { useState, useEffect } from 'react';
import { Receipt, AlertCircle, CheckCircle, Clock, X, Plus } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { getMyEmployeeRecord } from '../../utils/profileStorage';
import { formatDateUAE } from '../../utils/uaeValidators';
import { EXPENSE_CATEGORIES } from '../ExpensesManager';

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_BADGE = {
  pending:  'badge-amber',
  approved: 'badge-blue',
  paid:     'badge-green',
  rejected: 'badge-red',
};

const STATUS_LABEL = {
  pending:  'Pending Review',
  approved: 'Approved',
  paid:     'Paid',
  rejected: 'Rejected',
};

const EMPTY_FORM = {
  category:    'travel',
  amount:      '',
  expenseDate: new Date().toISOString().split('T')[0],
  description: '',
  receiptUrl:  '',
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function EmpExpenses() {
  const [emp, setEmp]           = useState(null);
  const [claims, setClaims]     = useState([]);
  const [loading, setLoading]   = useState(true);

  // Request form
  const [showForm, setShowForm]     = useState(false);
  const [form, setForm]             = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError]   = useState('');
  const [success, setSuccess]       = useState('');

  useEffect(() => {
    getMyEmployeeRecord().then(e => {
      setEmp(e);
      if (e?.id) return loadClaims(e.id);
    }).finally(() => setLoading(false));
  }, []);

  const loadClaims = async (employeeId) => {
    const { data, error } = await supabase
      .from('expense_claims')
      .select('*')
      .eq('employee_id', employeeId)
      .order('created_at', { ascending: false });
    if (!error) {
      setClaims((data || []).map(r => ({
        id:              r.id,
        category:        r.category,
        amount:          parseFloat(r.amount) || 0,
        expenseDate:     r.expense_date,
        description:     r.description,
        receiptUrl:      r.receipt_url,
        status:          r.status,
        rejectionReason: r.rejection_reason,
        createdAt:       r.created_at,
      })));
    }
  };

  const handleField = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async () => {
    setFormError('');
    setSuccess('');

    const amt = parseFloat(form.amount);
    if (!amt || amt <= 0)       { setFormError('Please enter a valid amount.'); return; }
    if (!form.expenseDate)      { setFormError('Please select the expense date.'); return; }
    if (!form.description.trim()) { setFormError('Please describe the expense.'); return; }

    setSubmitting(true);
    try {
      const { data, error } = await supabase.rpc('employee_submit_expense', {
        p_category:     form.category,
        p_amount:       amt,
        p_expense_date: form.expenseDate,
        p_description:  form.description.trim(),
        p_receipt_url:  form.receiptUrl.trim(),
      });
      if (error) throw error;

      // Reload claims
      if (emp?.id) await loadClaims(emp.id);
      setForm(EMPTY_FORM);
      setShowForm(false);
      setSuccess('Your expense claim has been submitted. HR will review it shortly.');
      setTimeout(() => setSuccess(''), 8000);
    } catch (err) {
      setFormError(err.message || 'Failed to submit claim. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Derived ───────────────────────────────────────────────────────────────
  const pending  = claims.filter(c => c.status === 'pending');
  const approved = claims.filter(c => c.status === 'approved');
  const paid     = claims.filter(c => c.status === 'paid');
  const rejected = claims.filter(c => c.status === 'rejected');
  const totalApproved = approved.reduce((s, c) => s + c.amount, 0);

  if (loading) return <div style={{ padding: 32 }}>Loading expenses…</div>;

  return (
    <div>
      <div className="emp-page-header">
        <div>
          <h2 style={{ fontWeight: 700, fontSize: 20, color: '#1e293b', margin: 0 }}>
            Expense Claims
          </h2>
          <p style={{ fontSize: 13, color: 'var(--gray-500)', marginTop: 4 }}>
            Submit and track your expense reimbursement requests
          </p>
        </div>
        {!showForm && (
          <button
            className="btn btn-primary btn-sm"
            onClick={() => { setShowForm(true); setFormError(''); }}
          >
            <Plus size={14} /> New Claim
          </button>
        )}
      </div>

      <div className="emp-page-body">

        {/* ── Success banner ── */}
        {success && (
          <div className="alert alert-success mb-4">
            <CheckCircle size={15} /> {success}
          </div>
        )}

        {/* ── Summary card (approved unpaid) ── */}
        {approved.length > 0 && (
          <div className="emp-card mb-4" style={{
            background: 'linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%)',
            border: '1px solid #bfdbfe',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 40, height: 40, borderRadius: '50%',
                background: 'var(--primary)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <Receipt size={18} color="#fff" />
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--gray-500)' }}>Approved — Pending Payment</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--primary)' }}>
                  AED {totalApproved.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                </div>
                <div style={{ fontSize: 12, color: 'var(--gray-400)' }}>
                  Will be included in your next payroll
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Submit form ── */}
        {showForm && (
          <div className="emp-card mb-4">
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>New Expense Claim</h3>

            {formError && (
              <div className="alert alert-danger mb-3">
                <AlertCircle size={14} /> {formError}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label style={{ fontSize: 13, fontWeight: 500 }}>Category *</label>
                <select
                  className="form-control"
                  value={form.category}
                  onChange={e => handleField('category', e.target.value)}
                  disabled={submitting}
                >
                  {Object.entries(EXPENSE_CATEGORIES).map(([val, label]) => (
                    <option key={val} value={val}>{label}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label style={{ fontSize: 13, fontWeight: 500 }}>Amount (AED) *</label>
                <input
                  className="form-control"
                  type="number"
                  min="0.01"
                  step="0.01"
                  placeholder="e.g. 150.00"
                  value={form.amount}
                  onChange={e => handleField('amount', e.target.value)}
                  disabled={submitting}
                />
              </div>

              <div className="form-group">
                <label style={{ fontSize: 13, fontWeight: 500 }}>Expense Date *</label>
                <input
                  className="form-control"
                  type="date"
                  value={form.expenseDate}
                  max={new Date().toISOString().split('T')[0]}
                  onChange={e => handleField('expenseDate', e.target.value)}
                  disabled={submitting}
                />
              </div>

              <div className="form-group">
                <label style={{ fontSize: 13, fontWeight: 500 }}>Receipt URL (optional)</label>
                <input
                  className="form-control"
                  type="url"
                  placeholder="https://drive.google.com/…"
                  value={form.receiptUrl}
                  onChange={e => handleField('receiptUrl', e.target.value)}
                  disabled={submitting}
                />
                <span className="hint">Link to a scanned receipt (Google Drive, Dropbox, etc.)</span>
              </div>
            </div>

            <div className="form-group" style={{ marginTop: 4 }}>
              <label style={{ fontSize: 13, fontWeight: 500 }}>Description *</label>
              <textarea
                className="form-control"
                rows={2}
                placeholder="Brief description of the expense (e.g. Taxi from airport to client site)"
                value={form.description}
                onChange={e => handleField('description', e.target.value)}
                disabled={submitting}
                style={{ resize: 'vertical' }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleSubmit}
                disabled={submitting || !form.amount || !form.description.trim()}
              >
                {submitting ? 'Submitting…' : 'Submit Claim'}
              </button>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => { setShowForm(false); setFormError(''); }}
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* ── Pending claims ── */}
        {pending.length > 0 && (
          <ClaimSection
            title="Pending Review"
            titleColor="var(--warning)"
            icon={<Clock size={14} />}
            claims={pending}
          />
        )}

        {/* ── Approved claims ── */}
        {approved.length > 0 && (
          <ClaimSection
            title="Approved — Awaiting Payroll"
            titleColor="var(--primary)"
            icon={<CheckCircle size={14} />}
            claims={approved}
          />
        )}

        {/* ── Paid claims ── */}
        {paid.length > 0 && (
          <ClaimSection
            title="Paid"
            titleColor="var(--success)"
            icon={<CheckCircle size={14} />}
            claims={paid}
          />
        )}

        {/* ── Rejected claims ── */}
        {rejected.length > 0 && (
          <ClaimSection
            title="Rejected"
            titleColor="var(--danger)"
            icon={<X size={14} />}
            claims={rejected}
            showReason
          />
        )}

        {/* ── Empty state ── */}
        {claims.length === 0 && !showForm && (
          <div className="emp-card" style={{ textAlign: 'center', padding: 48 }}>
            <Receipt size={36} style={{ color: 'var(--gray-300)', marginBottom: 12 }} />
            <p style={{ color: 'var(--gray-500)', marginBottom: 16 }}>No expense claims yet.</p>
            <button className="btn btn-primary btn-sm" onClick={() => setShowForm(true)}>
              <Plus size={14} /> Submit Your First Claim
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── ClaimSection sub-component ────────────────────────────────────────────────
function ClaimSection({ title, titleColor, icon, claims, showReason = false }) {
  return (
    <div className="emp-card mb-4">
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: titleColor, display: 'flex', alignItems: 'center', gap: 6 }}>
        {icon} {title}
      </h3>
      {claims.map(c => (
        <div key={c.id} style={{
          padding: '10px 0',
          borderBottom: '1px solid var(--gray-100)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>
                {EXPENSE_CATEGORIES[c.category] || c.category}
                <span style={{ fontWeight: 400, color: 'var(--gray-500)', marginLeft: 8, fontSize: 12 }}>
                  {formatDateUAE(c.expenseDate)}
                </span>
              </div>
              {c.description && (
                <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                  {c.description}
                </div>
              )}
              {showReason && c.rejectionReason && (
                <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 4 }}>
                  Reason: {c.rejectionReason}
                </div>
              )}
              {c.receiptUrl && (
                <a
                  href={c.receiptUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 11, color: 'var(--primary)', marginTop: 2, display: 'inline-block' }}
                >
                  View Receipt ↗
                </a>
              )}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                AED {c.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
              </div>
              <span className={`badge ${STATUS_BADGE[c.status] || 'badge-yellow'}`} style={{ fontSize: 10 }}>
                {STATUS_LABEL[c.status] || c.status}
              </span>
            </div>
          </div>
        </div>
      ))}
      <div style={{ textAlign: 'right', fontSize: 12, fontWeight: 600, color: titleColor, marginTop: 8 }}>
        Total: AED {claims.reduce((s, c) => s + c.amount, 0).toLocaleString('en-AE', { minimumFractionDigits: 2 })}
      </div>
    </div>
  );
}
