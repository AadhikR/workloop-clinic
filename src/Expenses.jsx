import { readFinancialCollection } from './financialCollections.js'
import Dialog from './PortalDialog.jsx'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  adminApproveExpense,
  adminRejectExpense,
  createExpense,
  deleteExpense,
  downloadClaimReceipt,
  managerApproveExpense,
  managerRejectExpense,
  readAdminExpenses,
  readManagerExpenses,
  readSelfExpenses,
  uploadExpenseReceipt,
} from './expenseApi.js'

const categories = [
  ['travel', 'Travel'], ['meals', 'Meals & Entertainment'], ['accommodation', 'Accommodation'],
  ['office_supplies', 'Office Supplies'], ['medical', 'Medical'], ['phone_internet', 'Phone & Internet'],
  ['training', 'Training & Education'], ['other', 'Other'],
]
const categoryLabels = Object.fromEntries(categories)
const statuses = ['all', 'pending', 'manager_approved', 'approved', 'paid', 'rejected']
const emptyForm = { category: 'travel', amount: '', expenseDate: new Date().toISOString().slice(0, 10), description: '' }

function money(value) {
  return Number(value ?? 0).toLocaleString('en-AE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function statusLabel(value) {
  return {
    pending: 'Pending', manager_approved: 'Manager Approved', manager_rejected: 'Manager Rejected',
    approved: 'HR Approved', paid: 'Paid', rejected: 'Rejected',
  }[value] ?? value
}

function statusBadge(value) {
  if (['approved', 'paid'].includes(value)) return 'badge badge-green'
  if (value === 'manager_approved') return 'badge badge-blue'
  if (['manager_rejected', 'rejected'].includes(value)) return 'badge badge-red'
  return 'badge badge-yellow'
}

function ExpenseFormDialog({ busy, onClose, onSubmit }) {
  const [form, setForm] = useState(emptyForm)
  const [receipt, setReceipt] = useState(null)
  return (
    <Dialog labelledBy="expense-form-title" onClose={() => { if (!busy) onClose() }}>
      <form onSubmit={(event) => { event.preventDefault(); onSubmit(form, receipt) }}>
        <div className="modal-header"><h3 id="expense-form-title">New Expense Claim</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={onClose}>×</button></div>
        <div className="modal-body">
          <div className="form-grid form-grid-2">
            <div className="form-group"><label htmlFor="expense-category">Category *</label><select id="expense-category" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
            <div className="form-group"><label htmlFor="expense-amount">Amount (AED) *</label><input id="expense-amount" required min="0.01" max="100000.00" step="0.01" type="number" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></div>
            <div className="form-group"><label htmlFor="expense-date">Expense Date *</label><input id="expense-date" required max={new Date().toISOString().slice(0, 10)} type="date" value={form.expenseDate} onChange={(event) => setForm({ ...form, expenseDate: event.target.value })} /></div>
            <div className="form-group"><label htmlFor="expense-receipt">Receipt</label><input id="expense-receipt" accept="application/pdf,image/png,image/jpeg" type="file" onChange={(event) => setReceipt(event.target.files?.[0] ?? null)} /><span className="hint">PDF, PNG, or JPEG. Maximum 10 MB.</span></div>
            <div className="form-group form-span"><label htmlFor="expense-description">Description *</label><textarea id="expense-description" required maxLength="2000" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
          </div>
        </div>
        <div className="modal-footer"><button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Submitting...' : 'Submit Claim'}</button></div>
      </form>
    </Dialog>
  )
}

function DecisionDialog({ busy, claim, kind, onClose, onSubmit }) {
  const [reason, setReason] = useState('')
  const needsReason = kind === 'reject' || kind === 'override'
  const title = kind === 'delete' ? 'Delete Expense Claim' : kind === 'approve' ? 'Approve Expense Claim' : 'Reject Expense Claim'
  return (
    <Dialog labelledBy="expense-decision-title" onClose={() => { if (!busy) onClose() }}>
      <form onSubmit={(event) => { event.preventDefault(); onSubmit(reason.trim()) }}>
        <div className="modal-header"><h3 id="expense-decision-title">{title}</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={onClose}>×</button></div>
        <div className="modal-body"><p><strong>{claim.employeeName ?? categoryLabels[claim.category] ?? claim.category}</strong><br />AED {money(claim.amount)} · {claim.description}</p>{needsReason && <div className="form-group"><label htmlFor="expense-decision-reason">Reason *</label><textarea id="expense-decision-reason" required maxLength="500" value={reason} onChange={(event) => setReason(event.target.value)} /></div>}{kind === 'delete' && <div className="alert alert-warning">Delete this claim? This cannot be undone.</div>}</div>
        <div className="modal-footer"><button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button><button type="submit" className={['delete', 'reject'].includes(kind) ? 'btn btn-danger' : 'btn btn-primary'} disabled={busy}>{busy ? 'Saving...' : title}</button></div>
      </form>
    </Dialog>
  )
}

function ExpenseTable({ busy, items, role, onAction }) {
  if (items.length === 0) return <div className="empty-state"><span aria-hidden="true" className="empty-state-icon">▧</span><h3>No expense claims found</h3><p>Claims matching this view will appear here.</p></div>
  return (
    <div className="table-wrap expense-table-wrap"><table className="expense-table"><thead><tr>{role !== 'self' && <th>Employee</th>}<th>Category</th><th>Amount</th><th>Date</th><th>Description</th><th>Receipt</th><th>Status</th><th>Actions</th></tr></thead><tbody>{items.map((claim) => <tr key={claim.id}>{role !== 'self' && <td><strong>{claim.employeeName}</strong></td>}<td>{categoryLabels[claim.category] ?? claim.category}</td><td className="font-bold">AED {money(claim.amount)}</td><td>{claim.expenseDate}</td><td className="expense-description-cell">{claim.description}</td><td>{claim.hasReceipt ? <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onAction('receipt', claim)}>View receipt</button> : <span className="text-muted">None</span>}</td><td><span className={statusBadge(claim.status)}>{statusLabel(claim.status)}</span>{claim.rejectionReason && <small className="text-danger">{claim.rejectionReason}</small>}{claim.payrollPeriod && <small>Payroll {claim.payrollPeriod}</small>}</td><td><div className="row-actions">{role === 'manager' && claim.canDecide && <><button type="button" className="btn btn-success btn-icon btn-sm" aria-label="Approve" disabled={busy} onClick={() => onAction('approve', claim)}>✓</button><button type="button" className="btn btn-danger btn-icon btn-sm" aria-label="Reject" disabled={busy} onClick={() => onAction('reject', claim)}>×</button></>}{role === 'admin' && claim.canDecide && <><button type="button" className="btn btn-success btn-icon btn-sm" aria-label="Approve" disabled={busy} onClick={() => onAction(claim.status === 'manager_rejected' ? 'override' : 'approve', claim)}>✓</button>{['pending', 'manager_approved'].includes(claim.status) && <button type="button" className="btn btn-danger btn-icon btn-sm" aria-label="Reject" disabled={busy} onClick={() => onAction('reject', claim)}>×</button>}</>}{(role === 'self' || role === 'admin') && ['pending', 'manager_rejected', 'rejected'].includes(claim.status) && !claim.payrollPeriod && <button type="button" className="btn btn-ghost btn-sm text-danger" disabled={busy} onClick={() => onAction('delete', claim)}>Delete</button>}</div></td></tr>)}</tbody></table></div>
  )
}

function SelfClaimSection({ busy, claims, onAction, title }) {
  if (claims.length === 0) return null
  return (
    <section className="employee-panel self-expense-section"><div className="panel-heading"><h3>{title}</h3><strong>AED {money(claims.reduce((sum, claim) => sum + Number(claim.amount), 0))}</strong></div>{claims.map((claim) => <article className="self-expense-row" key={claim.id}><div><strong>{categoryLabels[claim.category] ?? claim.category}</strong><span>{claim.expenseDate}</span><p>{claim.description}</p>{claim.rejectionReason && <small className="text-danger">Reason: {claim.rejectionReason}</small>}{claim.hasReceipt && <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onAction('receipt', claim)}>View receipt</button>}</div><div><strong>AED {money(claim.amount)}</strong><span className={statusBadge(claim.status)}>{statusLabel(claim.status)}</span>{['pending', 'manager_rejected', 'rejected'].includes(claim.status) && !claim.payrollPeriod && <button type="button" className="btn btn-ghost btn-sm text-danger" disabled={busy} onClick={() => onAction('delete', claim)}>Delete</button>}</div></article>)}</section>
  )
}

export default function Expenses({ account, authentication, branchId, view = 'all' }) {
  const [selfItems, setSelfItems] = useState([])
  const [queueItems, setQueueItems] = useState([])
  const [status, setStatus] = useState('loading')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [filter, setFilter] = useState(account.role === 'admin' || view === 'queue' ? 'pending' : 'all')
  const [showForm, setShowForm] = useState(false)
  const [decision, setDecision] = useState(null)

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      if (account.role === 'admin') {
        const result = await readFinancialCollection((options) => readAdminExpenses(authentication, branchId, options))
        setQueueItems(result.items)
      } else {
        if (view !== 'queue') setSelfItems((await readFinancialCollection((options) => readSelfExpenses(authentication, options))).items)
        if (account.role === 'manager' && view !== 'self') setQueueItems((await readFinancialCollection((options) => readManagerExpenses(authentication, options))).items)
      }
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }, [account.role, authentication, branchId, view])

  useEffect(() => { const pending = globalThis.setTimeout(load, 0); return () => globalThis.clearTimeout(pending) }, [load])

  const submit = async (form, receipt) => {
    setBusy(true)
    setMessage('')
    try {
      let receiptId = null
      if (receipt !== null) receiptId = (await uploadExpenseReceipt(authentication, receipt)).id
      await createExpense(authentication, { ...form, amount: Number(form.amount).toFixed(2), description: form.description.trim(), receiptId })
      setShowForm(false)
      setMessage('Expense claim submitted.')
      await load()
    } catch (error) {
      setMessage(error.message || 'The expense claim could not be submitted.')
    } finally {
      setBusy(false)
    }
  }

  const runAction = async (kind, claim, reason = '') => {
    setBusy(true)
    setMessage('')
    try {
      if (kind === 'delete') await deleteExpense(authentication, claim, account.role === 'admin' ? branchId : null)
      else if (account.role === 'manager' && kind === 'approve') await managerApproveExpense(authentication, claim)
      else if (account.role === 'manager') await managerRejectExpense(authentication, claim, reason)
      else if (['approve', 'override'].includes(kind)) await adminApproveExpense(authentication, branchId, claim, kind === 'override' ? reason : null)
      else await adminRejectExpense(authentication, branchId, claim, reason)
      setDecision(null)
      setMessage('Expense claim updated.')
      await load()
    } catch (error) {
      setMessage(error.message || 'The expense action could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  const filteredQueue = filter === 'all' ? queueItems : queueItems.filter((claim) => filter === 'rejected' ? ['manager_rejected', 'rejected'].includes(claim.status) : claim.status === filter)
  const summary = useMemo(() => ({
    pending: queueItems.filter((claim) => claim.status === 'pending').length,
    approved: queueItems.filter((claim) => claim.status === 'approved').reduce((sum, claim) => sum + Number(claim.amount), 0),
    paid: queueItems.filter((claim) => claim.status === 'paid').reduce((sum, claim) => sum + Number(claim.amount), 0),
  }), [queueItems])
  const onAction = async (kind, claim) => {
    if (kind !== 'receipt') { setDecision({ kind, claim }); return }
    setBusy(true)
    try {
      const signed = await downloadClaimReceipt(authentication, claim.id, account.role === 'admin' ? branchId : null)
      globalThis.open(signed.url, '_blank', 'noopener,noreferrer')
    } catch (error) { setMessage(error.message || 'The receipt is unavailable.') }
    finally { setBusy(false) }
  }
  const groupedSelf = Object.groupBy ? Object.groupBy(selfItems, (claim) => claim.status) : selfItems.reduce((groups, claim) => ({ ...groups, [claim.status]: [...(groups[claim.status] ?? []), claim] }), {})

  return (
    <section className={`expenses expenses-module ${account.role}-expenses`} aria-labelledby="expenses-title">
      <div className="module-toolbar"><div><h2 id="expenses-title">{view === 'queue' ? 'Expense Queue' : 'Expense Claims'}</h2><p>{account.role === 'admin' ? 'Review and approve employee expense reimbursements.' : view === 'queue' ? 'Review claims submitted by your direct reports.' : 'Submit and track your expense reimbursement requests.'}</p></div>{account.role !== 'admin' && view !== 'queue' && <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>＋ New Claim</button>}</div>
      {message && <div className="alert alert-info" role="status">{message}</div>}
      {status === 'loading' && <div className="module-loading" role="status">Loading expense claims...</div>}
      {status === 'unavailable' && <div className="alert alert-danger">Expense claims are unavailable.</div>}
      {status === 'ready' && account.role === 'admin' && <><div className="stats-grid expense-stats"><div className="stat-card"><div className="stat-label">Pending Claims</div><div className="stat-value">{summary.pending}</div></div><div className="stat-card"><div className="stat-label">Approved (Unpaid)</div><div className="stat-value text-primary">AED {money(summary.approved)}</div><div className="stat-sub">Reimbursed in payroll</div></div><div className="stat-card"><div className="stat-label">Total Paid</div><div className="stat-value text-success">AED {money(summary.paid)}</div><div className="stat-sub">All time</div></div></div><div className="tabs expense-tabs" role="tablist" aria-label="Expense status">{statuses.map((value) => <button type="button" role="tab" aria-selected={filter === value} className={`tab-btn${filter === value ? ' active' : ''}`} key={value} onClick={() => setFilter(value)}>{value === 'all' ? 'All' : statusLabel(value)}</button>)}</div><section className="card expense-queue-card"><ExpenseTable busy={busy} items={filteredQueue} role="admin" onAction={onAction} /></section></>}
      {status === 'ready' && account.role === 'manager' && view !== 'self' && <><div className="restored-toolbar"><div className="tabs expense-tabs" role="tablist" aria-label="Expense status">{[...statuses, 'manager_rejected'].map((value) => <button type="button" role="tab" aria-selected={filter === value} className={filter === value ? 'tab-btn active' : 'tab-btn'} key={value} onClick={() => setFilter(value)}>{value === 'all' ? 'All' : statusLabel(value)}</button>)}</div><button type="button" className="btn btn-outline" disabled={busy} onClick={load}>Refresh</button></div><section className="card expense-queue-card"><ExpenseTable busy={busy} items={filter === 'rejected' ? queueItems.filter((claim) => claim.status === 'rejected') : filteredQueue} role="manager" onAction={onAction} /></section></>}
      {status === 'ready' && account.role !== 'admin' && view !== 'queue' && <><div className="self-expense-summary"><span aria-hidden="true">▧</span><div><small>Approved, Pending Payment</small><strong>AED {money((groupedSelf.approved ?? []).reduce((sum, claim) => sum + Number(claim.amount), 0))}</strong><p>Included in a future payroll when processed</p></div></div><SelfClaimSection busy={busy} claims={groupedSelf.pending ?? []} onAction={onAction} title="Pending Review" /><SelfClaimSection busy={busy} claims={groupedSelf.manager_approved ?? []} onAction={onAction} title="Manager Approved, Awaiting HR" /><SelfClaimSection busy={busy} claims={groupedSelf.manager_rejected ?? []} onAction={onAction} title="Manager Rejected" /><SelfClaimSection busy={busy} claims={groupedSelf.approved ?? []} onAction={onAction} title="HR Approved, Awaiting Payroll" /><SelfClaimSection busy={busy} claims={groupedSelf.paid ?? []} onAction={onAction} title="Paid" /><SelfClaimSection busy={busy} claims={groupedSelf.rejected ?? []} onAction={onAction} title="Rejected" />{selfItems.length === 0 && <div className="empty-state"><h3>No expense claims yet</h3><p>Use New Claim to submit your first reimbursement request.</p></div>}</>}
      {showForm && <ExpenseFormDialog busy={busy} onClose={() => setShowForm(false)} onSubmit={submit} />}
      {decision && <DecisionDialog busy={busy} claim={decision.claim} kind={decision.kind} onClose={() => setDecision(null)} onSubmit={(reason) => runAction(decision.kind, decision.claim, reason)} />}
    </section>
  )
}
