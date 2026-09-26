import { useCallback, useEffect, useState } from 'react'

import {
  adminApproveExpense,
  adminRejectExpense,
  createExpense,
  deleteExpense,
  managerApproveExpense,
  managerRejectExpense,
  readAdminExpenses,
  readManagerExpenses,
  readSelfExpenses,
  uploadExpenseReceipt,
} from './expenseApi.js'

function ExpenseRows({ items, role, busy, onAction }) {
  if (items.length === 0) return <p>No expense claims are available.</p>
  return (
    <div className="expense-table-wrap">
      <table className="expense-table">
        <thead><tr>{role !== 'self' && <th>Employee</th>}<th>Date</th><th>Category</th><th>Amount</th><th>Status</th><th>Receipt</th><th>Actions</th></tr></thead>
        <tbody>
          {items.map((claim) => (
            <tr key={claim.id}>
              {role !== 'self' && <td>{claim.employeeName}</td>}
              <td>{claim.expenseDate}</td>
              <td>{claim.category}<small>{claim.description}</small></td>
              <td>AED {claim.amount}</td>
              <td>{claim.status.replaceAll('_', ' ')}{claim.rejectionReason && <small>{claim.rejectionReason}</small>}</td>
              <td>{claim.hasReceipt ? 'Attached' : 'None'}</td>
              <td>
                <div className="expense-actions">
                  {role === 'manager' && claim.canDecide && <>
                    <button type="button" disabled={busy} onClick={() => onAction('approve', claim)}>Approve</button>
                    <button type="button" className="danger" disabled={busy} onClick={() => onAction('reject', claim)}>Reject</button>
                  </>}
                  {role === 'admin' && claim.canDecide && <>
                    <button type="button" disabled={busy} onClick={() => onAction('approve', claim)}>Approve</button>
                    {['pending', 'manager_approved'].includes(claim.status) && <button type="button" className="danger" disabled={busy} onClick={() => onAction('reject', claim)}>Reject</button>}
                  </>}
                  {(role === 'self' || role === 'admin') && ['pending', 'manager_rejected', 'rejected'].includes(claim.status) && !claim.payrollPeriod && (
                    <button type="button" className="danger" disabled={busy} onClick={() => onAction('delete', claim)}>Delete</button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Expenses({ account, authentication, branchId }) {
  const [selfItems, setSelfItems] = useState([])
  const [queueItems, setQueueItems] = useState([])
  const [status, setStatus] = useState('loading')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [form, setForm] = useState({ category: '', amount: '', expenseDate: '', description: '' })
  const [receipt, setReceipt] = useState(null)

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      if (account.role === 'admin') {
        const result = await readAdminExpenses(authentication, branchId)
        setQueueItems(result.items)
      } else {
        const self = await readSelfExpenses(authentication)
        setSelfItems(self.items)
        if (account.role === 'manager') {
          const queue = await readManagerExpenses(authentication)
          setQueueItems(queue.items)
        }
      }
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }, [account.role, authentication, branchId])

  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      let receiptId = null
      if (receipt !== null) receiptId = (await uploadExpenseReceipt(authentication, receipt)).id
      await createExpense(authentication, { ...form, receiptId })
      setForm({ category: '', amount: '', expenseDate: '', description: '' })
      setReceipt(null)
      setMessage('Expense claim submitted.')
      await load()
    } catch {
      setMessage('The expense claim could not be submitted.')
    } finally {
      setBusy(false)
    }
  }

  const action = async (kind, claim, role) => {
    let reason = null
    if (kind === 'reject' || role === 'admin' && claim.status === 'manager_rejected') {
      reason = globalThis.prompt(kind === 'reject' ? 'Reason for rejection' : 'Reason for overriding the manager rejection')
      if (!reason?.trim()) return
      reason = reason.trim()
    }
    setBusy(true)
    setMessage('')
    try {
      if (kind === 'delete') await deleteExpense(authentication, claim, role === 'admin' ? branchId : null)
      else if (role === 'manager' && kind === 'approve') await managerApproveExpense(authentication, claim)
      else if (role === 'manager') await managerRejectExpense(authentication, claim, reason)
      else if (kind === 'approve') await adminApproveExpense(authentication, branchId, claim, reason)
      else await adminRejectExpense(authentication, branchId, claim, reason)
      await load()
    } catch {
      setMessage('The expense action could not be completed. Refresh and try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="expenses" aria-labelledby="expenses-title">
      <h2 id="expenses-title">Expenses</h2>
      {message && <p role="status">{message}</p>}
      {account.role !== 'admin' && (
        <>
          <form className="expense-form" onSubmit={submit}>
            <h3>Submit an expense claim</h3>
            <label>Category<input required maxLength="80" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} /></label>
            <label>Amount<input required inputMode="decimal" pattern="(?:0|[1-9][0-9]{0,9})\.[0-9]{2}" placeholder="0.00" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
            <label>Expense date<input required type="date" value={form.expenseDate} onChange={(event) => setForm({ ...form, expenseDate: event.target.value })} /></label>
            <label>Description<textarea required maxLength="2000" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
            <label>Receipt<input type="file" accept="application/pdf,image/png,image/jpeg" onChange={(event) => setReceipt(event.target.files?.[0] ?? null)} /></label>
            <button type="submit" disabled={busy}>Submit claim</button>
          </form>
          <h3>My claims</h3>
          <ExpenseRows items={selfItems} role="self" busy={busy} onAction={(kind, claim) => action(kind, claim, 'self')} />
        </>
      )}
      {account.role === 'manager' && <>
        <h3>Direct-report queue</h3>
        <ExpenseRows items={queueItems} role="manager" busy={busy} onAction={(kind, claim) => action(kind, claim, 'manager')} />
      </>}
      {account.role === 'admin' && <>
        <h3>Selected-branch claims</h3>
        <ExpenseRows items={queueItems} role="admin" busy={busy} onAction={(kind, claim) => action(kind, claim, 'admin')} />
      </>}
      {status === 'loading' && <p>Loading expense claims...</p>}
      {status === 'unavailable' && <p>Expense claims are unavailable.</p>}
    </section>
  )
}
