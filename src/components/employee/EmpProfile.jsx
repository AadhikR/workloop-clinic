import { useEffect, useState } from 'react';
import { User, AlertCircle, CheckCircle, LogOut, Edit2 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getMyEmployeeRecord } from '../../utils/profileStorage';
import { supabase } from '../../lib/supabase';

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-AE', { day: 'numeric', month: 'long', year: 'numeric' });
}

function daysUntil(iso) {
  if (!iso) return null;
  return Math.ceil((new Date(iso) - new Date()) / 86400000);
}

function expiryBadge(days) {
  if (days == null) return null;
  if (days < 0)  return { cls: 'badge-red',    label: 'Expired' };
  if (days < 30) return { cls: 'badge-red',    label: `${days}d` };
  if (days < 60) return { cls: 'badge-amber',  label: `${days}d` };
  return             { cls: 'badge-green',   label: fmtDate };
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', padding: '10px 0', borderBottom: '1px solid rgba(100,116,139,0.10)' }}>
      <div style={{ width: '45%', fontSize: 12, color: 'var(--gray-500)', fontWeight: 500, paddingRight: 8 }}>{label}</div>
      <div style={{ flex: 1, fontSize: 13, color: 'var(--gray-800)', fontWeight: 500 }}>{value || '—'}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="emp-card" style={{ marginBottom: 12 }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(100,116,139,0.10)', fontWeight: 700, fontSize: 13, color: 'var(--gray-700)' }}>
        {title}
      </div>
      <div style={{ padding: '0 16px 4px' }}>
        {children}
      </div>
    </div>
  );
}

export default function EmpProfile({ onSignOut, signingOut }) {
  const { user } = useAuth();
  const [emp, setEmp]           = useState(null);
  const [loading, setLoading]   = useState(true);
  const [editing, setEditing]   = useState(false);
  const [toast, setToast]       = useState(null);

  // Editable contact fields only
  const [phone, setPhone]             = useState('');
  const [personalEmail, setPersonalEmail] = useState('');
  const [emergencyName, setEmergencyName]   = useState('');
  const [emergencyPhone, setEmergencyPhone] = useState('');
  const [saving, setSaving]           = useState(false);

  function showToast(type, msg) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3500);
  }

  useEffect(() => {
    getMyEmployeeRecord().then(rec => {
      if (rec) {
        setEmp(rec);
        setPhone(rec.phone ?? '');
        setPersonalEmail(rec.personal_email ?? '');
        setEmergencyName(rec.emergency_contact_name ?? '');
        setEmergencyPhone(rec.emergency_contact_phone ?? '');
      }
      setLoading(false);
    });
  }, []);

  async function handleSave(e) {
    e.preventDefault();
    if (!emp) return;
    setSaving(true);

    const { error } = await supabase.rpc('employee_update_contact', {
      p_phone: phone,
      p_personal_email: personalEmail,
      p_emergency_contact_name: emergencyName,
      p_emergency_contact_phone: emergencyPhone,
    });

    setSaving(false);
    if (error) {
      showToast('error', 'Could not save. Please try again.');
      return;
    }
    setEmp(prev => ({ ...prev, phone, personal_email: personalEmail, emergency_contact_name: emergencyName, emergency_contact_phone: emergencyPhone }));
    setEditing(false);
    showToast('success', 'Contact details updated.');
  }

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>;
  if (!emp)    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Profile not found. Contact HR.</div>;

  const docs = [
    { label: 'Visa',        expiry: emp.visa_expiry },
    { label: 'Passport',    expiry: emp.passport_expiry },
    { label: 'Emirates ID', expiry: emp.emirates_id_expiry },
    { label: 'Labour Card', expiry: emp.labour_card_expiry },
  ].filter(d => d.expiry);

  return (
    <div>
      <div className="emp-page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2>My Profile</h2>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setEditing(v => !v)}
            style={{ color: 'var(--primary)' }}
          >
            <Edit2 size={13} /> {editing ? 'Cancel' : 'Edit'}
          </button>
        </div>
      </div>

      <div className="emp-page-body">

        {toast && (
          <div className={`alert ${toast.type === 'success' ? 'alert-success' : 'alert-danger'}`}
               style={{ marginBottom: 16, borderRadius: 10 }}>
            {toast.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
            {toast.msg}
          </div>
        )}

        {/* Avatar + name */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            background: 'linear-gradient(135deg, rgba(37,99,235,0.14), rgba(6,182,212,0.14))',
            border: '1px solid rgba(37,99,235,0.18)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <User size={26} color="#2563EB" />
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--gray-900)' }}>{emp.name}</div>
            <div style={{ fontSize: 13, color: 'var(--gray-500)' }}>{emp.job_title || 'Employee'}{emp.department ? ` · ${emp.department}` : ''}</div>
          </div>
        </div>

        {/* Edit form (contact fields only) */}
        {editing && (
          <div className="emp-card" style={{ padding: 16, marginBottom: 16 }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>Edit Contact Details</div>
            <form onSubmit={handleSave}>
              <div className="form-grid" style={{ gap: 10 }}>
                <div className="form-group">
                  <label>Phone</label>
                  <input className="form-control" type="tel" value={phone} onChange={e => setPhone(e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Personal Email</label>
                  <input className="form-control" type="email" value={personalEmail} onChange={e => setPersonalEmail(e.target.value)} />
                </div>
                <div style={{ height: 1, background: 'rgba(100,116,139,0.10)', margin: '4px 0' }} />
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--gray-500)' }}>Emergency Contact</div>
                <div className="form-group">
                  <label>Name</label>
                  <input className="form-control" value={emergencyName} onChange={e => setEmergencyName(e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Phone</label>
                  <input className="form-control" type="tel" value={emergencyPhone} onChange={e => setEmergencyPhone(e.target.value)} />
                </div>
                <button type="submit" className="btn btn-primary btn-sm" style={{ justifyContent: 'center' }} disabled={saving}>
                  {saving ? 'Saving…' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        )}

        <Section title="Employment">
          <Row label="Employee No."   value={emp.emp_no} />
          <Row label="MOL ID"         value={emp.mol_id} />
          <Row label="Start Date"     value={fmtDate(emp.employment_start_date)} />
          <Row label="Contract"       value={emp.contract_type} />
          <Row label="Status"         value={emp.employment_status} />
          <Row label="Department"     value={emp.department} />
        </Section>

        <Section title="Salary">
          <Row label="Basic Salary"   value={emp.basic_salary ? `AED ${parseFloat(emp.basic_salary).toLocaleString('en-AE')}` : null} />
          <Row label="IBAN"           value={emp.iban} />
          <Row label="Bank"           value={emp.bank_name} />
        </Section>

        <Section title="Contact">
          <Row label="Work Email"     value={emp.work_email} />
          <Row label="Personal Email" value={emp.personal_email} />
          <Row label="Phone"          value={emp.phone} />
        </Section>

        {emp.emergency_contact_name && (
          <Section title="Emergency Contact">
            <Row label="Name"         value={emp.emergency_contact_name} />
            <Row label="Relationship" value={emp.emergency_contact_relationship} />
            <Row label="Phone"        value={emp.emergency_contact_phone} />
          </Section>
        )}

        <Section title="UAE Documents">
          <Row label="Nationality"    value={emp.nationality} />
          <Row label="Visa Type"      value={emp.visa_type} />
          <Row label="Visa Number"    value={emp.visa_number} />
          <Row label="Visa Expiry"    value={fmtDate(emp.visa_expiry)} />
          <Row label="Passport No."   value={emp.passport_number} />
          <Row label="Passport Expiry" value={fmtDate(emp.passport_expiry)} />
          <Row label="Emirates ID"    value={emp.emirates_id} />
          <Row label="Emirates ID Expiry" value={fmtDate(emp.emirates_id_expiry)} />
          <Row label="Labour Card"    value={emp.labour_card_number} />
          <Row label="Labour Card Expiry" value={fmtDate(emp.labour_card_expiry)} />
          {emp.sponsoring_entity && <Row label="Sponsor"     value={emp.sponsoring_entity} />}
        </Section>

        {/* Document expiry warnings */}
        {docs.some(d => (daysUntil(d.expiry) ?? 999) < 60) && (
          <div className="alert alert-warning" style={{ borderRadius: 12, marginBottom: 16 }}>
            <AlertCircle size={14} style={{ flexShrink: 0 }} />
            <div>
              <strong>Documents expiring soon — contact HR:</strong>
              <ul style={{ margin: '6px 0 0', paddingLeft: 16, fontSize: 13 }}>
                {docs.filter(d => (daysUntil(d.expiry) ?? 999) < 60).map(d => (
                  <li key={d.label}>{d.label} — {fmtDate(d.expiry)} ({daysUntil(d.expiry)}d)</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Signed in as */}
        <div className="emp-card" style={{ padding: '12px 16px', marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--gray-500)' }}>Signed in as</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-800)', marginTop: 2 }}>{user?.email}</div>
        </div>

        {/* Sign out */}
        <button
          className="btn btn-outline"
          style={{ width: '100%', justifyContent: 'center', color: 'var(--danger)', borderColor: 'var(--danger)' }}
          onClick={onSignOut}
          disabled={signingOut}
        >
          <LogOut size={14} />
          {signingOut ? 'Signing out…' : 'Sign Out'}
        </button>
      </div>
    </div>
  );
}
