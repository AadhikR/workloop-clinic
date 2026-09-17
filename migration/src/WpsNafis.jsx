import { useCallback, useEffect, useState } from 'react'

import { readPayrollRuns } from './payrollApi.js'
import {
  confirmWps,
  createComplianceOverride,
  failWps,
  readNafisSnapshots,
  readSifInput,
  readWps,
  recordSifProjection,
  replaceNafisSnapshot,
  submitWps,
  updateWpsEntry,
} from './wpsNafisApi.js'

const ruleCodes = [
  'visa_expired',
  'emirates_id_expired',
  'labour_card_expired',
  'passport_expired',
  'professional_licence_expired',
]

export default function WpsNafis({ account, authentication, branchId }) {
  const [runs, setRuns] = useState([])
  const [runId, setRunId] = useState('')
  const [wps, setWps] = useState(null)
  const [sif, setSif] = useState(null)
  const [nafis, setNafis] = useState([])
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7))
  const [reference, setReference] = useState('')
  const [reason, setReason] = useState('')
  const [ruleCode, setRuleCode] = useState(ruleCodes[0])
  const [status, setStatus] = useState('loading')

  const refresh = useCallback(async () => {
    const [payroll, snapshots] = await Promise.all([
      readPayrollRuns(authentication, branchId, { status: 'generated' }),
      readNafisSnapshots(authentication, branchId),
    ])
    setRuns(payroll.items)
    setNafis(snapshots.items)
    const selected = payroll.items[0]?.id || ''
    setRunId(selected)
    if (selected) setWps(await readWps(authentication, branchId, selected))
    setStatus('ready')
  }, [authentication, branchId])

  useEffect(() => {
    const load = async () => {
      try {
        await refresh()
      } catch {
        setStatus('unavailable')
      }
    }
    void load()
  }, [refresh])

  if (account.role !== 'admin') return null

  const action = async (operation) => {
    setStatus('loading')
    try {
      const result = await operation()
      if (result?.runId) setWps(result)
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }

  const selectRun = async (event) => {
    const selected = event.target.value
    setRunId(selected)
    setSif(null)
    await action(async () => {
      const result = await readWps(authentication, branchId, selected)
      setWps(result)
      return result
    })
  }

  const currentNafis = nafis.find((item) => item.period === period) ?? null

  return (
    <section className="expenses" aria-labelledby="wps-nafis-title">
      <h2 id="wps-nafis-title">WPS and SIF</h2>
      <p>Review trusted SIF inputs and record bank payment state. File creation is not available here.</p>
      <label>
        Generated payroll
        <select value={runId} onChange={selectRun}>
          {runs.map((run) => <option key={run.id} value={run.id}>{run.period}</option>)}
        </select>
      </label>
      {status === 'loading' && <p>Loading WPS state...</p>}
      {status === 'unavailable' && <p>WPS or Nafis data is unavailable.</p>}
      {wps && (
        <div className="card">
          <p><strong>Status:</strong> {wps.status}</p>
          <div className="actions">
            <button type="button" onClick={() => action(async () => {
              const projection = await readSifInput(authentication, branchId, wps.runId, wps.status === 'partial_rejection')
              setSif(projection)
              return null
            })}>Preview SIF input</button>
            {(wps.status === 'draft' || wps.status === 'partial_rejection') && (
              <button type="button" onClick={() => action(() => recordSifProjection(authentication, branchId, wps))}>
                Record projection digest
              </button>
            )}
            {wps.status === 'sif_generated' && (
              <>
                <input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Bank reference" />
                <button type="button" onClick={() => action(() => submitWps(authentication, branchId, wps, reference))}>
                  Submit to bank
                </button>
              </>
            )}
            {['submitted', 'partial_rejection'].includes(wps.status) && (
              <button type="button" onClick={() => action(() => confirmWps(authentication, branchId, wps))}>Confirm paid</button>
            )}
            {wps.status !== 'confirmed' && (
              <button type="button" className="secondary" onClick={() => action(() => failWps(authentication, branchId, wps, reason))}>
                Mark failed
              </button>
            )}
          </div>
          <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Required reason" />
          <table>
            <thead><tr><th>Employee</th><th>Payment state</th><th>Actions</th></tr></thead>
            <tbody>{wps.entries.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.employeeName}</td><td>{entry.paymentStatus}</td>
                <td>{entry.paymentStatus === 'pending' && (
                  <>
                    <button type="button" onClick={() => action(() => updateWpsEntry(authentication, branchId, wps, entry, 'paid'))}>Paid</button>
                    <button type="button" className="secondary" onClick={() => action(() => updateWpsEntry(authentication, branchId, wps, entry, 'reject', reason))}>Reject</button>
                  </>
                )}</td>
              </tr>
            ))}</tbody>
          </table>
          <h3>Compliance override</h3>
          <select value={ruleCode} onChange={(event) => setRuleCode(event.target.value)}>
            {ruleCodes.map((code) => <option key={code} value={code}>{code}</option>)}
          </select>
          <button type="button" onClick={() => action(() => createComplianceOverride(authentication, branchId, wps.runId, {
            ruleCode, reason, payrollEntryId: null,
          }))}>Record override</button>
        </div>
      )}
      {sif && (
        <div className="card">
          <h3>{sif.mode === 'rejected' ? 'Rejected-entry input' : 'Full SIF input'}</h3>
          <p>{sif.header.employeeCount} rows · AED {sif.header.totalIntegerPay} · digest {sif.digest}</p>
          <table><thead><tr><th>MOL ID</th><th>Paid days</th><th>Basic</th><th>Variable</th><th>Total</th></tr></thead>
            <tbody>{sif.entries.map((entry) => <tr key={entry.payrollEntryId}>
              <td>{entry.employeeMolId}</td><td>{entry.paidDays}</td><td>{entry.basicPay}</td>
              <td>{entry.variablePay}</td><td>{entry.totalPay}</td>
            </tr>)}</tbody>
          </table>
        </div>
      )}
      <h2>Nafis snapshots</h2>
      <p>One trusted snapshot is kept for each branch and payroll period.</p>
      <input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} />
      <button type="button" onClick={() => action(async () => {
        const result = await replaceNafisSnapshot(authentication, branchId, period, currentNafis)
        setNafis((items) => [result, ...items.filter((item) => item.id !== result.id)])
        return null
      })}>{currentNafis ? 'Replace snapshot' : 'Generate snapshot'}</button>
      <ul>{nafis.map((item) => <li key={item.id}>
        {item.period}: {item.emiratiCount}/{item.totalHeadcount} UAE nationals ({item.ratioPercent}%)
      </li>)}</ul>
    </section>
  )
}
