import { useCallback, useEffect, useState } from 'react'
import { readSelfPayslip, readSelfPayslips } from './payrollApi.js'
import { openPdf } from './outputDelivery.js'
import { downloadSelfPayslipPdf } from './renderedOutputApi.js'

export default function Payslips({ account, authentication }) {
  const [items, setItems] = useState([])
  const [details, setDetails] = useState({})
  const [expanded, setExpanded] = useState(null)
  const [status, setStatus] = useState('loading')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const allowed = ['employee', 'manager'].includes(account.role)
  const load = useCallback(async () => {
    try { const result = await readSelfPayslips(authentication); setItems(result.items); setStatus('ready') }
    catch { setStatus('unavailable') }
  }, [authentication])
  useEffect(() => {
    if (!allowed) return
    let active = true
    readSelfPayslips(authentication).then((result) => { if (active) { setItems(result.items); setStatus('ready') } }).catch(() => { if (active) setStatus('unavailable') })
    return () => { active = false }
  }, [allowed, authentication])
  if (!allowed) return null
  const open = async (item) => {
    if (expanded === item.id) { setExpanded(null); return }
    setBusy(true); setMessage('')
    try { const detail = await readSelfPayslip(authentication, item.id); setDetails((previous) => ({ ...previous, [item.id]: detail })); setExpanded(item.id) }
    catch { setMessage('This payslip could not be opened. Your issued payslip list has been kept.') }
    finally { setBusy(false) }
  }
  return <section className="payslips" aria-labelledby="payslips-title">
    <header className="employee-section-heading"><div><h2 id="payslips-title">My payslips</h2><p>Issued payroll snapshots and protected printable PDFs.</p></div><button type="button" className="secondary" disabled={busy} onClick={load}>Reload</button></header>
    {status === 'unavailable' && <p role="alert">Payslips are unavailable. <button type="button" onClick={load}>Retry</button></p>}
    {status === 'loading' && <p role="status">Loading payslips...</p>}
    {message && <p role="alert">{message}</p>}
    <div className="staff-records">{[...items].sort((left, right) => right.period.localeCompare(left.period)).map((item) => {
      const selected = details[item.id]
      return <article className="employee-panel staff-record" key={item.id}>
        <button type="button" className="staff-record-toggle" disabled={busy} aria-expanded={expanded === item.id} aria-controls={`payslip-${item.id}`} onClick={() => open(item)}><span><strong>{item.period}</strong><small>Paid {item.paymentDate}</small></span><span className="status-pill" data-status="paid">Issued</span><strong>AED {item.netPay}</strong><span aria-hidden="true">{expanded === item.id ? '⌃' : '⌄'}</span></button>
        {expanded === item.id && selected && <div id={`payslip-${item.id}`} className="payslip-detail">
          <h3>{selected.period} · {selected.employeeName}</h3><p>Payment date: {selected.paymentDate}</p>
          <div className="employee-split-grid"><section><h4>Earnings</h4><dl>{selected.earnings.map((line) => <div key={`${line.label}:${line.amount}`}><dt>{line.label}</dt><dd>AED {line.amount}</dd></div>)}</dl></section><section><h4>Deductions</h4>{selected.deductions.length === 0 ? <p>None</p> : <dl>{selected.deductions.map((line) => <div key={`${line.label}:${line.amount}`}><dt>{line.label}</dt><dd>AED {line.amount}</dd></div>)}</dl>}</section></div>
          <p>Gross AED {selected.grossPay} · Total deductions AED {selected.totalDeductions}</p><p className="payslip-net"><strong>Net pay AED {selected.netPay}</strong></p>
          <button type="button" disabled={busy} onClick={async () => { setBusy(true); setMessage(''); try { openPdf(await downloadSelfPayslipPdf(authentication, selected.id)) } catch { setMessage('The printable PDF is unavailable. Your payslip remains open.') } finally { setBusy(false) } }}>Open printable PDF</button>
        </div>}
      </article>
    })}</div>
    {status === 'ready' && items.length === 0 && <div className="empty-state">No payslips have been issued.</div>}
  </section>
}
