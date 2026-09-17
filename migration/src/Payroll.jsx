import { useCallback, useEffect, useState } from 'react'

import {
  approvePayrollRun,
  createPayrollRun,
  deletePayrollRun,
  generatePayrollRun,
  payrollPreview,
  readPayrollApprovalHistory,
  readPayrollRun,
  readPayrollRuns,
  recallPayrollRun,
  rejectPayrollRun,
  refreshPayrollRun,
  repeatPayrollRun,
  savePayrollEntries,
  submitPayrollRun,
} from './payrollApi.js'

const today = new Date().toISOString().slice(0, 10)
const currentPeriod = today.slice(0, 7)

function EntryEditor({ value, onChange, disabled }) {
  const preview = payrollPreview(value)
  const set = (name, next) => onChange({ ...value, [name]: next })
  const manualItems = [...value.additionalAllowances, ...value.deductions]
    .filter((item) => !/^(?:AUTO_|LEAVE_|ATTENDANCE_|ROSTER_|EXPENSE_|ADVANCE_)/.test(item.code))
  return (
    <fieldset className="payroll-entry" disabled={disabled}>
      <legend>{value.employeeName}</legend>
      <p>Fixed pay: AED {value.fixedPay} · Net preview: AED {preview.netPay}</p>
      <div className="payroll-entry-grid">
        {[
          ['increment', 'Increment'], ['bonus', 'Bonus'], ['otherPay', 'Other pay'],
          ['variableAllowance', 'Variable allowance'],
        ].map(([name, label]) => (
          <label key={name}>{label}
            <input value={value[name]} pattern="-?\d+\.\d{2}" onChange={(event) => set(name, event.target.value)} />
          </label>
        ))}
        <label className="payroll-checkbox">
          <input type="checkbox" checked={value.excluded} onChange={(event) => set('excluded', event.target.checked)} />
          Exclude from this draft
        </label>
      </div>
      {(value.additionalAllowances.length > 0 || value.deductions.length > 0) && (
        <p className="payroll-adjustments">
          Manual items: {manualItems.length === 0 ? 'None' : manualItems
            .map((item) => `${item.label} ${item.amount} (${item.recurrence})`).join(', ')}
        </p>
      )}
      {value.sourceExplanations.length > 0 && (
        <ul className="payroll-source-explanations" aria-label={`${value.employeeName} automatic payroll sources`}>
          {value.sourceExplanations.map((item) => <li key={item}>{item}</li>)}
        </ul>
      )}
    </fieldset>
  )
}

export default function Payroll({ account, authentication, branchId }) {
  const [runs, setRuns] = useState([])
  const [selected, setSelected] = useState(null)
  const [entries, setEntries] = useState([])
  const [form, setForm] = useState({ period: currentPeriod, paymentDate: today })
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState([])
  const [reason, setReason] = useState('')

  const load = useCallback(async () => {
    if (account.role !== 'admin') return
    setStatus('loading')
    try {
      const result = await readPayrollRuns(authentication, branchId)
      setRuns(result.items)
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }, [account.role, authentication, branchId])

  useEffect(() => {
    const pending = globalThis.setTimeout(load, 0)
    return () => globalThis.clearTimeout(pending)
  }, [load])

  const open = async (run) => {
    setBusy(true)
    setMessage('')
    try {
      const detail = await readPayrollRun(authentication, branchId, run.id)
      setSelected(detail)
      setEntries(detail.entries)
      setHistory(await readPayrollApprovalHistory(authentication, branchId, run.id))
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  const runAction = async (operation, success) => {
    setBusy(true)
    setMessage('')
    try {
      const detail = await operation()
      if (detail) {
        setSelected(detail)
        setEntries(detail.entries)
        setHistory(await readPayrollApprovalHistory(authentication, branchId, detail.id))
      } else {
        setSelected(null)
        setEntries([])
      }
      setMessage(success)
      await load()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  if (account.role !== 'admin') return null

  return (
    <section className="payroll" aria-labelledby="payroll-title">
      <h2 id="payroll-title">Payroll drafts</h2>
      <p>FastAPI recalculates every amount, locks approval transitions, and issues immutable payslips.</p>
      <form className="payroll-create" onSubmit={(event) => {
        event.preventDefault()
        runAction(() => createPayrollRun(authentication, branchId, form), 'Payroll draft created.')
      }}>
        <label>Period<input required type="month" value={form.period} onChange={(event) => setForm({ ...form, period: event.target.value })} /></label>
        <label>Payment date<input required type="date" value={form.paymentDate} onChange={(event) => setForm({ ...form, paymentDate: event.target.value })} /></label>
        <button type="submit" disabled={busy}>Create draft</button>
      </form>
      {message && <p aria-live="polite">{message}</p>}
      {status === 'ready' && (
        <div className="payroll-layout">
          <div className="payroll-run-list">
            {runs.length === 0 && <p>No payroll drafts found.</p>}
            {runs.map((run) => (
              <button type="button" className="secondary" key={run.id} disabled={busy} onClick={() => open(run)}>
                <strong>{run.period}</strong>
                <span>AED {run.totalAmount} · {run.employeeCount} employees · {run.validationStatus}</span>
              </button>
            ))}
          </div>
          {selected && (
            <div className="payroll-editor">
              <h3>{selected.period} payroll · {selected.approvalStatus} · {selected.runStatus}</h3>
              {selected.blockingErrors.map((error) => <p className="payroll-blocking" key={error}>{error}</p>)}
              {selected.sourceWarnings.length > 0 && (
                <section className="payroll-source-warnings" aria-labelledby="payroll-source-warnings-title">
                  <h4 id="payroll-source-warnings-title">Source warnings</h4>
                  <p>Attendance and roster values stay blocked until Phase 10 publishes their approved projections.</p>
                  <ul>{selected.sourceWarnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                </section>
              )}
              <div className="payroll-actions">
                <button type="button" disabled={busy || selected.approvalStatus !== 'draft' || selected.runStatus !== 'draft'} onClick={() => runAction(
                  () => savePayrollEntries(authentication, branchId, selected, entries),
                  'Payroll entries saved.',
                )}>Save entries</button>
                <button type="button" className="secondary" disabled={busy || selected.approvalStatus !== 'draft' || selected.runStatus !== 'draft'} onClick={() => runAction(
                  () => refreshPayrollRun(authentication, branchId, selected),
                  'Automatic payroll inputs refreshed.',
                )}>Refresh payroll inputs</button>
                <button type="button" className="secondary" disabled={busy} onClick={() => runAction(
                  () => repeatPayrollRun(authentication, branchId, selected, form),
                  'Recurring manual items copied to the new draft.',
                )}>Repeat into form period</button>
                <button type="button" className="secondary" disabled={busy || selected.approvalStatus !== 'draft' || selected.runStatus !== 'draft'} onClick={() => runAction(
                  async () => { await deletePayrollRun(authentication, branchId, selected); return null },
                  'Payroll draft deleted.',
                )}>Delete draft</button>
                {selected.approvalStatus === 'draft' && selected.runStatus === 'draft' && (
                  <button type="button" disabled={busy || selected.validationStatus !== 'valid'} onClick={() => runAction(
                    () => submitPayrollRun(authentication, branchId, selected),
                    'Payroll submitted for approval.',
                  )}>Submit for approval</button>
                )}
                {selected.approvalStatus === 'pending_approval' && (
                  <>
                    <button type="button" disabled={busy} onClick={() => runAction(
                      () => approvePayrollRun(authentication, branchId, selected),
                      'Payroll approved.',
                    )}>Approve</button>
                    <button type="button" className="secondary" disabled={busy || !reason.trim()} onClick={() => runAction(
                      () => recallPayrollRun(authentication, branchId, selected, reason),
                      'Payroll recalled to draft.',
                    )}>Recall</button>
                    <button type="button" className="secondary" disabled={busy || !reason.trim()} onClick={() => runAction(
                      () => rejectPayrollRun(authentication, branchId, selected, reason),
                      'Payroll rejected to draft.',
                    )}>Reject</button>
                  </>
                )}
                {selected.approvalStatus === 'approved' && selected.runStatus === 'draft' && (
                  <button type="button" disabled={busy} onClick={() => runAction(
                    () => generatePayrollRun(authentication, branchId, selected),
                    'Payroll generated and payslips issued.',
                  )}>Generate payroll</button>
                )}
              </div>
              {selected.approvalStatus === 'pending_approval' && (
                <label>Recall or rejection reason
                  <input maxLength="500" value={reason} onChange={(event) => setReason(event.target.value)} />
                </label>
              )}
              {history.length > 0 && (
                <section aria-labelledby="payroll-history-title">
                  <h4 id="payroll-history-title">Approval history</h4>
                  <ol>{history.map((item) => (
                    <li key={item.id}>{item.action} by {item.actorName}{item.reason ? ` — ${item.reason}` : ''}</li>
                  ))}</ol>
                </section>
              )}
              {entries.map((item, index) => (
                <EntryEditor
                  key={item.id}
                  value={item}
                  disabled={busy || selected.approvalStatus !== 'draft' || selected.runStatus !== 'draft'}
                  onChange={(next) => setEntries(entries.map((entry, entryIndex) => entryIndex === index ? next : entry))}
                />
              ))}
            </div>
          )}
        </div>
      )}
      {status === 'unavailable' && <p>Payroll drafts are unavailable.</p>}
    </section>
  )
}
