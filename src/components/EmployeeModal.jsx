/**
 * EmployeeModal.jsx — Add/Edit Employee modal with tabbed UAE HR profile
 * Tabs: Personal | Job & Contract | Salary & Bank | UAE Compliance
 */
import { useState, useEffect } from 'react';
import { X, UserCheck, Briefcase, CreditCard, Shield, FolderOpen, Upload, AlertCircle, Trash2 } from 'lucide-react';
import { validateIBAN, validateEmiratesID, validateMolId, formatAED, formatDateUAE } from '../utils/uaeValidators';
import { calculateGratuity } from '../utils/gratuityCalculator';
import { getShifts } from '../utils/attendanceStorage';
import { getEmployeeDocuments, uploadEmployeeDocument, deleteEmployeeDocument } from '../utils/storage';

const FREE_ZONES = ['DIFC','ADGM','JAFZA','DMCC','DAFZA','TECOM','Dubai Internet City','Dubai Media City','Dubai Healthcare City','Meydan Free Zone','RAKEZ','SAIF Zone','KIZAD','Abu Dhabi Free Zone','Hamriyah Free Zone','Other'];

const DOC_TYPES = [
  'Visa', 'Passport', 'Emirates ID', 'Labour Card', 'Work Permit',
  'Medical Fitness Certificate', 'Educational Certificate',
  'Professional License', 'NOC / Reference Letter', 'Other',
];

function formatFileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function docExpiryStatus(expiryDate) {
  if (!expiryDate) return { label: 'No Expiry', cls: 'badge-gray' };
  const days = Math.ceil((new Date(expiryDate) - new Date()) / (1000 * 60 * 60 * 24));
  if (days < 0)   return { label: `Expired ${Math.abs(days)}d ago`, cls: 'badge-red' };
  if (days <= 30) return { label: `${days}d left`, cls: 'badge-red' };
  if (days <= 60) return { label: `${days}d left`, cls: 'badge-amber' };
  return { label: `Valid (${days}d)`, cls: 'badge-green' };
}
const VISA_TYPES = ['Employment Visa','Investor Visa','Dependent Visa','Tourist (Temp)','Exempt'];
const CONTRACT_TYPES = ['Unlimited','Limited'];
const EMP_STATUSES = ['Active','Probation','On Leave','Terminated'];
const GENDERS = ['Male','Female','Other'];
const MARITAL_STATUSES = ['Single','Married','Divorced','Widowed'];
const COUNTRIES = ['United Arab Emirates','Afghanistan','Albania','Algeria','Argentina','Armenia','Australia','Austria','Azerbaijan','Bahrain','Bangladesh','Belarus','Belgium','Brazil','Brunei','Bulgaria','Cambodia','Cameroon','Canada','Chad','Chile','China','Colombia','Croatia','Cuba','Cyprus','Czech Republic','Denmark','Egypt','Ethiopia','Finland','France','Georgia','Germany','Ghana','Greece','Hungary','Iceland','India','Indonesia','Iran','Iraq','Ireland','Israel','Italy','Japan','Jordan','Kazakhstan','Kenya','Kuwait','Kyrgyzstan','Lebanon','Libya','Malaysia','Maldives','Malta','Mauritius','Mexico','Morocco','Myanmar','Nepal','Netherlands','New Zealand','Nigeria','Norway','Oman','Pakistan','Palestine','Philippines','Poland','Portugal','Qatar','Romania','Russia','Rwanda','Saudi Arabia','Senegal','Serbia','Singapore','Somalia','South Africa','South Korea','Spain','Sri Lanka','Sudan','Sweden','Switzerland','Syria','Taiwan','Tanzania','Thailand','Tunisia','Turkey','Uganda','Ukraine','United Kingdom','United States','Uzbekistan','Vietnam','Yemen','Zambia','Zimbabwe'];

const EMPTY_EMP = {
  empNo:'', name:'', molId:'', bankName:'', bankRoutingCode:'', iban:'',
  basicSalary:'', allowance:'', active:true,
  personalEmail:'', workEmail:'', phone:'', dateOfBirth:'', gender:'',
  maritalStatus:'', homeCountryAddress:'', photoUrl:'',
  emergencyContactName:'', emergencyContactRelationship:'', emergencyContactPhone:'',
  jobTitle:'', department:'', reportingManagerId:'',
  startDate:'', probationEndDate:'', contractType:'Unlimited', contractEndDate:'',
  employmentStatus:'Active', terminationDate:'', terminationReason:'',
  housingAllowance:'', transportAllowance:'', otherAllowances:'', otherAllowancesLabel:'',
  bankAccountHolder:'',
  nationality:'', visaType:'', visaNumber:'', visaExpiry:'',
  passportNumber:'', passportExpiry:'',
  emiratesId:'', emiratesIdExpiry:'',
  labourCardNumber:'', labourCardExpiry:'',
  sponsoringEntity:'', workLocationType:'Mainland', freeZoneName:'',
  nafisRegistrationNo:'',
};

export default function EmployeeModal({ employee, allEmployees, onSave, onClose }) {
  const [form, setForm]         = useState(employee ? { ...EMPTY_EMP, ...employee } : { ...EMPTY_EMP });
  const [errors, setErrors]     = useState({});
  const [saving, setSaving]     = useState(false);
  const [tab, setTab]           = useState('personal');
  const [shifts, setShifts]         = useState([]);
  const [docs, setDocs]             = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploadForm, setUploadForm] = useState({ type: 'Visa', expiryDate: '', notes: '', file: null });
  const [uploading, setUploading]   = useState(false);
  const [uploadErr, setUploadErr]   = useState('');

  useEffect(() => {
    getShifts().then(setShifts).catch(() => {});
  }, []);

  // Load documents whenever the Documents tab becomes active (existing employees only)
  useEffect(() => {
    if (tab === 'documents' && employee?.id) {
      setDocsLoading(true);
      getEmployeeDocuments(employee.id)
        .then(setDocs)
        .catch(() => setDocs([]))
        .finally(() => setDocsLoading(false));
    }
  }, [tab, employee?.id]);

  const handleUpload = async () => {
    if (!uploadForm.file || !employee?.id) return;
    if (uploadForm.file.size > 10 * 1024 * 1024) {
      setUploadErr('File exceeds 10 MB limit. Please compress or choose a smaller file.');
      return;
    }
    setUploading(true);
    setUploadErr('');
    try {
      const doc = await uploadEmployeeDocument(
        employee.id,
        uploadForm.file,
        uploadForm.type,
        uploadForm.expiryDate || null,
        uploadForm.notes
      );
      setDocs(prev => [doc, ...prev]);
      setUploadForm(prev => ({ ...prev, file: null, notes: '', expiryDate: '' }));
    } catch (err) {
      setUploadErr(err.message || 'Upload failed. Ensure the employee-documents bucket exists in Supabase Storage.');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (doc) => {
    if (!window.confirm(`Delete "${doc.fileName}"? This cannot be undone.`)) return;
    try {
      await deleteEmployeeDocument(doc.id, doc.storagePath);
      setDocs(prev => prev.filter(d => d.id !== doc.id));
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  const f = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: undefined }));
  };

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Required';
    // Format-only checks — only run when the field has a value
    if (form.molId) {
      const molCheck = validateMolId(form.molId);
      if (!molCheck.valid) e.molId = molCheck.message;
    }
    if (form.iban) {
      const ibanCheck = validateIBAN(form.iban);
      if (!ibanCheck.valid) e.iban = ibanCheck.message;
    }
    if (form.emiratesId) {
      const eidCheck = validateEmiratesID(form.emiratesId);
      if (!eidCheck.valid) e.emiratesId = eidCheck.message;
    }
    if (form.basicSalary && (isNaN(form.basicSalary) || Number(form.basicSalary) < 0)) {
      e.basicSalary = 'Must be a positive number';
    }
    return e;
  };

  // Which tabs currently have errors (for cross-tab error banner)
  const TAB_FIELDS = {
    personal:   ['name'],
    job:        [],
    salary:     ['basicSalary', 'iban', 'bankRoutingCode'],
    compliance: ['molId', 'emiratesId'],
    documents:  [],
  };
  const tabsWithErrors = (errs) =>
    Object.entries(TAB_FIELDS)
      .filter(([, fields]) => fields.some(f => errs[f]))
      .map(([t]) => TABS.find(tb => tb.id === t)?.label)
      .filter(Boolean);

  const handleSave = async () => {
    const e = validate();
    if (Object.keys(e).length) {
      setErrors(e);
      // Switch to first tab that has errors
      const errTab = Object.entries(TAB_FIELDS).find(([, fields]) => fields.some(f => e[f]));
      if (errTab) setTab(errTab[0]);
      return;
    }
    setSaving(true);
    try {
      await onSave({
        ...form,
        basicSalary:        parseFloat(form.basicSalary) || 0,
        allowance:          parseFloat(form.allowance) || 0,
        housingAllowance:   parseFloat(form.housingAllowance) || 0,
        transportAllowance: parseFloat(form.transportAllowance) || 0,
        otherAllowances:    parseFloat(form.otherAllowances) || 0,
      });
    } finally {
      setSaving(false);
    }
  };

  const totalPackage = (parseFloat(form.basicSalary)||0) + (parseFloat(form.housingAllowance)||0) + (parseFloat(form.transportAllowance)||0) + (parseFloat(form.otherAllowances)||0);
  const gratuity = form.startDate ? calculateGratuity(parseFloat(form.basicSalary)||0, form.startDate) : null;

  const TABS = [
    { id:'personal',   label:'Personal',      icon:UserCheck },
    { id:'job',        label:'Job & Contract', icon:Briefcase },
    { id:'salary',     label:'Salary & Bank',  icon:CreditCard },
    { id:'compliance', label:'UAE Compliance', icon:Shield },
    ...(employee?.id ? [{ id:'documents', label:'Documents', icon:FolderOpen }] : []),
  ];

  return (
    <div className="modal-overlay">
      <div className="modal modal-xl" style={{ maxWidth:860 }}>
        <div className="modal-header">
          <h3>{employee?.id ? `Edit: ${employee.name}` : 'Add New Employee'}</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>

        <div className="tabs" style={{ padding:'0 20px', marginBottom:0, borderBottom:'2px solid var(--gray-200)' }}>
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button key={t.id} className={`tab-btn ${tab===t.id?'active':''}`} onClick={() => setTab(t.id)}>
                <Icon size={13} style={{ marginRight:5 }}/>{t.label}
              </button>
            );
          })}
        </div>

        <div className="modal-body">

          {/* Cross-tab error banner */}
          {Object.keys(errors).length > 0 && (() => {
            const tabs = tabsWithErrors(errors);
            return tabs.length > 0 ? (
              <div style={{ background:'#fef2f2', border:'1px solid #fecaca', borderRadius:8, padding:'10px 14px', marginBottom:16, fontSize:13, color:'#991b1b', display:'flex', gap:8, alignItems:'flex-start' }}>
                <span>⚠ Please fix errors on: <strong>{tabs.join(', ')}</strong></span>
              </div>
            ) : null;
          })()}

          {/* ── PERSONAL ── */}
          {tab === 'personal' && (
            <div className="form-grid form-grid-2">
              <div className="form-group">
                <label>Employee No.</label>
                <input className="form-control" value={form.empNo} onChange={e => f('empNo', e.target.value)} placeholder="e.g. 1001"/>
              </div>
              <div className="form-group">
                <label>Full Legal Name (as on passport) *</label>
                <input className="form-control" value={form.name} onChange={e => f('name', e.target.value)} placeholder="e.g. John Smith"/>
                {errors.name && <span className="text-danger text-sm">{errors.name}</span>}
              </div>
              <div className="form-group">
                <label>Personal Email</label>
                <input className="form-control" type="email" value={form.personalEmail} onChange={e => f('personalEmail', e.target.value)} placeholder="personal@email.com"/>
              </div>
              <div className="form-group">
                <label>Work Email</label>
                <input className="form-control" type="email" value={form.workEmail} onChange={e => f('workEmail', e.target.value)} placeholder="work@company.com"/>
              </div>
              <div className="form-group">
                <label>Phone Number</label>
                <input className="form-control" value={form.phone} onChange={e => f('phone', e.target.value)} placeholder="+971 50 000 0000"/>
              </div>
              <div className="form-group">
                <label>Date of Birth</label>
                <input className="form-control" type="date" value={form.dateOfBirth} onChange={e => f('dateOfBirth', e.target.value)}/>
              </div>
              <div className="form-group">
                <label>Gender</label>
                <select className="form-control" value={form.gender} onChange={e => f('gender', e.target.value)}>
                  <option value="">Select…</option>
                  {GENDERS.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Marital Status</label>
                <select className="form-control" value={form.maritalStatus} onChange={e => f('maritalStatus', e.target.value)}>
                  <option value="">Select…</option>
                  {MARITAL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label>Home Country Address</label>
                <input className="form-control" value={form.homeCountryAddress} onChange={e => f('homeCountryAddress', e.target.value)} placeholder="Full address in home country"/>
              </div>
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label style={{ fontWeight:600, marginBottom:6, display:'block' }}>Emergency Contact</label>
                <div className="form-grid form-grid-3" style={{ gap:10 }}>
                  <div className="form-group">
                    <label>Name</label>
                    <input className="form-control" value={form.emergencyContactName} onChange={e => f('emergencyContactName', e.target.value)} placeholder="Contact name"/>
                  </div>
                  <div className="form-group">
                    <label>Relationship</label>
                    <input className="form-control" value={form.emergencyContactRelationship} onChange={e => f('emergencyContactRelationship', e.target.value)} placeholder="e.g. Spouse"/>
                  </div>
                  <div className="form-group">
                    <label>Phone</label>
                    <input className="form-control" value={form.emergencyContactPhone} onChange={e => f('emergencyContactPhone', e.target.value)} placeholder="+971 50 000 0000"/>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── JOB & CONTRACT ── */}
          {tab === 'job' && (
            <div className="form-grid form-grid-2">
              <div className="form-group">
                <label>Job Title</label>
                <input className="form-control" value={form.jobTitle} onChange={e => f('jobTitle', e.target.value)} placeholder="e.g. Software Engineer"/>
              </div>
              <div className="form-group">
                <label>Department</label>
                <input className="form-control" value={form.department} onChange={e => f('department', e.target.value)} placeholder="e.g. Engineering"/>
              </div>
              <div className="form-group">
                <label>Reporting Manager</label>
                <select className="form-control" value={form.reportingManagerId} onChange={e => f('reportingManagerId', e.target.value)}>
                  <option value="">None</option>
                  {(allEmployees||[]).filter(e => e.id !== form.id).map(e => (
                    <option key={e.id} value={e.id}>{e.name}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Assigned Shift (Attendance)</label>
                <select className="form-control" value={form.shiftId || ''} onChange={e => f('shiftId', e.target.value)}>
                  <option value="">Company Default</option>
                  {shifts.map(s => (
                    <option key={s.id} value={s.id}>{s.name} ({s.startTime || 'Flexible'} – {s.endTime || ''}, {s.expectedHours}h)</option>
                  ))}
                </select>
                <span className="hint">Override the company default shift for this employee. Used by the Attendance module.</span>
              </div>
              <div className="form-group">
                <label>Employment Status</label>
                <select className="form-control" value={form.employmentStatus} onChange={e => f('employmentStatus', e.target.value)}>
                  {EMP_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Employment Start Date</label>
                <input className="form-control" type="date" value={form.startDate} onChange={e => f('startDate', e.target.value)}/>
              </div>
              <div className="form-group">
                <label>Probation End Date</label>
                <input className="form-control" type="date" value={form.probationEndDate} onChange={e => f('probationEndDate', e.target.value)}/>
              </div>
              <div className="form-group">
                <label>Contract Type</label>
                <select className="form-control" value={form.contractType} onChange={e => f('contractType', e.target.value)}>
                  {CONTRACT_TYPES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              {form.contractType === 'Limited' && (
                <div className="form-group">
                  <label>Contract End Date</label>
                  <input className="form-control" type="date" value={form.contractEndDate} onChange={e => f('contractEndDate', e.target.value)}/>
                </div>
              )}
              {form.employmentStatus === 'Terminated' && (
                <>
                  <div className="form-group">
                    <label>Termination Date</label>
                    <input className="form-control" type="date" value={form.terminationDate} onChange={e => f('terminationDate', e.target.value)}/>
                  </div>
                  <div className="form-group">
                    <label>Termination Reason</label>
                    <input className="form-control" value={form.terminationReason} onChange={e => f('terminationReason', e.target.value)} placeholder="e.g. Resignation"/>
                  </div>
                </>
              )}
              {gratuity && form.startDate && (
                <div className="form-group" style={{ gridColumn:'1/-1' }}>
                  <div style={{ background:gratuity.eligible?'var(--success-light)':'var(--gray-100)', borderRadius:8, padding:'12px 16px', border:`1px solid ${gratuity.eligible?'#a7f3d0':'var(--gray-200)'}` }}>
                    <div style={{ fontWeight:600, fontSize:13, color:gratuity.eligible?'var(--success)':'var(--gray-600)', marginBottom:4 }}>
                      Gratuity / EOSB Accrual (UAE Labour Law Art. 51)
                    </div>
                    <div style={{ fontSize:12.5, color:'var(--gray-700)' }}>
                      {gratuity.eligible
                        ? <><strong>{gratuity.serviceLabel}</strong> &nbsp;|&nbsp; Accrued: <strong>{formatAED(gratuity.gratuityCapped)}</strong>{gratuity.capped?' (capped at 2yr basic)':''}</>
                        : gratuity.breakdown}
                    </div>
                    {gratuity.eligible && <div style={{ fontSize:11.5, color:'var(--gray-500)', marginTop:4 }}>{gratuity.breakdown}</div>}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── SALARY & BANK ── */}
          {tab === 'salary' && (
            <div className="form-grid form-grid-2">
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label>MOL Employee ID (Labour Card No.) *</label>
                <input className="form-control font-mono" value={form.molId} onChange={e => f('molId', e.target.value.trim())} placeholder="e.g. 10003048635715"/>
                {errors.molId && <span className="text-danger text-sm">{errors.molId}</span>}
                <span className="hint">Unique ID provided by Ministry of Labour — used in WPS/SIF files</span>
              </div>
              <div className="form-group">
                <label>Basic Salary (AED) *</label>
                <input className="form-control" type="number" min="0" step="0.01" value={form.basicSalary} onChange={e => f('basicSalary', e.target.value)} placeholder="e.g. 5000"/>
                {errors.basicSalary && <span className="text-danger text-sm">{errors.basicSalary}</span>}
              </div>
              <div className="form-group">
                <label>Housing Allowance (AED)</label>
                <input className="form-control" type="number" min="0" step="0.01" value={form.housingAllowance} onChange={e => f('housingAllowance', e.target.value)} placeholder="e.g. 2000"/>
                <span className="hint">Separate line item — MOHRE compliant structure</span>
              </div>
              <div className="form-group">
                <label>Transport Allowance (AED)</label>
                <input className="form-control" type="number" min="0" step="0.01" value={form.transportAllowance} onChange={e => f('transportAllowance', e.target.value)} placeholder="e.g. 1000"/>
                <span className="hint">Separate line item — MOHRE compliant structure</span>
              </div>
              <div className="form-group">
                <label>Other Allowances (AED)</label>
                <input className="form-control" type="number" min="0" step="0.01" value={form.otherAllowances} onChange={e => f('otherAllowances', e.target.value)} placeholder="e.g. 500"/>
              </div>
              <div className="form-group">
                <label>Other Allowances Label</label>
                <input className="form-control" value={form.otherAllowancesLabel} onChange={e => f('otherAllowancesLabel', e.target.value)} placeholder="e.g. Meal Allowance"/>
              </div>
              {totalPackage > 0 && (
                <div className="form-group" style={{ gridColumn:'1/-1' }}>
                  <div style={{ background:'var(--primary-light)', borderRadius:8, padding:'10px 16px', border:'1px solid #bfdbfe' }}>
                    <span style={{ fontWeight:600, color:'var(--primary-dark)', fontSize:13 }}>Total Package: {formatAED(totalPackage)} / month</span>
                    <span style={{ fontSize:12, color:'var(--gray-500)', marginLeft:12 }}>
                      Basic {formatAED(parseFloat(form.basicSalary)||0)} + Housing {formatAED(parseFloat(form.housingAllowance)||0)} + Transport {formatAED(parseFloat(form.transportAllowance)||0)} + Other {formatAED(parseFloat(form.otherAllowances)||0)}
                    </span>
                  </div>
                </div>
              )}
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label style={{ fontWeight:600, marginBottom:6, display:'block' }}>Bank Details (for WPS / Payslip)</label>
                <div className="form-grid form-grid-2" style={{ gap:10 }}>
                  <div className="form-group">
                    <label>Bank Name</label>
                    <input className="form-control" value={form.bankName} onChange={e => f('bankName', e.target.value)} placeholder="e.g. ENBD, FAB, ADCB"/>
                  </div>
                  <div className="form-group">
                    <label>Bank / Routing Code *</label>
                    <input className="form-control font-mono" value={form.bankRoutingCode} onChange={e => f('bankRoutingCode', e.target.value.trim())} placeholder="e.g. 302620122"/>
                    {errors.bankRoutingCode && <span className="text-danger text-sm">{errors.bankRoutingCode}</span>}
                  </div>
                  <div className="form-group" style={{ gridColumn:'1/-1' }}>
                    <label>IBAN / Account Number *</label>
                    <input className="form-control font-mono" value={form.iban} onChange={e => f('iban', e.target.value.trim())} placeholder="e.g. AE080260001014950445301"/>
                    {errors.iban && <span className="text-danger text-sm">{errors.iban}</span>}
                    <span className="hint">UAE IBAN: starts with AE, 23 characters total</span>
                  </div>
                  <div className="form-group">
                    <label>Account Holder Name</label>
                    <input className="form-control" value={form.bankAccountHolder} onChange={e => f('bankAccountHolder', e.target.value)} placeholder="Name as on bank account"/>
                  </div>
                </div>
              </div>
              <div className="form-group">
                <label>Status</label>
                <select className="form-control" value={form.active ? 'active' : 'inactive'} onChange={e => f('active', e.target.value === 'active')}>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
            </div>
          )}

          {/* ── UAE COMPLIANCE ── */}
          {tab === 'compliance' && (
            <div className="form-grid form-grid-2">
              <div className="form-group">
                <label>Nationality</label>
                <select className="form-control" value={form.nationality} onChange={e => f('nationality', e.target.value)}>
                  <option value="">Select country…</option>
                  {COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                {form.nationality === 'United Arab Emirates' && (
                  <div style={{ marginTop:6, display:'inline-flex', alignItems:'center', gap:6, background:'#ecfdf5', border:'1px solid #a7f3d0', borderRadius:6, padding:'4px 10px', fontSize:12, color:'#065f46', fontWeight:600 }}>
                    <Shield size={12} /> UAE National — counts toward Emiratization quota
                  </div>
                )}
              </div>
              <div className="form-group">
                <label>Visa Type</label>
                <select className="form-control" value={form.visaType} onChange={e => f('visaType', e.target.value)}>
                  <option value="">Select…</option>
                  {VISA_TYPES.map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Visa Number</label>
                <input className="form-control" value={form.visaNumber} onChange={e => f('visaNumber', e.target.value)} placeholder="Visa number"/>
              </div>
              <div className="form-group">
                <label>Visa Expiry Date</label>
                <input className="form-control" type="date" value={form.visaExpiry} onChange={e => f('visaExpiry', e.target.value)}/>
                <span className="hint">Warning shown 60 days before expiry</span>
              </div>
              <div className="form-group">
                <label>Passport Number</label>
                <input className="form-control" value={form.passportNumber} onChange={e => f('passportNumber', e.target.value)} placeholder="Passport number"/>
              </div>
              <div className="form-group">
                <label>Passport Expiry Date</label>
                <input className="form-control" type="date" value={form.passportExpiry} onChange={e => f('passportExpiry', e.target.value)}/>
                <span className="hint">Warning shown 60 days before expiry</span>
              </div>
              <div className="form-group">
                <label>Emirates ID Number</label>
                <input className="form-control font-mono" value={form.emiratesId} onChange={e => f('emiratesId', e.target.value.trim())} placeholder="784-YYYY-XXXXXXX-X"/>
                {errors.emiratesId && <span className="text-danger text-sm">{errors.emiratesId}</span>}
                <span className="hint">Format: 784-YYYY-XXXXXXX-X (15 digits)</span>
              </div>
              <div className="form-group">
                <label>Emirates ID Expiry Date</label>
                <input className="form-control" type="date" value={form.emiratesIdExpiry} onChange={e => f('emiratesIdExpiry', e.target.value)}/>
                <span className="hint">Warning shown 30 days before expiry</span>
              </div>
              <div className="form-group">
                <label>Labour Card / Work Permit Number</label>
                <input className="form-control" value={form.labourCardNumber} onChange={e => f('labourCardNumber', e.target.value)} placeholder="Labour card number"/>
              </div>
              <div className="form-group">
                <label>Labour Card Expiry Date</label>
                <input className="form-control" type="date" value={form.labourCardExpiry} onChange={e => f('labourCardExpiry', e.target.value)}/>
                <span className="hint">Warning shown 60 days before expiry</span>
              </div>
              <div className="form-group">
                <label>Sponsoring Entity</label>
                <input className="form-control" value={form.sponsoringEntity} onChange={e => f('sponsoringEntity', e.target.value)} placeholder="Company name or individual"/>
              </div>
              <div className="form-group">
                <label>Work Location Type</label>
                <select className="form-control" value={form.workLocationType} onChange={e => f('workLocationType', e.target.value)}>
                  <option value="Mainland">Mainland</option>
                  <option value="Free Zone">Free Zone</option>
                </select>
                <span className="hint">Overrides company-level setting for this employee</span>
              </div>
              {form.workLocationType === 'Free Zone' && (
                <div className="form-group">
                  <label>Free Zone Name</label>
                  <select className="form-control" value={form.freeZoneName} onChange={e => f('freeZoneName', e.target.value)}>
                    <option value="">Select Free Zone…</option>
                    {FREE_ZONES.map(fz => <option key={fz} value={fz}>{fz}</option>)}
                  </select>
                </div>
              )}
              <div className="form-group" style={{ gridColumn:'1/-1', marginTop:8 }}>
                <label style={{ display:'flex', alignItems:'center', gap:6 }}>
                  <Shield size={13} style={{ color:'var(--primary)' }} />
                  Nafis Registration Number (UAE Nationals only)
                </label>
                <input
                  className="form-control font-mono"
                  value={form.nafisRegistrationNo}
                  onChange={e => f('nafisRegistrationNo', e.target.value.trim())}
                  placeholder="e.g. NFS-2024-XXXXXXX"
                  disabled={form.nationality !== 'United Arab Emirates'}
                />
                <span className="hint">
                  {form.nationality === 'United Arab Emirates'
                    ? 'Nafis registration number from the Nafis portal (nafis.gov.ae). Required for Emiratization reporting.'
                    : 'Only applicable to UAE national employees.'}
                </span>
              </div>
            </div>
          )}

          {/* ── DOCUMENTS ── */}
          {tab === 'documents' && (
            <div>
              {/* Upload form */}
              <div className="card mb-4">
                <div className="card-header"><h3>Upload New Document</h3></div>
                <div className="card-body">
                  <div className="form-grid form-grid-2" style={{ gap:12 }}>
                    <div className="form-group">
                      <label>Document Type</label>
                      <select className="form-control" value={uploadForm.type} onChange={e => setUploadForm(p => ({ ...p, type: e.target.value }))}>
                        {DOC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Expiry Date <span style={{ color:'var(--gray-400)', fontWeight:400 }}>(optional)</span></label>
                      <input type="date" className="form-control" value={uploadForm.expiryDate} onChange={e => setUploadForm(p => ({ ...p, expiryDate: e.target.value }))} />
                    </div>
                    <div className="form-group" style={{ gridColumn:'1/-1' }}>
                      <label>Notes <span style={{ color:'var(--gray-400)', fontWeight:400 }}>(optional)</span></label>
                      <input className="form-control" value={uploadForm.notes} onChange={e => setUploadForm(p => ({ ...p, notes: e.target.value }))} placeholder="e.g. Original submitted to PRO office" />
                    </div>
                    <div className="form-group" style={{ gridColumn:'1/-1' }}>
                      <label>File <span style={{ color:'var(--gray-400)', fontWeight:400 }}>PDF, JPG, PNG — max 10 MB</span></label>
                      <div
                        style={{ border:'2px dashed var(--gray-300)', borderRadius:8, padding:'14px 18px', textAlign:'center', cursor:'pointer', background:'var(--gray-50)', fontSize:13, color:'var(--gray-500)' }}
                        onClick={() => document.getElementById('doc-file-input').click()}
                      >
                        {uploadForm.file
                          ? <><strong style={{ color:'var(--gray-800)' }}>{uploadForm.file.name}</strong> <span style={{ color:'var(--gray-400)' }}>({formatFileSize(uploadForm.file.size)})</span></>
                          : <><Upload size={14} style={{ display:'inline', marginRight:6 }} />Click to choose file</>
                        }
                      </div>
                      <input
                        id="doc-file-input"
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        style={{ display:'none' }}
                        onChange={e => {
                          const file = e.target.files[0];
                          if (file) setUploadForm(p => ({ ...p, file }));
                          e.target.value = '';
                        }}
                      />
                    </div>
                  </div>

                  {uploadErr && (
                    <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:10, padding:'8px 12px', background:'#fef2f2', border:'1px solid #fecaca', borderRadius:6, fontSize:13, color:'#991b1b' }}>
                      <AlertCircle size={14} /> {uploadErr}
                    </div>
                  )}

                  <div style={{ marginTop:12 }}>
                    <button className="btn btn-primary" onClick={handleUpload} disabled={!uploadForm.file || uploading}>
                      {uploading
                        ? 'Uploading…'
                        : <><Upload size={14} style={{ marginRight:5 }} />Upload Document</>
                      }
                    </button>
                  </div>
                </div>
              </div>

              {/* Document list */}
              <div className="card">
                <div className="card-header">
                  <h3>Uploaded Documents {!docsLoading && `(${docs.length})`}</h3>
                </div>
                {docsLoading ? (
                  <div style={{ padding:'20px', textAlign:'center', color:'var(--gray-400)', fontSize:13 }}>Loading documents…</div>
                ) : docs.length === 0 ? (
                  <div style={{ padding:'24px 20px', textAlign:'center', color:'var(--gray-500)', fontSize:13 }}>
                    No documents uploaded yet. Use the form above to attach visa copies, passport scans, Emirates ID, and other compliance documents.
                  </div>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Type</th>
                          <th>File</th>
                          <th>Size</th>
                          <th>Uploaded</th>
                          <th>Expiry Status</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {docs.map(doc => {
                          const expiry = docExpiryStatus(doc.expiryDate);
                          return (
                            <tr key={doc.id}>
                              <td><span className="badge badge-blue" style={{ fontSize:11 }}>{doc.documentType}</span></td>
                              <td>
                                {doc.signedUrl
                                  ? <a href={doc.signedUrl} target="_blank" rel="noreferrer" style={{ color:'var(--primary)', textDecoration:'none', fontWeight:500, fontSize:13 }}>{doc.fileName}</a>
                                  : <span style={{ fontSize:13 }}>{doc.fileName}</span>
                                }
                                {doc.notes && <div style={{ fontSize:11, color:'var(--gray-400)', marginTop:1 }}>{doc.notes}</div>}
                              </td>
                              <td style={{ fontSize:12, color:'var(--gray-500)' }}>{formatFileSize(doc.fileSize)}</td>
                              <td style={{ fontSize:12, color:'var(--gray-500)' }}>{doc.uploadedAt?.split('T')[0] || '—'}</td>
                              <td>
                                <span className={`badge ${expiry.cls}`} style={{ fontSize:11 }}>
                                  {doc.expiryDate ? `${formatDateUAE(doc.expiryDate)} · ${expiry.label}` : expiry.label}
                                </span>
                              </td>
                              <td>
                                <button className="btn btn-ghost btn-icon btn-sm text-danger" title="Delete document" onClick={() => handleDeleteDoc(doc)}>
                                  <Trash2 size={13} />
                                </button>
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
          )}

        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          {tab !== 'documents' && (
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : (employee?.id ? 'Save Changes' : 'Add Employee')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
