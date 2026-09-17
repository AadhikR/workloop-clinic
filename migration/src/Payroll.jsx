import { useCallback, useEffect, useState } from 'react'

import {
  createPayrollRun,
  deletePayrollRun,
  payrollPreview,
  readPayrollRun,
  readPayrollRuns,
  refreshPayrollRun,
  repeatPayrollRun,
  savePayrollEntries,
} from './payrollApi.js'

const today = new Date().toISOString().slice(0, 10)
const currentPeriod = today.slice(0, 7)

function EntryEditor({ value, onChange, disabled }) {
  const preview = payrollPreview(value)
  const set = (name, next) => onChange({ ...value, [name]: next })
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
          Manual items: {[...value.additionalAllowances, ...value.deductions]
            .map((item) => `${item.label} ${item.amount} (${item.recurrence})`).join(', ')}
        </p>
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
      <p>FastAPI recalculates every amount before saving. Approval and automatic payroll inputs are not available yet.</p>
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
              <h3>{selected.period} editable draft</h3>
              {selected.blockingErrors.map((error) => <p className="payroll-blocking" key={error}>{error}</p>)}
              <div className="payroll-actions">
                <button type="button" disabled={busy} onClick={() => runAction(
                  () => savePayrollEntries(authentication, branchId, selected, entries),
                  'Payroll entries saved.',
                )}>Save entries</button>
                <button type="button" className="secondary" disabled={busy} onClick={() => runAction(
                  () => refreshPayrollRun(authentication, branchId, selected),
                  'Trusted salary snapshots refreshed.',
                )}>Refresh salaries</button>
                <button type="button" className="secondary" disabled={busy} onClick={() => runAction(
                  () => repeatPayrollRun(authentication, branchId, selected, form),
                  'Recurring manual items copied to the new draft.',
                )}>Repeat into form period</button>
                <button type="button" className="secondary" disabled={busy} onClick={() => runAction(
                  async () => { await deletePayrollRun(authentication, branchId, selected); return null },
                  'Payroll draft deleted.',
                )}>Delete draft</button>
              </div>
              {entries.map((item, index) => (
                <EntryEditor
                  key={item.id}
                  value={item}
                  disabled={busy}
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
