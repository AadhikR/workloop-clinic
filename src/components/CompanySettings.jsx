import { useState, useEffect } from 'react';
import { Building2, Info, CheckCircle, Save, AlertCircle, Loader } from 'lucide-react';
import { getCompany, saveCompany } from '../utils/storage';

const DEFAULT_COMPANY = {
  name: '',
  molEmployerId: '',
  defaultBankRoutingCode: '',
  address: '',
  contactEmail: '',
};

export default function CompanySettings() {
  const [company, setCompany] = useState(DEFAULT_COMPANY);
  const [saved, setSaved]     = useState(false);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCompany().then(stored => {
      if (stored) setCompany(stored);
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
      // Store returned id so future saves use UPDATE
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
            These are your company-level constants used in every SIF file. The <strong>MOL Employer ID</strong> and <strong>Default Bank Routing Code</strong> are required.
          </div>
        </div>

        <div className="card">
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

        <div className="card mt-4">
          <div className="card-header">
            <h3>SIF File Format Reference</h3>
          </div>
          <div className="card-body">
            <p className="text-sm text-muted mb-4">The generated SIF file follows the UAE WPS (Wage Protection System) format:</p>
            <div className="sif-preview">
              <span className="sif-line-edr">EDR,&lt;MOL_Employee_ID&gt;,&lt;Bank_Routing&gt;,&lt;IBAN&gt;,&lt;Start_Date&gt;,&lt;End_Date&gt;,&lt;Days&gt;,&lt;Basic_Fils&gt;,&lt;Variable_Fils&gt;,&lt;Leave_Days&gt;</span>{'\n'}
              <span className="sif-line-scr">SCR,&lt;MOL_Employer_ID&gt;,&lt;Bank_Routing&gt;,&lt;Payment_Date&gt;,&lt;Seq&gt;,&lt;MMYYYY&gt;,&lt;Emp_Count&gt;,&lt;Total_Fils&gt;,AED,&lt;Description&gt;</span>
            </div>
            <p className="text-sm text-muted mt-3">Amounts are in <strong>fils</strong> (1 AED = 100 fils). Dates are in <strong>YYYY-MM-DD</strong> format.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
