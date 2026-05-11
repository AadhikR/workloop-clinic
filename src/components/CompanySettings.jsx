import { useState, useEffect } from 'react';
import { Building2, Info, CheckCircle, Save, AlertCircle, Loader, MapPin, Calendar } from 'lucide-react';
import { getCompany, saveCompany } from '../utils/storage';

const FREE_ZONES = [
  'DIFC', 'ADGM', 'JAFZA', 'DMCC', 'DAFZA', 'TECOM', 'Dubai Internet City',
  'Dubai Media City', 'Dubai Healthcare City', 'Meydan Free Zone', 'RAKEZ',
  'SAIF Zone', 'KIZAD', 'Abu Dhabi Free Zone', 'Hamriyah Free Zone', 'Other',
];

const DEFAULT_COMPANY = {
  name: '',
  molEmployerId: '',
  defaultBankRoutingCode: '',
  address: '',
  contactEmail: '',
  defaultSalaryDay: 25,
  workLocationType: 'Mainland',
  freeZoneName: '',
  logoUrl: '',
};

export default function CompanySettings() {
  const [company, setCompany] = useState(DEFAULT_COMPANY);
  const [saved, setSaved]     = useState(false);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCompany().then(stored => {
      if (stored) setCompany({ ...DEFAULT_COMPANY, ...stored });
      setLoading(false);
    }).catch(err => {
      console.error('getCompany:', err);
      setLoading(false);
    });
  }, []);

  const handleChange = (field, value) => {
    setCompany(prev => ({ ...prev, [field]: value }));
    setSaved(false);
    setError('');
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const result = await saveCompany(company);
      if (result?.id && !company.id) {
        setCompany(prev => ({ ...prev, id: result.id }));
      }
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
                  onChange={e => handleChange('defaultSalaryDay', parseInt(e.target.value) || 25)}
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
