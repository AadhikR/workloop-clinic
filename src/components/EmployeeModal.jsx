/**
 * EmployeeModal.jsx — Add/Edit Employee modal with tabbed UAE HR profile
 * Tabs: Personal | Job & Contract | Salary & Bank | UAE Compliance
 */
import { useState, useEffect, useRef } from 'react';
import { X, UserCheck, Briefcase, CreditCard, Shield, Upload, User } from 'lucide-react';
import { validateIBAN, validateEmiratesID, validateMolId, formatAED, formatDateUAE } from '../utils/uaeValidators';
import { calculateGratuity } from '../utils/gratuityCalculator';
import { getShifts } from '../utils/attendanceStorage';

const FREE_ZONES = ['DIFC','ADGM','JAFZA','DMCC','DAFZA','TECOM','Dubai Internet City','Dubai Media City','Dubai Healthcare City','Meydan Free Zone','RAKEZ','SAIF Zone','KIZAD','Abu Dhabi Free Zone','Hamriyah Free Zone','Other'];
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
};

export default function EmployeeModal({ employee, allEmployees, onSave, onClose }) {
  const [form, setForm]         = useState(employee ? { ...EMPTY_EMP, ...employee } : { ...EMPTY_EMP });
  const [errors, setErrors]     = useState({});
  const [saving, setSaving]     = useState(false);
  const [tab, setTab]           = useState('personal');
  const [shifts, setShifts]     = useState([]);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [photoError, setPhotoError] = useState('');
  const photoRef = useRef();

  useEffect(() => {
    getShifts().then(setShifts).catch(() => {});
  }, []);

  const handlePhotoUpload = (file) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setPhotoError('Please select an image file.');
      return;
    }
    setPhotoError('');
    setPhotoUploading(true);
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const MAX = 256;
      const scale = Math.min(1, MAX / Math.max(img.width, img.height));
      const canvas = document.createElement('canvas');
      canvas.width  = Math.round(img.width  * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.82);
      f('photoUrl', dataUrl);
      setPhotoUploading(false);
    };
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      setPhotoError('Could not read image. Try a different file.');
      setPhotoUploading(false);
    };
    img.src = objectUrl;
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
              {/* Photo */}
              <div style={{ gridColumn:'1/-1', display:'flex', flexDirection:'column', alignItems:'center', gap:10, paddingBottom:8 }}>
                <div
                  style={{
                    width:72, height:72, borderRadius:'50%',
                    background:'var(--gray-100)', border:'2px solid var(--gray-200)',
                    overflow:'hidden', display:'flex', alignItems:'center', justifyContent:'center',
                    cursor:'pointer',
                  }}
                  onClick={() => photoRef.current?.click()}
                  title="Click to upload photo"
                >
                  {form.photoUrl
                    ? <img src={form.photoUrl} alt="avatar" style={{ width:'100%', height:'100%', objectFit:'cover' }} />
                    : <User size={30} color="var(--gray-400)" />}
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    disabled={photoUploading}
                    onClick={() => photoRef.current?.click()}
                  >
                    <Upload size={13} /> {photoUploading ? 'Uploading…' : 'Upload Photo'}
                  </button>
                  {form.photoUrl && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ color:'var(--danger)' }}
                      onClick={() => f('photoUrl', '')}
                    >Remove</button>
                  )}
                </div>
                <input
                  ref={photoRef} type="file" accept="image/*" style={{ display:'none' }}
                  onChange={e => { if (e.target.files[0]) handlePhotoUpload(e.target.files[0]); e.target.value = ''; }}
                />
                {photoError
                  ? <div style={{ fontSize:11, color:'var(--danger)' }}>{photoError}</div>
                  : <div style={{ fontSize:11, color:'var(--gray-400)' }}>JPG or PNG · max 256 px</div>}
              </div>
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
            </div>
          )}

        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : (employee?.id ? 'Save Changes' : 'Add Employee')}
          </button>
        </div>
      </div>
    </div>
  );
}
