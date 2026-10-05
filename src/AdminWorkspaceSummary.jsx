import { useEffect, useState } from 'react'
import { readAdminWorkspaceSummary } from './portalProjectionsApi.js'
import { readCollectionPages } from './collectionPages.js'
import { readPayrollRuns } from './payrollApi.js'
import { PortalTable, SummaryCards } from './PortalUi.jsx'

const warnings = {
  probation: ['Probation ending or overdue', 'employees'], contracts: ['Contracts ending or overdue', 'employees'],
  certifications: ['Certifications expiring or recently expired', 'training'], requests: ['Pending HR requests', 'requests'],
  appraisals: ['Appraisals awaiting review', 'appraisals'], documents: ['Identity documents expiring or overdue', 'employees'],
  insurance: ['Employee insurance expiring or recently expired', 'employees'], policyRenewals: ['Insurance policies due for renewal', 'company-settings'],
  payrollApproval: ['Payroll runs awaiting approval', 'payroll'], wpsOverdue: ['Overdue WPS confirmation', 'payroll'],
}

export default function AdminWorkspaceSummary({ authentication, branchId, businessDate, branch, dashboard, children }) {
  const [state, setState] = useState({ status: 'loading' })
  const key = `${branchId}:${businessDate}`
  useEffect(() => {
    let active = true
    Promise.all([
      readAdminWorkspaceSummary(authentication, branchId),
      readCollectionPages((cursor) => readPayrollRuns(authentication, branchId, { limit: 100, cursor })),
    ]).then(([summary, runs]) => {
      if (summary.businessDate !== businessDate || summary.payrollRuns !== runs.length || summary.activeEmployees !== dashboard.cards.find((card) => card.code === 'activeHeadcount')?.value) throw new Error('Workspace source changed')
      if (active) setState({ key, status: 'ready', summary, runs: [...runs].sort((a, b) => b.period.localeCompare(a.period) || b.sequence - a.sequence) })
    }).catch(() => { if (active) setState({ key, status: 'error' }) })
    return () => { active = false }
  }, [authentication, branchId, businessDate, dashboard, key])
  const view = state.key === key ? state : { status: 'loading' }
  if (view.status !== 'ready') return <section className="card card-body"><h3>Work requiring attention</h3>{view.status === 'loading' ? <p role="status">Loading administrator workspace...</p> : <p role="alert">Administrator workspace sources are unavailable or have changed. Refresh the dashboard to try again.</p>}</section>
  const { summary, runs } = view
  const steps = [[!!branch?.molEmployerId && !!branch?.defaultBankRoutingCode, 'Complete company settings', '/admin/company-settings'], [summary.activeEmployees > 0, 'Add employees', '/admin/employees'], [runs.some((run) => run.runStatus === 'generated'), 'Generate payroll', '/admin/payroll']]
  return <>
    <div className="dashboard-attention">{Object.entries(summary.alerts).filter(([, count]) => count > 0).map(([code, count]) => <div className="alert alert-warning" key={code}><strong>{warnings[code][0]} · {count}</strong><a href={`/admin/${warnings[code][1]}`}>Review</a></div>)}</div>
    {branch && steps.some(([done]) => !done) && <section className="card"><div className="card-header"><h3>Setup checklist</h3></div><ul className="dashboard-checklist">{steps.map(([done, label, href]) => <li key={label}><span aria-label={done ? 'Complete' : 'Action required'}>{done ? '✓' : '○'}</span><a href={href}>{label}</a></li>)}</ul></section>}
    <SummaryCards items={[
      { label: 'Active employees', value: summary.activeEmployees },
      { label: 'Payroll runs', value: summary.payrollRuns, detail: `${summary.draftPayrolls} drafts` },
      { label: 'SIF generated', value: summary.sifGenerated },
      { label: 'Document expiry alerts', value: summary.alerts.documents },
      { label: 'Insurance alerts', value: summary.alerts.insurance + summary.alerts.policyRenewals, detail: `${summary.insurancePolicies} policies` },
    ]} />
    {children}
    <section className="card"><div className="card-header"><h3>Recent payroll runs</h3><a href="/admin/payroll">View all payroll</a></div><div className="card-body dashboard-payroll-status">{dashboard.cards.filter((card) => ['finalizedPayroll', 'wpsStatus'].includes(card.code)).map((card) => <p key={card.code}>{card.label}: <strong>{card.value === 'not_available' ? 'Not available' : `${card.unit === 'AED' ? 'AED ' : ''}${card.value}`}</strong></p>)}</div><PortalTable label="Recent payroll runs"><thead><tr><th>Period</th><th>Employees</th><th>Total</th><th>Status</th><th>Approval</th></tr></thead><tbody>{runs.slice(0, 5).map((run) => <tr key={run.id}><td>{run.period}</td><td>{run.employeeCount}</td><td>AED {run.totalAmount}</td><td>{run.runStatus}</td><td>{run.approvalStatus.replaceAll('_', ' ')}</td></tr>)}{runs.length === 0 && <tr><td colSpan={5}>No payroll runs yet.</td></tr>}</tbody></PortalTable></section>
  </>
}
