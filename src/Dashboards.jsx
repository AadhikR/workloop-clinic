import { useEffect, useState } from 'react'
import { readDashboard } from './dashboardApi.js'
import { readDashboardPanel } from './dashboardPanels.js'
import { readBranch } from './organizationApi.js'
import ReportPreview from './ReportPreview.jsx'

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
  const [drill, setDrill] = useState(null)
  const requestKey = `${kind}:${branchId ?? 'self'}`
  useEffect(() => {
    let active = true
    readDashboard(authentication, kind, branchId).then((data) => {
      if (active) setState({ status: 'ready', data, requestKey })
    }).catch(() => { if (active) setState({ status: 'unavailable', requestKey }) })
    if (kind === 'admin') readBranch(authentication, branchId).then((value) => { if (active) setBranch({ key: requestKey, value }) }).catch(() => {})
    return () => { active = false }
  }, [authentication, branchId, kind, requestKey])
  const view = state.requestKey === requestKey ? state : { status: 'loading' }
  const go = (target) => `/admin/${targets[target] ?? 'tasks'}`
  const currentBranch = branch?.key === requestKey ? branch.value : null
  const period = view.data?.businessDate.slice(0, 7)
  return <section className="dashboard restoration-dashboard" data-dashboard-kind={kind} data-dashboard-status={view.status}>
    <div className="module-toolbar"><div><h2>{titles[kind]}</h2><p>{kind === 'clinical' ? 'Clinical staffing and credential overview' : kind === 'admin' ? 'Workforce, payroll, and compliance overview' : 'Your work summary'}</p></div>{view.status === 'ready' && <time dateTime={view.data.businessDate}>{view.data.businessDate}</time>}</div>
    {view.status === 'loading' && <p>Loading dashboard...</p>}{view.status === 'unavailable' && <p role="alert">Dashboard data is unavailable.</p>}
    {view.status === 'ready' && <>
      {kind === 'admin' && currentBranch && <section className="card"><div className="card-header"><h3>Setup checklist</h3></div><ul className="dashboard-checklist">{[[!!currentBranch.molEmployerId, 'MOL employer ID', '/admin/company-settings'], [!!currentBranch.defaultBankRoutingCode, 'Bank routing code', '/admin/company-settings'], [Number(view.data.cards.find((card) => card.code === 'activeHeadcount')?.value) > 0, 'Employee profiles', '/admin/employees']].map(([done, label, href]) => <li key={label}><span aria-label={done ? 'Complete' : 'Action required'}>{done ? '✓' : '○'}</span><a href={href}>{label}</a></li>)}</ul></section>}
      <div className="stats-grid dashboard-cards">{view.data.cards.map((card) => <article className="stat-card" key={card.code} data-card-code={card.code} data-severity={card.severity}><h3 className="stat-label">{card.label}</h3><p className="stat-value">{displayValue(card)}</p>{card.comparison && <small>{card.comparison.label}: {card.comparison.value} {card.comparison.unit}</small>}{kind === 'clinical' ? <button type="button" className="btn btn-ghost" aria-expanded={drill === card.code} onClick={() => setDrill(drill === card.code ? null : card.code)}>View details</button> : <a href={kind === 'self' ? `#${card.drillDown.target}` : go(card.drillDown.target)}>View details</a>}</article>)}</div>
      {kind !== 'self' && view.data.cards.filter((card) => ['warning', 'critical'].includes(card.severity)).map((card) => <div className="alert alert-warning" key={card.code}><strong>{card.label}: {displayValue(card)}</strong><a href={go(card.drillDown.target)}>Review</a></div>)}
      {kind === 'admin' && <><Panel authentication={authentication} branchId={branchId} reportId="emiratization" title="Emiratization / Nafis compliance" filters={{ period }} /><Panel authentication={authentication} branchId={branchId} reportId="payrollCost" title="Payroll cost trend and recent payroll runs" filters={{}} /></>}
      {kind === 'clinical' && drill && <section className="card card-body"><h3>{view.data.cards.find((card) => card.code === drill)?.label}</h3><p>{displayValue(view.data.cards.find((card) => card.code === drill))}</p><a href={go(view.data.cards.find((card) => card.code === drill).drillDown.target)}>Open work area</a></section>}
      {kind === 'clinical' && <><Panel authentication={authentication} branchId={branchId} reportId="staffingCompliance" title="Staffing compliance" filters={{ period }} /><Panel authentication={authentication} branchId={branchId} reportId="documentExpiry" title="Credential and document expiry alerts" filters={{ to: new Date(Date.parse(`${view.data.businessDate}T00:00:00Z`) + 90 * 86400000).toISOString().slice(0, 10) }} /></>}
    </>}
  </section>
}
