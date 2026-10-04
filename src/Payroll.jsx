import { readFinancialCollection } from './financialCollections.js'
import { useCallback, useEffect, useMemo, useState } from 'react'
import Dialog from './PortalDialog.jsx'
import PayrollRoutingDialog from './PayrollRoutingDialog.jsx'

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

function payrollIssues(run, entries) {
  const issues = new Map()
  for (const code of [...run.blockingErrors, ...run.sourceWarnings]) {
    const source = code.includes('attendance') ? 'attendance' : code.includes('roster') ? 'roster' : null
    if (source) {
      issues.set(source, source === 'attendance'
        ? { title: 'Attendance is not finalised', detail: 'Close the attendance period, then refresh payroll inputs.', href: '/admin/attendance' }
        : { title: 'Roster inputs are not ready', detail: 'Complete the roster payroll inputs, then refresh this draft.', href: '/admin/roster' })
    } else if (code.startsWith('negative_net_pay:')) {
      const employee = entries.find((entry) => entry.employeeId === code.split(':')[1])
      issues.set(code, { title: `${employee?.employeeName ?? 'An employee'} has negative net pay`, detail: 'Review the employee deductions before submitting this payroll.' })
    } else {
      issues.set(code, { title: 'Payroll requires review', detail: 'Refresh payroll inputs and review the salary entries before submitting.' })
    }
  }
  return [...issues.values()]
}

function EmployeeBreakdown({ entry, onClose }) {
  const preview = payrollPreview(entry)
  const row = (label, amount, deduction = false) => <div className="payroll-breakdown-row" key={label}><span>{label}</span><strong className={deduction ? 'text-danger' : ''}>AED {money(amount)}</strong></div>
  return <Dialog labelledBy="payroll-breakdown-title" onClose={onClose} drawer>
    <div className="modal-header"><div><span className="text-muted text-sm">Salary breakdown</span><h3 id="payroll-breakdown-title">{entry.employeeName}</h3></div><button type="button" className="btn btn-ghost btn-icon" aria-label="Close salary breakdown" onClick={onClose}>×</button></div>
    <div className="modal-body">
      <section className="payroll-breakdown-section"><h4>Earnings</h4>{[['Basic salary', entry.basicSalary], ['Housing', entry.housingAllowance], ['Transport', entry.transportAllowance], ['Fixed allowance', entry.fixedAllowance], ['Increment', entry.increment], ['Bonus / incentive', entry.bonus], ['Other pay', entry.otherPay], ['Variable allowance', entry.variableAllowance]].map(([label, amount]) => row(label, amount))}{entry.additionalAllowances.map((item) => row(item.label, item.amount))}{row('Gross earnings', preview.grossPay)}</section>
      <section className="payroll-breakdown-section"><h4>Deductions</h4>{row('Leave deduction', entry.leaveDeduction, true)}{entry.deductions.map((item) => row(item.label, item.amount, true))}{row('Total deductions', preview.totalDeductions, true)}</section>
      {entry.sourceExplanations.length > 0 && <section className="payroll-breakdown-section"><h4>Automatic payroll inputs</h4>{entry.sourceExplanations.map((text) => <p key={text}>{text}</p>)}</section>}
      <section className="payroll-breakdown-section"><h4>WPS split</h4>{row('Basic pay', preview.wpsBasicPay)}{row('Variable pay', preview.wpsVariablePay)}</section>
      <div className="payroll-net-result"><span>Net pay{entry.excluded ? ' · Excluded' : ''}</span><strong>AED {money(preview.netPay)}</strong></div>
    </div>
    <div className="modal-footer"><button type="button" className="btn btn-outline" onClick={onClose}>Close</button></div>
  </Dialog>
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

function SalaryEntries({ busy, editable, entries, originalEntries, onAdd, onChange, onRemove, onInspect }) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const entryStatus = (entry) => entry.excluded ? 'excluded' : Number(payrollPreview(entry).netPay) < 0 ? 'needs_review' : JSON.stringify(entry) !== JSON.stringify(originalEntries.find((item) => item.id === entry.id)) ? 'changed' : 'ready'
  const visible = entries.filter((entry) => entry.employeeName.toLowerCase().includes(search.trim().toLowerCase()) && (filter === 'all' || entryStatus(entry) === filter))
  const totals = useMemo(() => entries.filter((entry) => !entry.excluded).reduce((result, entry) => {
    const preview = payrollPreview(entry)
    for (const key of Object.keys(result)) result[key] += Number(preview[key] ?? entry[key] ?? 0)
    return result
  }, { basicSalary: 0, housingAllowance: 0, transportAllowance: 0, fixedAllowance: 0, increment: 0, bonus: 0, otherPay: 0, variableAllowance: 0, leaveDeduction: 0, grossPay: 0, netPay: 0 }), [entries])

  return (
    <section className="card payroll-entries-card" aria-labelledby="salary-entries-title">
      <div className="card-header payroll-entries-header">
        <div><h3 id="salary-entries-title">Employee Salary Entries</h3><p>Review exceptions first, then open an employee for a full pay breakdown.</p></div>
        <div className="payroll-entries-toolbar"><label className="payroll-entry-search"><input aria-label="Search payroll employees" placeholder="Search employee..." value={search} onChange={(event) => setSearch(event.target.value)} /></label><select className="payroll-status-filter" aria-label="Filter payroll employees" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All employees</option><option value="needs_review">Needs review</option><option value="changed">Changed</option><option value="ready">Ready</option><option value="excluded">Excluded</option></select><span className="text-muted text-sm">{visible.length} of {entries.length} · AED</span></div>
      </div>
      <div className="payroll-table table-wrap">
        <table>
          <thead><tr><th aria-label="Included">✓</th><th>Employee / Status</th><th>Basic</th><th>Housing</th><th>Transport</th><th>Fixed Allow.</th><th>Increment</th><th>Bonus/Incentive</th><th>Other Pay</th><th>Variable Allow.</th><th>Leave Ded.</th><th>Add. Allow.</th><th>Deductions</th><th className="gross-earnings">Gross Earnings</th><th>Net Pay</th></tr></thead>
          <tbody>
            {visible.map((entry) => {
              const index = entries.findIndex((item) => item.id === entry.id)
              const preview = payrollPreview(entry)
              const manualAllowances = entry.additionalAllowances.filter((item) => !/^(?:AUTO_|LEAVE_|ATTENDANCE_|ROSTER_|EXPENSE_|ADVANCE_)/.test(item.code))
              const manualDeductions = entry.deductions.filter((item) => !/^(?:AUTO_|LEAVE_|ATTENDANCE_|ROSTER_|EXPENSE_|ADVANCE_)/.test(item.code))
              return (
                <tr key={entry.id} className={entry.excluded ? 'excluded' : ''}>
                  <td><input type="checkbox" aria-label={`Include ${entry.employeeName}`} checked={!entry.excluded} disabled={!editable || busy} onChange={(event) => onChange(index, 'excluded', !event.target.checked)} /></td>
                  <td><button type="button" className="payroll-employee-link" onClick={() => onInspect(entry.id)}>{entry.employeeName}</button><span className={`payroll-row-status ${entryStatus(entry)}`}>{entryStatus(entry).replaceAll('_', ' ')}</span></td>
                  {['basicSalary', 'housingAllowance', 'transportAllowance', 'fixedAllowance'].map((field) => <td key={field}>{money(entry[field])}</td>)}
                  {['increment', 'bonus', 'otherPay'].map((field) => <td key={field}><input type="number" min="0" step="0.01" aria-label={`${entry.employeeName} ${field}`} disabled={!editable || busy || entry.excluded} inputMode="decimal" value={entry[field]} onChange={(event) => onChange(index, field, event.target.value)} /></td>)}
                  <td><input type="number" min="0" step="0.01" aria-label={`${entry.employeeName} variable allowance`} disabled={!editable || busy || entry.excluded} inputMode="decimal" value={entry.variableAllowance} onChange={(event) => onChange(index, 'variableAllowance', event.target.value)} /></td>
                  <td className="deduction-value">{money(entry.leaveDeduction)}</td>
                  <td className="adjustment-cell">
                    <span className="text-success">{money(entry.additionalAllowances.reduce((sum, item) => sum + Number(item.amount), 0))}</span><br />
                    <button type="button" className="payroll-inline-action" aria-label={`Add allowance for ${entry.employeeName}`} disabled={!editable || busy || entry.excluded} onClick={() => onAdd(index, 'allowance')}>Add</button>
                    {manualAllowances.map((item) => <button type="button" className="adjustment-chip" key={item.id} disabled={!editable || busy} title="Remove allowance" onClick={() => onRemove(index, 'allowance', item.id)}>{item.label} {money(item.amount)} ×</button>)}
                  </td>
                  <td className="adjustment-cell">
                    <span className="text-danger">{money(entry.deductions.reduce((sum, item) => sum + Number(item.amount), 0))}</span><br />
                    <button type="button" className="payroll-inline-action danger-link" aria-label={`Add deduction for ${entry.employeeName}`} disabled={!editable || busy || entry.excluded} onClick={() => onAdd(index, 'deduction')}>Add</button>
                    {manualDeductions.map((item) => <button type="button" className="adjustment-chip deduction" key={item.id} disabled={!editable || busy} title="Remove deduction" onClick={() => onRemove(index, 'deduction', item.id)}>{item.label} {money(item.amount)} ×</button>)}
                  </td>
                  <td className="gross-earnings">{money(preview.grossPay)}</td>
                  <td className="font-bold">{money(preview.netPay)}</td>
                </tr>
              )
            })}
            {visible.length === 0 && <tr><td colSpan="15"><div className="empty-state"><h3>No matching employees</h3><p>Change the search or employee filter.</p></div></td></tr>}
          </tbody>
          <tfoot><tr><th colSpan="2">Run totals</th><td>{money(totals.basicSalary)}</td><td>{money(totals.housingAllowance)}</td><td>{money(totals.transportAllowance)}</td><td>{money(totals.fixedAllowance)}</td><td>{money(totals.increment)}</td><td>{money(totals.bonus)}</td><td>{money(totals.otherPay)}</td><td>{money(totals.variableAllowance)}</td><td className="deduction-value">{money(totals.leaveDeduction)}</td><td>{money(entries.filter((entry) => !entry.excluded).reduce((sum, entry) => sum + entry.additionalAllowances.reduce((amount, item) => amount + Number(item.amount), 0), 0))}</td><td className="deduction-value">{money(entries.filter((entry) => !entry.excluded).reduce((sum, entry) => sum + entry.deductions.reduce((amount, item) => amount + Number(item.amount), 0), 0))}</td><td className="gross-earnings">{money(totals.grossPay)}</td><td>{money(totals.netPay)}</td></tr></tfoot>
        </table>
      </div>
      <p className="payroll-table-note">Base pay and leave deductions come from employee records and payroll inputs. Run totals include all included employees, even when this view is filtered.</p>
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
  const [dirty, setDirty] = useState(false)
  const [showValidation, setShowValidation] = useState(false)
  const [detailEmployeeId, setDetailEmployeeId] = useState(null)
  const [confirmBack, setConfirmBack] = useState(false)
  const [routingOpen, setRoutingOpen] = useState(false)

  const load = useCallback(async () => {
    if (account.role !== 'admin') return
    setStatus('loading')
    try {
      const result = await readFinancialCollection((options) => readPayrollRuns(authentication, branchId, options))
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
      setDirty(false)
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
        setDirty(false)
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

  const updateEntry = (index, field, value) => {
    setDirty(true)
    setEntries((current) => current.map((entry, position) => position === index ? { ...entry, [field]: value } : entry))
  }
  const removeAdjustment = (index, kind, id) => {
    setDirty(true)
    setEntries((current) => current.map((entry, position) => {
      if (position !== index) return entry
      const field = kind === 'allowance' ? 'additionalAllowances' : 'deductions'
      return { ...entry, [field]: entry[field].filter((item) => item.id !== id) }
    }))
  }

  const saveDraft = () => {
    const fields = ['increment', 'bonus', 'otherPay', 'variableAllowance']
    if (entries.some((entry) => fields.some((field) => !Number.isFinite(Number(entry[field])) || Number(entry[field]) < 0))) {
      setMessage('Enter a non-negative amount in each editable salary field before saving.')
      return
    }
    const prepared = entries.map((entry) => ({ ...entry, ...Object.fromEntries(fields.map((field) => [field, Number(entry[field]).toFixed(2)])) }))
    return runAction(() => savePayrollEntries(authentication, branchId, selected, prepared), 'Payroll entries saved.')
  }
  const addAdjustment = (values) => {
    const field = adjustment.kind === 'allowance' ? 'additionalAllowances' : 'deductions'
    const item = {
      id: crypto.randomUUID(),
      code: `MANUAL_${adjustment.kind === 'allowance' ? 'ALLOW' : 'DEDUCT'}_${Date.now().toString(36).toUpperCase()}`.slice(0, 40),
      label: values.label.trim(), amount: Number(values.amount).toFixed(2), recurrence: values.recurrence,
      note: values.note.trim() || null,
    }
    setEntries((current) => current.map((entry, index) => index === adjustment.index ? { ...entry, [field]: [...entry[field], item] } : entry))
    setDirty(true)
    setAdjustment(null)
  }

  if (account.role !== 'admin') return null

  if (selected) {
    const issues = payrollIssues(selected, entries)
    const detailEmployee = entries.find((entry) => entry.id === detailEmployeeId)
    const editable = selected.approvalStatus === 'draft' && selected.runStatus === 'draft'
    const activeEntries = entries.filter((entry) => !entry.excluded)
    const totals = activeEntries.reduce((sum, entry) => {
      const preview = payrollPreview(entry)
      return { gross: sum.gross + Number(preview.grossPay), deductions: sum.deductions + Number(preview.totalDeductions), net: sum.net + Number(preview.netPay) }
    }, { gross: 0, deductions: 0, net: 0 })
    return (
      <section className="payroll payroll-detail" aria-labelledby="payroll-detail-title">
        <div className="payroll-detail-toolbar">
          <div className="payroll-detail-heading">
            <button type="button" className="btn btn-ghost btn-sm payroll-back" onClick={() => dirty ? setConfirmBack(true) : setSelected(null)}>← Back</button>
            <h2 id="payroll-detail-title">Payroll: {periodLabel(selected.period)}</h2>
            <span className={badge(selected.approvalStatus)}>{selected.approvalStatus === 'draft' ? 'Draft' : selected.approvalStatus === 'pending_approval' ? 'Pending approval' : 'Approved'}</span>
          </div>
          <div className="payroll-actions">
            <span className={`payroll-save-state${dirty ? ' unsaved' : ''}`} role="status">{busy ? 'Working...' : dirty ? 'Unsaved changes' : 'All changes saved'}</span>
            <button type="button" className="btn btn-outline btn-sm" disabled={busy || !editable || dirty} title={dirty ? 'Save your changes before refreshing payroll inputs' : undefined} onClick={() => runAction(() => refreshPayrollRun(authentication, branchId, selected), 'Automatic payroll inputs refreshed.')}>Refresh inputs</button>
            <button type="button" className="btn btn-outline btn-sm" disabled={busy || !editable} onClick={saveDraft}>Save Draft</button>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setShowValidation(true)}>Validate{issues.length ? ` (${issues.length})` : ''}</button>
            {editable && <button type="button" className="btn btn-primary btn-sm" disabled={busy || dirty || selected.validationStatus !== 'valid'} title={dirty ? 'Save changes before submitting' : issues.length ? 'Resolve payroll validation issues before submitting' : undefined} onClick={() => runAction(() => submitPayrollRun(authentication, branchId, selected), 'Payroll submitted for approval.')}>Submit for Approval</button>}
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
            <div className="form-group"><label htmlFor="run-salary-period">Salary Period</label><input id="run-salary-period" value={periodLabel(selected.period)} readOnly /></div>
            <div className="form-group"><label htmlFor="run-payment-date">Payment Date</label><input id="run-payment-date" type="date" value={selected.paymentDate} readOnly /></div>
            <div className="form-group"><label htmlFor="run-sequence">Sequence</label><input id="run-sequence" value={selected.sequence} readOnly /></div>
          </div>
        </section>
        <div className="stats-grid payroll-summary-grid">
          <div className="stat-card"><div className="stat-label">Employees</div><div className="stat-value">{activeEntries.length}</div><div className="stat-sub">{entries.length - activeEntries.length} excluded</div></div>
          <div className="stat-card"><div className="stat-label">Gross Earnings</div><div className="stat-value">{money(totals.gross)}</div><div className="stat-sub">AED</div></div>
          <div className="stat-card"><div className="stat-label">Total Deductions</div><div className="stat-value text-danger">{money(totals.deductions)}</div><div className="stat-sub">AED</div></div>
          <div className="stat-card payroll-grand-total"><div className="stat-label">Net Payroll</div><div className="stat-value">{money(totals.net)}</div><div className="stat-sub">AED</div></div>
        </div>
        {issues.length > 0 && <div className="alert alert-warning payroll-validation-summary"><div><strong>Payroll needs review</strong><p>{issues.map((issue) => issue.title).join('. ')}. Resolve these items before submitting for approval.</p></div><button type="button" className="btn btn-outline btn-sm" onClick={() => setShowValidation(true)}>Review issues</button></div>}
        {!editable && <div className="alert alert-info">{selected.runStatus === 'generated' ? 'Payroll finalised. Salary entries are locked and payslips have been issued.' : selected.approvalStatus === 'approved' ? 'Payroll approved. Generate payroll to issue payslips and lock this run.' : 'Payroll is pending approval. Entries are locked during review.'}</div>}
        <SalaryEntries busy={busy} editable={editable} entries={entries} originalEntries={selected.entries} onInspect={setDetailEmployeeId} onAdd={(index, kind) => setAdjustment({ index, kind })} onChange={updateEntry} onRemove={removeAdjustment} />
        {history.length > 0 && <section className="card payroll-approval-history"><div className="card-header"><h3>Approval History</h3></div><ol>{history.map((item) => <li key={item.id}><strong>{item.action}</strong> by {item.actorName}{item.reason ? `: ${item.reason}` : ''}<time>{new Date(item.createdAt).toLocaleString('en-AE')}</time></li>)}</ol></section>}
        {adjustment && <AdjustmentDialog entry={entries[adjustment.index]} kind={adjustment.kind} busy={busy} onClose={() => setAdjustment(null)} onSave={addAdjustment} />}
        {detailEmployee && <EmployeeBreakdown entry={detailEmployee} onClose={() => setDetailEmployeeId(null)} />}
        {showValidation && <Dialog labelledBy="payroll-validation-title" onClose={() => setShowValidation(false)}><div className="modal-header"><h3 id="payroll-validation-title">Payroll validation</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close validation" onClick={() => setShowValidation(false)}>×</button></div><div className="modal-body"><div className={`alert ${selected.validationStatus === 'valid' && !dirty ? 'alert-success' : 'alert-warning'}`}>{dirty ? 'Save changes to validate the latest payroll figures.' : selected.validationStatus === 'valid' ? 'Payroll is ready for approval.' : 'Resolve these issues before submitting payroll.'}</div><ul className="payroll-readiness-list">{issues.map((issue) => <li key={issue.title}><strong>{issue.title}</strong><p>{issue.detail}</p>{issue.href && <a href={issue.href}>Open {issue.href.endsWith('attendance') ? 'Attendance' : 'Roster'}</a>}</li>)}</ul></div><div className="modal-footer"><button type="button" className="btn btn-outline" onClick={() => setShowValidation(false)}>Close</button></div></Dialog>}
        {confirmBack && <Dialog labelledBy="payroll-unsaved-title" onClose={() => setConfirmBack(false)}><div className="modal-header"><h3 id="payroll-unsaved-title">Unsaved payroll changes</h3></div><div className="modal-body"><p>Save this draft before leaving, or discard your unsaved changes.</p></div><div className="modal-footer"><button type="button" className="btn btn-outline" onClick={() => setConfirmBack(false)}>Keep editing</button><button type="button" className="btn btn-danger" onClick={() => { setConfirmBack(false); setDirty(false); setSelected(null) }}>Discard changes</button></div></Dialog>}
      </section>
    )
  }

  const latest = runs[0]
  return (
    <section className="payroll payroll-list" aria-labelledby="payroll-title">
      <div className="module-toolbar payroll-toolbar">
        <div><h2 id="payroll-title">Payroll Runs</h2><p>Build salary drafts, complete approval, and issue payroll output.</p></div>
        <div className="module-actions"><button type="button" className="btn btn-outline" disabled={busy} onClick={() => setRoutingOpen(true)}>Routing settings</button>
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
      {routingOpen && <PayrollRoutingDialog authentication={authentication} branchId={branchId} onClose={() => setRoutingOpen(false)} onSaved={async () => { await load(); setMessage('Routing code saved.') }} />}
      {planDialog && <PayrollPlanDialog activeEmployeeCount={latest?.employeeCount ?? null} busy={busy} initial={emptyPlan} mode={planDialog} onClose={() => setPlanDialog(null)} onSubmit={submitPlan} />}
      {deleteTarget && <Dialog labelledBy="delete-payroll-title" onClose={() => setDeleteTarget(null)}><div className="modal-header"><h3 id="delete-payroll-title">Delete Payroll Draft</h3><button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={() => setDeleteTarget(null)}>×</button></div><div className="modal-body"><p>Delete the {periodLabel(deleteTarget.period)} payroll draft? This cannot be undone.</p></div><div className="modal-footer"><button type="button" className="btn btn-outline" onClick={() => setDeleteTarget(null)}>Cancel</button><button type="button" className="btn btn-danger" disabled={busy} onClick={() => runAction(async () => { await deletePayrollRun(authentication, branchId, deleteTarget); return null }, 'Payroll draft deleted.').then((succeeded) => { if (succeeded) setDeleteTarget(null) })}>Delete Draft</button></div></Dialog>}
    </section>
  )
}
