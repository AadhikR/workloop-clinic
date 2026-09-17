import { useEffect, useState } from 'react'

import { readSelfPayslip, readSelfPayslips } from './payrollApi.js'

export default function Payslips({ account, authentication }) {
  const [items, setItems] = useState([])
  const [selected, setSelected] = useState(null)
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    if (account.role !== 'employee') return undefined
    const controller = new AbortController()
    readSelfPayslips(authentication)
      .then((result) => {
        if (!controller.signal.aborted) {
          setItems(result.items)
          setStatus('ready')
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus('unavailable')
      })
    return () => controller.abort()
  }, [account.role, authentication])

  if (account.role !== 'employee') return null

  const open = async (id) => {
    setStatus('loading-detail')
    try {
      setSelected(await readSelfPayslip(authentication, id))
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }

  return (
    <section className="payslips" aria-labelledby="payslips-title">
      <h2 id="payslips-title">My payslips</h2>
      <p>Issued payroll snapshots are read-only. PDF downloads will arrive in a later phase.</p>
      {status === 'unavailable' && <p>Payslips are unavailable.</p>}
      {status === 'loading' && <p>Loading payslips…</p>}
      {items.map((item) => (
        <button type="button" className="secondary" key={item.id} onClick={() => open(item.id)}>
          <strong>{item.period}</strong> · AED {item.netPay}
        </button>
      ))}
      {status === 'ready' && items.length === 0 && <p>No payslips have been issued.</p>}
      {selected && (
        <article className="payslip-detail">
          <h3>{selected.period} · {selected.employeeName}</h3>
          <p>Payment date: {selected.paymentDate}</p>
          <h4>Earnings</h4>
          <dl>{selected.earnings.map((line) => <div key={`${line.label}:${line.amount}`}><dt>{line.label}</dt><dd>AED {line.amount}</dd></div>)}</dl>
          <h4>Deductions</h4>
          {selected.deductions.length === 0
            ? <p>None</p>
            : <dl>{selected.deductions.map((line) => <div key={`${line.label}:${line.amount}`}><dt>{line.label}</dt><dd>AED {line.amount}</dd></div>)}</dl>}
          <p><strong>Gross:</strong> AED {selected.grossPay}</p>
          <p><strong>Total deductions:</strong> AED {selected.totalDeductions}</p>
          <p><strong>Net pay:</strong> AED {selected.netPay}</p>
        </article>
      )}
    </section>
  )
}
