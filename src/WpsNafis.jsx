import { useCallback, useEffect, useState } from 'react'
import Dialog from './PortalDialog.jsx'
import { readFinancialCollection } from './financialCollections.js'

import { readPayrollRuns } from './payrollApi.js'
import { saveDownload } from './outputDelivery.js'
import { downloadNafis } from './outputApi.js'
import {
  confirmWps,
  createComplianceOverride,
  failWps,
  readNafisSnapshots,
  downloadSif,
  previewSif,
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
  if (account.role !== 'admin') return null
  return <ScopedWps account={account} authentication={authentication} branchId={branchId} key={branchId} />
}

function ScopedWps({ account, authentication, branchId }) {
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
  const [message, setMessage] = useState('')

  const refresh = useCallback(async () => {
    const [payroll, snapshots] = await Promise.all([
      readFinancialCollection((page) => readPayrollRuns(authentication, branchId, { status: 'generated', ...page })),
      readFinancialCollection((page) => readNafisSnapshots(authentication, branchId, undefined, page)),
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
    setMessage('')
    try {
      const result = await operation()
      if (result?.runId) setWps(result)
      setStatus('ready')
    } catch {
      setMessage('The action could not be completed. Your values and the last confirmed state are retained.')
      setStatus('ready')
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
    <section className="wps-workspace" aria-labelledby="wps-nafis-title">
      <h2 id="wps-nafis-title">WPS and SIF</h2>
      <p>Preview and download SIF files from the finalized payroll projection.</p>
      <label>
        Generated payroll
        <select value={runId} onChange={selectRun} disabled={status !== 'ready'}>
          {runs.map((run) => <option key={run.id} value={run.id}>{run.period}</option>)}
        </select>
      </label>
      {status === 'loading' && <p>Loading WPS state...</p>}
      {status === 'unavailable' && <p>WPS or Nafis data is unavailable.</p>}
      {message && <p role="alert">{message}</p>}
      <fieldset disabled={status !== 'ready'} className="wps-controls">
      {wps && (
        <div className="card">
          <p><strong>Status:</strong> {wps.status}</p>
          <div className="actions">
            <button type="button" onClick={() => action(async () => {
              const projection = await previewSif(authentication, branchId, wps.runId, wps.status === 'partial_rejection')
              setSif(projection)
              return null
            })}>Preview SIF</button>
            <button type="button" onClick={() => action(async () => {
              const output = await downloadSif(authentication, branchId, wps.runId, wps.status === 'partial_rejection')
              saveDownload(output)
              return null
            })}>Download SIF</button>
            {(wps.status === 'draft' || wps.status === 'partial_rejection') && (
              <button type="button" onClick={() => action(() => recordSifProjection(authentication, branchId, wps))}>
                Prepare SIF
              </button>
            )}
            {wps.status === 'sif_generated' && (
              <>
                <label>Bank reference<input value={reference} onChange={(event) => setReference(event.target.value)} /></label>
                <button type="button" onClick={() => action(() => submitWps(authentication, branchId, wps, reference))}>
                  Record bank submission
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
          <label>Required reason<input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <div className="table-wrap"><table>
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
          </table></div>
          <h3>Compliance override</h3>
          <select aria-label="Compliance rule" value={ruleCode} onChange={(event) => setRuleCode(event.target.value)}>
            {ruleCodes.map((code) => <option key={code} value={code}>{code}</option>)}
          </select>
          <button type="button" onClick={() => action(() => createComplianceOverride(authentication, branchId, wps.runId, {
            ruleCode, reason, payrollEntryId: null,
          }))}>Record override</button>
        </div>
      )}
      {sif && (
        <Dialog labelledBy="sif-preview-title" onClose={() => setSif(null)}><div className="modal-header"><h3 id="sif-preview-title">SIF preview · {sif.filename}</h3><button type="button" aria-label="Close SIF preview" onClick={() => setSif(null)}>×</button></div><div className="modal-body">
          <p>{sif.recordCount - 1} employee rows · digest {sif.sourceDigest}</p>
          <p>Blue rows are employee detail records. The yellow row is the salary control record.</p>
          <div className="sif-preview">{sif.records.map((record, index) => <div className={record.type === 'EDR' ? 'sif-line-edr' : 'sif-line-scr'} key={index}>{Object.values(record).join(',')}</div>)}</div>
          <h4>Employee summary</h4><div className="table-wrap"><table><thead><tr><th>MOL ID</th><th>IBAN</th><th>Period</th><th>Paid days</th><th>Basic</th><th>Variable</th><th>Total</th></tr></thead>
            <tbody>{sif.records.filter((record) => record.type === 'EDR').map((entry) => <tr key={entry.employeeMolId}>
              <td>{entry.employeeMolId}</td><td>{entry.iban}</td><td>{entry.periodStart} to {entry.periodEnd}</td><td>{entry.paidDays}</td><td>{entry.basicPay}</td>
              <td>{entry.variablePay}</td><td>{entry.basicPay + entry.variablePay}</td>
            </tr>)}{sif.records.filter((record) => record.type === 'SCR').map((record) => <tr className="sif-line-scr" key="total"><th colSpan={6}>Total · {record.employeeCount} employees</th><td>{record.totalPay} {record.currency}</td></tr>)}</tbody>
          </table></div></div><div className="modal-footer"><button type="button" onClick={() => setSif(null)}>Close</button><button type="button" disabled={status === 'loading'} onClick={() => action(async () => { saveDownload(await downloadSif(authentication, branchId, wps.runId, wps.status === 'partial_rejection')); return null })}>Download SIF</button></div></Dialog>
      )}
      <h2>Nafis snapshots</h2>
      <p>One trusted snapshot is kept for each branch and payroll period.</p>
      <label>
        Nafis period
        <input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} />
      </label>
      <button type="button" onClick={() => action(async () => {
        const result = await replaceNafisSnapshot(authentication, branchId, period, currentNafis)
        setNafis((items) => [result, ...items.filter((item) => item.id !== result.id)])
        return null
      })}>{currentNafis ? 'Replace snapshot' : 'Generate snapshot'}</button>
      <ul>{nafis.map((item) => <li key={item.id}>
        {item.period}: {item.emiratiCount}/{item.totalHeadcount} UAE nationals ({item.ratioPercent}%)
        {' '}<button type="button" className="secondary" onClick={() => action(async () => { saveDownload(await downloadNafis(authentication, branchId, item.id)); return null })}>Download CSV</button>
      </li>)}</ul>
      </fieldset>
    </section>
  )
}
