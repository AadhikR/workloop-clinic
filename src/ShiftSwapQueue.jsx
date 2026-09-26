import { useCallback, useEffect, useState } from 'react'

import { approveShiftSwap, readAdminShiftSwaps, rejectShiftSwap } from './shiftSwapApi.js'

export default function ShiftSwapQueue({ authentication, branchId }) {
  const [swaps, setSwaps] = useState([])
  const [status, setStatus] = useState('pending')
  const [message, setMessage] = useState('')
  const load = useCallback(() => readAdminShiftSwaps(authentication, branchId, { status, limit: 100 }).then(setSwaps), [authentication, branchId, status])

  useEffect(() => {
    let active = true
    load().catch(() => { if (active) { setSwaps([]); setMessage('Shift swap requests are unavailable.') } })
    return () => { active = false }
  }, [load])

  const approve = async (swap) => {
    try { await approveShiftSwap(authentication, branchId, swap, { idempotencyKey: crypto.randomUUID() }); await load(); setMessage('Shift swap approved in a new publication version.') }
    catch { setMessage('Approval failed because the roster, employee, leave, staffing, or payroll source changed.') }
  }

  const reject = async (swap) => {
    const reason = window.prompt('Reason for rejecting this shift swap:')
    if (!reason) return
    try { await rejectShiftSwap(authentication, branchId, swap, reason, { idempotencyKey: crypto.randomUUID() }); await load(); setMessage('Shift swap rejected.') }
    catch { setMessage('The swap request changed and could not be rejected.') }
  }

  return (
    <section className="shift-swap-queue" aria-labelledby="shift-swap-queue-title">
      <h2 id="shift-swap-queue-title">Shift swaps</h2>
      <p>Review the selected branch queue. Approval creates a new immutable roster publication.</p>
      <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="cancelled">Cancelled</option></select></label>
      {swaps.length === 0 ? <p>No {status} shift swaps.</p> : <ul>{swaps.map((swap) => <li key={swap.id}><span><strong>{swap.requesterEmployeeName}: {swap.requesterDate}</strong><small>Swap with {swap.targetEmployeeName}: {swap.targetDate} · {swap.reason}</small></span>{swap.status === 'pending' && <span><button type="button" onClick={() => approve(swap)}>Approve</button><button type="button" className="secondary" onClick={() => reject(swap)}>Reject</button></span>}</li>)}</ul>}
      {message && <p role="status">{message}</p>}
    </section>
  )
}
