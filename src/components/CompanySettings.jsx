import { useState, useEffect } from 'react';
import { Building2, Info, CheckCircle, Save, AlertCircle, Loader, MapPin, Calendar, ShieldCheck, Heart, Plus, Trash2, Edit2 } from 'lucide-react';
import { getCompany, saveCompany, getInsurancePolicies, saveInsurancePolicy, deleteInsurancePolicy } from '../utils/storage';
import { useCompany } from '../context/CompanyContext';
import { formatDateUAE, validateEmail, validateBankRoutingCode, clampNumber } from '../utils/uaeValidators';

// UAE sectors with their approximate 2024 Emiratization quota targets (Cabinet Res. 27/2023)
const SECTORS = [
  { name: 'Banking & Financial Services',  defaultQuota: 8  },
  { name: 'Insurance',                     defaultQuota: 5  },
  { name: 'Telecommunications',            defaultQuota: 8  },
  { name: 'Healthcare & Pharmaceuticals',  defaultQuota: 5  },
  { name: 'Retail & Trade',               defaultQuota: 4  },
  { name: 'Information Technology',        defaultQuota: 4  },
  { name: 'Real Estate',                   defaultQuota: 4  },
  { name: 'Education',                     defaultQuota: 5  },
  { name: 'Manufacturing & Industry',      defaultQuota: 2  },
  { name: 'Construction',                  defaultQuota: 2  },
  { name: 'Hospitality & Tourism',         defaultQuota: 2  },
  { name: 'Transportation & Logistics',    defaultQuota: 2  },
  { name: 'Oil, Gas & Energy',            defaultQuota: 2  },
  { name: 'Media & Marketing',             defaultQuota: 2  },
  { name: 'Legal & Consultancy',           defaultQuota: 2  },
  { name: 'Other',                         defaultQuota: 2  },
];

const FREE_ZONES = [
  'DIFC', 'ADGM', 'JAFZA', 'DMCC', 'DAFZA', 'TECOM', 'Dubai Internet City',
  'Dubai Media City', 'Dubai Healthcare City', 'Meydan Free Zone', 'RAKEZ',
  'SAIF Zone', 'KIZAD', 'Abu Dhabi Free Zone', 'Hamriyah Free Zone', 'Other',
];

const DEFAULT_COMPANY = {
  name: '',
  branchName: '',
  molEmployerId: '',
  defaultBankRoutingCode: '',
  address: '',
  contactEmail: '',
  defaultSalaryDay: 25,
  workLocationType: 'Mainland',
  freeZoneName: '',
  logoUrl: '',
  sector: '',
  nafisQuotaPercent: 2,
  // Feature toggles (migration 049) — default true so existing installs behave
  // exactly as before. Admin can disable per company/branch.
  enableNafis: true,
  enableStaffingRules: true,
  enableBiometricImport: true,
};

const EMPTY_POLICY = { insurerName:'', policyNumber:'', tierName:'', annualPremium:'', renewalDate:'', brokerName:'', brokerContact:'', notes:'' };

function policyRenewalStatus(renewalDate) {
  if (!renewalDate) return { label: 'No Date', cls: 'badge-gray' };
  const days = Math.ceil((new Date(renewalDate) - new Date()) / (1000 * 60 * 60 * 24));
  if (days < 0)    return { label: `Expired ${Math.abs(days)}d ago`, cls: 'badge-red' };
  if (days <= 30)  return { label: `${days}d to renewal`, cls: 'badge-red' };
  if (days <= 60)  return { label: `${days}d to renewal`, cls: 'badge-amber' };
  return { label: `${days}d to renewal`, cls: 'badge-green' };
}

export default function CompanySettings() {
  const { activeCompanyId, refreshCompanies } = useCompany();
  const [company, setCompany] = useState(DEFAULT_COMPANY);
  const [saved, setSaved]     = useState(false);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(true);

  // ── Insurance Policies state ──
  const [policies, setPolicies]       = useState([]);
  const [showPolicyForm, setShowPolicyForm] = useState(false);
  const [editingPolicy, setEditingPolicy]   = useState(null); // policy object being edited
  const [policyForm, setPolicyForm]     = useState(EMPTY_POLICY);
  const [policySaving, setPolicySaving] = useState(false);
  const [policyError, setPolicyError]   = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([getCompany(activeCompanyId), getInsurancePolicies()]).then(([stored, pols]) => {
      if (stored) setCompany({ ...DEFAULT_COMPANY, ...stored });
      else setCompany(DEFAULT_COMPANY); // fresh branch — start blank
      setPolicies(pols);
      setLoading(false);
    }).catch(err => {
      console.error('CompanySettings load:', err);
      setLoading(false);
    });
  }, [activeCompanyId]); // Re-load when the active branch changes

  const openAddPolicy = () => {
    setEditingPolicy(null);
    setPolicyForm(EMPTY_POLICY);
    setPolicyError('');
    setShowPolicyForm(true);
  };

  const openEditPolicy = (policy) => {
    setEditingPolicy(policy);
    setPolicyForm({
      insurerName:   policy.insurerName,
      policyNumber:  policy.policyNumber,
      tierName:      policy.tierName,
      annualPremium: policy.annualPremium || '',
      renewalDate:   policy.renewalDate || '',
      brokerName:    policy.brokerName,
      brokerContact: policy.brokerContact,
      notes:         policy.notes,
    });
    setPolicyError('');
    setShowPolicyForm(true);
  };

  const handleSavePolicy = async () => {
    if (!policyForm.insurerName.trim()) { setPolicyError('Insurer name is required.'); return; }
    // Duplicate policy number check within this company. Empty policy numbers
    // are allowed to repeat (many small policies leave the field blank).
    const pn = (policyForm.policyNumber || '').trim();
    if (pn) {
      const dup = policies.find(p => (p.policyNumber || '').trim() === pn && p.id !== editingPolicy?.id);
      if (dup) { setPolicyError(`Policy number already used by "${dup.insurerName}".`); return; }
    }
    setPolicySaving(true);
    setPolicyError('');
    try {
      const saved = await saveInsurancePolicy({ ...policyForm, ...(editingPolicy ? { id: editingPolicy.id } : {}) });
      setPolicies(prev => editingPolicy
        ? prev.map(p => p.id === editingPolicy.id ? saved : p)
        : [...prev, saved]
      );
      setShowPolicyForm(false);
      setEditingPolicy(null);
    } catch (err) {
      setPolicyError(err.message || 'Save failed. Please try again.');
    } finally {
      setPolicySaving(false);
    }
  };

  const handleDeletePolicy = async (policy) => {
    if (!window.confirm(`Delete "${policy.insurerName}" policy? Employee assignments will be cleared.`)) return;
    try {
      await deleteInsurancePolicy(policy.id);
      setPolicies(prev => prev.filter(p => p.id !== policy.id));
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  const handleChange = (field, value) => {
    setCompany(prev => ({ ...prev, [field]: value }));
    setSaved(false);
    setError('');
  };

  const handleSave = async () => {
    // Format guards — only enforced when the field is non-empty so first-run
    // partial setups can still save.
    const emailCheck = validateEmail(company.contactEmail);
    if (!emailCheck.valid) { setError(emailCheck.message); return; }
    const rcCheck = validateBankRoutingCode(company.defaultBankRoutingCode);
    if (!rcCheck.valid) { setError(rcCheck.message); return; }

    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const result = await saveCompany(company);
      if (result?.id && !company.id) {
        setCompany(prev => ({ ...prev, id: result.id }));
      }
      // Refresh the branch switcher so renamed branches show the new label
      refreshCompanies().catch(() => {});
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to save company:', err);
      setError(err.message || 'Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="page-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
        <Loader size={24} style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h2>Company / Employer Settings</h2>
        <div className="page-header-actions">
          {saved && !saving && (
            <span className="auto-save-indicator">
              <CheckCircle size={14} /> Saved
            </span>
          )}
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            {saving ? <Loader size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={15} />}
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
        </div>
      </div>

      <div className="page-body">

        {error && (
          <div className="alert alert-danger mb-4">
            <AlertCircle size={16} />
            <div><strong>Save failed:</strong> {error}</div>
          </div>
        )}

        <div className="alert alert-info mb-4">
          <Info size={16} />
          <div>
            These are your company-level constants used in every WPS/SIF file and payslip.
            The <strong>MOL Employer ID</strong> and <strong>Default Bank Routing Code</strong> are required for WPS generation.
          </div>
        </div>

        {/* ── Employer Information ── */}
        <div className="card mb-4">
          <div className="card-header">
            <h3><Building2 size={16} style={{display:'inline',marginRight:6}} />Employer Information</h3>
          </div>
          <div className="card-body">
            <div className="form-grid form-grid-2">
              <div className="form-group">
                <label>Company Name *</label>
                <input
                  className="form-control"
                  value={company.name}
                  onChange={e => handleChange('name', e.target.value)}
                  placeholder="e.g. Example Trading LLC"
                />
              </div>
              <div className="form-group">
                <label>Branch / Entity Label</label>
                <input
                  className="form-control"
                  value={company.branchName}
                  onChange={e => handleChange('branchName', e.target.value)}
                  placeholder="e.g. Dubai HQ, Abu Dhabi Branch"
                />
                <span className="hint">Short label shown in the branch switcher. Leave blank to use the company name.</span>
              </div>
              <div className="form-group">
                <label>MOL Employer ID *</label>
                <input
                  className="form-control font-mono"
                  value={company.molEmployerId}
                  onChange={e => handleChange('molEmployerId', e.target.value.trim())}
                  placeholder="e.g. 0000000123456"
                />
                <span className="hint">13-digit Ministry of Labour employer number</span>
              </div>
              <div className="form-group">
                <label>Default Bank / Routing Code</label>
                <input
                  className="form-control font-mono"
                  value={company.defaultBankRoutingCode}
                  onChange={e => handleChange('defaultBankRoutingCode', e.target.value.trim())}
                  placeholder="e.g. 300000001"
                />
                <span className="hint">Used in the SCR line if not overridden per payroll run</span>
              </div>
              <div className="form-group">
                <label>Contact Email</label>
                <input
                  className="form-control"
                  type="email"
                  value={company.contactEmail}
                  onChange={e => handleChange('contactEmail', e.target.value)}
                  placeholder="payroll@company.com"
                />
              </div>
              <div className="form-group" style={{gridColumn:'1/-1'}}>
                <label>Address</label>
                <input
                  className="form-control"
                  value={company.address}
                  onChange={e => handleChange('address', e.target.value)}
                  placeholder="Dubai, UAE"
                />
              </div>
            </div>
          </div>
        </div>

        {/* ── Payroll Settings ── */}
        <div className="card mb-4">
          <div className="card-header">
            <h3><Calendar size={16} style={{display:'inline',marginRight:6}} />Payroll Settings</h3>
          </div>
          <div className="card-body">
            <div className="form-grid form-grid-2">
              <div className="form-group">
                <label>Default Salary Payment Day</label>
                <input
                  className="form-control"
                  type="number"
                  min={1}
                  max={31}
                  value={company.defaultSalaryDay}
                  onChange={e => handleChange('defaultSalaryDay', clampNumber(parseInt(e.target.value) || 25, 1, 31))}
                  placeholder="25"
                />
                <span className="hint">
                  Day of month salary is typically paid (used for WPS 30-day deadline tracking).
                  UAE Labour Law Article 56 requires payment within 30 days.
                </span>
              </div>
              <div className="form-group">
                <label>Company Logo (for Payslips)</label>
                <input
                  className="form-control"
                  value={company.logoUrl}
                  onChange={e => handleChange('logoUrl', e.target.value)}
                  placeholder="https://... or leave blank"
                />
                <span className="hint">URL to your company logo — displayed on PDF payslips</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Work Location ── */}
        <div className="card mb-4">
          <div className="card-header">
            <h3><MapPin size={16} style={{display:'inline',marginRight:6}} />Work Location &amp; Jurisdiction</h3>
          </div>
          <div className="card-body">
            <div className="form-grid form-grid-2">
              <div className="form-group">
                <label>Work Location Type</label>
                <select
                  className="form-control"
                  value={company.workLocationType}
                  onChange={e => handleChange('workLocationType', e.target.value)}
                >
                  <option value="Mainland">Mainland</option>
                  <option value="Free Zone">Free Zone</option>
                </select>
                <span className="hint">
                  Affects labour law applicability. Free Zone employees may be governed by their zone's authority (e.g. DIFC, ADGM).
                  Can be overridden per employee.
                </span>
              </div>
              {company.workLocationType === 'Free Zone' && (
                <div className="form-group">
                  <label>Free Zone Name</label>
                  <select
                    className="form-control"
                    value={company.freeZoneName}
                    onChange={e => handleChange('freeZoneName', e.target.value)}
                  >
                    <option value="">Select Free Zone…</option>
                    {FREE_ZONES.map(fz => (
                      <option key={fz} value={fz}>{fz}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Feature Toggles ── */}
        <div className="card mb-4">
          <div className="card-header">
            <h3>Modules &amp; Features</h3>
          </div>
          <div className="card-body">
            <div className="alert alert-info mb-4">
              <Info size={15} />
              <div style={{ fontSize: 13 }}>
                Small clinics can hide modules that aren't required at their size.
                Turning a module off hides its panels and menu entries but does not delete any data —
                turn it back on and everything reappears.
              </div>
            </div>
            <div style={{ display: 'grid', gap: 12 }}>
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--gray-200)' }}>
                <input
                  type="checkbox"
                  checked={company.enableNafis !== false}
                  onChange={e => handleChange('enableNafis', e.target.checked)}
                  style={{ marginTop: 3 }}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>Emiratization / Nafis Compliance</div>
                  <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                    Shows the Emiratization panel on the Dashboard and the sector/quota fields below.
                    Only mandatory for private-sector employers with 20+ skilled staff (2026 rules).
                  </div>
                </div>
              </label>

              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--gray-200)' }}>
                <input
                  type="checkbox"
                  checked={company.enableStaffingRules !== false}
                  onChange={e => handleChange('enableStaffingRules', e.target.checked)}
                  style={{ marginTop: 3 }}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>Roster Staffing Rules</div>
                  <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                    Enforce per-department minimum-staff rules on roster publish.
                    Useful for larger clinics with fixed shift minimums; small clinics usually leave this off.
                  </div>
                </div>
              </label>

              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--gray-200)' }}>
                <input
                  type="checkbox"
                  checked={company.enableBiometricImport !== false}
                  onChange={e => handleChange('enableBiometricImport', e.target.checked)}
                  style={{ marginTop: 3 }}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>Biometric Punch-In Import</div>
                  <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                    Enable if your clinic has a fingerprint / face-recognition device and you upload its CSV punches.
                    Turn off to hide the Biometric Import tab under Attendance.
                  </div>
                </div>
              </label>
            </div>
          </div>
        </div>

        {/* ── Emiratization / Nafis Compliance ── */}
        {company.enableNafis !== false && (
        <div className="card mb-4">
          <div className="card-header">
            <h3><ShieldCheck size={16} style={{ display:'inline', marginRight:6 }} />Emiratization / Nafis Compliance</h3>
          </div>
          <div className="card-body">
            <div className="alert alert-info mb-4" style={{ marginBottom:16 }}>
              <Info size={15} />
              <div style={{ fontSize:13 }}>
                UAE Cabinet Resolution No. 27 of 2023 mandates Emiratization quotas in the private sector.
                Set your industry sector below — the required percentage is pre-filled based on current MOHRE targets
                and can be adjusted to match your company's specific obligation.
                Non-compliance carries fines of <strong>AED 6,000 per month per unfilled Emirati slot</strong>.
              </div>
            </div>
            <div className="form-grid form-grid-2">
              <div className="form-group">
                <label>Industry Sector</label>
                <select
                  className="form-control"
                  value={company.sector}
                  onChange={e => {
                    const selected = SECTORS.find(s => s.name === e.target.value);
                    handleChange('sector', e.target.value);
                    if (selected) handleChange('nafisQuotaPercent', selected.defaultQuota);
                  }}
                >
                  <option value="">Select your sector…</option>
                  {SECTORS.map(s => (
                    <option key={s.name} value={s.name}>{s.name}</option>
                  ))}
                </select>
                <span className="hint">Used to pre-fill the Emiratization quota target for your industry</span>
              </div>
              <div className="form-group">
                <label>Required Emiratization Rate (%)</label>
                <input
                  className="form-control"
                  type="number"
                  min="0"
                  max="100"
                  step="0.5"
                  value={company.nafisQuotaPercent}
                  onChange={e => handleChange('nafisQuotaPercent', clampNumber(e.target.value, 0, 100))}
                  placeholder="e.g. 4"
                />
                <span className="hint">
                  Percentage of UAE nationals required among active headcount.
                  {company.sector && (() => {
                    const s = SECTORS.find(sec => sec.name === company.sector);
                    return s ? ` Suggested for ${s.name}: ${s.defaultQuota}%` : '';
                  })()}
                </span>
              </div>
            </div>
            {company.sector && (
              <div style={{ marginTop:4, padding:'10px 14px', background:'var(--gray-50)', borderRadius:8, border:'1px solid var(--gray-200)', fontSize:13, color:'var(--gray-600)' }}>
                <strong>Current setup:</strong> {company.sector} · Target {company.nafisQuotaPercent}% UAE nationals.
                The Emiratization panel on the Dashboard will show your live compliance status.
              </div>
            )}
          </div>
        </div>
        )}

        {/* ── Medical Insurance Policies ── */}
        <div className="card mb-4">
          <div className="card-header">
            <h3><Heart size={16} style={{ display:'inline', marginRight:6, color:'var(--danger)' }} />Medical Insurance Policies</h3>
            <button className="btn btn-primary btn-sm" onClick={openAddPolicy} style={{ display:'flex', alignItems:'center', gap:5 }}>
              <Plus size={13} />Add Policy
            </button>
          </div>
          <div className="card-body">
            <div className="alert alert-info mb-4">
              <Info size={15} />
              <div style={{ fontSize:13 }}>
                Dubai Law No. 11 of 2013 and Abu Dhabi Circular No. 23/2014 mandate employer-provided health insurance for all employees.
                Add your company's insurance policies here, then assign each employee to a policy via their profile's <strong>Insurance</strong> tab.
                Renewal alerts appear on the Dashboard 60 days before expiry.
              </div>
            </div>

            {/* Add / Edit form */}
            {showPolicyForm && (
              <div style={{ background:'var(--gray-50)', borderRadius:8, padding:'14px 16px', marginBottom:16, border:'1px solid var(--gray-200)' }}>
                <div style={{ fontWeight:600, fontSize:13, marginBottom:12, color:'var(--gray-700)' }}>
                  {editingPolicy ? `Edit: ${editingPolicy.insurerName}` : 'New Insurance Policy'}
                </div>
                <div className="form-grid form-grid-2" style={{ gap:12 }}>
                  <div className="form-group">
                    <label>Insurer Name *</label>
                    <input className="form-control" value={policyForm.insurerName}
                      onChange={e => setPolicyForm(p => ({ ...p, insurerName: e.target.value }))}
                      placeholder="e.g. Daman, AXA Gulf, Oman Insurance" />
                  </div>
                  <div className="form-group">
                    <label>Policy / Certificate Number</label>
                    <input className="form-control font-mono" value={policyForm.policyNumber}
                      onChange={e => setPolicyForm(p => ({ ...p, policyNumber: e.target.value }))}
                      placeholder="Group certificate or policy number" />
                  </div>
                  <div className="form-group">
                    <label>Coverage Tier Name</label>
                    <input className="form-control" value={policyForm.tierName}
                      onChange={e => setPolicyForm(p => ({ ...p, tierName: e.target.value }))}
                      placeholder="e.g. Gold, Silver, Enhanced Basic" />
                  </div>
                  <div className="form-group">
                    <label>Annual Premium (AED)</label>
                    <input className="form-control" type="number" min="0" step="0.01" value={policyForm.annualPremium}
                      onChange={e => setPolicyForm(p => ({ ...p, annualPremium: e.target.value }))}
                      placeholder="e.g. 50000" />
                  </div>
                  <div className="form-group">
                    <label>Renewal Date</label>
                    <input type="date" className="form-control" value={policyForm.renewalDate}
                      onChange={e => setPolicyForm(p => ({ ...p, renewalDate: e.target.value }))} />
                    <span className="hint">Dashboard alert fires 60 days before this date</span>
                  </div>
                  <div className="form-group">
                    <label>Broker / Agent Name</label>
                    <input className="form-control" value={policyForm.brokerName}
                      onChange={e => setPolicyForm(p => ({ ...p, brokerName: e.target.value }))}
                      placeholder="Broker name" />
                  </div>
                  <div className="form-group">
                    <label>Broker Contact</label>
                    <input className="form-control" value={policyForm.brokerContact}
                      onChange={e => setPolicyForm(p => ({ ...p, brokerContact: e.target.value }))}
                      placeholder="Phone or email" />
                  </div>
                  <div className="form-group" style={{ gridColumn:'1/-1' }}>
                    <label>Notes</label>
                    <input className="form-control" value={policyForm.notes}
                      onChange={e => setPolicyForm(p => ({ ...p, notes: e.target.value }))}
                      placeholder="e.g. Covers inpatient, outpatient, dental — Dubai Plan E" />
                  </div>
                </div>
                {policyError && (
                  <div style={{ color:'var(--danger)', fontSize:13, marginTop:8 }}>{policyError}</div>
                )}
                <div style={{ display:'flex', gap:8, marginTop:12 }}>
                  <button className="btn btn-primary btn-sm" onClick={handleSavePolicy}
                    disabled={policySaving || !policyForm.insurerName.trim()}>
                    {policySaving ? 'Saving…' : (editingPolicy ? 'Update Policy' : 'Add Policy')}
                  </button>
                  <button className="btn btn-outline btn-sm"
                    onClick={() => { setShowPolicyForm(false); setEditingPolicy(null); setPolicyError(''); }}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Policies list */}
            {policies.length === 0 ? (
              <div style={{ textAlign:'center', color:'var(--gray-400)', fontSize:13, padding:'12px 0' }}>
                No insurance policies configured. Click <strong>Add Policy</strong> to add your company's health insurance plan.
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Insurer</th>
                      <th>Policy No.</th>
                      <th>Tier</th>
                      <th>Annual Premium</th>
                      <th>Renewal Date</th>
                      <th>Broker</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {policies.map(policy => {
                      const rs = policyRenewalStatus(policy.renewalDate);
                      return (
                        <tr key={policy.id}>
                          <td style={{ fontWeight:500 }}>{policy.insurerName}</td>
                          <td style={{ fontFamily:'monospace', fontSize:12 }}>{policy.policyNumber || '—'}</td>
                          <td>{policy.tierName || '—'}</td>
                          <td style={{ fontSize:12 }}>
                            {policy.annualPremium ? `AED ${policy.annualPremium.toLocaleString('en-AE')}` : '—'}
                          </td>
                          <td>
                            {policy.renewalDate ? (
                              <span className={`badge ${rs.cls}`} style={{ fontSize:11 }}>
                                {formatDateUAE(policy.renewalDate)} · {rs.label}
                              </span>
                            ) : '—'}
                          </td>
                          <td style={{ fontSize:12 }}>{policy.brokerName || '—'}</td>
                          <td>
                            <div style={{ display:'flex', gap:4 }}>
                              <button className="btn btn-ghost btn-icon btn-sm" title="Edit policy"
                                onClick={() => openEditPolicy(policy)}>
                                <Edit2 size={13} />
                              </button>
                              <button className="btn btn-ghost btn-icon btn-sm text-danger" title="Delete policy"
                                onClick={() => handleDeletePolicy(policy)}>
                                <Trash2 size={13} />
                              </button>
                            </div>
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

        {/* ── SIF File Format Reference ── */}
        <div className="card mt-4">
          <div className="card-header">
            <h3>WPS / SIF File Format Reference</h3>
          </div>
          <div className="card-body">
            <p className="text-sm text-muted mb-4">The generated SIF file follows the UAE WPS (Wage Protection System) format:</p>
            <div className="sif-preview">
              <span className="sif-line-edr">EDR,&lt;MOL_Employee_ID&gt;,&lt;Bank_Routing&gt;,&lt;IBAN&gt;,&lt;Start_Date&gt;,&lt;End_Date&gt;,&lt;Days&gt;,&lt;Basic_AED&gt;,&lt;Variable_AED&gt;,&lt;Leave_Days&gt;</span>{'\n'}
              <span className="sif-line-scr">SCR,&lt;MOL_Employer_ID&gt;,&lt;Bank_Routing&gt;,&lt;Payment_Date&gt;,&lt;Seq&gt;,&lt;MMYYYY&gt;,&lt;Emp_Count&gt;,&lt;Total_AED&gt;,AED,&lt;Description&gt;</span>
            </div>
            <p className="text-sm text-muted mt-3">
              Amounts are in <strong>integer AED</strong>. Dates are in <strong>YYYY-MM-DD</strong> format.
              The variable allowance field in the EDR line = Basic + Housing + Transport + Other Allowances − Deductions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
