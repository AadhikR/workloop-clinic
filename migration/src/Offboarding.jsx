import { useCallback, useEffect, useState } from 'react'

import {
  addTask,
  advanceVisa,
  changeTask,
  completeOffboarding,
  deleteTask,
  initializeChecklist,
  previewSettlement,
  readChecklists,
} from './offboardingApi.js'
import { openPdf, saveDownload } from './outputDelivery.js'
import {
  downloadFinalSettlementPdf,
  downloadOffboardingLetterPdf,
} from './renderedOutputApi.js'

const zeroAdjustments = {
  noticePay: '0.00', noticeDeduction: '0.00', otherEarnings: '0.00',
  otherDeductions: '0.00', adjustmentReason: '',
}

export default function Offboarding({ account, authentication, branchId }) {
  const [items, setItems] = useState([])
  const [employeeId, setEmployeeId] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState(null)

  const load = useCallback(async () => {
    if (account.role === 'admin') setItems(await readChecklists(authentication, branchId))
  }, [account.role, authentication, branchId])

  useEffect(() => {
    const pending = globalThis.setTimeout(() => {
      load().catch(() => setMessage('Offboarding records are unavailable.'))
    }, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  if (account.role !== 'admin') return null

  const run = async (action, success) => {
    setBusy(true); setMessage(''); setPreview(null)
    try { await action(); setMessage(success); await load() }
    catch { setMessage('The offboarding action could not be completed.') }
    finally { setBusy(false) }
  }

  const initialize = (event) => {
    event.preventDefault()
    run(() => initializeChecklist(authentication, branchId, employeeId.trim()), 'Checklist initialized.')
  }

  const taskAction = (checklist, task) => run(
    () => changeTask(
      authentication, branchId, checklist, task, task.completed ? 'reopen' : 'complete', task.notes,
    ),
    task.completed ? 'Task reopened.' : 'Task completed.',
  )

  const createTask = (checklist) => {
    const name = globalThis.prompt('Custom task name')?.trim()
    if (name) run(() => addTask(authentication, branchId, checklist, name), 'Task added.')
  }

  const calculate = async (checklist) => {
    setBusy(true); setMessage('')
    try { setPreview({ checklist, data: await previewSettlement(authentication, branchId, checklist, zeroAdjustments) }) }
    catch { setMessage('Settlement cannot be calculated until every required source is ready.') }
    finally { setBusy(false) }
  }

  const finish = (checklist, settlement) => {
    const reason = globalThis.prompt('Termination reason for the employment record')?.trim()
    if (!reason) return
    run(
      () => completeOffboarding(
        authentication, branchId, checklist, zeroAdjustments, settlement, reason,
      ),
      'Offboarding and final settlement completed.',
    )
  }

  return <section className="records-benefits" aria-labelledby="offboarding-title">
    <h2 id="offboarding-title">Offboarding and final settlement</h2>
    <p role="status" aria-live="polite">{message}</p>
    <form className="expense-form" onSubmit={initialize}>
      <label>Employee ID<input required value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} /></label>
      <button type="submit" disabled={busy}>Initialize checklist</button>
    </form>
    {items.map((checklist) => <article className="card" key={checklist.id}>
      <h3>{checklist.employeeName}</h3>
      <p>Status: {checklist.status}. Visa: {checklist.visaCancellationStatus}.</p>
      <ul>{checklist.tasks.map((task) => <li key={task.id}>
        <button type="button" disabled={busy || checklist.status === 'completed'} onClick={() => taskAction(checklist, task)}>
          {task.completed ? 'Reopen' : 'Complete'}
        </button>{' '}{task.taskName} <small>{task.source}</small>
        {task.source === 'custom' && !task.completed && <button
          type="button" className="danger" disabled={busy}
          onClick={() => run(
            () => deleteTask(authentication, branchId, checklist, task), 'Task deleted.',
          )}
        >Delete</button>}
      </li>)}</ul>
      {checklist.status === 'in_progress' && <div className="actions">
        <button type="button" disabled={busy} onClick={() => createTask(checklist)}>Add custom task</button>
        {checklist.visaCancellationStatus !== 'cancelled' && <button type="button" disabled={busy} onClick={() => run(() => advanceVisa(authentication, branchId, checklist), 'Visa state advanced.')}>Advance visa state</button>}
        <button type="button" disabled={busy} onClick={() => calculate(checklist)}>Preview settlement</button>
      </div>}
      {checklist.status === 'completed' && <div className="actions">
        <button type="button" disabled={busy} onClick={() => run(
          async () => openPdf(await downloadOffboardingLetterPdf(
            authentication, branchId, checklist.id, 'noc',
          )),
          'No objection certificate opened.',
        )}>Print NOC</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => run(
          async () => saveDownload(await downloadOffboardingLetterPdf(
            authentication, branchId, checklist.id, 'experience',
          )),
          'Experience letter downloaded.',
        )}>Download experience letter</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => run(
          async () => openPdf(await downloadFinalSettlementPdf(
            authentication, branchId, checklist.id,
          )),
          'Final settlement opened.',
        )}>Print final settlement</button>
      </div>}
    </article>)}
    {preview && <div className="card">
      <h3>Settlement preview for {preview.checklist.employeeName}</h3>
      <dl>
        <dt>Final salary</dt><dd>AED {preview.data.finalSalary}</dd>
        <dt>Leave encashment</dt><dd>AED {preview.data.leaveEncashment}</dd>
        <dt>Gratuity</dt><dd>AED {preview.data.gratuity}</dd>
        <dt>Advance deduction</dt><dd>AED {preview.data.advanceDeduction}</dd>
        <dt>Net settlement</dt><dd>AED {preview.data.netAmount}</dd>
      </dl>
      <p>A different administrator must review and complete this checklist.</p>
      <button type="button" disabled={busy} onClick={() => finish(preview.checklist, preview.data)}>Review and complete</button>
    </div>}
  </section>
}
