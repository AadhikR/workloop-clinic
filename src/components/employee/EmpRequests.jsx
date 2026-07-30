import { useEffect, useState } from 'react';
import { Mail, Clock, CheckCircle, XCircle, Send, Download } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { getMyLetterRequests } from '../../utils/letterStorage';
import { LETTER_TYPES, printLetter } from '../../utils/letterTemplates';
import { formatDateUAE } from '../../utils/uaeValidators';
import { getMyEmployeeRecord, getMyCompany } from '../../utils/profileStorage';

const STATUS_BADGE = {
  pending:   { cls: 'badge-amber', label: 'Pending Review', Icon: Clock },
  completed: { cls: 'badge-green', label: 'Ready',          Icon: CheckCircle },
  rejected:  { cls: 'badge-red',   label: 'Rejected',       Icon: XCircle },
};

export default function EmpRequests() {
  const [requests,    setRequests]    = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [form,        setForm]        = useState({ type: LETTER_TYPES[0], purpose: '' });
  const [submitting,  setSubmitting]  = useState(false);
  const [toast,       setToast]       = useState(null);
  const [emp,         setEmp]         = useState(null);
  const [company,     setCompany]     = useState(null);

  const load = () => getMyLetterRequests().then(r => { setRequests(r); setLoading(false); });

  useEffect(() => {
    load();
    Promise.all([getMyEmployeeRecord(), getMyCompany()]).then(([e, c]) => {
      setEmp(e);
      setCompany(c);
    });
  }, []);

  const showToast = (type, msg) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  // External-facing letters carry addressee info that HR needs to draft them.
  // For those types we require a non-empty purpose. Internal letters remain optional.
  const EXTERNAL_LETTER_TYPES = new Set([
    'Salary Certificate — Bank',
    'Salary Certificate — Embassy',
    'NOC (No Objection Certificate)',
    'Salary Transfer Letter',
  ]);

  const handleSubmit = async e => {
    e.preventDefault();
    if (EXTERNAL_LETTER_TYPES.has(form.type)) {
      const purpose = (form.purpose || '').trim();
      if (purpose.length < 5) {
        showToast('error', 'Please enter the addressee or purpose (at least 5 characters) for this letter type.');
        return;
      }
    }
    setSubmitting(true);
    try {
      const { error } = await supabase.rpc('employee_request_letter', {
        p_letter_type: form.type,
        p_purpose:     form.purpose,
      });
      if (error) throw error;
      setForm({ type: LETTER_TYPES[0], purpose: '' });
      await load();
      showToast('success', 'Request submitted. HR will prepare your letter shortly.');
    } catch (err) {
      showToast('error', err.message || 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="emp-page-body">
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>
      </div>
    );
  }

  return (
    <div className="emp-page-body">
      {toast && (
        <div className={`alert alert-${toast.type === 'success' ? 'success' : 'danger'}`} style={{ marginBottom: 16 }}>
          {toast.msg}
        </div>
      )}

      {/* Request form */}
      <div className="emp-card" style={{ marginBottom: 20 }}>
        <div className="emp-card-header">
          <h3>Request a Letter</h3>
          <p style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
            HR will generate and send your letter within 1–2 working days.
          </p>
        </div>
        <div className="emp-card-body">
          <form onSubmit={handleSubmit}>
            <div className="form-grid form-grid-2" style={{ gap: 14 }}>
              <div className="form-group">
                <label>Letter Type</label>
                <select
                  className="form-control"
                  value={form.type}
                  onChange={e => setForm(p => ({ ...p, type: e.target.value }))}
                >
                  {LETTER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>
                  Purpose / Addressed To
                  <span style={{ color: 'var(--gray-400)', fontWeight: 400, marginLeft: 4 }}>(optional)</span>
                </label>
                <input
                  className="form-control"
                  placeholder="e.g. Abu Dhabi Islamic Bank, UAE Visa Application…"
                  value={form.purpose}
                  onChange={e => setForm(p => ({ ...p, purpose: e.target.value }))}
                />
              </div>
            </div>
            <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
              <button type="submit" className="btn btn-primary" disabled={submitting} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Send size={14} />
                {submitting ? 'Submitting…' : 'Submit Request'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Request history */}
      <div className="emp-card">
        <div className="emp-card-header">
          <h3>My Requests {!loading && `(${requests.length})`}</h3>
        </div>
        {requests.length === 0 ? (
          <div style={{ padding: '28px 20px', textAlign: 'center', color: 'var(--gray-500)', fontSize: 13 }}>
            <Mail size={32} style={{ margin: '0 auto 10px', display: 'block', opacity: 0.3 }} />
            No requests yet. Use the form above to request a letter.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Letter Type</th>
                  <th>Purpose</th>
                  <th>Requested</th>
                  <th>Status</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {requests.map(req => {
                  const { cls, label, Icon } = STATUS_BADGE[req.status] || STATUS_BADGE.pending;
                  return (
                    <tr key={req.id}>
                      <td style={{ fontSize: 13, fontWeight: 500 }}>{req.letterType}</td>
                      <td style={{ fontSize: 12, color: 'var(--gray-500)' }}>{req.purpose || <span style={{ color: 'var(--gray-300)' }}>—</span>}</td>
                      <td style={{ fontSize: 12, color: 'var(--gray-500)', whiteSpace: 'nowrap' }}>{formatDateUAE(req.requestedAt)}</td>
                      <td>
                        <span className={`badge ${cls}`} style={{ fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <Icon size={10} />{label}
                        </span>
                        {req.status === 'completed' && (
                          <div style={{ marginTop: 4 }}>
                            {emp && company && (
                              <button
                                className="btn btn-ghost btn-sm"
                                style={{ fontSize: 11, padding: '3px 8px', color: 'var(--primary)', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                onClick={() => printLetter({
                                  letterType:   req.letterType,
                                  purpose:      req.purpose,
                                  employeeName: emp.name,
                                  jobTitle:     emp.job_title,
                                  department:   emp.department,
                                  basicSalary:  parseFloat(emp.basic_salary) || 0,
                                  allowance:    parseFloat(emp.housing_allowance || 0) + parseFloat(emp.transport_allowance || 0) + parseFloat(emp.other_allowance || 0),
                                  passportNumber: emp.passport_number,
                                  nationality: emp.nationality,
                                  employmentStartDate: emp.employment_start_date,
                                }, company)}
                              >
                                <Download size={11} /> View Letter
                              </button>
                            )}
                            {req.completedAt && (
                              <span style={{ fontSize: 10, color: 'var(--gray-400)', marginLeft: 4 }}>
                                Ready {formatDateUAE(req.completedAt)}
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td style={{ fontSize: 12, color: 'var(--danger)' }}>
                        {req.status === 'rejected' && req.rejectionReason
                          ? req.rejectionReason
                          : <span style={{ color: 'var(--gray-300)' }}>—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
