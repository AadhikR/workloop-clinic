import { useCallback, useEffect, useState } from 'react'

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

const currentPeriod = new Date().toISOString().slice(0, 7)
const emptyPlan = { amount: '', reason: '', installmentCount: 3, repaymentStartPeriod: currentPeriod }

function AdvanceRows({ items, admin, busy, onAction }) {
  if (items.length === 0) return <p>No salary advances are available.</p>
  return (
    <div className="expense-table-wrap">
      <table className="expense-table">
        <thead><tr>{admin && <th>Employee</th>}<th>Advance</th><th>Schedule</th><th>Outstanding</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          {items.map((advance) => (
            <tr key={advance.id}>
              {admin && <td>{advance.employeeName}<small>Created by {advance.creatorName}</small></td>}
              <td>AED {advance.amount}<small>{advance.reason}</small></td>
              <td>{advance.installmentCount} × AED {advance.monthlyInstallment}<small>Starts {advance.repaymentStartPeriod}</small></td>
              <td>AED {advance.outstandingBalance}<small>{advance.nextRepaymentPeriod ? `Next: ${advance.nextRepaymentPeriod}` : 'No future installment'}</small></td>
              <td>{advance.status}{advance.rejectionReason && <small>{advance.rejectionReason}</small>}</td>
              <td>
                <div className="expense-actions">
                  {!admin && advance.status === 'pending' && <button type="button" className="danger" disabled={busy} onClick={() => onAction('withdraw', advance)}>Withdraw</button>}
                  {admin && advance.canDecide && <>
                    <button type="button" disabled={busy} onClick={() => onAction('approve', advance)}>Approve</button>
                    <button type="button" className="danger" disabled={busy} onClick={() => onAction('reject', advance)}>Reject</button>
                    <button type="button" className="secondary" disabled={busy} onClick={() => onAction('schedule', advance)}>Edit schedule</button>
                  </>}
                  {admin && advance.status === 'active' && <>
                    <button type="button" disabled={busy} onClick={() => onAction('repay', advance)}>Repayment</button>
                    <button type="button" className="secondary" disabled={busy} onClick={() => onAction('settle', advance)}>Settle</button>
                  </>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Advances({ account, authentication, branchId }) {
  const admin = account.role === 'admin'
  const [items, setItems] = useState([])
  const [status, setStatus] = useState('loading')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [employeeId, setEmployeeId] = useState('')
  const [plan, setPlan] = useState(emptyPlan)

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const result = admin
        ? await readAdminAdvances(authentication, branchId)
        : await readSelfAdvances(authentication)
      setItems(result.items)
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }, [admin, authentication, branchId])

  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      const values = { ...plan, installmentCount: Number(plan.installmentCount) }
      if (admin) await createAdminAdvance(authentication, branchId, { employeeId, ...values })
      else await createSelfAdvance(authentication, values)
      setPlan(emptyPlan)
      setEmployeeId('')
      setMessage('Salary advance request submitted.')
      await load()
    } catch {
      setMessage('The salary advance request could not be submitted.')
    } finally {
      setBusy(false)
    }
  }

  const action = async (kind, advance) => {
    setBusy(true)
    setMessage('')
    try {
      if (kind === 'withdraw') await withdrawAdvance(authentication, advance)
      else if (kind === 'approve') await approveAdvance(authentication, branchId, advance)
      else if (kind === 'reject') {
        const reason = globalThis.prompt('Reason for rejection')?.trim()
        if (!reason) return
        await rejectAdvance(authentication, branchId, advance, reason)
      } else if (kind === 'repay') {
        const amount = globalThis.prompt('Repayment amount in fixed decimal notation, for example 250.00')?.trim()
        if (!amount) return
        await recordAdvanceRepayment(authentication, branchId, advance, amount)
      } else if (kind === 'settle') {
        if (!globalThis.confirm(`Record the exact remaining balance of AED ${advance.outstandingBalance}?`)) return
        await settleAdvance(authentication, branchId, advance)
      } else {
        const amount = globalThis.prompt('Revised advance amount', advance.amount)?.trim()
        const count = Number(globalThis.prompt('Revised installment count', String(advance.installmentCount)))
        const start = globalThis.prompt('Revised start period (YYYY-MM)', advance.repaymentStartPeriod)?.trim()
        if (!amount || !start || !Number.isInteger(count)) return
        await replaceAdvanceSchedule(authentication, branchId, advance, {
          amount, installmentCount: count, repaymentStartPeriod: start,
        })
      }
      await load()
    } catch {
      setMessage('The salary advance action could not be completed. Refresh and try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="expenses" aria-labelledby="advances-title">
      <h2 id="advances-title">Salary advances</h2>
      {message && <p role="status">{message}</p>}
      <form className="expense-form" onSubmit={submit}>
        <h3>{admin ? 'Create an employee advance' : 'Request an advance'}</h3>
        {admin && <label>Employee ID<input required value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} /></label>}
        <label>Amount<input required inputMode="decimal" pattern="(?:0|[1-9][0-9]{0,9})\.[0-9]{2}" placeholder="0.00" value={plan.amount} onChange={(event) => setPlan({ ...plan, amount: event.target.value })} /></label>
        <label>Reason<textarea required maxLength="500" value={plan.reason} onChange={(event) => setPlan({ ...plan, reason: event.target.value })} /></label>
        <label>Installments<input required type="number" min="1" max="120" value={plan.installmentCount} onChange={(event) => setPlan({ ...plan, installmentCount: event.target.value })} /></label>
        <label>First repayment period<input required type="month" value={plan.repaymentStartPeriod} onChange={(event) => setPlan({ ...plan, repaymentStartPeriod: event.target.value })} /></label>
        <button type="submit" disabled={busy}>Submit advance</button>
      </form>
      <h3>{admin ? 'Selected-branch advances' : 'My advances'}</h3>
      <AdvanceRows items={items} admin={admin} busy={busy} onAction={action} />
      {status === 'loading' && <p>Loading salary advances...</p>}
      {status === 'unavailable' && <p>Salary advances are unavailable.</p>}
    </section>
  )
}
