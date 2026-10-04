import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  approveAdvance,
  createAdminAdvance,
  createSelfAdvance,
  readAdminAdvances,
  readSelfAdvances,
  recordAdvanceRepayment,
  rejectAdvance,
  replaceAdvanceSchedule,
  settleAdvance,
  withdrawAdvance,
} from './advanceApi.js'
import { readAllEmployees, readEmployeeSelf } from './employeeApi.js'

const currentPeriod = new Date().toISOString().slice(0, 7)
const emptyPlan = { amount: '', reason: '', installmentCount: 3, repaymentStartPeriod: currentPeriod }

function money(value) {
  return Number(value ?? 0).toLocaleString('en-AE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function statusLabel(value) {
  return { pending: 'Pending', active: 'Active', settled: 'Settled', cancelled: 'Cancelled' }[value] ?? value
}

function statusBadge(value) {
  return `badge ${value === 'active' ? 'badge-blue' : value === 'settled' ? 'badge-green' : value === 'cancelled' ? 'badge-red' : 'badge-yellow'}`
}

function AdvanceDialog({ admin, busy, employees, initial = emptyPlan, onClose, onSubmit }) {
  const [employeeId, setEmployeeId] = useState('')
  const [plan, setPlan] = useState(initial)
  return (
    <div className="modal-overlay" role="presentation">
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="advance-dialog-title" onSubmit={(event) => {
        event.preventDefault()
        onSubmit({ ...plan, employeeId })
      }}>
        <div className="modal-header"><h3 id="advance-dialog-title">{admin ? 'New Salary Advance' : 'New Advance Request'}</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={onClose}>×</button></div>
        <div className="modal-body">
          <div className="form-grid form-grid-2">
            {admin && <div className="form-group"><label htmlFor="advance-employee">Employee *</label><select id="advance-employee" required value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}><option value="">Select employee</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name} ({employee.empNo})</option>)}</select></div>}
            <div className="form-group"><label htmlFor="advance-amount">Advance Amount (AED) *</label><input id="advance-amount" required min="0.01" step="0.01" type="number" value={plan.amount} onChange={(event) => setPlan({ ...plan, amount: event.target.value })} /></div>
            <div className="form-group"><label htmlFor="advance-installments">Repayment Months *</label><input id="advance-installments" required min="1" max="120" type="number" value={plan.installmentCount} onChange={(event) => setPlan({ ...plan, installmentCount: event.target.value })} /></div>
            <div className="form-group"><label htmlFor="advance-period">First Repayment Month *</label><input id="advance-period" required type="month" value={plan.repaymentStartPeriod} onChange={(event) => setPlan({ ...plan, repaymentStartPeriod: event.target.value })} /></div>
            <div className="form-group form-span"><label htmlFor="advance-reason">Reason *</label><textarea id="advance-reason" required maxLength="500" value={plan.reason} onChange={(event) => setPlan({ ...plan, reason: event.target.value })} /></div>
          </div>
        </div>
        <div className="modal-footer"><button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Submitting...' : admin ? 'Create Advance' : 'Submit Request'}</button></div>
      </form>
    </div>
  )
}

function AdvanceActionDialog({ advance, busy, kind, onClose, onSubmit }) {
  const [reason, setReason] = useState('')
  const [amount, setAmount] = useState(advance.outstandingBalance)
  const [count, setCount] = useState(advance.installmentCount)
  const [period, setPeriod] = useState(advance.repaymentStartPeriod)
  const labels = { reject: 'Reject Advance', repay: 'Record Repayment', schedule: 'Edit Repayment Schedule', settle: 'Settle Advance', withdraw: 'Withdraw Request' }
  return (
    <div className="modal-overlay" role="presentation">
      <form className="modal advance-action-dialog" role="dialog" aria-modal="true" aria-labelledby="advance-action-title" onSubmit={(event) => {
        event.preventDefault()
        onSubmit({ amount, count: Number(count), period, reason: reason.trim() })
      }}>
        <div className="modal-header"><h3 id="advance-action-title">{labels[kind]}</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={onClose}>×</button></div>
        <div className="modal-body">
          <p><strong>{advance.employeeName ?? 'Your request'}</strong><br />AED {money(advance.amount)} · {advance.reason}</p>
          {kind === 'reject' && <div className="form-group"><label htmlFor="advance-reject-reason">Reason *</label><textarea id="advance-reject-reason" required maxLength="500" value={reason} onChange={(event) => setReason(event.target.value)} /></div>}
          {kind === 'repay' && <div className="form-group"><label htmlFor="advance-repayment">Repayment Amount (AED) *</label><input id="advance-repayment" required min="0.01" max={advance.outstandingBalance} step="0.01" type="number" value={amount} onChange={(event) => setAmount(event.target.value)} /></div>}
          {kind === 'schedule' && <div className="form-grid form-grid-2"><div className="form-group"><label htmlFor="advance-schedule-amount">Revised Amount *</label><input id="advance-schedule-amount" required min="0.01" step="0.01" type="number" value={amount} onChange={(event) => setAmount(event.target.value)} /></div><div className="form-group"><label htmlFor="advance-schedule-count">Installments *</label><input id="advance-schedule-count" required min="1" max="120" type="number" value={count} onChange={(event) => setCount(event.target.value)} /></div><div className="form-group"><label htmlFor="advance-schedule-period">First Repayment Month *</label><input id="advance-schedule-period" required type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></div></div>}
          {kind === 'settle' && <div className="alert alert-warning">This records the remaining AED {money(advance.outstandingBalance)} as settled.</div>}
          {kind === 'withdraw' && <div className="alert alert-warning">Withdraw this pending request? This cannot be undone.</div>}
        </div>
        <div className="modal-footer"><button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button><button type="submit" className={['reject', 'withdraw'].includes(kind) ? 'btn btn-danger' : 'btn btn-primary'} disabled={busy}>{busy ? 'Saving...' : labels[kind]}</button></div>
      </form>
    </div>
  )
}

function AdvanceSchedule({ advance }) {
  if (!advance.schedule?.length && !advance.repayments?.length) return <p className="text-muted">No repayment activity has been recorded.</p>
  return (
    <div className="advance-expanded">
      <div className="advance-progress-summary"><div><span>Original amount</span><strong>AED {money(advance.amount)}</strong></div><div><span>Outstanding</span><strong>AED {money(advance.outstandingBalance)}</strong></div><div><span>Next staged month</span><strong>{advance.nextRepaymentPeriod ?? 'Schedule complete'}</strong></div></div>
      {advance.schedule?.length > 0 && <div className="advance-schedule-grid">{advance.schedule.map((item) => <div key={item.period} className={item.status}><span>{item.period}</span><strong>AED {money(item.scheduledAmount)}</strong><small>{item.status}</small></div>)}</div>}
      {advance.repayments?.length > 0 && <div className="table-wrap advance-repayments"><table><thead><tr><th>Date</th><th>Amount (AED)</th><th>Kind</th><th>Payroll Period</th></tr></thead><tbody>{advance.repayments.map((item) => <tr key={item.id}><td>{item.paidDate}</td><td>{money(item.amount)}</td><td>{item.repaymentKind}</td><td>{item.payrollPeriod ?? 'Manual'}</td></tr>)}</tbody></table></div>}
    </div>
  )
}

function AdminAdvances({ busy, expandedId, filter, items, onAction, onExpand, onFilter }) {
  const visible = filter === 'all' ? items : items.filter((item) => item.status === filter)
  return (
    <section className="card advances-table-card" aria-labelledby="all-advances-title">
      <div className="card-header advances-card-header"><h3 id="all-advances-title">All Advances</h3><div className="advance-filters" role="tablist" aria-label="Advance status">{['all', 'pending', 'active', 'settled', 'cancelled'].map((value) => <button type="button" role="tab" aria-selected={filter === value} className={filter === value ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'} key={value} onClick={() => onFilter(value)}>{value === 'all' ? 'All' : statusLabel(value)} ({value === 'all' ? items.length : items.filter((item) => item.status === value).length})</button>)}</div></div>
      {visible.length === 0 ? <div className="empty-state"><p>No {filter === 'all' ? '' : `${filter} `}advances found.</p></div> : <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Amount (AED)</th><th>Repayment</th><th className="text-right">Monthly Ded.</th><th className="text-right">Outstanding</th><th>Reason</th><th>Status</th><th>Actions</th><th aria-label="Details" /></tr></thead><tbody>{visible.map((advance) => <AdvanceAdminRows advance={advance} busy={busy} expanded={expandedId === advance.id} key={advance.id} onAction={onAction} onExpand={onExpand} />)}</tbody></table></div>}
    </section>
  )
}

function AdvanceAdminRows({ advance, busy, expanded, onAction, onExpand }) {
  return <><tr><td><strong>{advance.employeeName}</strong><small>Created by {advance.creatorName}</small></td><td>{money(advance.amount)}</td><td>{advance.installmentCount} months<small>Starts {advance.repaymentStartPeriod}</small></td><td className="text-right deduction-value">{advance.status === 'active' ? money(advance.monthlyInstallment) : '—'}</td><td className="text-right font-bold">{money(advance.outstandingBalance)}</td><td>{advance.reason}</td><td><span className={statusBadge(advance.status)}>{statusLabel(advance.status)}</span>{advance.rejectionReason && <small className="text-danger">{advance.rejectionReason}</small>}</td><td><div className="row-actions">{advance.canDecide && <><button type="button" className="btn btn-success btn-icon btn-sm" aria-label="Approve" disabled={busy} onClick={() => onAction('approve', advance)}>✓</button><button type="button" className="btn btn-danger btn-icon btn-sm" aria-label="Reject" disabled={busy} onClick={() => onAction('reject', advance)}>×</button><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => onAction('schedule', advance)}>Schedule</button></>}{advance.status === 'active' && <><button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => onAction('repay', advance)}>Repayment</button><button type="button" className="btn btn-success btn-sm" disabled={busy} onClick={() => onAction('settle', advance)}>Settle</button></>}</div></td><td><button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label="Toggle repayment details" onClick={() => onExpand(advance.id)}>{expanded ? '⌃' : '⌄'}</button></td></tr>{expanded && <tr className="advance-detail-row"><td colSpan="9"><AdvanceSchedule advance={advance} /></td></tr>}</>
}

function SelfAdvanceSection({ busy, items, onAction, title }) {
  if (items.length === 0) return null
  return <section className="employee-panel self-advance-section"><h3>{title}</h3>{items.map((advance) => { const repaid = Number(advance.amount) === 0 ? 0 : Math.round((1 - Number(advance.outstandingBalance) / Number(advance.amount)) * 100); return <article className="self-advance-row" key={advance.id}><div><strong>AED {money(advance.amount)}</strong><p>{advance.reason}</p><small>Requested {new Date(advance.createdAt).toLocaleDateString('en-AE')}</small>{advance.rejectionReason && <small className="text-danger">Reason: {advance.rejectionReason}</small>}</div><div className="self-advance-meta"><span className={statusBadge(advance.status)}>{statusLabel(advance.status)}</span>{advance.status === 'active' && <><strong>AED {money(advance.outstandingBalance)} outstanding</strong><div className="advance-progress"><span style={{ width: `${repaid}%` }} /></div><small>{repaid}% repaid · AED {money(advance.monthlyInstallment)} monthly</small></>}{advance.status === 'pending' && <button type="button" className="btn btn-ghost btn-sm text-danger" disabled={busy} onClick={() => onAction('withdraw', advance)}>Withdraw</button>}</div></article> })}</section>
}

export default function Advances({ account, authentication, branchId }) {
  const admin = account.role === 'admin'
  const [items, setItems] = useState([])
  const [employees, setEmployees] = useState([])
  const [status, setStatus] = useState('loading')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [basicSalary, setBasicSalary] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [filter, setFilter] = useState('all')
  const [expandedId, setExpandedId] = useState(null)
  const [actionDialog, setActionDialog] = useState(null)

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      if (admin) {
        const [advances, staff] = await Promise.all([readAdminAdvances(authentication, branchId), readAllEmployees(authentication, branchId, { sort: 'name' })])
        setItems(advances.items)
        setEmployees(staff.filter((employee) => employee.active))
      } else {
        const advances = await readSelfAdvances(authentication)
        setItems(advances.items)
      }
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }, [admin, authentication, branchId])

  useEffect(() => { const pending = globalThis.setTimeout(load, 0); return () => globalThis.clearTimeout(pending) }, [load])
  useEffect(() => {
    if (admin) return undefined
    const controller = new AbortController()
    readEmployeeSelf(authentication, { signal: controller.signal }).then((employee) => setBasicSalary(employee.basicSalary)).catch(() => setBasicSalary(null))
    return () => controller.abort()
  }, [admin, authentication])

  const submit = async (values) => {
    if (!admin && basicSalary !== null && Number(values.amount) > Number(basicSalary)) {
      setMessage(`The requested amount cannot exceed your basic monthly salary of AED ${money(basicSalary)}.`)
      return
    }
    setBusy(true)
    setMessage('')
    try {
      const plan = { amount: Number(values.amount).toFixed(2), reason: values.reason.trim(), installmentCount: Number(values.installmentCount), repaymentStartPeriod: values.repaymentStartPeriod }
      if (admin) await createAdminAdvance(authentication, branchId, { employeeId: values.employeeId, ...plan })
      else await createSelfAdvance(authentication, plan)
      setShowCreate(false)
      setMessage(admin ? 'Salary advance created.' : 'Your advance request has been submitted.')
      await load()
    } catch (error) {
      setMessage(error.message || 'The salary advance request could not be submitted.')
    } finally {
      setBusy(false)
    }
  }

  const runAction = async (kind, advance, values = {}) => {
    setBusy(true)
    setMessage('')
    try {
      if (kind === 'withdraw') await withdrawAdvance(authentication, advance)
      if (kind === 'approve') await approveAdvance(authentication, branchId, advance)
      if (kind === 'reject') await rejectAdvance(authentication, branchId, advance, values.reason)
      if (kind === 'repay') await recordAdvanceRepayment(authentication, branchId, advance, Number(values.amount).toFixed(2))
      if (kind === 'settle') await settleAdvance(authentication, branchId, advance)
      if (kind === 'schedule') await replaceAdvanceSchedule(authentication, branchId, advance, { amount: Number(values.amount).toFixed(2), installmentCount: values.count, repaymentStartPeriod: values.period })
      setActionDialog(null)
      setMessage('Salary advance updated.')
      await load()
    } catch (error) {
      setMessage(error.message || 'The salary advance action could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  const onAction = (kind, advance) => kind === 'approve' ? runAction(kind, advance) : setActionDialog({ kind, advance })
  const pending = items.filter((item) => item.status === 'pending')
  const active = items.filter((item) => item.status === 'active')
  const history = items.filter((item) => ['settled', 'cancelled'].includes(item.status))
  const totalOutstanding = useMemo(() => active.reduce((sum, item) => sum + Number(item.outstandingBalance), 0), [active])

  return (
    <section className={`advances-module${admin ? ' administrator-advances' : ' self-advances'}`} aria-labelledby="advances-title">
      <div className="module-toolbar"><div><h2 id="advances-title">Salary Advances</h2><p>{admin ? 'Review requests, manage repayment schedules, and record settlements.' : 'View your advances and submit new requests.'}</p></div><button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>＋ {admin ? 'New Advance' : 'Request Advance'}</button></div>
      {message && <div className="alert alert-info" role="status">{message}</div>}
      {status === 'loading' && <div className="module-loading" role="status">Loading salary advances...</div>}
      {status === 'unavailable' && <div className="alert alert-danger">Salary advances are unavailable.</div>}
      {status === 'ready' && admin && <><div className="stats-grid advance-stats"><div className="stat-card"><div className="stat-label">Pending Requests</div><div className="stat-value">{pending.length}</div><div className="stat-sub">awaiting approval</div></div><div className="stat-card"><div className="stat-label">Active Advances</div><div className="stat-value">{active.length}</div><div className="stat-sub">being repaid</div></div><div className="stat-card"><div className="stat-label">Total Outstanding</div><div className="stat-value text-primary">{money(totalOutstanding)}</div><div className="stat-sub">AED outstanding balance</div></div></div><AdminAdvances busy={busy} expandedId={expandedId} filter={filter} items={items} onAction={onAction} onExpand={(id) => setExpandedId((current) => current === id ? null : id)} onFilter={setFilter} /></>}
      {status === 'ready' && !admin && <><div className="self-advance-summary"><span aria-hidden="true">$</span><div><small>Total Outstanding Balance</small><strong>AED {money(totalOutstanding)}</strong><p>across {active.length} active advance{active.length === 1 ? '' : 's'}</p></div></div><SelfAdvanceSection busy={busy} items={pending} onAction={onAction} title="Pending Requests" /><SelfAdvanceSection busy={busy} items={active} onAction={onAction} title="Active Advances" /><SelfAdvanceSection busy={busy} items={history} onAction={onAction} title="Past Advances" />{items.length === 0 && <div className="empty-state"><h3>No advance requests yet</h3><p>Use Request Advance to submit your first request.</p></div>}</>}
      {showCreate && <AdvanceDialog admin={admin} busy={busy} employees={employees} onClose={() => setShowCreate(false)} onSubmit={submit} />}
      {actionDialog && <AdvanceActionDialog advance={actionDialog.advance} busy={busy} kind={actionDialog.kind} onClose={() => setActionDialog(null)} onSubmit={(values) => runAction(actionDialog.kind, actionDialog.advance, values)} />}
    </section>
  )
}
