import { useEffect, useMemo, useRef, useState } from 'react'

import { useCompanyContext } from './companyContextState.js'
import { HttpClientError } from './http.js'
import { createIdempotencyRecoveryStore } from './idempotencyRecovery.js'
import {
  createBranch,
  deleteBranch,
  readIdempotencyNamespaces,
  readIdempotencyStatus,
  updateBranch,
  updateCompany,
} from './organizationApi.js'
import { AdminInsurance } from './RecordsBenefits.jsx'

const logoLimit = 64 * 1024

function readLogo(file) {
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file?.type) || file.size > logoLimit) {
    throw new TypeError('Choose a PNG, JPG, or WebP logo no larger than 64 KB.')
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('The logo file could not be read.'))
    reader.readAsDataURL(file)
  })
}

function errorMessage(error) {
  if (!(error instanceof HttpClientError)) return 'The request failed. No changes were saved.'
  if (error.code === 'state_conflict') return 'Someone changed this record. Review the refreshed values before saving again.'
  if (error.code === 'branch_conflict') return 'This branch name or its retained records prevent the change.'
  if (error.code === 'idempotency_in_progress') return 'The branch request is still running. Keep this page open and retry shortly.'
  if (error.code === 'idempotency_conflict') return 'This saved request key belongs to different data. Review the current branches before trying again.'
  return error.message
}

function CompanyForm({ authentication }) {
  const organization = useCompanyContext()
  const [draft, setDraft] = useState(organization.company)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      const company = await updateCompany(authentication, {
        name: draft.name,
        sector: draft.sector,
        nafisQuotaPercent: draft.nafisQuotaPercent,
        enableNafis: draft.enableNafis,
        expectedUpdatedAt: organization.company.updatedAt,
      })
      organization.replaceCompany(company)
      setMessage('Company settings saved.')
    } catch (error) {
      if (error instanceof HttpClientError && error.code === 'state_conflict') {
        await organization.refresh().catch(() => {})
      }
      setMessage(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="settings-form restoration-settings-card card" onSubmit={submit}>
      <div className="card-header"><h3>Employer information</h3></div>
      <div className="card-body employee-form-grid">
        <label>Company name<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} required /></label>
        <label>Industry sector<input value={draft.sector} onChange={(event) => setDraft({ ...draft, sector: event.target.value })} /></label>
        <label>Required Emiratization rate (%)<input value={draft.nafisQuotaPercent} inputMode="decimal" onChange={(event) => setDraft({ ...draft, nafisQuotaPercent: event.target.value })} required /></label>
        <label className="checkbox"><input type="checkbox" checked={draft.enableNafis} onChange={(event) => setDraft({ ...draft, enableNafis: event.target.checked })} /> Enable Nafis</label>
      </div>
      <div className="card-footer"><button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save employer information'}</button>{message && <p role="status">{message}</p>}</div>
    </form>
  )
}

function BranchForm({ authentication }) {
  const organization = useCompanyContext()
  const [draft, setDraft] = useState(organization.selectedBranch)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [logoMessage, setLogoMessage] = useState('')
  const logoInput = useRef(null)

  const field = (name) => (event) => setDraft({
    ...draft,
    [name]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
  })

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      const branch = await updateBranch(authentication, draft.id, {
        name: draft.name,
        molEmployerId: draft.molEmployerId,
        defaultBankRoutingCode: draft.defaultBankRoutingCode,
        address: draft.address,
        contactEmail: draft.contactEmail,
        defaultSalaryDay: draft.defaultSalaryDay === '' ? null : Number(draft.defaultSalaryDay),
        workLocationType: draft.workLocationType,
        freeZoneName: draft.freeZoneName,
        logoUrl: draft.logoUrl,
        enableStaffingRules: draft.enableStaffingRules,
        enableBiometricImport: draft.enableBiometricImport,
        expectedUpdatedAt: organization.selectedBranch.updatedAt,
      })
      organization.replaceBranch(branch)
      setMessage('Branch settings saved.')
    } catch (error) {
      if (error instanceof HttpClientError && error.code === 'state_conflict') {
        await organization.refresh().catch(() => {})
      }
      setMessage(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true)
      setMessage('Select delete again to confirm.')
      return
    }
    setSaving(true)
    setMessage('')
    try {
      await deleteBranch(authentication, draft.id, organization.selectedBranch.updatedAt)
      organization.removeBranch(draft.id)
    } catch (error) {
      if (error instanceof HttpClientError && error.code === 'state_conflict') {
        await organization.refresh().catch(() => {})
      }
      setMessage(errorMessage(error))
      setConfirmDelete(false)
    } finally {
      setSaving(false)
    }
  }

  const chooseLogo = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setLogoMessage('')
    try {
      const logoUrl = await readLogo(file)
      setDraft((current) => ({ ...current, logoUrl }))
    } catch (error) {
      setLogoMessage(error.message)
    } finally {
      event.target.value = ''
    }
  }

  return (
    <form className="settings-form restoration-settings-sections" onSubmit={submit}>
      <section className="card"><div className="card-header"><h3>Branch details</h3></div><div className="card-body employee-form-grid">
        <label>Branch or entity label<input value={draft.name} onChange={field('name')} required /></label>
        <label>MOL employer ID<input value={draft.molEmployerId} onChange={field('molEmployerId')} /></label>
        <label>Contact email<input type="email" value={draft.contactEmail} onChange={field('contactEmail')} /></label>
        <label className="full-row">Address<textarea value={draft.address} onChange={field('address')} /></label>
      </div></section>
      <section className="card"><div className="card-header"><h3>Payroll settings</h3></div><div className="card-body employee-form-grid">
        <label>Default bank routing code<input value={draft.defaultBankRoutingCode} onChange={field('defaultBankRoutingCode')} /></label>
        <label>Default salary payment day<input type="number" min="1" max="31" value={draft.defaultSalaryDay ?? ''} onChange={field('defaultSalaryDay')} /></label>
        <div className="company-logo-field full-row"><span>Company logo for payslips and letters</span>{draft.logoUrl && <img src={draft.logoUrl} alt="Company logo preview" />}
          <input ref={logoInput} className="sr-only" aria-label="Logo file" type="file" accept="image/png,image/jpeg,image/webp" onChange={chooseLogo} />
          <div className="actions"><button type="button" className="secondary" onClick={() => logoInput.current?.click()}>{draft.logoUrl ? 'Replace logo' : 'Upload logo'}</button><button type="button" className="secondary" disabled={!draft.logoUrl} onClick={() => setDraft({ ...draft, logoUrl: '' })}>Remove logo</button></div>
          {logoMessage && <p role="status">{logoMessage}</p>}
        </div>
      </div></section>
      <section className="card"><div className="card-header"><h3>Work location and jurisdiction</h3></div><div className="card-body employee-form-grid">
        <label>Work location<select value={draft.workLocationType} onChange={field('workLocationType')}><option value="mainland">Mainland</option><option value="free_zone">Free zone</option></select></label>
        {draft.workLocationType === 'free_zone' && <label>Free zone name<input value={draft.freeZoneName} onChange={field('freeZoneName')} /></label>}
      </div></section>
      <section className="card"><div className="card-header"><h3>Modules and features</h3></div><div className="card-body"><label className="checkbox"><input type="checkbox" checked={draft.enableStaffingRules} onChange={field('enableStaffingRules')} /> Enable staffing rules</label></div></section>
      <div className="settings-actions card">
        <button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save branch'}</button>
        <button type="button" className="danger" disabled={saving} onClick={remove}>{confirmDelete ? 'Confirm delete' : 'Delete branch'}</button>
        {message && <p role="status">{message}</p>}
      </div>
    </form>
  )
}

function CreateBranchForm({ authentication }) {
  const organization = useCompanyContext()
  const refreshOrganization = organization.refresh
  const recovery = useMemo(() => createIdempotencyRecoveryStore({ localStorage: globalThis.localStorage }), [])
  const [name, setName] = useState('')
  const [namespace, setNamespace] = useState(null)
  const [recoveryReady, setRecoveryReady] = useState(false)
  const [intentKey, setIntentKey] = useState(null)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [reviewedConflict, setReviewedConflict] = useState(false)
  const [unresolvedKeys, setUnresolvedKeys] = useState([])
  const [requestInProgress, setRequestInProgress] = useState(false)
  const [confirmedRecoveredIntent, setConfirmedRecoveredIntent] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    readIdempotencyNamespaces(authentication, { signal: controller.signal })
      .then(async (namespaces) => {
        setNamespace(namespaces.current)
        const completed = []
        const unresolved = []
        let inProgress = false
        for (const entry of recovery.accepted(namespaces.accepted)) {
          const state = await readIdempotencyStatus(authentication, entry.key, { signal: controller.signal })
          if (state === 'completed') {
            completed.push(entry.key)
          } else if (state === 'not_found') {
            unresolved.push(entry.key)
          } else {
            inProgress = true
          }
        }
        if (completed.length) {
          await refreshOrganization()
          completed.forEach((key) => recovery.complete(key))
        }
        setUnresolvedKeys(unresolved)
        setRequestInProgress(inProgress)
        if (inProgress) {
          setMessage('A previous branch request is still running. No new request will be sent yet.')
        } else if (unresolved.length) {
          setMessage('A previous branch request did not commit. Review this form and submit once to confirm a new request.')
        }
        setRecoveryReady(true)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setMessage('Recovery is unavailable. No branch can be submitted yet.')
        }
      })
    return () => controller.abort()
  }, [authentication, recovery, refreshOrganization])

  const submit = async (event) => {
    event.preventDefault()
    if (!namespace || !recoveryReady || requestInProgress) {
      setMessage('Recovery is unavailable. No branch was submitted.')
      return
    }
    if (unresolvedKeys.length && !confirmedRecoveredIntent) {
      setConfirmedRecoveredIntent(true)
      setMessage('Submit once more to confirm that this is still the request you want to make.')
      return
    }
    setSaving(true)
    setMessage('')
    let key = intentKey
    if (reviewedConflict) {
      key = null
      setReviewedConflict(false)
    }
    if (unresolvedKeys.length) {
      unresolvedKeys.forEach((key) => recovery.complete(key))
      setUnresolvedKeys([])
      setConfirmedRecoveredIntent(false)
    }
    if (key === null) {
      key = recovery.begin(namespace)
      setIntentKey(key)
    }
    try {
      const result = await createBranch(authentication, { name }, { idempotencyKey: key })
      await organization.refresh(result.data.id)
      recovery.complete(key)
      setIntentKey(null)
      setName('')
      setMessage(result.replayed ? 'The existing branch result was recovered.' : 'Branch created.')
    } catch (error) {
      const terminal = error instanceof HttpClientError && [
        'invalid_request', 'validation_failed', 'branch_conflict', 'idempotency_conflict',
      ].includes(error.code)
      if (terminal) {
        recovery.complete(key)
        setIntentKey(null)
      }
      if (error instanceof HttpClientError && error.code === 'idempotency_conflict') {
        await organization.refresh().catch(() => {})
        setReviewedConflict(true)
      }
      setMessage(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="settings-form" onSubmit={submit}>
      <h3>Create branch</h3>
      <label>Name<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
      <button type="submit" disabled={saving || !namespace || !recoveryReady || requestInProgress}>{saving ? 'Creating...' : 'Create branch'}</button>
      {message && <p role="status">{message}</p>}
    </form>
  )
}

export default function OrganizationSettings({ authentication }) {
  const organization = useCompanyContext()
  if (!organization.company || !organization.selectedBranch) return null
  return (
    <section className="organization-settings" aria-labelledby="organization-settings-title">
      <h2 id="organization-settings-title">Organization settings</h2>
      <CompanyForm key={organization.company.updatedAt} authentication={authentication} />
      <BranchForm key={`${organization.selectedBranch.id}-${organization.selectedBranch.updatedAt}`} authentication={authentication} />
      <section className="card" aria-label="Medical insurance policies"><AdminInsurance authentication={authentication} branchId={organization.selectedBranch.id} policiesOnly /></section>
      <section className="card"><div className="card-header"><h3>WPS and SIF file reference</h3></div></section>
      <CreateBranchForm authentication={authentication} />
    </section>
  )
}
