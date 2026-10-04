import { useCallback, useEffect, useMemo, useState } from 'react'

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
import { saveDownload } from './outputDelivery.js'
import { downloadPayslipsZip } from './renderedOutputApi.js'

const today = new Date().toISOString().slice(0, 10)
const currentPeriod = today.slice(0, 7)
const emptyPlan = { period: currentPeriod, paymentDate: today }

function money(value) {
  return Number(value ?? 0).toLocaleString('en-AE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function periodLabel(value) {
  const [year, month] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(Date.UTC(year, month - 1, 1)))
}

function badge(value) {
  if (['approved', 'generated', 'valid'].includes(value)) return 'badge badge-green'
  if (value === 'pending_approval') return 'badge badge-blue'
  if (['blocking', 'rejected'].includes(value)) return 'badge badge-red'
  return 'badge badge-yellow'
}

function Dialog({ children, labelledBy, onClose }) {
  return (
    <div className="modal-overlay" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
        {children}
      </section>
    </div>
  )
}

function PayrollPlanDialog({ activeEmployeeCount, busy, initial, mode, onClose, onSubmit }) {
  const [values, setValues] = useState(initial)
  return (
    <Dialog labelledBy="payroll-plan-title" onClose={onClose}>
      <form onSubmit={(event) => { event.preventDefault(); onSubmit(values) }}>
        <div className="modal-header">
          <h3 id="payroll-plan-title">{mode === 'repeat' ? 'Repeat Last Payroll' : 'New Payroll Run'}</h3>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {mode === 'repeat' && (
            <div className="alert alert-info">
              The new draft uses current employee pay and copies supported recurring manual items from the selected run.
            </div>
          )}
          <div className="form-grid form-grid-2 payroll-plan-grid">
            <div className="form-group">
              <label htmlFor="payroll-period">Salary Period (Month) *</label>
              <input id="payroll-period" className="form-control" required type="month" value={values.period} onChange={(event) => setValues({ ...values, period: event.target.value })} />
            </div>
            <div className="form-group">
              <label htmlFor="payroll-payment-date">Payment Date *</label>
              <input id="payroll-payment-date" className="form-control" required type="date" value={values.paymentDate} onChange={(event) => setValues({ ...values, paymentDate: event.target.value })} />
              <span className="hint">Date salary is transferred to the bank</span>
            </div>
          </div>
          <div className="alert alert-info payroll-plan-note">
            Creates a payroll draft for <strong>{activeEmployeeCount === null ? 'all server-eligible active employees' : `${activeEmployeeCount} active employee${activeEmployeeCount === 1 ? '' : 's'}`}</strong>. Adjust individual amounts on the next screen.
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Creating...' : mode === 'repeat' ? 'Create from Last Payroll' : 'Create Payroll Run'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}

function AdjustmentDialog({ entry, kind, busy, onClose, onSave }) {
  const [values, setValues] = useState({ label: '', amount: '', recurrence: 'one_time', note: '' })
  const title = kind === 'allowance' ? 'Add allowance' : 'Add deduction'
  return (
    <Dialog labelledBy="payroll-adjustment-title" onClose={onClose}>
      <form onSubmit={(event) => { event.preventDefault(); onSave(values) }}>
        <div className="modal-header">
          <h3 id="payroll-adjustment-title">{title} for {entry.employeeName}</h3>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body form-grid form-grid-2">
          <div className="form-group">
            <label htmlFor="adjustment-label">Label *</label>
            <input id="adjustment-label" required maxLength="80" value={values.label} onChange={(event) => setValues({ ...values, label: event.target.value })} />
          </div>
          <div className="form-group">
            <label htmlFor="adjustment-amount">Amount (AED) *</label>
            <input id="adjustment-amount" required min="0.01" step="0.01" type="number" value={values.amount} onChange={(event) => setValues({ ...values, amount: event.target.value })} />
          </div>
          <div className="form-group">
            <label htmlFor="adjustment-recurrence">Recurrence *</label>
            <select id="adjustment-recurrence" value={values.recurrence} onChange={(event) => setValues({ ...values, recurrence: event.target.value })}>
              <option value="one_time">This payroll only</option>
              <option value="recurring">Carry into repeated payrolls</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="adjustment-note">Note</label>
            <input id="adjustment-note" maxLength="200" value={values.note} onChange={(event) => setValues({ ...values, note: event.target.value })} />
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>Add</button>
        </div>
      </form>
    </Dialog>
  )
}

function PayrollHistory({ busy, runs, onDelete, onOpen }) {
  if (runs.length === 0) {
    return (
      <div className="empty-state payroll-empty">
        <span aria-hidden="true" className="empty-state-icon">▤</span>
        <h3>No payroll runs yet</h3>
        <p>Create the first payroll run to start salary processing.</p>
      </div>
    )
  }
  return (
    <div className="table-wrap payroll-history-table">
      <table>
        <thead><tr><th>Period</th><th>Payment Date</th><th>Employees</th><th className="text-right">Total (AED)</th><th>Status</th><th>Approval</th><th>Validation</th><th>Updated</th><th aria-label="Actions" /></tr></thead>
        <tbody>{runs.map((run) => (
          <tr key={run.id} className="payroll-history-row" onClick={() => onOpen(run)}>
            <td><strong>{periodLabel(run.period)}</strong></td>
            <td>{run.paymentDate}</td>
            <td>{run.employeeCount}</td>
            <td className="text-right font-bold">{money(run.totalAmount)}</td>
            <td><span className={badge(run.runStatus)}>{run.runStatus === 'generated' ? 'Generated' : 'Draft'}</span></td>
            <td><span className={badge(run.approvalStatus)}>{run.approvalStatus.replaceAll('_', ' ')}</span></td>
            <td><span className={badge(run.validationStatus)}>{run.validationStatus}</span></td>
            <td className="text-muted text-sm">{new Date(run.updatedAt).toLocaleDateString('en-AE')}</td>
            <td onClick={(event) => event.stopPropagation()}>
              <div className="row-actions">
                <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label={`Open ${run.period}`} onClick={() => onOpen(run)}>›</button>
                {run.runStatus === 'draft' && run.approvalStatus === 'draft' && (
                  <button type="button" className="btn btn-ghost btn-icon btn-sm text-danger" disabled={busy} aria-label={`Delete ${run.period}`} onClick={() => onDelete(run)}>×</button>
                )}
              </div>
            </td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

function SalaryEntries({ busy, editable, entries, onAdd, onChange, onRemove }) {
  const totals = useMemo(() => entries.filter((entry) => !entry.excluded).reduce((result, entry) => {
    const preview = payrollPreview(entry)
    for (const key of Object.keys(result)) result[key] += Number(preview[key] ?? entry[key] ?? 0)
    return result
  }, { basicSalary: 0, housingAllowance: 0, transportAllowance: 0, fixedAllowance: 0, increment: 0, bonus: 0, otherPay: 0, variableAllowance: 0, leaveDeduction: 0, wpsVariablePay: 0, netPay: 0 }), [entries])

  return (
    <section className="card payroll-entries-card" aria-labelledby="salary-entries-title">
      <div className="card-header payroll-entries-header">
        <div><h3 id="salary-entries-title">Employee Salary Entries</h3><p>{entries.length} employee{entries.length === 1 ? '' : 's'} in this run</p></div>
        <span className="text-muted text-sm">Values in AED</span>
      </div>
      <div className="payroll-table table-wrap">
        <table>
          <thead><tr><th aria-label="Included">✓</th><th>Name</th><th>Basic</th><th>Housing</th><th>Transport</th><th>Allowance</th><th>Increment</th><th>Bonus/Incentive</th><th>Other Pay</th><th>Leave Ded.</th><th>Add Allow.</th><th>Deductions</th><th>Final Allow.</th><th>Total (AED)</th></tr></thead>
          <tbody>
            {entries.map((entry, index) => {
              const preview = payrollPreview(entry)
              const manualAllowances = entry.additionalAllowances.filter((item) => !/^(?:AUTO_|LEAVE_|ATTENDANCE_|ROSTER_|EXPENSE_|ADVANCE_)/.test(item.code))
              const manualDeductions = entry.deductions.filter((item) => !/^(?:AUTO_|LEAVE_|ATTENDANCE_|ROSTER_|EXPENSE_|ADVANCE_)/.test(item.code))
              return (
                <tr key={entry.id} className={entry.excluded ? 'excluded' : ''}>
                  <td><input type="checkbox" aria-label={`Include ${entry.employeeName}`} checked={!entry.excluded} disabled={!editable || busy} onChange={(event) => onChange(index, 'excluded', !event.target.checked)} /></td>
                  <td><strong>{entry.employeeName}</strong><small>{entry.sourceExplanations.join(' · ')}</small></td>
                  {['basicSalary', 'housingAllowance', 'transportAllowance', 'fixedAllowance'].map((field) => <td key={field}>{money(entry[field])}</td>)}
                  {['increment', 'bonus', 'otherPay'].map((field) => <td key={field}><input aria-label={`${entry.employeeName} ${field}`} disabled={!editable || busy} inputMode="decimal" value={entry[field]} onChange={(event) => onChange(index, field, event.target.value)} /></td>)}
                  <td><input aria-label={`${entry.employeeName} variable allowance`} disabled={!editable || busy} inputMode="decimal" value={entry.variableAllowance} onChange={(event) => onChange(index, 'variableAllowance', event.target.value)} /></td>
                  <td className="deduction-value">{money(entry.leaveDeduction)}</td>
                  <td className="adjustment-cell">
                    <button type="button" className="payroll-inline-action" disabled={!editable || busy} onClick={() => onAdd(index, 'allowance')}>Add</button>
                    {manualAllowances.map((item) => <button type="button" className="adjustment-chip" key={item.id} disabled={!editable || busy} title="Remove allowance" onClick={() => onRemove(index, 'allowance', item.id)}>{item.label} {money(item.amount)} ×</button>)}
                  </td>
                  <td className="adjustment-cell">
                    <button type="button" className="payroll-inline-action danger-link" disabled={!editable || busy} onClick={() => onAdd(index, 'deduction')}>Add</button>
                    {manualDeductions.map((item) => <button type="button" className="adjustment-chip deduction" key={item.id} disabled={!editable || busy} title="Remove deduction" onClick={() => onRemove(index, 'deduction', item.id)}>{item.label} {money(item.amount)} ×</button>)}
                  </td>
                  <td className="final-allowance">{money(preview.wpsVariablePay)}</td>
                  <td className="font-bold">{money(preview.netPay)}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot><tr><th colSpan="2">Totals</th><td>{money(totals.basicSalary)}</td><td>{money(totals.housingAllowance)}</td><td>{money(totals.transportAllowance)}</td><td>{money(totals.fixedAllowance)}</td><td>{money(totals.increment)}</td><td>{money(totals.bonus)}</td><td>{money(totals.otherPay)}</td><td className="deduction-value">{money(totals.leaveDeduction)}</td><td /><td /><td className="final-allowance">{money(totals.wpsVariablePay)}</td><td>{money(totals.netPay)}</td></tr></tfoot>
        </table>
      </div>
    </section>
  )
}

export default function Payroll({ account, authentication, branchId }) {
  const [runs, setRuns] = useState([])
  const [selected, setSelected] = useState(null)
  const [entries, setEntries] = useState([])
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState([])
  const [reason, setReason] = useState('')
  const [planDialog, setPlanDialog] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [adjustment, setAdjustment] = useState(null)

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
        setHistory([])
      }
      setMessage(success)
      await load()
      return true
    } catch (error) {
      setMessage(error.message)
      return false
    } finally {
      setBusy(false)
    }
  }

  const submitPlan = (values) => runAction(
    () => planDialog === 'repeat'
      ? repeatPayrollRun(authentication, branchId, runs[0], values)
      : createPayrollRun(authentication, branchId, values),
    planDialog === 'repeat' ? 'Payroll repeated into a new draft.' : 'Payroll draft created.',
  ).then((succeeded) => {
    if (succeeded) setPlanDialog(null)
  })

  const updateEntry = (index, field, value) => setEntries((current) => current.map((entry, position) => position === index ? { ...entry, [field]: value } : entry))
  const removeAdjustment = (index, kind, id) => setEntries((current) => current.map((entry, position) => {
    if (position !== index) return entry
    const field = kind === 'allowance' ? 'additionalAllowances' : 'deductions'
    return { ...entry, [field]: entry[field].filter((item) => item.id !== id) }
  }))
  const addAdjustment = (values) => {
    const field = adjustment.kind === 'allowance' ? 'additionalAllowances' : 'deductions'
    const item = {
      id: crypto.randomUUID(),
      code: `MANUAL_${adjustment.kind === 'allowance' ? 'ALLOW' : 'DEDUCT'}_${Date.now().toString(36).toUpperCase()}`.slice(0, 40),
      label: values.label.trim(), amount: Number(values.amount).toFixed(2), recurrence: values.recurrence,
      note: values.note.trim() || null,
    }
    setEntries((current) => current.map((entry, index) => index === adjustment.index ? { ...entry, [field]: [...entry[field], item] } : entry))
    setAdjustment(null)
  }

  if (account.role !== 'admin') return null

  if (selected) {
    const editable = selected.approvalStatus === 'draft' && selected.runStatus === 'draft'
    const activeEntries = entries.filter((entry) => !entry.excluded)
    const totals = activeEntries.reduce((sum, entry) => {
      const preview = payrollPreview(entry)
      return { basic: sum.basic + Number(preview.wpsBasicPay), variable: sum.variable + Number(preview.wpsVariablePay), net: sum.net + Number(preview.netPay) }
    }, { basic: 0, variable: 0, net: 0 })
    return (
      <section className="payroll payroll-detail" aria-labelledby="payroll-detail-title">
        <div className="payroll-detail-toolbar">
          <div className="payroll-detail-heading">
            <button type="button" className="btn btn-ghost payroll-back" onClick={() => setSelected(null)}>← Back</button>
            <h2 id="payroll-detail-title">Payroll: {periodLabel(selected.period)}</h2>
            <span className={badge(selected.approvalStatus)}>{selected.approvalStatus.replaceAll('_', ' ')}</span>
          </div>
          <div className="payroll-actions">
            <button type="button" className="btn btn-outline" disabled={busy || !editable} onClick={() => runAction(() => refreshPayrollRun(authentication, branchId, selected), 'Automatic payroll inputs refreshed.')}>Refresh inputs</button>
            <button type="button" className="btn btn-outline" disabled={busy || !editable} onClick={() => runAction(() => savePayrollEntries(authentication, branchId, selected, entries), 'Payroll entries saved.')}>Save Draft</button>
            {editable && <button type="button" className="btn btn-primary" disabled={busy || selected.validationStatus !== 'valid'} onClick={() => runAction(() => submitPayrollRun(authentication, branchId, selected), 'Payroll submitted for approval.')}>Submit for Approval</button>}
            {selected.approvalStatus === 'pending_approval' && <>
              <button type="button" className="btn btn-success" disabled={busy} onClick={() => runAction(() => approvePayrollRun(authentication, branchId, selected), 'Payroll approved.')}>Approve</button>
              <button type="button" className="btn btn-outline" disabled={busy || !reason.trim()} onClick={() => runAction(() => recallPayrollRun(authentication, branchId, selected, reason), 'Payroll recalled to draft.')}>Recall</button>
              <button type="button" className="btn btn-danger" disabled={busy || !reason.trim()} onClick={() => runAction(() => rejectPayrollRun(authentication, branchId, selected, reason), 'Payroll rejected to draft.')}>Reject</button>
            </>}
            {selected.approvalStatus === 'approved' && selected.runStatus === 'draft' && <button type="button" className="btn btn-primary" disabled={busy} onClick={() => runAction(() => generatePayrollRun(authentication, branchId, selected), 'Payroll generated and payslips issued.')}>Generate Payroll</button>}
            {selected.approvalStatus === 'approved' && selected.runStatus === 'generated' && <button type="button" className="btn btn-success" disabled={busy} onClick={() => runAction(async () => { saveDownload(await downloadPayslipsZip(authentication, branchId, selected.id)); return selected }, 'Payslip archive downloaded.')}>Download Payslips</button>}
          </div>
        </div>
        {message && <div className="alert alert-info" role="status">{message}</div>}
        {selected.approvalStatus === 'pending_approval' && <div className="payroll-reason"><label>Recall or rejection reason<input maxLength="500" value={reason} onChange={(event) => setReason(event.target.value)} /></label></div>}
        <section className="card payroll-run-details" aria-labelledby="payroll-run-details-title">
          <div className="card-header"><h3 id="payroll-run-details-title">Payroll Run Details</h3></div>
          <div className="form-grid form-grid-3 payroll-meta-grid">
            <div className="form-group"><label>Salary Period</label><input value={selected.period} readOnly /></div>
            <div className="form-group"><label>Payment Date</label><input value={selected.paymentDate} readOnly /></div>
            <div className="form-group"><label>Sequence</label><input value={selected.sequence} readOnly /></div>
          </div>
        </section>
        <div className="stats-grid payroll-summary-grid">
          <div className="stat-card"><div className="stat-label">Employees</div><div className="stat-value">{activeEntries.length}</div><div className="stat-sub">{entries.length - activeEntries.length} excluded</div></div>
          <div className="stat-card"><div className="stat-label">Total Basic</div><div className="stat-value">{money(totals.basic)}</div><div className="stat-sub">AED</div></div>
          <div className="stat-card"><div className="stat-label">Total WPS Allowance</div><div className="stat-value">{money(totals.variable)}</div><div className="stat-sub">AED variable pay</div></div>
          <div className="stat-card payroll-grand-total"><div className="stat-label">Grand Total (WPS)</div><div className="stat-value">{money(totals.net)}</div><div className="stat-sub">AED</div></div>
        </div>
        {selected.blockingErrors.map((error) => <div className="alert alert-danger" key={error}>{error}</div>)}
        {selected.sourceWarnings.map((warning) => <div className="alert alert-warning" key={warning}>{warning}</div>)}
        <SalaryEntries busy={busy} editable={editable} entries={entries} onAdd={(index, kind) => setAdjustment({ index, kind })} onChange={updateEntry} onRemove={removeAdjustment} />
        {history.length > 0 && <section className="card payroll-approval-history"><div className="card-header"><h3>Approval History</h3></div><ol>{history.map((item) => <li key={item.id}><strong>{item.action}</strong> by {item.actorName}{item.reason ? `: ${item.reason}` : ''}<time>{new Date(item.createdAt).toLocaleString('en-AE')}</time></li>)}</ol></section>}
        {adjustment && <AdjustmentDialog entry={entries[adjustment.index]} kind={adjustment.kind} busy={busy} onClose={() => setAdjustment(null)} onSave={addAdjustment} />}
      </section>
    )
  }

  const latest = runs[0]
  return (
    <section className="payroll payroll-list" aria-labelledby="payroll-title">
      <div className="module-toolbar payroll-toolbar">
        <div><h2 id="payroll-title">Payroll Runs</h2><p>Build salary drafts, complete approval, and issue payroll output.</p></div>
        <div className="module-actions">
          {latest && <button type="button" className="btn btn-outline" disabled={busy} onClick={() => setPlanDialog('repeat')}>▣ Repeat Last Payroll</button>}
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => setPlanDialog('new')}>＋ New Payroll Run</button>
        </div>
      </div>
      {message && <div className="alert alert-info" role="status">{message}</div>}
      <div className="stats-grid payroll-list-stats">
        <div className="stat-card"><div className="stat-label">Total Runs</div><div className="stat-value">{runs.length}</div></div>
        <div className="stat-card"><div className="stat-label">Generated</div><div className="stat-value text-success">{runs.filter((run) => run.runStatus === 'generated').length}</div></div>
        <div className="stat-card"><div className="stat-label">Drafts</div><div className="stat-value text-warning">{runs.filter((run) => run.runStatus === 'draft').length}</div></div>
      </div>
      <section className="card payroll-history-card" aria-labelledby="payroll-history-title">
        <div className="card-header"><h3 id="payroll-history-title">▤ Payroll History</h3></div>
        {status === 'loading' ? <div className="module-loading" role="status">Loading payroll runs...</div> : status === 'unavailable' ? <div className="alert alert-danger">Payroll runs are unavailable.</div> : <PayrollHistory busy={busy} runs={runs} onDelete={setDeleteTarget} onOpen={open} />}
      </section>
      {planDialog && <PayrollPlanDialog activeEmployeeCount={latest?.employeeCount ?? null} busy={busy} initial={emptyPlan} mode={planDialog} onClose={() => setPlanDialog(null)} onSubmit={submitPlan} />}
      {deleteTarget && <Dialog labelledBy="delete-payroll-title" onClose={() => setDeleteTarget(null)}><div className="modal-header"><h3 id="delete-payroll-title">Delete Payroll Draft</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={() => setDeleteTarget(null)}>×</button></div><div className="modal-body"><p>Delete the {periodLabel(deleteTarget.period)} payroll draft? This cannot be undone.</p></div><div className="modal-footer"><button type="button" className="btn btn-outline" onClick={() => setDeleteTarget(null)}>Cancel</button><button type="button" className="btn btn-danger" disabled={busy} onClick={() => runAction(async () => { await deletePayrollRun(authentication, branchId, deleteTarget); return null }, 'Payroll draft deleted.').then((succeeded) => { if (succeeded) setDeleteTarget(null) })}>Delete Draft</button></div></Dialog>}
    </section>
  )
}
