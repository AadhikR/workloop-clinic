/**
 * EmployeeModal.jsx — Add/Edit Employee modal with tabbed UAE HR profile
 * Tabs: Personal | Job & Contract | Salary & Bank | UAE Compliance
 */
import { useState, useEffect } from 'react';
import { X, UserCheck, Briefcase, CreditCard, Shield, FolderOpen, Upload, AlertCircle, Trash2, Heart, Plus, ShieldCheck, FileText, RefreshCw, CheckCircle, XCircle, Printer } from 'lucide-react';
import { validateIBAN, validateEmiratesID, validateMolId, formatAED, formatDateUAE, daysUntil } from '../utils/uaeValidators';
import { calculateGratuity } from '../utils/gratuityCalculator';
import { getShifts } from '../utils/attendanceStorage';
import {
  getEmployeeDocuments, uploadEmployeeDocument, deleteEmployeeDocument,
  verifyEmployeeDocument, rejectEmployeeDocument,
  getInsurancePolicies, getEmployeeInsurance, saveEmployeeInsurance,
  getInsuranceDependants, saveInsuranceDependant, deleteInsuranceDependant,
  saveEmployee, getEmployeeContracts, saveEmployeeContract, addJobHistoryEntry,
} from '../utils/storage';
import { getEmployeePortalRole, setEmployeePortalRole } from '../utils/profileStorage';
import { getDepartments } from '../utils/departmentStorage';

const FREE_ZONES = ['DIFC','ADGM','JAFZA','DMCC','DAFZA','TECOM','Dubai Internet City','Dubai Media City','Dubai Healthcare City','Meydan Free Zone','RAKEZ','SAIF Zone','KIZAD','Abu Dhabi Free Zone','Hamriyah Free Zone','Other'];

// Grouped document types — rendered as <optgroup> in the upload form
export const DOC_GROUPS = [
  {
    label: 'UAE Residency & Work',
    types: ['Visa', 'Passport', 'Emirates ID', 'Labour Card', 'Work Permit'],
  },
  {
    label: 'Clinical Credentials',
    types: ['DHA Licence', 'DOH Licence', 'MOH Licence', 'BLS Certificate', 'ACLS Certificate', 'PALS Certificate', 'NRP Certificate', 'CME Certificate'],
  },
  {
    label: 'General',
    types: ['Medical Fitness Certificate', 'Educational Certificate', 'Professional License', 'NOC / Reference Letter', 'Other'],
  },
];

export const CLINICAL_DOC_TYPES = new Set([
  'DHA Licence', 'DOH Licence', 'MOH Licence',
  'BLS Certificate', 'ACLS Certificate', 'PALS Certificate',
  'NRP Certificate', 'CME Certificate',
]);

function formatFileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function docExpiryStatus(expiryDate, isClinical = false) {
  if (!expiryDate) return { label: 'No Expiry', cls: 'badge-gray' };
  const days = Math.ceil((new Date(expiryDate) - new Date()) / (1000 * 60 * 60 * 24));
  if (days < 0)   return { label: `Expired ${Math.abs(days)}d ago`, cls: 'badge-red' };
  if (days <= 30) return { label: `${days}d left`, cls: 'badge-red' };
  // Clinical credentials show amber from 90 days out (harder to renew)
  if (isClinical && days <= 90) return { label: `${days}d left`, cls: 'badge-amber' };
  if (!isClinical && days <= 60) return { label: `${days}d left`, cls: 'badge-amber' };
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
  licenceAuthority:'None', licenceNumber:'', licenceExpiry:'',
};

export default function EmployeeModal({ employee, allEmployees, onSave, onClose }) {
  const [form, setForm]         = useState(employee ? { ...EMPTY_EMP, ...employee } : { ...EMPTY_EMP });
  const [errors, setErrors]     = useState({});
  const [saving, setSaving]     = useState(false);
  const [tab, setTab]           = useState('personal');
  const [deptList, setDeptList]     = useState([]);
  const [shifts, setShifts]         = useState([]);
  const [docs, setDocs]             = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploadForm, setUploadForm] = useState({ type: 'Visa', documentNumber: '', expiryDate: '', notes: '', file: null });
  const [uploading, setUploading]   = useState(false);
  const [uploadErr, setUploadErr]   = useState('');

  // Insurance tab state
  const [insuranceRecord, setInsuranceRecord]     = useState(null);
  const [insurancePolicies, setInsurancePolicies] = useState([]);
  const [insuranceLoading, setInsuranceLoading]   = useState(false);
  const [insuranceSaving, setInsuranceSaving]     = useState(false);
  const [insuranceForm, setInsuranceForm] = useState({ policyId:'', memberId:'', cardNumber:'', effectiveDate:'', expiryDate:'', tierName:'' });
  const [dependants, setDependants]       = useState([]);
  const [depForm, setDepForm]             = useState({ name:'', relationship:'', dateOfBirth:'', cardNumber:'' });
  const [depSaving, setDepSaving]         = useState(false);

  // Portal role (Feature 6) — only relevant for existing employees with activated portal
  const [portalRole, setPortalRole]         = useState(null);  // null = not loaded yet
  const [portalRoleSaving, setPortalRoleSaving] = useState(false);
  const [portalRoleErr, setPortalRoleErr]   = useState('');
  const [portalRoleOk, setPortalRoleOk]     = useState('');

  // Contract history (Feature 12)
  const [contracts, setContracts]                   = useState([]);
  const [contractsLoading, setContractsLoading]     = useState(false);
  const [contractAction, setContractAction]         = useState(null); // null | 'renew' | 'convert' | 'not_renew'
  const [renewForm, setRenewForm]                   = useState({ startDate:'', endDate:'', notes:'' });
  const [contractActionSaving, setContractActionSaving] = useState(false);
  const [contractActionMsg, setContractActionMsg]   = useState('');

  useEffect(() => {
    getShifts().then(setShifts).catch(() => {});
    getDepartments().then(setDeptList).catch(() => {});
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

  // Load portal role when the Job tab opens (only for existing activated employees)
  useEffect(() => {
    if (tab === 'job' && employee?.id && employee?.authUserId) {
      setPortalRole(null);
      getEmployeePortalRole(employee.id)
        .then(r => setPortalRole(r || 'employee'))
        .catch(() => setPortalRole('employee'));
    }
  }, [tab, employee?.id, employee?.authUserId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load insurance data whenever the Insurance tab becomes active
  useEffect(() => {
    if (tab === 'insurance' && employee?.id) {
      setInsuranceLoading(true);
      Promise.all([
        getInsurancePolicies(),
        getEmployeeInsurance(employee.id),
        getInsuranceDependants(employee.id),
      ]).then(([pols, ins, deps]) => {
        setInsurancePolicies(pols);
        setDependants(deps);
        if (ins) {
          setInsuranceRecord(ins);
          setInsuranceForm({
            policyId:      ins.policyId || '',
            memberId:      ins.memberId || '',
            cardNumber:    ins.cardNumber || '',
            effectiveDate: ins.effectiveDate || '',
            expiryDate:    ins.expiryDate || '',
            tierName:      ins.tierName || '',
          });
        } else {
          setInsuranceRecord(null);
          setInsuranceForm({ policyId:'', memberId:'', cardNumber:'', effectiveDate:'', expiryDate:'', tierName:'' });
        }
      }).catch(() => {}).finally(() => setInsuranceLoading(false));
    }
  }, [tab, employee?.id]);

  // Load contract history when Contracts tab becomes active
  useEffect(() => {
    if (tab === 'contracts' && employee?.id) {
      setContractsLoading(true);
      getEmployeeContracts(employee.id)
        .then(setContracts)
        .catch(() => setContracts([]))
        .finally(() => setContractsLoading(false));
    }
  }, [tab, employee?.id]); // eslint-disable-line react-hooks/exhaustive-deps

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
        uploadForm.notes,
        uploadForm.documentNumber
      );
      setDocs(prev => [doc, ...prev]);
      setUploadForm(prev => ({ ...prev, file: null, notes: '', expiryDate: '', documentNumber: '' }));
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

  const handleVerifyDoc = async (doc) => {
    try {
      await verifyEmployeeDocument(doc.id);
      setDocs(prev => prev.map(d => d.id === doc.id ? { ...d, status: 'verified' } : d));
    } catch (err) {
      alert('Verify failed: ' + err.message);
    }
  };

  const handleRejectDoc = async (doc) => {
    const reason = window.prompt('Rejection reason (shown to employee):');
    if (reason === null) return; // cancelled
    try {
      await rejectEmployeeDocument(doc.id, reason);
      setDocs(prev => prev.map(d => d.id === doc.id ? { ...d, status: 'rejected', rejectionReason: reason } : d));
    } catch (err) {
      alert('Reject failed: ' + err.message);
    }
  };

  const handleSaveInsurance = async () => {
    if (!employee?.id) return;
    setInsuranceSaving(true);
    try {
      const saved = await saveEmployeeInsurance({ ...insuranceForm, employeeId: employee.id });
      setInsuranceRecord(saved);
    } catch (err) {
      alert('Failed to save insurance: ' + err.message);
    } finally {
      setInsuranceSaving(false);
    }
  };

  const handleAddDependant = async () => {
    if (!depForm.name.trim() || !employee?.id) return;
    setDepSaving(true);
    try {
      const saved = await saveInsuranceDependant({ ...depForm, employeeId: employee.id });
      setDependants(prev => [...prev, saved]);
      setDepForm({ name:'', relationship:'', dateOfBirth:'', cardNumber:'' });
    } catch (err) {
      alert('Failed to add dependant: ' + err.message);
    } finally {
      setDepSaving(false);
    }
  };

  const handleDeleteDependant = async (dep) => {
    if (!window.confirm(`Remove ${dep.name} from insurance?`)) return;
    try {
      await deleteInsuranceDependant(dep.id);
      setDependants(prev => prev.filter(d => d.id !== dep.id));
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  // ── Contract action handlers (Feature 12) ───────────────────────────────────

  const handleRenewContract = async () => {
    if (!renewForm.endDate || !employee?.id) return;
    setContractActionSaving(true);
    try {
      const isFromUnlimited = form.contractType === 'Unlimited';
      const saved = await saveEmployeeContract({
        employeeId:   employee.id,
        contractType: 'Limited',
        startDate:    renewForm.startDate || form.contractEndDate || '',
        endDate:      renewForm.endDate,
        action:       isFromUnlimited ? 'converted' : 'renewed',
        notes:        renewForm.notes,
      });
      // Persist updated contract fields on the employee record
      await saveEmployee({
        ...form,
        contractType:       'Limited',
        contractEndDate:    renewForm.endDate,
        basicSalary:        parseFloat(form.basicSalary)       || 0,
        allowance:          parseFloat(form.allowance)         || 0,
        housingAllowance:   parseFloat(form.housingAllowance)  || 0,
        transportAllowance: parseFloat(form.transportAllowance)|| 0,
        otherAllowances:    parseFloat(form.otherAllowances)   || 0,
      });
      addJobHistoryEntry(
        employee.id,
        isFromUnlimited ? 'contract_converted' : 'contract_renewed',
        form.contractEndDate || form.contractType,
        `Limited to ${formatDateUAE(renewForm.endDate)}`,
        renewForm.notes,
      ).catch(() => {});
      setForm(prev => ({ ...prev, contractType:'Limited', contractEndDate:renewForm.endDate }));
      setContracts(prev => [saved, ...prev]);
      setContractAction(null);
      setContractActionMsg(isFromUnlimited
        ? 'Contract converted to Limited successfully.'
        : 'Contract renewed successfully.');
      setTimeout(() => setContractActionMsg(''), 4000);
    } catch (err) {
      alert('Failed to renew contract: ' + err.message);
    } finally {
      setContractActionSaving(false);
    }
  };

  const handleConvertToUnlimited = async () => {
    if (!employee?.id) return;
    setContractActionSaving(true);
    try {
      const saved = await saveEmployeeContract({
        employeeId:   employee.id,
        contractType: 'Unlimited',
        startDate:    form.startDate || '',
        endDate:      '',
        action:       'converted',
        notes:        renewForm.notes,
      });
      await saveEmployee({
        ...form,
        contractType:       'Unlimited',
        contractEndDate:    '',
        basicSalary:        parseFloat(form.basicSalary)       || 0,
        allowance:          parseFloat(form.allowance)         || 0,
        housingAllowance:   parseFloat(form.housingAllowance)  || 0,
        transportAllowance: parseFloat(form.transportAllowance)|| 0,
        otherAllowances:    parseFloat(form.otherAllowances)   || 0,
      });
      addJobHistoryEntry(employee.id, 'contract_converted', 'Limited', 'Unlimited', renewForm.notes).catch(() => {});
      setForm(prev => ({ ...prev, contractType:'Unlimited', contractEndDate:'' }));
      setContracts(prev => [saved, ...prev]);
      setContractAction(null);
      setContractActionMsg('Contract converted to Unlimited successfully.');
      setTimeout(() => setContractActionMsg(''), 4000);
    } catch (err) {
      alert('Failed to convert contract: ' + err.message);
    } finally {
      setContractActionSaving(false);
    }
  };

  const handleNotRenewing = async () => {
    if (!employee?.id) return;
    setContractActionSaving(true);
    try {
      const saved = await saveEmployeeContract({
        employeeId:   employee.id,
        contractType: form.contractType,
        startDate:    form.startDate || '',
        endDate:      form.contractEndDate || '',
        action:       'not_renewed',
        notes:        renewForm.notes,
      });
      addJobHistoryEntry(employee.id, 'contract_not_renewed', form.contractEndDate, 'Not Renewing', renewForm.notes).catch(() => {});
      setContracts(prev => [saved, ...prev]);
      setContractAction(null);
      setContractActionMsg('Non-renewal recorded. Notify the employee and initiate offboarding when ready. UAE law requires 30 days notice.');
      setTimeout(() => setContractActionMsg(''), 6000);
    } catch (err) {
      alert('Failed to record: ' + err.message);
    } finally {
      setContractActionSaving(false);
    }
  };

  const printContractLetter = () => {
    const totalPkg = (parseFloat(form.basicSalary)||0) + (parseFloat(form.housingAllowance)||0) + (parseFloat(form.transportAllowance)||0) + (parseFloat(form.otherAllowances)||0);
    const fmt = (d) => d ? new Date(d).toLocaleDateString('en-AE', { day:'2-digit', month:'long', year:'numeric' }) : '—';
    const html = `<!DOCTYPE html><html><head><title>Contract — ${form.name}</title>
<style>
  body{font-family:Arial,sans-serif;padding:60px;color:#333;max-width:700px;margin:auto}
  h1{font-size:20px;margin-bottom:4px}
  .meta{color:#666;font-size:13px;margin-bottom:36px}
  p{font-size:14px;line-height:1.6}
  table{width:100%;border-collapse:collapse;margin:18px 0}
  td{padding:9px 14px;border:1px solid #e5e7eb;font-size:13px}
  td:first-child{font-weight:600;color:#555;width:38%;background:#f9fafb}
  .sig{margin-top:64px;display:flex;justify-content:space-between}
  .sig-block{width:44%;border-top:2px solid #374151;padding-top:10px;font-size:13px}
  @media print{button{display:none!important}}
</style></head><body>
<h1>CONTRACT AMENDMENT / RENEWAL LETTER</h1>
<div class="meta">Date: ${new Date().toLocaleDateString('en-AE',{day:'2-digit',month:'long',year:'numeric'})}</div>
<p>Dear <strong>${form.name}</strong>,</p>
<p>This letter confirms your current employment contract details with the company. Please review and acknowledge below.</p>
<table>
  <tr><td>Employee Name</td><td>${form.name}</td></tr>
  <tr><td>Employee No.</td><td>${form.empNo || '—'}</td></tr>
  <tr><td>Job Title</td><td>${form.jobTitle || '—'}</td></tr>
  <tr><td>Department</td><td>${form.department || '—'}</td></tr>
  <tr><td>Contract Type</td><td>${form.contractType}</td></tr>
  <tr><td>Employment Start Date</td><td>${fmt(form.startDate)}</td></tr>
  ${form.contractType === 'Limited' && form.contractEndDate ? `<tr><td>Contract End Date</td><td>${fmt(form.contractEndDate)}</td></tr>` : ''}
  <tr><td>Basic Salary</td><td>AED ${(parseFloat(form.basicSalary)||0).toLocaleString('en-AE',{minimumFractionDigits:2})}</td></tr>
  <tr><td>Total Monthly Package</td><td>AED ${totalPkg.toLocaleString('en-AE',{minimumFractionDigits:2})}</td></tr>
</table>
<p>All other terms and conditions of your employment remain unchanged unless expressly stated otherwise.</p>
<p>Please sign below to acknowledge receipt of this letter.</p>
<div class="sig">
  <div class="sig-block">Employee Signature<br/><br/>${form.name}</div>
  <div class="sig-block">HR / Employer Representative<br/><br/>Authorised Signatory</div>
</div>
</body></html>`;
    const win = window.open('', '_blank', 'width=820,height=920');
    if (!win) { alert('Pop-up blocked — please allow pop-ups for this site.'); return; }
    win.document.write(html);
    win.document.close();
    win.print();
  };

  const f = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: undefined }));
  };

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Required';

    if (!String(form.empNo || '').trim()) {
      e.empNo = 'Required';
    } else {
      const dupNo = (allEmployees || []).find(
        emp => emp.empNo && String(emp.empNo).trim() === String(form.empNo).trim() && emp.id !== employee?.id
      );
      if (dupNo) e.empNo = `Employee No. already used by ${dupNo.name}`;
    }

    if (!form.workEmail || !form.workEmail.trim()) e.workEmail = 'Required';

    // MOL ID — required, format-checked, and must be unique
    if (!form.molId || !form.molId.trim()) {
      e.molId = 'Required';
    } else {
      const molCheck = validateMolId(form.molId);
      if (!molCheck.valid) {
        e.molId = molCheck.message;
      } else {
        // Duplicate MOL ID check — skip for the employee being edited (same id)
        const dup = (allEmployees || []).find(
          emp => emp.molId && emp.molId === form.molId.trim() && emp.id !== employee?.id
        );
        if (dup) e.molId = `MOL ID already used by ${dup.name}`;
      }
    }

    if (!form.bankName || !form.bankName.trim()) e.bankName = 'Required';
    if (!String(form.bankRoutingCode || '').trim()) e.bankRoutingCode = 'Required';

    if (!form.iban || !form.iban.trim()) {
      e.iban = 'Required';
    } else {
      const ibanCheck = validateIBAN(form.iban);
      if (!ibanCheck.valid) e.iban = ibanCheck.message;
    }

    if (form.emiratesId) {
      const eidCheck = validateEmiratesID(form.emiratesId);
      if (!eidCheck.valid) e.emiratesId = eidCheck.message;
    }

    if (!form.basicSalary || isNaN(form.basicSalary) || Number(form.basicSalary) <= 0) {
      e.basicSalary = 'Required — must be a positive number';
    }

    return e;
  };

  // Which tabs currently have errors (for cross-tab error banner)
  const TAB_FIELDS = {
    personal:   ['name', 'empNo', 'workEmail'],
    job:        [],
    salary:     ['basicSalary', 'iban', 'bankRoutingCode', 'bankName'],
    compliance: ['molId', 'emiratesId'],
    documents:  [],
    insurance:  [],
    contracts:  [],
  };
  const FIELD_LABELS = {
    name:            'Full name',
    empNo:           'Employee No.',
    workEmail:       'Work email',
    molId:           'MOL ID',
    iban:            'IBAN',
    bankName:        'Bank name',
    bankRoutingCode: 'Bank routing code',
    emiratesId:      'Emirates ID',
    basicSalary:     'Basic salary',
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
    ...(employee?.id ? [
      { id:'documents', label:'Documents',  icon:FolderOpen },
      { id:'insurance', label:'Insurance',  icon:Heart },
      { id:'contracts', label:'Contracts',  icon:FileText },
    ] : []),
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
            const items = Object.entries(TAB_FIELDS).flatMap(([tabId, fields]) => {
              const tabLabel = TABS.find(t => t.id === tabId)?.label;
              return fields
                .filter(fld => errors[fld])
                .map(fld => ({ tabLabel, fieldLabel: FIELD_LABELS[fld] ?? fld, message: errors[fld] }));
            });
            return items.length > 0 ? (
              <div style={{ background:'#fef2f2', border:'1px solid #fecaca', borderRadius:8, padding:'10px 14px', marginBottom:16, fontSize:13, color:'#991b1b' }}>
                <div style={{ fontWeight:500, marginBottom: items.length > 1 ? 5 : 0 }}>⚠ Please fix the following:</div>
                <ul style={{ margin:'4px 0 0', paddingLeft:18 }}>
                  {items.map((item, i) => (
                    <li key={i}><strong>{item.tabLabel}</strong> · {item.fieldLabel}: {item.message}</li>
                  ))}
                </ul>
              </div>
            ) : null;
          })()}

          {/* ── PERSONAL ── */}
          {tab === 'personal' && (
            <div className="form-grid form-grid-2">
              <div className="form-group">
                <label>Employee No. *</label>
                <input className="form-control" value={form.empNo} onChange={e => f('empNo', e.target.value)} placeholder="e.g. 1001"/>
                {errors.empNo && <span className="text-danger text-sm">{errors.empNo}</span>}
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
                <label>Work Email *</label>
                <input className="form-control" type="email" value={form.workEmail} onChange={e => f('workEmail', e.target.value)} placeholder="work@company.com"/>
                {errors.workEmail && <span className="text-danger text-sm">{errors.workEmail}</span>}
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
                <input
                  className="form-control"
                  list="dept-suggestions"
                  value={form.department}
                  onChange={e => f('department', e.target.value)}
                  placeholder="e.g. Nursing"
                />
                <datalist id="dept-suggestions">
                  {deptList.map(d => {
                    const parent = deptList.find(p => p.id === d.parentId);
                    return (
                      <option key={d.id} value={d.name}
                        label={parent ? `${d.name} (under ${parent.name})` : d.name}
                      />
                    );
                  })}
                </datalist>
              </div>
              <div className="form-group">
                <label>Reporting Manager</label>
                <select className="form-control" value={form.reportingManagerId} onChange={e => f('reportingManagerId', e.target.value)}>
                  <option value="">None</option>
                  {(allEmployees||[])
                    .filter(e => e.id !== form.id && e.employmentStatus !== 'Terminated')
                    .map(e => (
                      <option key={e.id} value={e.id}>{e.name}</option>
                    ))}
                </select>
              </div>
              {/* Portal Role — only visible when employee has an activated portal account */}
              {employee?.id && employee?.authUserId && (
                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <ShieldCheck size={14} style={{ color: '#2563eb' }} /> Portal Role
                  </label>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <select
                      className="form-control"
                      value={portalRole || 'employee'}
                      disabled={portalRole === null || portalRoleSaving}
                      onChange={async (e) => {
                        const newRole = e.target.value;
                        setPortalRoleErr('');
                        setPortalRoleOk('');
                        setPortalRoleSaving(true);
                        try {
                          await setEmployeePortalRole(employee.id, newRole);
                          setPortalRole(newRole);
                          setPortalRoleOk(`Role updated to ${newRole}.`);
                          setTimeout(() => setPortalRoleOk(''), 3000);
                        } catch (err) {
                          setPortalRoleErr(err.message || 'Failed to update role.');
                        } finally {
                          setPortalRoleSaving(false);
                        }
                      }}
                    >
                      <option value="employee">Employee</option>
                      <option value="manager">Manager</option>
                    </select>
                    {portalRoleSaving && <span style={{ fontSize: 12, color: '#64748b' }}>Saving…</span>}
                  </div>
                  {portalRoleErr && <span className="hint" style={{ color: '#ef4444' }}>{portalRoleErr}</span>}
                  {portalRoleOk  && <span className="hint" style={{ color: '#22c55e' }}>{portalRoleOk}</span>}
                  <span className="hint">
                    Manager role gives access to the Leave Approval Queue for their direct reports.
                  </span>
                </div>
              )}

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
              {totalPackage > 0 && (() => {
                const basic     = parseFloat(form.basicSalary)      || 0;
                const housing   = parseFloat(form.housingAllowance)  || 0;
                const transport = parseFloat(form.transportAllowance)|| 0;
                const basicPct     = Math.round(basic     / totalPackage * 100);
                const housingPct   = Math.round(housing   / totalPackage * 100);
                const transportPct = Math.round(transport / totalPackage * 100);

                const checks = [
                  {
                    label:  'Basic Salary',
                    value:  formatAED(basic),
                    pct:    basicPct,
                    status: basicPct >= 60 ? 'ok' : basicPct >= 50 ? 'warn' : 'error',
                    note:   basicPct >= 60
                      ? 'Compliant — MoHRE recommended ≥60%, EOSB gratuity basis correct'
                      : basicPct >= 50
                        ? 'Below MoHRE recommended 60% — gratuity basis partially affected'
                        : `Below 50% — gratuity calculated on a smaller base (Art. 51, Labour Law No. 33/2021)`,
                  },
                  {
                    label:  'Housing Allowance',
                    value:  formatAED(housing),
                    pct:    housingPct,
                    status: housingPct <= 25 ? 'ok' : 'warn',
                    note:   housingPct > 25
                      ? 'Exceeds MoHRE recommended 25% — verify against company housing policy'
                      : 'Within MoHRE recommended range (≤25%)',
                  },
                  {
                    label:  'Transport Allowance',
                    value:  formatAED(transport),
                    pct:    transportPct,
                    status: transportPct <= 10 ? 'ok' : 'warn',
                    note:   transportPct > 10
                      ? 'Exceeds MoHRE recommended 10% — verify against company policy'
                      : 'Within MoHRE recommended range (≤10%)',
                  },
                ];

                const hasWarning = checks.some(c => c.status !== 'ok');
                const COLORS = {
                  ok:    { bg: '#f0fdf4', border: '#bbf7d0', dot: '#16a34a', text: '#166534' },
                  warn:  { bg: '#fffbeb', border: '#fde68a', dot: '#d97706', text: '#92400e' },
                  error: { bg: '#fff5f5', border: '#fecaca', dot: '#dc2626', text: '#991b1b' },
                };

                return (
                  <div className="form-group" style={{ gridColumn:'1/-1' }}>
                    {/* Package summary */}
                    <div style={{ background:'var(--primary-light)', borderRadius:8, padding:'10px 16px', border:'1px solid #bfdbfe', marginBottom: 10 }}>
                      <span style={{ fontWeight:600, color:'var(--primary-dark)', fontSize:13 }}>Total Package: {formatAED(totalPackage)} / month</span>
                      <span style={{ fontSize:12, color:'var(--gray-500)', marginLeft:12 }}>
                        Basic {formatAED(basic)} + Housing {formatAED(housing)} + Transport {formatAED(transport)} + Other {formatAED(parseFloat(form.otherAllowances)||0)}
                      </span>
                    </div>

                    {/* Salary distribution validation */}
                    <div style={{
                      border: `1px solid ${hasWarning ? '#fde68a' : '#bbf7d0'}`,
                      borderRadius: 8,
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        padding: '7px 14px',
                        background: hasWarning ? '#fffbeb' : '#f0fdf4',
                        borderBottom: `1px solid ${hasWarning ? '#fde68a' : '#bbf7d0'}`,
                        fontSize: 12, fontWeight: 600,
                        color: hasWarning ? '#92400e' : '#166534',
                        display: 'flex', alignItems: 'center', gap: 6,
                      }}>
                        {hasWarning ? '⚠ Salary Distribution Warnings' : '✓ Salary Distribution — Compliant'}
                        <span style={{ fontWeight: 400, color: 'var(--gray-500)', marginLeft: 4 }}>
                          Contract: {form.contractType || 'Unlimited'}
                        </span>
                      </div>
                      {checks.map(c => {
                        const col = COLORS[c.status];
                        return (
                          <div key={c.label} style={{
                            display: 'grid',
                            gridTemplateColumns: '140px 80px 60px 1fr',
                            gap: 8, alignItems: 'center',
                            padding: '6px 14px',
                            borderBottom: '1px solid var(--gray-100)',
                            background: c.status !== 'ok' ? col.bg : 'transparent',
                          }}>
                            <span style={{ fontSize: 12, fontWeight: 500 }}>{c.label}</span>
                            <span style={{ fontSize: 12, fontFamily: 'monospace' }}>{c.value}</span>
                            <span style={{
                              fontSize: 11, fontWeight: 700,
                              color: col.text, background: col.bg,
                              border: `1px solid ${col.border}`,
                              borderRadius: 4, padding: '1px 6px', textAlign: 'center',
                            }}>
                              {c.pct}%
                            </span>
                            <span style={{ fontSize: 11, color: c.status !== 'ok' ? col.text : 'var(--gray-400)' }}>
                              {c.note}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label style={{ fontWeight:600, marginBottom:6, display:'block' }}>Bank Details (for WPS / Payslip)</label>
                <div className="form-grid form-grid-2" style={{ gap:10 }}>
                  <div className="form-group">
                    <label>Bank Name *</label>
                    <input className="form-control" value={form.bankName} onChange={e => f('bankName', e.target.value)} placeholder="e.g. ENBD, FAB, ADCB"/>
                    {errors.bankName && <span className="text-danger text-sm">{errors.bankName}</span>}
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

              {/* ── Professional Licence (Feature 7.1) ── */}
              <div style={{ gridColumn:'1/-1', borderTop:'1px solid var(--gray-100)', paddingTop:16, marginTop:8 }}>
                <p style={{ fontWeight:600, fontSize:13, color:'var(--gray-700)', marginBottom:12, display:'flex', alignItems:'center', gap:6 }}>
                  <ShieldCheck size={14} style={{ color:'var(--primary)' }} />
                  Professional Licence (DHA / DOH / MOH)
                </p>
                <div className="form-grid">
                  <div className="form-group">
                    <label>Licence Authority</label>
                    <select className="form-control" value={form.licenceAuthority} onChange={e => f('licenceAuthority', e.target.value)}>
                      <option value="None">None / Not Applicable</option>
                      <option value="DHA">DHA — Dubai Health Authority</option>
                      <option value="DOH">DOH — Department of Health Abu Dhabi</option>
                      <option value="MOH">MOH — Ministry of Health</option>
                      <option value="HAAD">HAAD — Health Authority Abu Dhabi</option>
                      <option value="DHCC">DHCC — Dubai Healthcare City Authority</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Licence Number</label>
                    <input
                      className="form-control font-mono"
                      value={form.licenceNumber}
                      onChange={e => f('licenceNumber', e.target.value.trim())}
                      placeholder="e.g. DHA-P-XXXXXXXX"
                      disabled={form.licenceAuthority === 'None'}
                    />
                  </div>
                  <div className="form-group">
                    <label>Licence Expiry Date</label>
                    <input
                      className="form-control"
                      type="date"
                      value={form.licenceExpiry}
                      onChange={e => f('licenceExpiry', e.target.value)}
                      disabled={form.licenceAuthority === 'None'}
                    />
                    {form.licenceAuthority !== 'None' && (
                      form.licenceExpiry
                        ? (() => {
                            const days = daysUntil(form.licenceExpiry);
                            if (days < 0) return <span className="hint" style={{ color:'var(--danger)' }}>⚠ Expired {Math.abs(days)}d ago — payroll SIF generation will require override</span>;
                            if (days <= 30) return <span className="hint" style={{ color:'var(--warning)' }}>⚠ Expires in {days}d — renew soon</span>;
                            return <span className="hint" style={{ color:'var(--success)' }}>Valid — {days}d remaining</span>;
                          })()
                        : <span className="hint" style={{ color:'var(--warning)' }}>⚠ Set a licence expiry date to track renewal</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── INSURANCE ── */}
          {tab === 'insurance' && (
            <div>
              {insuranceLoading ? (
                <div style={{ padding:'20px', textAlign:'center', color:'var(--gray-400)', fontSize:13 }}>Loading insurance data…</div>
              ) : (
                <>
                  {/* Coverage Assignment */}
                  <div className="card mb-4">
                    <div className="card-header">
                      <h3>Coverage Assignment</h3>
                      {insuranceRecord && (
                        <span className="badge badge-green" style={{ fontSize:11 }}>Assigned</span>
                      )}
                    </div>
                    <div className="card-body">
                      {insurancePolicies.length === 0 && (
                        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:14, padding:'8px 12px', background:'#eff6ff', border:'1px solid #bfdbfe', borderRadius:6, fontSize:13, color:'#1e40af' }}>
                          <AlertCircle size={14} />
                          No policies set up yet. Go to <strong>Company Settings → Medical Insurance Policies</strong> to add a policy first.
                        </div>
                      )}
                      <div className="form-grid form-grid-2" style={{ gap:12 }}>
                        <div className="form-group">
                          <label>Insurance Policy</label>
                          <select className="form-control" value={insuranceForm.policyId}
                            onChange={e => setInsuranceForm(p => ({ ...p, policyId: e.target.value }))}>
                            <option value="">Select policy…</option>
                            {insurancePolicies.map(pol => (
                              <option key={pol.id} value={pol.id}>
                                {pol.insurerName}{pol.tierName ? ` — ${pol.tierName}` : ''}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Coverage Tier</label>
                          <input className="form-control" value={insuranceForm.tierName}
                            onChange={e => setInsuranceForm(p => ({ ...p, tierName: e.target.value }))}
                            placeholder="e.g. Gold, Silver, Basic" />
                          <span className="hint">Overrides the policy-level tier for this employee</span>
                        </div>
                        <div className="form-group">
                          <label>Member ID</label>
                          <input className="form-control font-mono" value={insuranceForm.memberId}
                            onChange={e => setInsuranceForm(p => ({ ...p, memberId: e.target.value }))}
                            placeholder="Insurer-assigned member ID" />
                        </div>
                        <div className="form-group">
                          <label>Insurance Card Number</label>
                          <input className="form-control font-mono" value={insuranceForm.cardNumber}
                            onChange={e => setInsuranceForm(p => ({ ...p, cardNumber: e.target.value }))}
                            placeholder="Physical card or certificate number" />
                        </div>
                        <div className="form-group">
                          <label>Effective Date</label>
                          <input type="date" className="form-control" value={insuranceForm.effectiveDate}
                            onChange={e => setInsuranceForm(p => ({ ...p, effectiveDate: e.target.value }))} />
                        </div>
                        <div className="form-group">
                          <label>Expiry Date</label>
                          <input type="date" className="form-control" value={insuranceForm.expiryDate}
                            onChange={e => setInsuranceForm(p => ({ ...p, expiryDate: e.target.value }))} />
                          <span className="hint">Dashboard alert fires 60 days before expiry</span>
                        </div>
                      </div>
                      <div style={{ marginTop:14 }}>
                        <button className="btn btn-primary" onClick={handleSaveInsurance} disabled={insuranceSaving}>
                          {insuranceSaving ? 'Saving…' : (insuranceRecord ? 'Update Coverage' : 'Assign Coverage')}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Dependants */}
                  <div className="card">
                    <div className="card-header">
                      <h3>Dependants <span style={{ color:'var(--gray-400)', fontWeight:400, fontSize:13 }}>({dependants.length})</span></h3>
                    </div>
                    <div className="card-body">
                      {/* Add dependant form */}
                      <div style={{ background:'var(--gray-50)', borderRadius:8, padding:'12px 14px', marginBottom:16, border:'1px solid var(--gray-200)' }}>
                        <div style={{ fontWeight:600, fontSize:13, marginBottom:10, color:'var(--gray-700)' }}>Add Dependant</div>
                        <div className="form-grid form-grid-2" style={{ gap:10 }}>
                          <div className="form-group">
                            <label>Full Name</label>
                            <input className="form-control" value={depForm.name}
                              onChange={e => setDepForm(p => ({ ...p, name: e.target.value }))}
                              placeholder="Dependant's full name" />
                          </div>
                          <div className="form-group">
                            <label>Relationship</label>
                            <select className="form-control" value={depForm.relationship}
                              onChange={e => setDepForm(p => ({ ...p, relationship: e.target.value }))}>
                              <option value="">Select…</option>
                              {['Spouse','Child','Parent','Sibling','Other'].map(r => (
                                <option key={r} value={r}>{r}</option>
                              ))}
                            </select>
                          </div>
                          <div className="form-group">
                            <label>Date of Birth</label>
                            <input type="date" className="form-control" value={depForm.dateOfBirth}
                              onChange={e => setDepForm(p => ({ ...p, dateOfBirth: e.target.value }))} />
                          </div>
                          <div className="form-group">
                            <label>Insurance Card No.</label>
                            <input className="form-control font-mono" value={depForm.cardNumber}
                              onChange={e => setDepForm(p => ({ ...p, cardNumber: e.target.value }))}
                              placeholder="Dependant's card number" />
                          </div>
                        </div>
                        <button className="btn btn-primary btn-sm" style={{ marginTop:8 }}
                          onClick={handleAddDependant} disabled={!depForm.name.trim() || depSaving}>
                          {depSaving ? 'Adding…' : <><Plus size={13} style={{ marginRight:5 }} />Add Dependant</>}
                        </button>
                      </div>

                      {/* Dependants list */}
                      {dependants.length === 0 ? (
                        <div style={{ textAlign:'center', color:'var(--gray-400)', fontSize:13, padding:'8px 0' }}>
                          No dependants registered. Add family members covered under this employee's insurance.
                        </div>
                      ) : (
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>Name</th>
                                <th>Relationship</th>
                                <th>Date of Birth</th>
                                <th>Card No.</th>
                                <th></th>
                              </tr>
                            </thead>
                            <tbody>
                              {dependants.map(dep => (
                                <tr key={dep.id}>
                                  <td style={{ fontWeight:500 }}>{dep.name}</td>
                                  <td>{dep.relationship || '—'}</td>
                                  <td style={{ fontSize:12, color:'var(--gray-500)' }}>{dep.dateOfBirth ? formatDateUAE(dep.dateOfBirth) : '—'}</td>
                                  <td style={{ fontSize:12, fontFamily:'monospace' }}>{dep.cardNumber || '—'}</td>
                                  <td>
                                    <button className="btn btn-ghost btn-icon btn-sm text-danger"
                                      title="Remove dependant" onClick={() => handleDeleteDependant(dep)}>
                                      <Trash2 size={13} />
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
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
                        {DOC_GROUPS.map(g => (
                          <optgroup key={g.label} label={g.label}>
                            {g.types.map(t => <option key={t} value={t}>{t}</option>)}
                          </optgroup>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Document Number <span style={{ color:'var(--gray-400)', fontWeight:400 }}>(optional)</span></label>
                      <input className="form-control" value={uploadForm.documentNumber} onChange={e => setUploadForm(p => ({ ...p, documentNumber: e.target.value }))} placeholder="e.g. passport / licence / certificate number" />
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
                    No documents uploaded yet. Use the form above to attach visa copies, passport scans, Emirates ID, clinical credentials (DHA/DOH Licence, BLS, ACLS, etc.), and other compliance documents.
                  </div>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Type</th>
                          <th>Number</th>
                          <th>File</th>
                          <th>Expiry Status</th>
                          <th>Review Status</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {docs.map(doc => {
                          const clinical = CLINICAL_DOC_TYPES.has(doc.documentType);
                          const expiry = docExpiryStatus(doc.expiryDate, clinical);
                          const isPending = doc.status === 'pending_verification';
                          const isRejected = doc.status === 'rejected';
                          return (
                            <tr key={doc.id} style={isPending ? { background: 'rgba(217,119,6,0.04)' } : undefined}>
                              <td>
                                <span className={`badge ${clinical ? 'badge-cyan' : 'badge-blue'}`} style={{ fontSize:11 }}>{doc.documentType}</span>
                                {clinical && <span style={{ fontSize:10, color:'var(--accent)', marginLeft:4, fontWeight:600 }}>Clinical</span>}
                                {doc.submittedBy === 'employee' && <div style={{ fontSize:10, color:'var(--gray-400)', marginTop:2 }}>Self-submitted</div>}
                              </td>
                              <td style={{ fontSize:12, color:'var(--gray-600)' }}>
                                {doc.documentNumber || <span style={{ color:'var(--gray-300)' }}>—</span>}
                              </td>
                              <td>
                                {doc.signedUrl
                                  ? <a href={doc.signedUrl} target="_blank" rel="noreferrer" style={{ color:'var(--primary)', textDecoration:'none', fontWeight:500, fontSize:13 }}>{doc.fileName}</a>
                                  : <span style={{ fontSize:13 }}>{doc.fileName}</span>
                                }
                                {doc.notes && <div style={{ fontSize:11, color:'var(--gray-400)', marginTop:1 }}>{doc.notes}</div>}
                              </td>
                              <td>
                                <span className={`badge ${expiry.cls}`} style={{ fontSize:11 }}>
                                  {doc.expiryDate ? `${formatDateUAE(doc.expiryDate)} · ${expiry.label}` : expiry.label}
                                </span>
                              </td>
                              <td>
                                {isPending ? (
                                  <span className="badge badge-amber" style={{ fontSize:11 }}>Pending Review</span>
                                ) : isRejected ? (
                                  <div>
                                    <span className="badge badge-red" style={{ fontSize:11 }}>Rejected</span>
                                    {doc.rejectionReason && <div style={{ fontSize:10, color:'var(--danger)', marginTop:2 }}>{doc.rejectionReason}</div>}
                                  </div>
                                ) : (
                                  <span className="badge badge-green" style={{ fontSize:11 }}>Verified</span>
                                )}
                              </td>
                              <td>
                                <div style={{ display:'flex', gap:4 }}>
                                  {isPending && (
                                    <>
                                      <button className="btn btn-ghost btn-icon btn-sm" title="Verify document" style={{ color:'var(--success)' }} onClick={() => handleVerifyDoc(doc)}>
                                        <CheckCircle size={13} />
                                      </button>
                                      <button className="btn btn-ghost btn-icon btn-sm text-danger" title="Reject document" onClick={() => handleRejectDoc(doc)}>
                                        <XCircle size={13} />
                                      </button>
                                    </>
                                  )}
                                  <button className="btn btn-ghost btn-icon btn-sm text-danger" title="Delete document" onClick={() => handleDeleteDoc(doc)}>
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
          )}

          {/* ── CONTRACTS ── */}
          {tab === 'contracts' && employee?.id && (
            <div>
              {/* Current contract status card */}
              <div style={{ background:'#f8fafc', borderRadius:10, padding:'16px 20px', marginBottom:20, border:'1px solid var(--gray-200)', display:'flex', alignItems:'flex-start', justifyContent:'space-between', flexWrap:'wrap', gap:14 }}>
                <div style={{ display:'flex', gap:32, flexWrap:'wrap', flex:1 }}>
                  <div>
                    <div style={{ fontSize:12, color:'var(--gray-500)', marginBottom:5 }}>Contract Type</div>
                    <span className={`badge ${form.contractType === 'Limited' ? 'badge-blue' : 'badge-green'}`} style={{ fontSize:12 }}>
                      {form.contractType}
                    </span>
                  </div>
                  {form.contractType === 'Limited' && form.contractEndDate && (() => {
                    const days = Math.ceil((new Date(form.contractEndDate) - new Date()) / 86400000);
                    return (
                      <div>
                        <div style={{ fontSize:12, color:'var(--gray-500)', marginBottom:5 }}>Contract End Date</div>
                        <div style={{ fontWeight:600, fontSize:14 }}>{formatDateUAE(form.contractEndDate)}</div>
                        <div style={{ fontSize:12, marginTop:3, fontWeight:600,
                          color: days < 0 ? 'var(--danger)' : days <= 30 ? 'var(--warning)' : days <= 60 ? '#d97706' : 'var(--success)' }}>
                          {days < 0 ? `Expired ${Math.abs(days)}d ago` : days === 0 ? 'Expires today' : `${days} days remaining`}
                        </div>
                      </div>
                    );
                  })()}
                  <div>
                    <div style={{ fontSize:12, color:'var(--gray-500)', marginBottom:5 }}>Start Date</div>
                    <div style={{ fontWeight:600, fontSize:14 }}>{formatDateUAE(form.startDate) || '—'}</div>
                  </div>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={printContractLetter} style={{ flexShrink:0 }}>
                  <Printer size={13} style={{ marginRight:5 }} />Print Letter
                </button>
              </div>

              {/* Action buttons (only when no action is pending) */}
              {!contractAction && (
                <div style={{ marginBottom:20 }}>
                  <div style={{ fontSize:11, fontWeight:600, color:'var(--gray-400)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:10 }}>Contract Actions</div>
                  <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
                    {form.contractType === 'Limited' ? (
                      <>
                        <button className="btn btn-primary btn-sm"
                          onClick={() => { setContractAction('renew'); setRenewForm({ startDate:form.contractEndDate||'', endDate:'', notes:'' }); }}>
                          <RefreshCw size={13} style={{ marginRight:5 }} />Renew Contract
                        </button>
                        <button className="btn btn-ghost btn-sm" style={{ border:'1px solid var(--gray-300)' }}
                          onClick={() => { setContractAction('convert'); setRenewForm({ startDate:'', endDate:'', notes:'' }); }}>
                          <CheckCircle size={13} style={{ marginRight:5 }} />Convert to Unlimited
                        </button>
                        <button className="btn btn-ghost btn-sm" style={{ border:'1px solid #fca5a5', color:'#dc2626' }}
                          onClick={() => { setContractAction('not_renew'); setRenewForm({ startDate:'', endDate:'', notes:'' }); }}>
                          Not Renewing
                        </button>
                      </>
                    ) : (
                      <button className="btn btn-ghost btn-sm" style={{ border:'1px solid var(--gray-300)' }}
                        onClick={() => { setContractAction('renew'); setRenewForm({ startDate:'', endDate:'', notes:'' }); }}>
                        <RefreshCw size={13} style={{ marginRight:5 }} />Convert to Limited
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Renew / Convert-to-Limited form */}
              {contractAction === 'renew' && (
                <div style={{ background:'#eff6ff', borderRadius:10, padding:'16px 20px', marginBottom:20, border:'1px solid #bfdbfe' }}>
                  <div style={{ fontWeight:600, fontSize:14, marginBottom:14, color:'#1d4ed8' }}>
                    {form.contractType === 'Unlimited' ? 'Convert to Limited Contract' : 'Renew Limited Contract'}
                  </div>
                  <div className="form-grid form-grid-2">
                    <div className="form-group">
                      <label>New Start Date</label>
                      <input className="form-control" type="date" value={renewForm.startDate}
                        onChange={e => setRenewForm(p => ({ ...p, startDate:e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label>New End Date *</label>
                      <input className="form-control" type="date" value={renewForm.endDate}
                        onChange={e => setRenewForm(p => ({ ...p, endDate:e.target.value }))} />
                    </div>
                    <div className="form-group" style={{ gridColumn:'1/-1' }}>
                      <label>Notes <span style={{ fontWeight:400, color:'var(--gray-400)' }}>(optional)</span></label>
                      <input className="form-control" value={renewForm.notes}
                        onChange={e => setRenewForm(p => ({ ...p, notes:e.target.value }))}
                        placeholder="e.g. Annual renewal, same terms and conditions" />
                    </div>
                  </div>
                  <div style={{ display:'flex', gap:10, marginTop:12 }}>
                    <button className="btn btn-primary btn-sm" onClick={handleRenewContract}
                      disabled={!renewForm.endDate || contractActionSaving}>
                      {contractActionSaving ? 'Saving…' : 'Confirm'}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setContractAction(null)}>Cancel</button>
                  </div>
                </div>
              )}

              {/* Convert to Unlimited form */}
              {contractAction === 'convert' && (
                <div style={{ background:'#f0fdf4', borderRadius:10, padding:'16px 20px', marginBottom:20, border:'1px solid #bbf7d0' }}>
                  <div style={{ fontWeight:600, fontSize:14, marginBottom:8, color:'#166534' }}>Convert to Unlimited Contract</div>
                  <p style={{ fontSize:13, color:'var(--gray-600)', marginBottom:14 }}>
                    This changes the contract type to Unlimited and clears the end date. The action is logged to job history.
                    Under Federal Decree-Law No. 33 of 2021, unlimited contracts offer stronger employee protections.
                  </p>
                  <div className="form-group">
                    <label>Notes <span style={{ fontWeight:400, color:'var(--gray-400)' }}>(optional)</span></label>
                    <input className="form-control" value={renewForm.notes}
                      onChange={e => setRenewForm(p => ({ ...p, notes:e.target.value }))}
                      placeholder="e.g. Converted after 2 years of service" />
                  </div>
                  <div style={{ display:'flex', gap:10, marginTop:12 }}>
                    <button className="btn btn-primary btn-sm" onClick={handleConvertToUnlimited}
                      disabled={contractActionSaving}>
                      {contractActionSaving ? 'Saving…' : 'Confirm Conversion'}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setContractAction(null)}>Cancel</button>
                  </div>
                </div>
              )}

              {/* Not Renewing form */}
              {contractAction === 'not_renew' && (
                <div style={{ background:'#fff7ed', borderRadius:10, padding:'16px 20px', marginBottom:20, border:'1px solid #fed7aa' }}>
                  <div style={{ fontWeight:600, fontSize:14, marginBottom:8, color:'#c2410c' }}>Mark as Not Renewing</div>
                  <p style={{ fontSize:13, color:'var(--gray-600)', marginBottom:14 }}>
                    This logs non-renewal intent to the contract history. The employee's status remains unchanged — initiate
                    offboarding separately when ready.{' '}
                    <strong>UAE Labour Law requires 30 days notice before a limited contract expires.</strong>
                  </p>
                  <div className="form-group">
                    <label>Reason / Notes <span style={{ fontWeight:400, color:'var(--gray-400)' }}>(optional)</span></label>
                    <input className="form-control" value={renewForm.notes}
                      onChange={e => setRenewForm(p => ({ ...p, notes:e.target.value }))}
                      placeholder="e.g. Project ended, position eliminated" />
                  </div>
                  <div style={{ display:'flex', gap:10, marginTop:12 }}>
                    <button
                      style={{ background:'#ea580c', color:'white', border:'none', borderRadius:8, padding:'7px 16px', fontSize:13, fontWeight:600, cursor: contractActionSaving ? 'not-allowed' : 'pointer', opacity: contractActionSaving ? 0.6 : 1 }}
                      onClick={handleNotRenewing} disabled={contractActionSaving}>
                      {contractActionSaving ? 'Saving…' : 'Confirm Non-Renewal'}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setContractAction(null)}>Cancel</button>
                  </div>
                </div>
              )}

              {/* Success message */}
              {contractActionMsg && (
                <div className="alert alert-success mb-4" style={{ marginBottom:16 }}>
                  <CheckCircle size={14} /> {contractActionMsg}
                </div>
              )}

              {/* Contract history table */}
              <div style={{ fontWeight:600, fontSize:14, marginBottom:10, color:'var(--gray-700)' }}>
                Contract History
                {!contractsLoading && (
                  <span style={{ fontWeight:400, color:'var(--gray-400)', fontSize:13, marginLeft:8 }}>({contracts.length})</span>
                )}
              </div>
              {contractsLoading ? (
                <div style={{ color:'var(--gray-400)', fontSize:13, padding:'14px 0' }}>Loading…</div>
              ) : contracts.length === 0 ? (
                <div style={{ color:'var(--gray-500)', fontSize:13, padding:'16px', background:'var(--gray-50)', borderRadius:8, textAlign:'center' }}>
                  No contract actions recorded yet. Use the buttons above to log a renewal, conversion, or non-renewal.
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Action</th>
                        <th>Type</th>
                        <th>Start Date</th>
                        <th>End Date</th>
                        <th>By</th>
                        <th>Notes</th>
                        <th>Date Logged</th>
                      </tr>
                    </thead>
                    <tbody>
                      {contracts.map(c => (
                        <tr key={c.id}>
                          <td>
                            <span className={`badge ${c.action==='renewed'?'badge-blue':c.action==='converted'?'badge-green':c.action==='not_renewed'?'badge-red':'badge-gray'}`} style={{ fontSize:11 }}>
                              {c.action==='renewed'?'Renewed':c.action==='converted'?'Converted':c.action==='not_renewed'?'Not Renewing':'New'}
                            </span>
                          </td>
                          <td style={{ fontSize:13 }}>{c.contractType}</td>
                          <td style={{ fontSize:12, color:'var(--gray-600)' }}>{formatDateUAE(c.startDate) || '—'}</td>
                          <td style={{ fontSize:12, color:'var(--gray-600)' }}>{formatDateUAE(c.endDate) || '—'}</td>
                          <td style={{ fontSize:12, color:'var(--gray-500)' }}>{c.renewedBy || '—'}</td>
                          <td style={{ fontSize:12, color:'var(--gray-500)', maxWidth:160 }}>{c.notes || '—'}</td>
                          <td style={{ fontSize:12, color:'var(--gray-500)', whiteSpace:'nowrap' }}>{c.createdAt?.split('T')[0] || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          {tab !== 'documents' && tab !== 'insurance' && tab !== 'contracts' && (
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : (employee?.id ? 'Save Changes' : 'Add Employee')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
