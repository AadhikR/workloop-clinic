import { useEffect, useState } from 'react'

import { readEmployeeSelf, updateEmployeeSelfContact } from './employeeApi.js'

const sections = [
  ['Personal', [['Name', 'name'], ['Employee number', 'empNo'], ['Date of birth', 'dateOfBirth'], ['Nationality', 'nationality'], ['Personal email', 'personalEmail'], ['UAE phone', 'phone']]],
  ['Job', [['Job title', 'jobTitle'], ['Department', 'department'], ['Reporting manager', 'reportingManager.name'], ['Work location', 'workLocationType']]],
  ['Salary', [['Basic salary', 'basicSalary', 'money'], ['Housing allowance', 'housingAllowance', 'money'], ['Transport allowance', 'transportAllowance', 'money'], ['Other allowances', 'otherAllowances', 'money']]],
  ['Bank', [['Bank', 'bankName'], ['Account holder', 'bankAccountHolder'], ['Routing code', 'bankRoutingCode'], ['IBAN', 'iban']]],
  ['UAE compliance', [['Visa type', 'visaType'], ['Visa number', 'visaNumber'], ['Visa expiry', 'visaExpiry'], ['Passport', 'passportNumber'], ['Passport expiry', 'passportExpiry'], ['Emirates ID', 'emiratesId'], ['Emirates ID expiry', 'emiratesIdExpiry'], ['Labour card', 'labourCardNumber'], ['Labour card expiry', 'labourCardExpiry']]],
  ['Employment', [['Status', 'employmentStatus'], ['Start date', 'employmentStartDate'], ['Probation end', 'probationEndDate'], ['Emergency contact', 'emergencyContactName'], ['Emergency phone', 'emergencyContactPhone']]],
]

function valueAt(employee, path, kind) {
  const value = path.split('.').reduce((current, key) => current?.[key], employee)
  if (value === null || value === undefined || value === '') return 'Not recorded'
  if (kind === 'money') return `AED ${value}`
  return String(value).replaceAll('_', ' ')
}

function expiryStatus(value) {
  if (!value) return 'none'
  const days = Math.ceil((new Date(`${value}T00:00:00+04:00`) - Date.now()) / 86400000)
  if (days < 0) return 'expired'
  if (days <= 30) return 'critical'
  if (days <= 90) return 'warning'
  return 'valid'
}

export default function EmployeeProfile({ authentication, onSignOut }) {
  const [employee, setEmployee] = useState(null)
  const [form, setForm] = useState(null)
  const [editing, setEditing] = useState(false)
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    const controller = new AbortController()
    readEmployeeSelf(authentication, { signal: controller.signal }).then((value) => {
      if (!controller.signal.aborted) {
        setEmployee(value)
        setForm({ phone: value.phone, personalEmail: value.personalEmail, emergencyContactName: value.emergencyContactName, emergencyContactPhone: value.emergencyContactPhone })
        setStatus('ready')
      }
    }).catch(() => { if (!controller.signal.aborted) setStatus('error') })
    return () => controller.abort()
  }, [authentication])

  const submit = async (event) => {
    event.preventDefault()
    setStatus('saving')
    try {
      const updated = await updateEmployeeSelfContact(authentication, { ...form, expectedUpdatedAt: employee.updatedAt })
      setEmployee(updated)
      setEditing(false)
      setStatus('saved')
    } catch {
      setStatus('error-saving')
    }
  }

  if (status === 'loading') return <section className="employee-profile"><p>Loading your profile...</p></section>
  if (!employee) return <section className="employee-profile"><h2>Profile</h2><p role="alert">Your profile is unavailable.</p></section>

  return (
    <section className="employee-profile" aria-labelledby="employee-profile-title">
      <div className="employee-section-heading"><div><h2 id="employee-profile-title">Profile</h2><p>Review the information held by HR. You can update contact details only.</p></div><button type="button" className="secondary" onClick={() => setEditing((value) => !value)}>{editing ? 'Cancel edit' : 'Edit contact details'}</button></div>
      {status === 'saved' && <p className="feedback success" role="status">Contact details saved.</p>}
      {status === 'error-saving' && <p className="feedback danger" role="alert">Contact details could not be saved.</p>}
      <div className="employee-profile-sections">{sections.map(([title, fields]) => (
        <section className="employee-panel" key={title}><h3>{title}</h3><dl>{fields.map(([label, path, kind]) => <div key={path}><dt>{label}</dt><dd>{valueAt(employee, path, kind)}{path.endsWith('Expiry') && <span className="status-pill" data-status={expiryStatus(employee[path])}>{expiryStatus(employee[path])}</span>}</dd></div>)}</dl></section>
      ))}</div>
      {editing && <form className="employee-contact-form" onSubmit={submit}>
        <h3>Edit contact details</h3>
        <div className="employee-form-grid">
          <label>Personal email<input type="email" required value={form.personalEmail} onChange={(event) => setForm({ ...form, personalEmail: event.target.value })} /></label>
          <label>UAE phone<input type="tel" required pattern="(?:\\+971|0)5[0-9]{8}" placeholder="+971501234567" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
          <label>Emergency contact name<input required maxLength="180" value={form.emergencyContactName} onChange={(event) => setForm({ ...form, emergencyContactName: event.target.value })} /></label>
          <label>Emergency contact phone<input type="tel" required pattern="(?:\\+971|0)5[0-9]{8}" value={form.emergencyContactPhone} onChange={(event) => setForm({ ...form, emergencyContactPhone: event.target.value })} /></label>
        </div>
        <button type="submit" disabled={status === 'saving'}>{status === 'saving' ? 'Saving...' : 'Save contact details'}</button>
      </form>}
      <div className="employee-signout"><button type="button" className="danger" onClick={onSignOut}>Sign out</button></div>
    </section>
  )
}
