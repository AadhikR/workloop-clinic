import { useCallback, useEffect, useState } from 'react'

import { closeAttendancePeriod, readAttendancePeriods } from './attendancePeriodsApi.js'
import { downloadAttendance } from './outputApi.js'
import { saveDownload } from './outputDelivery.js'

const labels = {
  ambiguous_events: 'ambiguous events',
  missing_calculation_days: 'missing calculation days',
  missing_clock_outs: 'missing clock-outs',
  pending_corrections: 'pending corrections',
  salary_source_changed: 'changed salary sources',
  stale_source_snapshots: 'stale calculations',
  unapproved_overtime: 'unapproved overtime',
  unresolved_absences: 'unresolved absences',
}

export default function AttendancePeriods({ authentication, branchId }) {
  const [periods, setPeriods] = useState([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const result = await readAttendancePeriods(authentication, branchId, { limit: 24 })
    setPeriods(result.data)
  }, [authentication, branchId])

  useEffect(() => {
    const refresh = async () => {
      try { await load() }
      catch { setMessage('Attendance period readiness is unavailable.') }
    }
    void refresh()
  }, [load])

  const close = async (item) => {
    let amendmentReason = null
    if (item.version > 0) {
      amendmentReason = window.prompt('Why is a successor close version required?')
      if (!amendmentReason) return
    }
    setBusy(true); setMessage('')
    try {
      await closeAttendancePeriod(authentication, branchId, item.period, { expectedVersion: item.version, amendmentReason }, { idempotencyKey: crypto.randomUUID() })
      await load()
      setMessage(item.version > 0 ? 'A successor attendance close version was created.' : 'Attendance period closed for payroll.')
    } catch {
      setMessage('Nothing changed because the period has blockers or its source state changed.')
    } finally { setBusy(false) }
  }

  return (
    <section className="attendance-periods" aria-labelledby="attendance-periods-title">
      <h2 id="attendance-periods-title">Attendance period close</h2>
      <p>Review server-calculated blockers, close a complete period, and expose its immutable payroll input.</p>
      {periods.length === 0 ? <p>No calculated attendance periods are available.</p> : (
        <ul className="period-list">
          {periods.map((item) => (
            <li key={item.id}>
              <span>
                <strong>{item.period}</strong> — {item.payrollReady ? `Payroll ready, version ${item.version}` : `${item.blockerCount} blocker${item.blockerCount === 1 ? '' : 's'}`}
                {item.blockers.length > 0 && <small>{item.blockers.map((blocker) => `${blocker.count} ${labels[blocker.code]}`).join(', ')}</small>}
                {item.closedAt && <small>Closed {item.closedAt} by {item.closedByActorName}</small>}
              </span>
              <button type="button" disabled={busy || item.blockerCount > 0} onClick={() => close(item)}>{item.version > 0 ? 'Create amendment' : 'Close period'}</button>
              <button type="button" className="secondary" disabled={busy} onClick={async () => saveDownload(await downloadAttendance(authentication, branchId, item.id))}>Download CSV</button>
            </li>
          ))}
        </ul>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  )
}
