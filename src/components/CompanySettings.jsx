import { useState, useEffect, useRef } from 'react';
import { Building2, Info, CheckCircle } from 'lucide-react';
import { getCompany, saveCompany } from '../utils/storage';

const DEFAULT_COMPANY = {
  name: '',
  molEmployerId: '',
  defaultBankRoutingCode: '',
  address: '',
  contactEmail: '',
};

export default function CompanySettings() {
  const [company, setCompany]     = useState(DEFAULT_COMPANY);
  const [autoSaved, setAutoSaved] = useState(false);
  const [saving, setSaving]       = useState(false);
  const autoSaveTimer             = useRef(null);
  const companyRef                = useRef(DEFAULT_COMPANY);

  useEffect(() => {
    getCompany().then(stored => {
      if (stored) {
        setCompany(stored);
        companyRef.current = stored;
      }
    });
  }, []);

  const handleChange = (field, value) => {
    setCompany(prev => {
      const next = { ...prev, [field]: value };
      companyRef.current = next;

      // Auto-save with debounce
      if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
      autoSaveTimer.current = setTimeout(async () => {
        setSaving(true);
        try {
          await saveCompany(companyRef.current);
          setAutoSaved(true);
          setTimeout(() => setAutoSaved(false), 2000);
        } catch (err) {
          console.error('Failed to save company:', err);
        } finally {
          setSaving(false);
        }
      }, 600);

      return next;
    });
  };

  return (
    <div>
      <div className="page-header">
        <h2>Company / Employer Settings</h2>
        <div className="page-header-actions">
          {saving && (
            <span className="auto-save-indicator" style={{ color: 'var(--gray-400)' }}>
              Saving…
            </span>
          )}
          {autoSaved && !saving && (
            <span className="auto-save-indicator">
              <CheckCircle size={14} /> Auto-saved
            </span>
          )}
        </div>
      </div>

      <div className="page-body">

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
                  placeholder="e.g. Aadhik Trading LLC"
                />
              </div>
              <div className="form-group">
                <label>MOL Employer ID *</label>
                <input
                  className="form-control font-mono"
                  value={company.molEmployerId}
                  onChange={e => handleChange('molEmployerId', e.target.value.trim())}
                  placeholder="e.g. 0000000816726"
                />
                <span className="hint">13-digit Ministry of Labour employer number</span>
              </div>
              <div className="form-group">
                <label>Default Bank / Routing Code</label>
                <input
                  className="form-control font-mono"
                  value={company.defaultBankRoutingCode}
                  onChange={e => handleChange('defaultBankRoutingCode', e.target.value.trim())}
                  placeholder="e.g. 302620122"
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
