import { useEffect, useState } from 'react'
import { readDashboard } from './dashboardApi.js'
import { readDashboardPanel } from './dashboardPanels.js'
import { readBranch, readCompany } from './organizationApi.js'
import AdminWorkspaceSummary from './AdminWorkspaceSummary.jsx'
import ReportPreview from './ReportPreview.jsx'
import { readClinicalCredentials, readClinicalWorkforceSummary, readClinicalWorkforceDetails } from './portalProjectionsApi.js'

const credentialStatuses = { credentialsValid: 'valid', credentialsExpiring: 'expiring', credentialsExpired: 'expired' }

function CredentialDetails({ authentication, branchId, card, go }) {
  const [state, setState] = useState({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const key = `${branchId}:${card.code}:${card.value}:${attempt}`
  useEffect(() => {
    let active = true
    readClinicalCredentials(authentication, branchId, credentialStatuses[card.code]).then((items) => {
      if (items.length !== Number(card.value)) throw new Error('Credential source changed')
      if (active) setState({ key, status: 'ready', items })
    }).catch(() => { if (active) setState({ key, status: 'unavailable' }) })
    return () => { active = false }
  }, [authentication, branchId, card.code, card.value, key])
  const view = state.key === key ? state : { status: 'loading' }
  return <section className="card clinical-credential-details"><div className="card-header"><h3>{card.label}</h3><a href={go(card.drillDown.target)}>Open work area</a></div>
    {view.status === 'loading' && <p role="status">Loading credential details...</p>}
    {view.status === 'unavailable' && <p role="alert">Credential details are unavailable or have changed. Refresh the dashboard for current totals. <button type="button" onClick={() => setAttempt(attempt + 1)}>Retry details</button></p>}
    {view.status === 'ready' && (view.items.length === 0 ? <div className="empty-state">No credentials in this group.</div> : <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Credential</th><th>Expiry date</th><th>Status</th></tr></thead><tbody>{view.items.map((item) => <tr key={item.id}><td>{item.employeeName}</td><td>{item.sourceType.replaceAll('_', ' ')}</td><td>{item.expiryDate ?? 'No expiry date'}</td><td>{item.status}</td></tr>)}</tbody></table></div>)}
  </section>
}

const workforceLabels = { activeStaff: 'Active staff', credentialCompliance: 'Credential compliance', coverage: "Today's coverage", probation: 'On probation', newJoiners: 'New joiners this month', birthdays: 'Birthdays this month', onLeaveToday: 'On leave today', pendingLeave: 'Pending leave requests', onDutyNow: 'On duty now' }

function WorkforceDetails({ authentication, branchId, card, expectedCount }) {
  const [state, setState] = useState({ status: 'loading' })
  const key = `${branchId}:${card.code}:${expectedCount}`
  useEffect(() => {
    let active = true
    readClinicalWorkforceDetails(authentication, branchId, card.code).then((items) => {
      if (items.length !== expectedCount) throw new Error('Clinical source changed')
      if (active) setState({ key, status: 'ready', items })
    }).catch(() => { if (active) setState({ key, status: 'error' }) })
    return () => { active = false }
  }, [authentication, branchId, card.code, expectedCount, key])
  const view = state.key === key ? state : { status: 'loading' }
  return <section className="card clinical-workforce-details"><div className="card-header"><h3>{card.label}</h3></div>{view.status === 'loading' ? <p role="status">Loading staff details...</p> : view.status === 'error' ? <p role="alert">Details are unavailable or have changed. Refresh the clinical dashboard for current totals.</p> : view.items.length === 0 ? <div className="empty-state">No records in this group.</div> : <div className="table-wrap"><table><thead><tr><th>Name</th><th>Job title</th><th>Department</th><th>Status</th><th>Date</th><th>Details</th></tr></thead><tbody>{view.items.map((item) => <tr key={item.id}><td>{item.employeeName}</td><td>{item.jobTitle || 'Not assigned'}</td><td>{item.department || 'Unassigned'}</td><td>{item.status.replaceAll('_', ' ')}</td><td>{item.sourceDate ?? 'Not applicable'}</td><td>{item.sourceLabel}{item.sourceTime && new Date(item.sourceTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' })}</td></tr>)}</tbody></table></div>}</section>
}

function ClinicalOverview({ authentication, branchId, dashboard, go, onRefresh }) {
  const [state, setState] = useState({ status: 'loading' })
  const [drill, setDrill] = useState(null)
  const key = `${branchId}:${dashboard.businessDate}`
  useEffect(() => {
    let active = true
    Promise.all([readClinicalWorkforceSummary(authentication, branchId), readBranch(authentication, branchId)]).then(([summary, branch]) => {
      if (summary.businessDate !== dashboard.businessDate) throw new Error('Clinical date changed')
      if (active) setState({ key, status: 'ready', summary, branch })
    }).catch(() => { if (active) setState({ key, status: 'error' }) })
    return () => { active = false }
  }, [authentication, branchId, dashboard.businessDate, key])
  const view = state.key === key ? state : { status: 'loading' }
  const counts = view.summary?.counts
  const cards = Object.entries(workforceLabels).map(([code, label]) => ({ code, label,
    value: !counts ? 'not_available' : code === 'credentialCompliance' ? counts[code] ? Math.round(view.summary.compliant / counts[code] * 100) : 'No credentials' : code === 'coverage' ? counts[code] ? Math.round(view.summary.rostered / counts[code] * 100) : 0 : counts[code],
    unit: ['credentialCompliance', 'coverage'].includes(code) ? 'percent' : 'employees', severity: 'info',
  }))
  cards.splice(2, 0, ...dashboard.cards.filter((card) => ['credentialsExpiring', 'credentialsExpired'].includes(card.code)))
  if (view.branch?.enableStaffingRules) cards.push(dashboard.cards.find((card) => card.code === 'staffingValidation'))
  const selected = cards.find((card) => card.code === drill)
  return <>
    <div className="restored-toolbar"><button type="button" className="btn btn-outline" onClick={onRefresh}>Refresh clinical dashboard</button></div>
    {view.status === 'loading' && <p role="status">Loading workforce sources...</p>}{view.status === 'error' && <p role="alert">Clinical workforce sources are unavailable. Refresh to try again.</p>}
    <div className="stats-grid dashboard-cards clinical-cards">{cards.map((card) => <article className="stat-card" key={card.code} data-card-code={card.code} data-severity={card.severity}><h3 className="stat-label">{card.label}</h3><p className="stat-value">{typeof card.value === 'string' && card.value !== 'not_available' ? card.value : displayValue(card)}</p><button type="button" className="btn btn-ghost" disabled={card.value === 'not_available'} aria-expanded={drill === card.code} onClick={() => setDrill(drill === card.code ? null : card.code)}>View details</button></article>)}</div>
    {selected && (credentialStatuses[selected.code] ? <CredentialDetails authentication={authentication} branchId={branchId} card={selected} go={go} /> : Object.hasOwn(workforceLabels, selected.code) ? <WorkforceDetails authentication={authentication} branchId={branchId} card={selected} expectedCount={counts[selected.code]} /> : <Panel authentication={authentication} branchId={branchId} reportId="staffingCompliance" title="Staffing ratios" filters={{ period: dashboard.businessDate.slice(0, 7) }} />)}
    {view.status === 'ready' && <section className="card"><div className="card-header"><h3>Department headcount</h3></div><div className="table-wrap"><table><thead><tr><th>Department</th><th>Headcount</th><th>Credentialled staff</th><th>Compliance</th><th>Min staff</th><th>Coverage</th></tr></thead><tbody>{view.summary.departments.map((department) => <tr key={department.department}><td>{department.department || 'Unassigned'}</td><td>{department.headcount}</td><td>{department.credentialled}</td><td>{Math.round(department.credentialled / department.headcount * 100)}%</td><td>{view.branch.enableStaffingRules ? department.minStaff || 'No minimum' : 'Not enabled'}</td><td>{department.rostered} / {department.headcount}</td></tr>)}{view.summary.departments.length === 0 && <tr><td colSpan={6}>No active staff in this branch.</td></tr>}</tbody></table></div></section>}
  </>
}

const titles = { admin: 'Dashboard', clinical: 'Clinical dashboard', self: 'My dashboard' }
const targets = { employees: 'employees', payroll: 'payroll', wps: 'payroll', nafis: 'reports', recordsBenefits: 'employees', developmentAssets: 'training', roster: 'roster', attendance: 'attendance' }
function displayValue(card) {
  if (card.value === 'not_available') return 'Not available'
  if (card.unit === 'AED') return `AED ${card.value}`
  if (card.unit === 'percent') return `${card.value}%`
  return `${card.value}`
}
function Panel({ authentication, branchId, reportId, title, filters }) {
  const [state, setState] = useState({ status: 'loading' })
  const key = JSON.stringify([branchId, reportId, filters])
  useEffect(() => {
    let active = true
    readDashboardPanel(authentication, branchId, reportId, JSON.parse(key)[2]).then((data) => {
      if (active) setState({ key, status: 'ready', data })
    }).catch(() => { if (active) setState({ key, status: 'unavailable' }) })
    return () => { active = false }
  }, [authentication, branchId, reportId, key])
  if (state.key !== key || state.status === 'loading') return <section className="card card-body"><h3>{title}</h3><p>Loading...</p></section>
  if (state.status === 'unavailable') return <section className="card card-body"><h3>{title}</h3><p role="alert">This dashboard source is unavailable.</p></section>
  return <ReportPreview report={state.data} title={title} />
}
export default function Dashboard({ authentication, branchId, kind }) {
  const [state, setState] = useState({ status: 'loading' })
  const [branch, setBranch] = useState(null)
  const [company, setCompany] = useState(null)
  const [revision, setRevision] = useState(0)
  const requestKey = `${kind}:${branchId ?? 'self'}:${revision}`
  useEffect(() => {
    let active = true
    readDashboard(authentication, kind, branchId).then((data) => {
      if (active) setState({ status: 'ready', data, requestKey })
    }).catch(() => { if (active) setState({ status: 'unavailable', requestKey }) })
    if (kind === 'admin') Promise.all([readBranch(authentication, branchId), readCompany(authentication)]).then(([value, employer]) => { if (active) { setBranch({ key: requestKey, value }); setCompany({ key: requestKey, value: employer }) } }).catch(() => {})
    return () => { active = false }
  }, [authentication, branchId, kind, requestKey])
  const view = state.requestKey === requestKey ? state : { status: 'loading' }
  const go = (target) => `/admin/${targets[target] ?? 'tasks'}`
  const currentBranch = branch?.key === requestKey ? branch.value : null
  const currentCompany = company?.key === requestKey ? company.value : null
  const period = view.data?.businessDate.slice(0, 7)
  return <section className="dashboard restoration-dashboard" data-dashboard-kind={kind} data-dashboard-status={view.status}>
    <div className="module-toolbar"><div><h2>{titles[kind]}</h2><p>{kind === 'clinical' ? 'Clinical staffing and credential overview' : kind === 'admin' ? 'Workforce, payroll, and compliance overview' : 'Your work summary'}</p></div>{view.status === 'ready' && <time dateTime={view.data.businessDate}>{view.data.businessDate}</time>}</div>
    {view.status === 'loading' && <p>Loading dashboard...</p>}{view.status === 'unavailable' && <p role="alert">Dashboard data is unavailable.</p>}
    {view.status === 'ready' && <>
      {kind === 'admin' && <AdminWorkspaceSummary key={requestKey} authentication={authentication} branchId={branchId} businessDate={view.data.businessDate} branch={currentBranch} dashboard={view.data}>{currentCompany?.enableNafis && <Panel authentication={authentication} branchId={branchId} reportId="emiratization" title="Emiratization / Nafis compliance" filters={{ period }} />}<Panel authentication={authentication} branchId={branchId} reportId="payrollCost" title="Payroll cost trend" filters={{}} /></AdminWorkspaceSummary>}
      {kind === 'clinical' ? <ClinicalOverview key={requestKey} authentication={authentication} branchId={branchId} dashboard={view.data} go={go} onRefresh={() => setRevision(revision + 1)} /> : kind === 'self' && <div className="stats-grid dashboard-cards">{view.data.cards.map((card) => <article className="stat-card" key={card.code} data-card-code={card.code} data-severity={card.severity}><h3 className="stat-label">{card.label}</h3><p className="stat-value">{displayValue(card)}</p>{card.comparison && <small>{card.comparison.label}: {card.comparison.value} {card.comparison.unit}</small>}<a href={`#${card.drillDown.target}`}>View details</a></article>)}</div>}
      {kind === 'clinical' && view.data.cards.filter((card) => ['warning', 'critical'].includes(card.severity)).map((card) => <div className="alert alert-warning" key={card.code}><strong>{card.label}: {displayValue(card)}</strong><a href={go(card.drillDown.target)}>Review</a></div>)}
      {kind === 'clinical' && <><Panel authentication={authentication} branchId={branchId} reportId="staffingCompliance" title="Staffing compliance" filters={{ period }} /><Panel authentication={authentication} branchId={branchId} reportId="documentExpiry" title="Credential and document expiry alerts" filters={{ to: new Date(Date.parse(`${view.data.businessDate}T00:00:00Z`) + 90 * 86400000).toISOString().slice(0, 10) }} /></>}
    </>}
  </section>
}
