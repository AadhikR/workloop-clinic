import { useEffect, useState } from 'react'

import { readPersonalSchedule } from './rosterApi.js'

function currentPeriod() { return new Date().toISOString().slice(0, 7) }

export default function PersonalSchedule({ authentication }) {
  const [period, setPeriod] = useState(currentPeriod())
  const [schedule, setSchedule] = useState([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    let active = true
    readPersonalSchedule(authentication, period)
      .then((items) => { if (active) { setSchedule(items); setMessage('') } })
      .catch(() => { if (active) { setSchedule([]); setMessage('Your published schedule is unavailable.') } })
    return () => { active = false }
  }, [authentication, period])

  return (
    <section className="personal-schedule" aria-labelledby="personal-schedule-title">
      <h2 id="personal-schedule-title">My schedule</h2>
      <p>Only your current published roster is shown here.</p>
      <label>Month<input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></label>
      {schedule.length === 0 && !message && <p>No published shifts for this month.</p>}
      <ul>{schedule.map((item) => <li key={item.rosterAssignmentId}><strong>{item.date} — {item.shiftCode ?? item.shiftName}</strong><span>{item.plannedHours} planned hours{item.actualHours === null ? '' : ` · ${item.actualHours} actual hours`}{item.overtimeHours === '0.00' ? '' : ` · ${item.overtimeHours} approved overtime hours`}</span></li>)}</ul>
      {message && <p role="status">{message}</p>}
    </section>
  )
}
